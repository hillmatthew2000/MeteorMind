"""The MeteorMind main window."""

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Literal, TypeVar

from ..api import MAX_FORECAST_DAYS, APIError, MissingAPIKeyError
from ..config import SIGNUP_URL, ConfigError
from ..models import ForecastData, Location, WeatherData, WeatherQuery
from ..preferences import CACHE_MINUTES_RANGE, HISTORY_LIMIT_RANGE, THEMES, Preferences
from ..reporting import ReportError, WeatherReport, write_report
from ..service import InputError, WeatherService, parse_place
from ..storage import StorageError
from ..units import (
    DistanceUnit,
    PressureUnit,
    TemperatureUnit,
    UnitEnum,
    UnitPreferences,
    WindSpeedUnit,
    create_imperial_preferences,
    create_metric_preferences,
)
from .theme import Theme, resolve_palette
from .widgets import PlaceholderEntry, PlacePicker, ScrollFrame, WeatherPanel
from .worker import BackgroundWorker

U = TypeVar("U", TemperatureUnit, WindSpeedUnit, PressureUnit, DistanceUnit)

USER_ERRORS = (APIError, ConfigError, InputError, ReportError, StorageError)

SHORTCUTS = (
    ("Ctrl+L", "Search for a place"),
    ("F5", "Refresh the weather"),
    ("Ctrl+D", "Add or remove the shown place as a favorite"),
    ("Ctrl+1 … Ctrl+4", "Weather, History, Reports, Settings"),
    ("Ctrl+T", "Switch between light and dark"),
    ("Delete", "Remove the selected favorite"),
    ("F1", "Show these shortcuts"),
    ("Ctrl+Q", "Quit"),
)

REPORT_LABELS = {
    "compare": "Compare current weather",
    "forecast-compare": "Compare forecasts",
    "forecast": "Detailed forecast",
    "trends": "Temperature trend (from history)",
    "locations": "Most looked-up places",
    "history": "Recent queries",
}
WEATHER_TAB, HISTORY_TAB, REPORTS_TAB, SETTINGS_TAB = range(4)
REPORTS_NEEDING_ONE_PLACE = {"forecast", "trends"}
REPORTS_TAKING_PLACES = {"compare", "forecast-compare", "forecast", "trends"}


@dataclass(frozen=True)
class Shown:
    """The place currently on the Weather tab and its data."""

    location: Location
    weather: WeatherData
    forecast: list[ForecastData]


def describe(error: BaseException) -> tuple[str, list[str]]:
    if isinstance(error, USER_ERRORS):
        return str(error), list(getattr(error, "suggestions", []))
    return f"Something went wrong: {error}", ["Try again; if it keeps happening, report it."]


