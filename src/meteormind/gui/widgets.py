"""Reusable widgets for the desktop app."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence
from tkinter import ttk

from ..models import ForecastData, Location, WeatherData
from ..units import WeatherFormatter

# Symbols for OpenWeatherMap icon codes ("01d", "10n", ...). Only characters
# from the Basic Multilingual Plane are used: Tk 8.6 cannot draw the others.
_SYMBOLS = {
    "01": "☀",
    "02": "⛅",
    "03": "☁",
    "04": "☁",
    "09": "☂",
    "10": "☂",
    "11": "⚡",
    "13": "❄",
    "50": "≋",
}


def weather_symbol(icon: str) -> str:
    if icon.startswith("01") and icon.endswith("n"):
        return "☾"
    return _SYMBOLS.get(icon[:2], "·")


class PlaceholderEntry(ttk.Entry):
    """An entry that shows a muted hint while it is empty and unfocused."""

    def __init__(self, master: tk.Misc, placeholder: str, **kwargs: object) -> None:
        self.var = tk.StringVar(master)
        super().__init__(master, textvariable=self.var, **kwargs)  # type: ignore[arg-type]
        self.placeholder = placeholder
        self._showing = False
        self.bind("<FocusIn>", self._hide, add="+")
        self.bind("<FocusOut>", self._show, add="+")
        self._show()

    def _show(self, _event: object = None) -> None:
        if not self.var.get():
            self._showing = True
            self.configure(style="Placeholder.TEntry")
            self.var.set(self.placeholder)

    def _hide(self, _event: object = None) -> None:
        if self._showing:
            self._showing = False
            self.var.set("")
            self.configure(style="TEntry")

    @property
    def value(self) -> str:
        return "" if self._showing else self.var.get().strip()

    def set_value(self, text: str) -> None:
        self._hide()
        self.var.set(text)
        if self.focus_get() is not self:
            self._show()


class ScrollFrame(ttk.Frame):
    """A vertically scrolling container; put children in :attr:`inner`.

    The scrollbar only appears when the content is taller than the space
    available, and the mouse wheel scrolls while the pointer is over it.
    """

    def __init__(self, master: tk.Misc, padding: tuple[int, int] = (0, 0)) -> None:
        super().__init__(master)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, padding=padding)
        self._window = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.inner.bind("<Configure>", self._update, add="+")
        self.canvas.bind("<Configure>", self._update, add="+")
        self.bind("<Enter>", lambda _e: self._bind_wheel(True))
        self.bind("<Leave>", lambda _e: self._bind_wheel(False))

    def _update(self, _event: object = None) -> None:
        width = self.canvas.winfo_width()
        self.canvas.itemconfigure(self._window, width=width)
        height = self.inner.winfo_reqheight()
        self.canvas.configure(scrollregion=(0, 0, width, height))
        if height > self.canvas.winfo_height() + 1:
            self.scrollbar.grid(row=0, column=1, sticky="ns")
        else:
            self.scrollbar.grid_remove()
            self.canvas.yview_moveto(0)

    def _bind_wheel(self, active: bool) -> None:
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            if active:
                self.bind_all(sequence, self._on_wheel)
            else:
                self.unbind_all(sequence)

    def _on_wheel(self, event: tk.Event[tk.Misc]) -> None:
        if not self.scrollbar.winfo_ismapped():
            return
        if event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")


class ForecastCard(ttk.Frame):
    """One day of the forecast."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, style="Card.TFrame", padding=(12, 10))
        self.day = ttk.Label(self, style="CardBold.TLabel")
        self.date = ttk.Label(self, style="CardMuted.TLabel")
        self.symbol = ttk.Label(self, style="CardForecastSymbol.TLabel")
        self.high = ttk.Label(self, style="CardBold.TLabel")
        self.low = ttk.Label(self, style="CardMuted.TLabel")
        self.description = ttk.Label(self, style="Card.TLabel", justify="left")
        self.precipitation = ttk.Label(self, style="CardMuted.TLabel")
        for row, widget in enumerate(
            (
                self.day,
                self.date,
                self.symbol,
                self.high,
                self.low,
                self.description,
                self.precipitation,
            )
        ):
            widget.grid(row=row, column=0, sticky="w", pady=(6 if widget is self.symbol else 0, 0))
        self.bind("<Configure>", self._rewrap)

    def _rewrap(self, event: tk.Event[tk.Misc]) -> None:
        for label in (self.description, self.precipitation):
            label.configure(wraplength=max(event.width - 24, 60))

    def show(self, day: ForecastData, fmt: WeatherFormatter) -> None:
        self.day.configure(text=f"{day.date:%A}")
        self.date.configure(text=f"{day.date:%d %B}")
        self.symbol.configure(text=weather_symbol(day.icon))
        self.high.configure(text=f"High {fmt.format_temperature(day.temperature_max)}")
        self.low.configure(text=f"Low {fmt.format_temperature(day.temperature_min)}")
        self.description.configure(text=day.description)
        self.precipitation.configure(
            text=f"{day.precipitation_chance}% chance of rain or snow"
            if day.precipitation_chance
            else "Dry"
        )


class WeatherPanel(ttk.Frame):
    """Current conditions and forecast, with empty, loading and error states."""

    STAT_COLUMNS = 3

    def __init__(self, master: tk.Misc, on_toggle_favorite: Callable[[], None]) -> None:
        super().__init__(master)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Empty state
        self.empty = ttk.Frame(self)
        self.empty_title = ttk.Label(self.empty, style="Title.TLabel")
        self.empty_text = ttk.Label(self.empty, style="Muted.TLabel", justify="center")
        self.empty_action = ttk.Button(self.empty, style="Accent.TButton")
        self.empty_title.pack(pady=(0, 6))
        self.empty_text.pack()

        # Loading state
        self.loading = ttk.Frame(self)
        self.loading_text = ttk.Label(self.loading, style="Muted.TLabel")
        self.progress = ttk.Progressbar(self.loading, mode="indeterminate", length=220)
        self.loading_text.pack(pady=(0, 10))
        self.progress.pack()

        # Error state
        self.error = ttk.Frame(self)
        self.error_title = ttk.Label(self.error, style="Error.TLabel", justify="center")
        self.error_text = ttk.Label(self.error, style="Muted.TLabel", justify="left")
        self.error_retry = ttk.Button(self.error, text="Try again")
        self.error_title.pack(pady=(0, 8))
        self.error_text.pack()
        self.error_retry.pack(pady=(14, 0))

        for state in (self.empty, self.loading, self.error):
            state.grid(row=0, column=0)
        self.content = ScrollFrame(self, padding=(16, 12))
        self._build_content(self.content.inner, on_toggle_favorite)
        self.content.grid(row=0, column=0, sticky="nsew")
        self.current_state: ttk.Frame | ScrollFrame = self.content
        self.bind("<Configure>", self._rewrap)

    def _build_content(self, content: ttk.Frame, on_toggle_favorite: Callable[[], None]) -> None:
        content.columnconfigure(0, weight=1)

        card = ttk.Frame(content, style="Card.TFrame", padding=(20, 16))
        card.grid(row=0, column=0, sticky="ew")
        card.columnconfigure(2, weight=1)
        self.place_label = ttk.Label(card, style="CardTitle.TLabel")
        self.favorite_button = ttk.Button(card, command=on_toggle_favorite)
        self.subtitle = ttk.Label(card, style="CardMuted.TLabel")
        self.symbol = ttk.Label(card, style="CardSymbol.TLabel")
        self.temperature = ttk.Label(card, style="CardDisplay.TLabel")
        self.summary = ttk.Label(card, style="CardLarge.TLabel", justify="left")
        self.place_label.grid(row=0, column=0, columnspan=3, sticky="w")
        self.favorite_button.grid(row=0, column=3, sticky="ne")
        self.subtitle.grid(row=1, column=0, columnspan=4, sticky="w")
        self.symbol.grid(row=2, column=0, sticky="w", padx=(0, 12), pady=(8, 0))
        self.temperature.grid(row=2, column=1, sticky="w", pady=(8, 0))
        self.summary.grid(row=2, column=2, columnspan=2, sticky="w", padx=(24, 0), pady=(8, 0))
        ttk.Separator(card).grid(row=3, column=0, columnspan=4, sticky="ew", pady=14)

        stats = ttk.Frame(card, style="Card.TFrame", borderwidth=0)
        stats.grid(row=4, column=0, columnspan=4, sticky="ew")
        self.stats: dict[str, ttk.Label] = {}
        names = ("Feels like", "Humidity", "Wind", "Pressure", "Visibility", "Today")
        for i, name in enumerate(names):
            row, column = divmod(i, self.STAT_COLUMNS)
            stats.columnconfigure(column, weight=1, uniform="stat")
            ttk.Label(stats, text=name, style="CardMuted.TLabel").grid(
                row=row * 2, column=column, sticky="w"
            )
            value = ttk.Label(stats, style="CardBold.TLabel")
            value.grid(row=row * 2 + 1, column=column, sticky="w", pady=(0, 10))
            self.stats[name] = value

        self.forecast_title = ttk.Label(content, style="Heading.TLabel")
        self.forecast_title.grid(row=1, column=0, sticky="w", pady=(18, 8))
        self.forecast_row = ttk.Frame(content)
        self.forecast_row.grid(row=2, column=0, sticky="ew")
        self.cards: list[ForecastCard] = []

    def _rewrap(self, event: tk.Event[tk.Misc]) -> None:
        width = max(event.width - 80, 200)
        for label in (self.empty_text, self.error_text):
            label.configure(wraplength=min(width, 560))

    def _show_state(self, state: ttk.Frame | ScrollFrame) -> None:
        if state is not self.loading:
            self.progress.stop()
        for frame in (self.empty, self.loading, self.error, self.content):
            if frame is state:
                frame.grid()
            else:
                frame.grid_remove()
        self.current_state = state

    def show_empty(
        self,
        title: str,
        text: str,
        action: tuple[str, Callable[[], None]] | None = None,
    ) -> None:
        self.empty_title.configure(text=title)
        self.empty_text.configure(text=text)
        if action:
            self.empty_action.configure(text=action[0], command=action[1])
            self.empty_action.pack(pady=(16, 0))
        else:
            self.empty_action.pack_forget()
        self._show_state(self.empty)

    def show_loading(self, text: str) -> None:
        self.loading_text.configure(text=text)
        self.progress.start(12)
        self._show_state(self.loading)

    def show_error(
        self, message: str, suggestions: Sequence[str], retry: Callable[[], None] | None
    ) -> None:
        self.error_title.configure(text=message)
        self.error_text.configure(text="\n".join(f"•  {tip}" for tip in suggestions))
        if retry:
            self.error_retry.configure(command=retry)
            self.error_retry.pack(pady=(14, 0))
        else:
            self.error_retry.pack_forget()
        self._show_state(self.error)

    def show_weather(
        self,
        location: Location,
        weather: WeatherData,
        forecast: Sequence[ForecastData],
        fmt: WeatherFormatter,
        is_favorite: bool,
    ) -> None:
        self.place_label.configure(text=location.display_name)
        self.subtitle.configure(
            text=f"Observed {weather.timestamp:%A %d %B, %H:%M}  ·  "
            f"{location.latitude:.2f}, {location.longitude:.2f}"
        )
        self.symbol.configure(text=weather_symbol(weather.icon))
        self.temperature.configure(text=fmt.format_temperature(weather.temperature, decimals=0))
        self.summary.configure(text=weather.description)
        self.set_favorite(is_favorite)

        wind = fmt.format_wind_speed(weather.wind_speed)
        if weather.wind_speed > 0:
            wind += f" {fmt.format_wind_direction(weather.wind_direction).split()[0]}"
        today = "—"
        if weather.temp_min is not None and weather.temp_max is not None:
            today = (
                f"{fmt.format_temperature(weather.temp_min, decimals=0)} to "
                f"{fmt.format_temperature(weather.temp_max, decimals=0)}"
            )
        values = {
            "Feels like": fmt.format_temperature(weather.feels_like),
            "Humidity": fmt.format_humidity(weather.humidity),
            "Wind": wind,
            "Pressure": fmt.format_pressure(weather.pressure),
            "Visibility": fmt.format_visibility(weather.visibility),
            "Today": today,
        }
        for name, label in self.stats.items():
            label.configure(text=values[name])

        self.forecast_title.configure(text=f"Next {len(forecast)} days" if forecast else "")
        while len(self.cards) < len(forecast):
            self.cards.append(ForecastCard(self.forecast_row))
        for column, card in enumerate(self.cards):
            if column < len(forecast):
                self.forecast_row.columnconfigure(column, weight=1, uniform="day")
                card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 10, 0))
                card.show(forecast[column], fmt)
            else:
                self.forecast_row.columnconfigure(column, weight=0, uniform="")
                card.grid_remove()
        self._show_state(self.content)

    def set_favorite(self, is_favorite: bool) -> None:
        self.favorite_button.configure(text="★ Favorite" if is_favorite else "☆ Add to favorites")