class MeteorMindApp:
    """Builds the window and connects it to a :class:`WeatherService`."""

    def __init__(self, root: tk.Tk | tk.Toplevel, service: WeatherService) -> None:
        self.root = root
        self.service = service
        self.worker = BackgroundWorker(root.after)
        self.theme = Theme(root)
        self.shown: Shown | None = None
        self.report: WeatherReport | None = None
        self._request = 0
        self._favorite_ids: dict[str, Location] = {}
        self._history_ids: dict[str, WeatherQuery] = {}

        root.title("MeteorMind" + (" — demo data" if service.is_demo else ""))
        root.geometry("1120x760")
        root.minsize(860, 600)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        self._build_toolbar()
        self.banner = ttk.Frame(root, style="Banner.TFrame", padding=(16, 8))
        self.banner_text = ttk.Label(self.banner, style="Banner.TLabel")
        self.banner_text.pack(side="left")
        self.banner_button = ttk.Button(
            self.banner, text="Add a key", command=self.open_key_settings
        )
        self._build_body()
        self.status = tk.StringVar(root, value="Ready")
        status_bar = ttk.Frame(root, style="Status.TFrame")
        status_bar.grid(row=3, column=0, sticky="ew")
        ttk.Label(status_bar, textvariable=self.status, style="Status.TLabel").pack(side="left")
        ttk.Label(status_bar, text="F1  Keyboard shortcuts", style="Status.TLabel").pack(
            side="right"
        )

        self.apply_theme()
        self._bind_shortcuts()
        self.refresh_favorites()
        self.refresh_history()
        self.update_banner()
        self.show_start_state()
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.search_entry.focus_set()

    # Layout --------------------------------------------------------------------

    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self.root, style="Toolbar.TFrame", padding=(16, 10))
        bar.grid(row=0, column=0, sticky="ew")
        bar.columnconfigure(1, weight=1)
        ttk.Label(bar, text="MeteorMind", style="ToolbarTitle.TLabel").grid(row=0, column=0)
        self.search_entry = PlaceholderEntry(bar, "Search a city, e.g. Paris, FR", width=36)
        self.search_entry.grid(row=0, column=2, padx=(0, 8))
        self.search_entry.bind("<Return>", lambda _e: self.search())
        self.search_entry.bind("<Escape>", lambda _e: self.search_entry.set_value(""))
        self.search_button = ttk.Button(
            bar, text="Search", style="Accent.TButton", command=self.search
        )
        self.search_button.grid(row=0, column=3)

    def _build_body(self) -> None:
        body = ttk.Frame(self.root, padding=(12, 12, 12, 8))
        body.grid(row=2, column=0, sticky="nsew")
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        self._build_sidebar(body)
        self.tabs = ttk.Notebook(body)
        self.tabs.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        self.weather_panel = WeatherPanel(self.tabs, self.toggle_favorite)
        self.theme.track(self.weather_panel.content.canvas)
        self.tabs.add(self.weather_panel, text="Weather")
        self.tabs.add(self._build_history_tab(), text="History")
        self.tabs.add(self._build_reports_tab(), text="Reports")
        self.tabs.add(self._build_settings_tab(), text="Settings")

    def _build_sidebar(self, parent: ttk.Frame) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=12)
        card.grid(row=0, column=0, sticky="ns")
        card.rowconfigure(1, weight=1)
        ttk.Label(card, text="Favorites", style="CardBold.TLabel").grid(row=0, column=0, sticky="w")
        self.favorites_tree = ttk.Treeview(card, show="tree", selectmode="browse", height=12)
        self.favorites_tree.column("#0", width=210)
        self.favorites_tree.grid(row=1, column=0, sticky="nsew", pady=8)
        self.favorites_tree.bind("<<TreeviewSelect>>", lambda _e: self.open_selected_favorite())
        self.favorites_tree.bind("<Delete>", lambda _e: self.remove_selected_favorite())
        buttons = ttk.Frame(card, style="CardBody.TFrame")
        buttons.grid(row=2, column=0, sticky="ew")
        buttons.columnconfigure((0, 1), weight=1)
        ttk.Button(buttons, text="Move to top", command=self.move_selected_favorite).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        ttk.Button(buttons, text="Remove", command=self.remove_selected_favorite).grid(
            row=0, column=1, sticky="ew"
        )

    def _build_history_tab(self) -> ttk.Frame:
        tab = ttk.Frame(self.tabs, padding=16)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        bar = ttk.Frame(tab)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.history_filter = PlaceholderEntry(bar, "Filter by place or country", width=32)
        self.history_filter.pack(side="left")
        self.history_filter.var.trace_add("write", lambda *_: self.refresh_history())
        ttk.Button(bar, text="Clear…", command=self.clear_history).pack(side="right")
        ttk.Button(bar, text="Export…", command=self.export_history).pack(side="right", padx=8)
        self.history_count = ttk.Label(bar, style="Muted.TLabel")
        self.history_count.pack(side="right", padx=8)

        columns = ("when", "place", "type", "temp", "conditions")
        self.history_tree = ttk.Treeview(tab, columns=columns, show="headings", selectmode="browse")
        layout: tuple[tuple[str, str, int, Literal["w", "e"]], ...] = (
            ("when", "When", 150, "w"),
            ("place", "Place", 260, "w"),
            ("type", "Type", 90, "w"),
            ("temp", "Temperature", 110, "e"),
            ("conditions", "Conditions", 180, "w"),
        )
        for column, title, width, anchor in layout:
            self.history_tree.heading(column, text=title, anchor=anchor)
            self.history_tree.column(column, width=width, anchor=anchor, stretch=column != "type")
        scroll = ttk.Scrollbar(tab, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scroll.set)
        self.history_tree.grid(row=1, column=0, sticky="nsew")
        scroll.grid(row=1, column=1, sticky="ns")
        self.history_tree.bind("<Double-1>", lambda _e: self.open_selected_history())
        self.history_tree.bind("<Return>", lambda _e: self.open_selected_history())
        self.history_empty = ttk.Label(tab, style="Muted.TLabel")
        return tab

    def _build_reports_tab(self) -> ttk.Frame:
        tab = ttk.Frame(self.tabs, padding=16)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)
        controls = ttk.Frame(tab, style="Card.TFrame", padding=12)
        controls.grid(row=0, column=0, sticky="ew")
        controls.columnconfigure(3, weight=1)

        ttk.Label(controls, text="Report", style="Card.TLabel").grid(row=0, column=0, sticky="w")
        self.report_kind = tk.StringVar(tab, value=REPORT_LABELS["compare"])
        kind = ttk.Combobox(
            controls,
            textvariable=self.report_kind,
            values=[REPORT_LABELS[k] for k in REPORT_LABELS],
            state="readonly",
            width=30,
        )
        kind.grid(row=1, column=0, sticky="w", padx=(0, 12))
        kind.bind("<<ComboboxSelected>>", lambda _e: self._update_report_controls())
        ttk.Label(controls, text="Days", style="Card.TLabel").grid(row=0, column=1, sticky="w")
        self.report_days = tk.IntVar(tab, value=MAX_FORECAST_DAYS)
        self.report_days_box = ttk.Spinbox(
            controls, from_=1, to=MAX_FORECAST_DAYS, textvariable=self.report_days, width=4,
            state="readonly",
        )  # fmt: skip
        self.report_days_box.grid(row=1, column=1, sticky="w", padx=(0, 12))
        self.report_places_label = ttk.Label(controls, style="Card.TLabel")
        self.report_places_label.grid(row=0, column=2, columnspan=4, sticky="w")
        self.report_places = ttk.Entry(controls)
        self.report_places.grid(row=1, column=2, columnspan=2, sticky="ew", padx=(0, 12))
        self.report_places.bind("<Return>", lambda _e: self.generate_report())
        self.report_button = ttk.Button(
            controls, text="Create report", style="Accent.TButton", command=self.generate_report
        )
        self.report_button.grid(row=1, column=4)
        self.report_save = ttk.Button(
            controls, text="Save…", command=self.save_report, state="disabled"
        )
        self.report_save.grid(row=1, column=5, padx=(8, 0))

        self.report_note = ttk.Label(tab, style="Muted.TLabel")
        self.report_note.grid(row=1, column=0, sticky="w", pady=6)
        frame = ttk.Frame(tab, style="Card.TFrame", padding=1)
        frame.grid(row=2, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.report_text = tk.Text(
            frame, wrap="none", font=self.theme.fonts.mono, padx=12, pady=10, state="disabled"
        )
        self.theme.track(self.report_text)
        yscroll = ttk.Scrollbar(frame, orient="vertical", command=self.report_text.yview)
        xscroll = ttk.Scrollbar(frame, orient="horizontal", command=self.report_text.xview)
        self.report_text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.report_text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self._update_report_controls()
        return tab

    def _build_settings_tab(self) -> ScrollFrame:
        scroller = ScrollFrame(self.tabs, padding=(16, 16))
        self.theme.track(scroller.canvas)
        tab = scroller.inner
        tab.columnconfigure((0, 1), weight=1, uniform="settings")
        columns = [ttk.Frame(tab), ttk.Frame(tab)]
        columns[0].grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        columns[1].grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        def card(column: int, title: str) -> ttk.Frame:
            frame = ttk.Frame(columns[column], style="Card.TFrame", padding=14)
            frame.pack(fill="x", pady=(0, 12))
            frame.columnconfigure(1, weight=1)
            ttk.Label(frame, text=title, style="CardBold.TLabel").grid(
                row=0, column=0, columnspan=3, sticky="w", pady=(0, 8)
            )
            return frame

        units = card(0, "Units")
        self.unit_vars: dict[str, tk.StringVar] = {}
        current = self.service.preferences.units
        for row, (name, title, member) in enumerate(
            (
                ("temperature", "Temperature", current.temperature),
                ("wind_speed", "Wind speed", current.wind_speed),
                ("pressure", "Pressure", current.pressure),
                ("distance", "Distance", current.distance),
            ),
            start=1,
        ):
            ttk.Label(units, text=title, style="Card.TLabel").grid(
                row=row, column=0, sticky="w", pady=3
            )
            var = tk.StringVar(tab)
            box = ttk.Combobox(
                units,
                textvariable=var,
                values=[self._unit_text(m) for m in type(member)],
                state="readonly",
            )
            box.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(12, 0), pady=3)
            box.bind("<<ComboboxSelected>>", lambda _e: self.apply_units_from_controls())
            self.unit_vars[name] = var
        presets = ttk.Frame(units, style="CardBody.TFrame")
        presets.grid(row=5, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Button(
            presets, text="Metric", command=lambda: self.set_units(create_metric_preferences())
        ).pack(side="left")
        ttk.Button(
            presets, text="Imperial", command=lambda: self.set_units(create_imperial_preferences())
        ).pack(side="left", padx=8)

        appearance = card(1, "Appearance")
        self.theme_var = tk.StringVar(tab, value=self.service.preferences.theme)
        for row, value in enumerate(THEMES, start=1):
            ttk.Radiobutton(
                appearance,
                text={"system": "Match the system", "light": "Light", "dark": "Dark"}[value],
                value=value,
                variable=self.theme_var,
                command=lambda: self.set_theme(self.theme_var.get()),
            ).grid(row=row, column=0, columnspan=2, sticky="w", pady=2)

        limits = card(1, "History and cache")
        self.history_limit = tk.IntVar(tab, value=self.service.preferences.history_limit)
        self.cache_minutes = tk.IntVar(tab, value=self.service.preferences.cache_minutes)
        for row, (title, number, (low, high), step) in enumerate(
            (
                ("Queries to keep", self.history_limit, HISTORY_LIMIT_RANGE, 10),
                ("Cache responses (minutes)", self.cache_minutes, CACHE_MINUTES_RANGE, 1),
            ),
            start=1,
        ):
            ttk.Label(limits, text=title, style="Card.TLabel").grid(
                row=row, column=0, sticky="w", pady=3
            )
            spinbox = ttk.Spinbox(
                limits, from_=low, to=high, increment=step, textvariable=number, width=8,
                command=self.apply_limits,
            )  # fmt: skip
            spinbox.grid(row=row, column=1, sticky="w", padx=(12, 0), pady=3)
            spinbox.bind("<FocusOut>", lambda _e: self.apply_limits())
            spinbox.bind("<Return>", lambda _e: self.apply_limits())

        key = card(0, "OpenWeatherMap API key")
        self.key_status = ttk.Label(key, style="CardMuted.TLabel", justify="left")
        key.bind("<Configure>", lambda e: self.key_status.configure(wraplength=e.width - 30))
        self.key_status.grid(row=1, column=0, columnspan=3, sticky="w")
        self.key_entry = ttk.Entry(key, show="•")
        self.key_entry.grid(row=2, column=0, columnspan=2, sticky="ew", pady=8)
        self.key_entry.bind("<Return>", lambda _e: self.save_key())
        ttk.Button(key, text="Save", style="Accent.TButton", command=self.save_key).grid(
            row=2, column=2, sticky="e", padx=(6, 0)
        )
        key_buttons = ttk.Frame(key, style="CardBody.TFrame")
        key_buttons.grid(row=3, column=0, columnspan=3, sticky="ew")
        key_buttons.columnconfigure((0, 1), weight=1, uniform="key")
        ttk.Button(key_buttons, text="Test", command=self.test_key).grid(
            row=0, column=0, sticky="ew"
        )
        ttk.Button(key_buttons, text="Remove", command=self.remove_key).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )
        ttk.Button(
            key,
            text="Get a free key ↗",
            style="Link.TButton",
            command=lambda: webbrowser.open(SIGNUP_URL),
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))

        data = card(1, "Your data")
        self.data_folder = tk.StringVar(tab, value=str(self.service.store.directory))
        folder = ttk.Entry(data, textvariable=self.data_folder, state="readonly")
        folder.grid(row=1, column=0, columnspan=3, sticky="ew")
        data_buttons = ttk.Frame(data, style="CardBody.TFrame")
        data_buttons.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        data_buttons.columnconfigure((0, 1), weight=1, uniform="data")
        for index, (text, command) in enumerate(
            (
                ("Open folder", self.open_data_folder),
                ("Back up", self.backup),
                ("Clear cache", self.clear_cache),
                ("Delete all…", self.delete_all_data),
            )
        ):
            row, column = divmod(index, 2)
            ttk.Button(data_buttons, text=text, command=command).grid(
                row=row, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0), pady=(0, 6)
            )

        self._load_settings_controls()
        return scroller

    # Theme and shortcuts -------------------------------------------------------

    def apply_theme(self) -> None:
        self.theme.apply(resolve_palette(self.service.preferences.theme))

    def set_theme(self, theme: str) -> None:
        self._save_preferences(replace(self.service.preferences, theme=theme))
        self.theme_var.set(theme)
        self.apply_theme()

    def toggle_theme(self) -> None:
        self.set_theme("light" if self.theme.palette.name == "dark" else "dark")

    def show_tab(self, index: int) -> None:
        self.tabs.select(index)  # type: ignore[no-untyped-call]  # unannotated in typeshed

    def _bind_shortcuts(self) -> None:
        bindings: dict[str, Callable[[], object]] = {
            "<Control-l>": self.focus_search,
            "<Control-f>": self.focus_search,
            "<F5>": self.refresh,
            "<Control-r>": self.refresh,
            "<Control-d>": self.toggle_favorite,
            "<Control-t>": self.toggle_theme,
            "<F1>": self.show_shortcuts,
            "<Control-q>": self.close,
            "<Control-w>": self.close,
        }
        for number in range(1, 5):
            bindings[f"<Control-Key-{number}>"] = partial(self.show_tab, number - 1)
        for sequence, action in bindings.items():
            self.root.bind_all(sequence, self._shortcut(action))

    @staticmethod
    def _shortcut(action: Callable[[], object]) -> Callable[[tk.Event[tk.Misc]], str]:
        def handler(_event: tk.Event[tk.Misc]) -> str:
            action()
            return "break"

        return handler

    def focus_search(self) -> None:
        self.show_tab(WEATHER_TAB)
        self.search_entry.focus_set()
        self.search_entry.select_range(0, "end")

    def show_shortcuts(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Keyboard shortcuts")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.configure(background=self.theme.palette.background)
        body = ttk.Frame(dialog, padding=18)
        body.pack()
        for row, (keys, action) in enumerate(SHORTCUTS):
            ttk.Label(body, text=keys, style="Bold.TLabel").grid(
                row=row, column=0, sticky="w", padx=(0, 18), pady=2
            )
            ttk.Label(body, text=action).grid(row=row, column=1, sticky="w", pady=2)
        close = ttk.Button(body, text="Close", command=dialog.destroy)
        close.grid(row=len(SHORTCUTS), column=1, sticky="e", pady=(12, 0))
        dialog.bind("<Escape>", lambda _e: dialog.destroy())
        close.focus_set()

    # Background jobs -----------------------------------------------------------

    def run(
        self,
        job: Callable[[], object],
        on_success: Callable[..., None],
        busy: str,
        on_error: Callable[[BaseException], None] | None = None,
    ) -> None:
        self.status.set(busy)
        self.root.configure(cursor="watch")

        def done(result: object) -> None:
            self._idle()
            on_success(result)

        def failed(error: BaseException) -> None:
            self._idle()
            if on_error:
                on_error(error)
            else:
                self.show_error_dialog(error)

        self.worker.submit(job, done, failed)

    def _idle(self) -> None:
        if not self.worker.busy:
            self.root.configure(cursor="")
            self.status.set("Ready")

    def show_error_dialog(self, error: BaseException) -> None:
        message, suggestions = describe(error)
        messagebox.showerror("MeteorMind", message, detail="\n".join(suggestions), parent=self.root)
        self.status.set(message)

    # Weather -------------------------------------------------------------------

    def show_start_state(self) -> None:
        if not self.service.has_provider:
            self.weather_panel.show_empty(
                "Add your OpenWeatherMap key to get started",
                "MeteorMind needs a free API key to look up weather. You can also "
                "explore with sample data: run  meteormind gui --demo",
                ("Add a key", self.open_key_settings),
            )
        elif self.service.favorites:
            first = next(iter(self.service.favorites))
            self.load_place(first)
        else:
            self.weather_panel.show_empty(
                "Search for a place",
                "Type a city in the search box above (Ctrl+L), for example “Lisbon” or "
                "“Portland, US”. Places you add to favorites appear on the left.",
            )

    def search(self) -> None:
        query = self.search_entry.value
        if not query:
            self.focus_search()
            return
        try:
            parse_place(query)
        except InputError as error:
            self.show_tab(WEATHER_TAB)
            self.weather_panel.show_error(str(error), error.suggestions, None)
            return
        self.show_tab(WEATHER_TAB)
        self._request += 1
        request = self._request
        self.weather_panel.show_loading(f"Looking for “{query}”…")

        def found(places: list[Location]) -> None:
            if request != self._request:
                return
            if not places:
                self.weather_panel.show_error(
                    f"No place called “{query}” was found.",
                    ["Check the spelling.", "Add a country code, for example “Paris, FR”."],
                    None,
                )
            elif len(places) == 1:
                self.load_place(places[0])
            else:
                choice = PlacePicker(self.root, query, places).ask()
                if choice:
                    self.load_place(choice)
                else:
                    self._restore_view()

        self.run(
            lambda: self.service.search(query),
            found,
            f"Searching for {query}…",
            self._weather_failed(request, self.search),
        )

    def load_place(self, location: Location) -> None:
        """Fetch and show current weather and the forecast for a place."""
        self._request += 1
        request = self._request
        self.show_tab(WEATHER_TAB)
        self.weather_panel.show_loading(f"Loading the weather for {location.display_name}…")

        def fetch() -> Shown:
            weather = self.service.current_weather(location)
            forecast = self.service.forecast(location, MAX_FORECAST_DAYS)
            return Shown(location, weather, forecast)

        def show(shown: Shown) -> None:
            if request != self._request:
                return
            self.shown = shown
            self._render_shown()
            self.refresh_history()
            self.status.set(f"Updated {shown.location.display_name}")

        self.run(
            fetch,
            show,
            f"Loading {location.display_name}…",
            self._weather_failed(request, lambda: self.load_place(location)),
        )

    def _weather_failed(
        self, request: int, retry: Callable[[], None]
    ) -> Callable[[BaseException], None]:
        def failed(error: BaseException) -> None:
            if request != self._request:
                return
            if isinstance(error, MissingAPIKeyError):
                self.show_start_state()
                return
            message, suggestions = describe(error)
            self.weather_panel.show_error(message, suggestions, retry)
            self.status.set(message)

        return failed

    def _render_shown(self) -> None:
        if self.shown is None:
            return
        shown = self.shown
        self.weather_panel.show_weather(
            shown.location,
            shown.weather,
            shown.forecast,
            self.service.formatter,
            shown.location in self.service.favorites,
        )
        self._select_favorite(shown.location)

    def _restore_view(self) -> None:
        if self.shown:
            self._render_shown()
        else:
            self.show_start_state()

    def refresh(self) -> None:
        if self.shown:
            self.load_place(self.shown.location)

    # Favorites -----------------------------------------------------------------

    def refresh_favorites(self) -> None:
        tree = self.favorites_tree
        tree.delete(*tree.get_children())
        self._favorite_ids = {}
        for index, location in enumerate(self.service.favorites):
            iid = str(index)
            self._favorite_ids[iid] = location
            tree.insert("", "end", iid=iid, text=location.display_name)
        self._select_favorite(self.shown.location if self.shown else None)

    def _select_favorite(self, location: Location | None) -> None:
        """Highlight the favorite being shown, if it is one."""
        tree = self.favorites_tree
        for iid, favorite in self._favorite_ids.items():
            if location is not None and favorite.key == location.key:
                if tree.selection() != (iid,):
                    tree.selection_set(iid)
                    tree.see(iid)
                return
        if tree.selection():
            tree.selection_remove(*tree.selection())

    def _selected_favorite(self) -> Location | None:
        selected = self.favorites_tree.selection()
        return self._favorite_ids.get(selected[0]) if selected else None

    def open_selected_favorite(self) -> None:
        location = self._selected_favorite()
        if location is None:
            return
        if self.shown and self.shown.location.key == location.key and not self.worker.busy:
            self.show_tab(WEATHER_TAB)
            return
        self.load_place(location)

    def toggle_favorite(self) -> None:
        if self.shown is None:
            return
        location = self.shown.location
        try:
            if location in self.service.favorites:
                self.service.remove_favorite(location)
                self.status.set(f"Removed {location.display_name} from favorites")
            else:
                self.service.add_favorite(location)
                self.status.set(f"Added {location.display_name} to favorites")
        except StorageError as error:
            self.show_error_dialog(error)
        self.refresh_favorites()
        self.weather_panel.set_favorite(location in self.service.favorites)

    def remove_selected_favorite(self) -> None:
        location = self._selected_favorite()
        if location is None:
            return
        try:
            self.service.remove_favorite(location)
        except StorageError as error:
            self.show_error_dialog(error)
        self.refresh_favorites()
        if self.shown and self.shown.location.key == location.key:
            self.weather_panel.set_favorite(False)
        self.status.set(f"Removed {location.display_name} from favorites")

    def move_selected_favorite(self) -> None:
        location = self._selected_favorite()
        if location is None:
            return
        try:
            self.service.move_favorite_to_top(location)
        except StorageError as error:
            self.show_error_dialog(error)
        self.refresh_favorites()

    # History -------------------------------------------------------------------

    def refresh_history(self) -> None:
        history = self.service.history
        term = self.history_filter.value
        queries = history.search_queries(term) if term else history.get_recent_queries()
        fmt = self.service.formatter
        tree = self.history_tree
        tree.delete(*tree.get_children())
        self._history_ids = {}
        for index, query in enumerate(queries):
            weather = query.weather_data
            iid = str(index)
            self._history_ids[iid] = query
            tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    f"{query.query_time:%Y-%m-%d %H:%M}",
                    query.location.display_name,
                    query.query_type.title(),
                    fmt.format_temperature(weather.temperature) if weather else "",
                    weather.description if weather else "",
                ),
            )
        total = len(history)
        self.history_count.configure(
            text=f"{len(queries)} of {total}" if term else f"{total} queries"
        )
        if queries:
            self.history_empty.grid_remove()
        else:
            self.history_empty.configure(
                text="Nothing matches the filter." if term else "Places you look up appear here."
            )
            self.history_empty.grid(row=2, column=0, sticky="w", pady=8)

    def open_selected_history(self) -> None:
        selected = self.history_tree.selection()
        if selected:
            self.load_place(self._history_ids[selected[0]].location)

    def export_history(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Export history",
            defaultextension=".json",
            initialfile="meteormind-history.json",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        try:
            self.service.history.export_history(path)
        except StorageError as error:
            self.show_error_dialog(error)
            return
        self.status.set(f"Exported the history to {path}")

    def clear_history(self) -> None:
        count = len(self.service.history)
        if not count or not messagebox.askyesno(
            "Clear history", f"Delete all {count} queries?", parent=self.root, icon="warning"
        ):
            return
        try:
            self.service.history.clear_history()
        except StorageError as error:
            self.show_error_dialog(error)
        self.refresh_history()

    # Reports -------------------------------------------------------------------

    def _report_key(self) -> str:
        label = self.report_kind.get()
        return next(key for key, text in REPORT_LABELS.items() if text == label)

    def _update_report_controls(self) -> None:
        kind = self._report_key()
        if kind in REPORTS_NEEDING_ONE_PLACE:
            label = "Place"
        elif kind in REPORTS_TAKING_PLACES:
            label = "Places, separated by ;  (empty: your favorites)"
        else:
            label = "Uses your query history"
        self.report_places_label.configure(text=label)
        self.report_places.configure(
            state="normal" if kind in REPORTS_TAKING_PLACES else "disabled"
        )
        days = "readonly" if kind in ("forecast", "forecast-compare") else "disabled"
        self.report_days_box.configure(state=days)

    def generate_report(self) -> None:
        kind = self._report_key()
        if kind in REPORTS_TAKING_PLACES:
            places = [p.strip() for p in self.report_places.get().split(";") if p.strip()]
        else:
            places = []
        days = self.report_days.get()
        self.report_button.configure(state="disabled")

        def done(result: tuple[WeatherReport, list[str]]) -> None:
            self.report_button.configure(state="normal")
            self.report, warnings = result
            self._set_report_text(self.report.to_table_string())
            self.report_save.configure(state="normal" if self.report.rows else "disabled")
            self.report_note.configure(
                text="Could not fetch: " + "; ".join(warnings) if warnings else ""
            )
            self.refresh_history()

        def failed(error: BaseException) -> None:
            self.report_button.configure(state="normal")
            self.show_error_dialog(error)

        self.run(
            lambda: self.service.build_report(kind, places, days),
            done,
            "Creating the report…",
            failed,
        )

    def _set_report_text(self, text: str) -> None:
        self.report_text.configure(state="normal")
        self.report_text.delete("1.0", "end")
        self.report_text.insert("1.0", text)
        self.report_text.configure(state="disabled")

    def save_report(self) -> None:
        if self.report is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save report",
            defaultextension=".txt",
            initialfile=f"meteormind-{self._report_key()}.txt",
            filetypes=[("Text", "*.txt"), ("CSV", "*.csv"), ("JSON", "*.json")],
        )
        if not path:
            return
        try:
            saved = write_report(self.report, Path(path))
        except ReportError as error:
            self.show_error_dialog(error)
            return
        self.status.set(f"Saved the report to {saved}")

    # Settings ------------------------------------------------------------------

    @staticmethod
    def _unit_text(unit: UnitEnum) -> str:
        return f"{unit.label} ({unit.symbol})"

    def _load_settings_controls(self) -> None:
        units = self.service.preferences.units
        for name, member in (
            ("temperature", units.temperature),
            ("wind_speed", units.wind_speed),
            ("pressure", units.pressure),
            ("distance", units.distance),
        ):
            self.unit_vars[name].set(self._unit_text(member))
        prefs = self.service.preferences
        self.theme_var.set(prefs.theme)
        self.history_limit.set(prefs.history_limit)
        self.cache_minutes.set(prefs.cache_minutes)
        self.update_key_status()

    def _unit_from(self, name: str, current: U) -> U:
        text = self.unit_vars[name].get()
        return next((m for m in type(current) if self._unit_text(m) == text), current)

    def apply_units_from_controls(self) -> None:
        units = self.service.preferences.units
        self.set_units(
            UnitPreferences(
                temperature=self._unit_from("temperature", units.temperature),
                wind_speed=self._unit_from("wind_speed", units.wind_speed),
                pressure=self._unit_from("pressure", units.pressure),
                distance=self._unit_from("distance", units.distance),
            )
        )

    def set_units(self, units: UnitPreferences) -> None:
        self._save_preferences(replace(self.service.preferences, units=units))
        self._load_settings_controls()
        self._render_shown()
        self.refresh_history()
        if self.report is not None:
            self.report_note.configure(text="Create the report again to use the new units.")

    def apply_limits(self) -> None:
        prefs = self.service.preferences
        try:
            history_limit = int(self.history_limit.get())
            cache_minutes = int(self.cache_minutes.get())
        except (tk.TclError, ValueError):
            self._load_settings_controls()
            return
        low, high = HISTORY_LIMIT_RANGE
        history_limit = min(max(history_limit, low), high)
        low, high = CACHE_MINUTES_RANGE
        cache_minutes = min(max(cache_minutes, low), high)
        if (history_limit, cache_minutes) != (prefs.history_limit, prefs.cache_minutes):
            self._save_preferences(
                replace(prefs, history_limit=history_limit, cache_minutes=cache_minutes)
            )
            self.refresh_history()
        self.history_limit.set(history_limit)
        self.cache_minutes.set(cache_minutes)

    def _save_preferences(self, preferences: Preferences) -> None:
        try:
            self.service.update_preferences(preferences)
        except StorageError as error:
            self.show_error_dialog(error)

    def update_key_status(self) -> None:
        lookup = self.service.config.find_api_key()
        text = "Demo mode is on, so no key is used. " if self.service.is_demo else ""
        if lookup.found:
            text += f"A key is set (from {lookup.source})."
        else:
            text += "No key is set. Paste a key below and save it."
        self.key_status.configure(text=text)

    def update_banner(self) -> None:
        if self.service.is_demo:
            self.banner_text.configure(
                text="Demo mode: the weather shown is generated sample data, not real observations."
            )
            self.banner_button.pack_forget()
        elif not self.service.has_provider:
            self.banner_text.configure(text="No OpenWeatherMap API key is set up yet.")
            self.banner_button.pack(side="right")
        else:
            self.banner.grid_remove()
            return
        self.banner.grid(row=1, column=0, sticky="ew")

    def open_key_settings(self) -> None:
        self.show_tab(SETTINGS_TAB)
        self.key_entry.focus_set()

    def save_key(self) -> None:
        key = self.key_entry.get().strip()
        if not key:
            self.key_entry.focus_set()
            return
        try:
            self.service.set_api_key(key)
        except ConfigError as error:
            self.show_error_dialog(error)
            return
        self.key_entry.delete(0, "end")
        self.update_key_status()
        self.update_banner()
        self.status.set("Saved the API key")
        if not self.service.is_demo and self.shown is None:
            self.show_start_state()

    def test_key(self) -> None:
        def done(ok: bool) -> None:
            if ok:
                messagebox.showinfo("MeteorMind", "The key works.", parent=self.root)
            else:
                messagebox.showerror(
                    "MeteorMind",
                    "OpenWeatherMap rejected the key.",
                    detail="New keys can take up to two hours to activate.",
                    parent=self.root,
                )

        self.run(self.service.test_connection, done, "Testing the API key…")

    def remove_key(self) -> None:
        try:
            removed = self.service.clear_api_key()
        except ConfigError as error:
            self.show_error_dialog(error)
            return
        self.update_key_status()
        self.update_banner()
        self.status.set("Removed the saved key" if removed else "No key was saved")

    def open_data_folder(self) -> None:
        folder = self.service.store.directory
        folder.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(folder)
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(folder)])

    def backup(self) -> None:
        try:
            path = self.service.backup()
        except StorageError as error:
            self.show_error_dialog(error)
            return
        self.status.set(f"Backed up to {path}")

    def clear_cache(self) -> None:
        self.service.clear_cache()
        self.status.set("Cleared cached responses")

    def delete_all_data(self) -> None:
        if not messagebox.askyesno(
            "Delete all data",
            "Delete your favorites, history and settings?",
            detail="Your API key is kept. This cannot be undone.",
            parent=self.root,
            icon="warning",
        ):
            return
        try:
            self.service.clear_all_data()
        except StorageError as error:
            self.show_error_dialog(error)
        self.shown = None
        self.report = None
        self._set_report_text("")
        self._load_settings_controls()
        self.apply_theme()
        self.refresh_favorites()
        self.refresh_history()
        self.show_start_state()
        self.status.set("All data deleted")

    # Lifecycle -----------------------------------------------------------------

    def close(self) -> None:
        self.worker.close()
        self.root.destroy()