class PlacePicker(tk.Toplevel):
    """A modal list for choosing between places with the same name."""

    def __init__(self, master: tk.Misc, query: str, places: Sequence[Location]) -> None:
        super().__init__(master)
        self.places = list(places)
        self.choice: Location | None = None
        self.title("Choose a place")
        self.transient(master.winfo_toplevel())
        self.resizable(False, False)

        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=f"Several places match “{query}”:", style="TLabel").pack(anchor="w")
        self.tree = ttk.Treeview(body, show="tree", height=min(len(places), 8), selectmode="browse")
        self.tree.column("#0", width=360)
        for index, place in enumerate(self.places):
            coordinates = f"   ({place.latitude:.2f}, {place.longitude:.2f})"
            self.tree.insert("", "end", iid=str(index), text=place.display_name + coordinates)
        self.tree.pack(fill="both", expand=True, pady=10)
        self.tree.selection_set("0")
        self.tree.focus("0")

        buttons = ttk.Frame(body)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Show weather", style="Accent.TButton", command=self._accept).pack(
            side="right", padx=(0, 8)
        )
        self.tree.bind("<Double-1>", lambda _e: self._accept())
        self.bind("<Return>", lambda _e: self._accept())
        self.bind("<Escape>", lambda _e: self.destroy())

    def _accept(self) -> None:
        selected = self.tree.selection()
        if selected:
            self.choice = self.places[int(selected[0])]
        self.destroy()

    def ask(self) -> Location | None:
        self.update_idletasks()
        parent = self.master.winfo_toplevel()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_reqwidth()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.grab_set()
        self.tree.focus_set()
        self.wait_window()
        return self.choice
