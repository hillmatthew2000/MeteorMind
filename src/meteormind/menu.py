"""The interactive text menu started by running ``meteormind`` with no command.

Every prompt can be left empty (or answered with Ctrl+C) to go back. End of
input (Ctrl+Z/Ctrl+D, or a closed pipe) leaves the menu cleanly.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import TextIO, TypeVar

from .api import MAX_FORECAST_DAYS, APIError
from .config import ConfigError
from .console import (
    describe_error,
    describe_forecast,
    describe_weather,
    favorites_table,
    format_pairs,
    history_table,
)
from .models import Location
from .preferences import CACHE_MINUTES_RANGE, HISTORY_LIMIT_RANGE
from .reporting import REPORT_FORMATS, ReportError, WeatherReport, write_report
from .service import InputError, WeatherService
from .storage import StorageError, format_file_size
from .units import (
    DistanceUnit,
    PressureUnit,
    TemperatureUnit,
    WindSpeedUnit,
    create_imperial_preferences,
    create_metric_preferences,
)

E = TypeVar("E", TemperatureUnit, WindSpeedUnit, PressureUnit, DistanceUnit)

UNIT_NAMES: dict[object, str] = {
    TemperatureUnit.CELSIUS: "Celsius",
    TemperatureUnit.FAHRENHEIT: "Fahrenheit",
    TemperatureUnit.KELVIN: "Kelvin",
    WindSpeedUnit.METERS_PER_SECOND: "metres per second",
    WindSpeedUnit.KILOMETERS_PER_HOUR: "kilometres per hour",
    WindSpeedUnit.MILES_PER_HOUR: "miles per hour",
    WindSpeedUnit.KNOTS: "knots",
    PressureUnit.HECTOPASCAL: "hectopascals",
    PressureUnit.MILLIBARS: "millibars",
    PressureUnit.INCHES_OF_MERCURY: "inches of mercury",
    PressureUnit.ATMOSPHERES: "atmospheres",
    DistanceUnit.KILOMETERS: "kilometres",
    DistanceUnit.MILES: "miles",
    DistanceUnit.METERS: "metres",
    DistanceUnit.FEET: "feet",
}

HELP_TEXT = """\
MeteorMind shows current weather and five-day forecasts from OpenWeatherMap.

Places: type a city name, optionally with a country code ("Paris, FR").
When several places match, you can pick the one you meant.

Favorites are kept with the most recently used first. History keeps your
recent lookups, which the reports use for statistics and temperature trends.
Responses are cached for a few minutes (see Settings) to save API calls.

At any prompt, press Enter on an empty line or Ctrl+C to go back.

The same features are available as commands, for scripts:
  meteormind current London        meteormind forecast Paris, FR --days 3
  meteormind favorites add Tokyo   meteormind report compare --format csv
Run "meteormind --help" for the full list, or "meteormind gui" for the
desktop app."""


class EndOfInput(Exception):
    """Standard input was closed."""


class Menu:
    def __init__(
        self,
        service: WeatherService,
        input_func: Callable[[str], str] = input,
        out: TextIO | None = None,
    ) -> None:
        self.service = service
        self._input = input_func
        self.out = out or sys.stdout

    # Prompts -------------------------------------------------------------------

    def say(self, text: str = "") -> None:
        print(text, file=self.out)

    def ask(self, prompt: str) -> str:
        """Read one line; raises :class:`EndOfInput` when input is closed."""
        try:
            return self._input(prompt).strip()
        except EOFError:
            raise EndOfInput from None

    def choose(self, title: str, options: Sequence[tuple[str, str]], back: str = "Back") -> str:
        """Show numbered options; returns the chosen key, or "" for back."""
        while True:
            self.say()
            self.say(title)
            for n, (_, label) in enumerate(options, 1):
                self.say(f"  {n}. {label}")
            self.say(f"  0. {back}")
            answer = self.ask("> ").lower()
            if answer in {"", "0", "q"}:
                return ""
            if answer.isdigit() and 1 <= int(answer) <= len(options):
                return options[int(answer) - 1][0]
            self.say(f"Please enter a number from 0 to {len(options)}.")

    def confirm(self, question: str) -> bool:
        return self.ask(f"{question} [y/N] ").lower() in {"y", "yes"}

    def ask_number(
        self, prompt: str, low: int, high: int, default: int | None = None
    ) -> int | None:
        while True:
            answer = self.ask(prompt)
            if not answer:
                return default
            if answer.isdigit() and low <= int(answer) <= high:
                return int(answer)
            self.say(f"Please enter a whole number from {low} to {high}.")

    def pick(self, items: Sequence[Location], prompt: str) -> Location | None:
        """Choose one place from a numbered list."""
        for n, location in enumerate(items, 1):
            self.say(f"  {n}. {location.display_name}")
        number = self.ask_number(prompt, 1, len(items))
        return items[number - 1] if number else None

    def ask_place(self, prompt: str = "Place (e.g. Paris, FR): ") -> Location | None:
        """Ask for a place name and resolve it, letting the user pick between matches."""
        query = self.ask(prompt)
        if not query:
            return None
        matches = self.service.search(query)
        if not matches:
            raise InputError(
                f"No place called '{query}' was found.",
                ["Check the spelling, or add a country code such as 'Paris, FR'."],
            )
        if len(matches) == 1:
            return matches[0]
        self.say(f"Several places match '{query}':")
        return self.pick(matches, f"Which one? [1-{len(matches)}, Enter for 1] ") or matches[0]

    # Main loop -----------------------------------------------------------------

    def run(self) -> int:
        self.say("MeteorMind" + (" (demo data)" if self.service.is_demo else ""))
        if not self.service.has_provider:
            self.say("No OpenWeatherMap API key is set up yet: choose 'API key' to add one.")
        actions: dict[str, Callable[[], None]] = {
            "current": self.current_weather,
            "forecast": self.forecast,
            "favorites": self.favorites_menu,
            "history": self.history_menu,
            "reports": self.reports_menu,
            "settings": self.settings_menu,
            "key": self.api_key_menu,
            "help": lambda: self.say(HELP_TEXT),
        }
        options = [
            ("current", "Current weather"),
            ("forecast", "Forecast"),
            ("favorites", "Favorites"),
            ("history", "History"),
            ("reports", "Reports"),
            ("settings", "Settings"),
            ("key", "API key"),
            ("help", "Help"),
        ]
        try:
            while True:
                try:
                    choice = self.choose("Main menu", options, back="Quit")
                except KeyboardInterrupt:
                    break
                if not choice:
                    break
                self.guard(actions[choice])
        except EndOfInput:
            self.say()
        return 0

    def guard(self, action: Callable[..., object], *args: object) -> None:
        """Run a menu action, reporting failures instead of leaving the menu."""
        try:
            action(*args)
        except KeyboardInterrupt:
            self.say("\nCancelled.")
        except (APIError, ConfigError, InputError, ReportError, StorageError) as exc:
            self.say(describe_error(exc))

    # Weather -------------------------------------------------------------------

    def current_weather(self) -> None:
        location = self.ask_place()
        if location is None:
            return
        weather = self.service.current_weather(location)
        self.say()
        self.say(describe_weather(weather, location, self.service.formatter))
        if location not in self.service.favorites and self.confirm(
            f"Add {location.display_name} to favorites?"
        ):
            self.service.add_favorite(location)
            self.say("Added.")

    def forecast(self) -> None:
        location = self.ask_place()
        if location is None:
            return
        days = self.ask_number(
            f"Days [1-{MAX_FORECAST_DAYS}, Enter for {MAX_FORECAST_DAYS}]: ",
            1,
            MAX_FORECAST_DAYS,
            MAX_FORECAST_DAYS,
        )
        forecast = self.service.forecast(location, days or MAX_FORECAST_DAYS)
        self.say()
        self.say(f"{len(forecast)}-day forecast for {location.display_name}")
        self.say(describe_forecast(forecast, self.service.formatter))

    # Favorites -----------------------------------------------------------------

    def pick_favorite(self, verb: str) -> Location | None:
        favorites = list(self.service.favorites)
        if not favorites:
            self.say("You have no favorites yet.")
            return None
        return self.pick(favorites, f"{verb} which favorite? [1-{len(favorites)}] ")

    def favorites_menu(self) -> None:
        while True:
            choice = self.choose(
                "Favorites",
                [
                    ("list", "List favorites"),
                    ("weather", "Current weather for a favorite"),
                    ("add", "Add a favorite"),
                    ("remove", "Remove a favorite"),
                    ("top", "Move a favorite to the top"),
                ],
            )
            if not choice:
                return
            self.guard(self._favorites_action, choice)

    def _favorites_action(self, choice: str) -> None:
        service = self.service
        if choice == "list":
            favorites = list(service.favorites)
            self.say(favorites_table(favorites) if favorites else "You have no favorites yet.")
        elif choice == "weather":
            location = self.pick_favorite("Show")
            if location:
                weather = service.current_weather(location)
                service.touch_favorite(location)
                self.say(describe_weather(weather, location, service.formatter))
        elif choice == "add":
            location = self.ask_place()
            if location:
                added = service.add_favorite(location)
                verb = "Added" if added else "Already a favorite:"
                self.say(f"{verb} {location.display_name}")
        elif choice == "remove":
            location = self.pick_favorite("Remove")
            if location and self.confirm(f"Remove {location.display_name}?"):
                service.remove_favorite(location)
                self.say(f"Removed {location.display_name}.")
        elif choice == "top":
            location = self.pick_favorite("Move")
            if location:
                service.move_favorite_to_top(location)
                self.say(f"{location.display_name} is now first.")

    # History -------------------------------------------------------------------

    def history_menu(self) -> None:
        history = self.service.history
        while True:
            recent = history.get_recent_queries(15)
            self.say()
            if recent:
                self.say(f"Most recent of {len(history)} queries:")
                self.say(history_table(recent, self.service.formatter))
            else:
                self.say("No queries yet.")
            choice = self.choose(
                "History",
                [("search", "Search"), ("export", "Export to a JSON file"), ("clear", "Clear")],
            )
            if not choice:
                return
            self.guard(self._history_action, choice)

    def _history_action(self, choice: str) -> None:
        history = self.service.history
        if choice == "search":
            term = self.ask("Place name or country code: ")
            if term:
                matches = history.search_queries(term, 50)
                self.say(
                    history_table(matches, self.service.formatter)
                    if matches
                    else f"Nothing matches '{term}'."
                )
        elif choice == "export":
            default = f"meteormind-history-{datetime.now():%Y%m%d-%H%M}.json"
            name = self.ask(f"File name [{default}]: ") or default
            self.say(f"Saved to {history.export_history(Path(name))}")
        elif choice == "clear" and self.confirm(f"Delete all {len(history)} queries?"):
            history.clear_history()
            self.say("History cleared.")

    # Reports -------------------------------------------------------------------

    def reports_menu(self) -> None:
        while True:
            choice = self.choose(
                "Reports",
                [
                    ("compare", "Compare current weather at your favorites"),
                    ("compare-places", "Compare current weather at places you name"),
                    ("forecast", "Detailed forecast for a place"),
                    ("forecast-compare", "Compare forecasts at your favorites"),
                    ("locations", "Most looked-up places"),
                    ("trends", "Temperature trend for a place (from history)"),
                    ("history", "Recent queries"),
                ],
            )
            if not choice:
                return
            self.guard(self._report_action, choice)

    def _report_action(self, choice: str) -> None:
        places: list[str] = []
        if choice == "compare-places":
            text = self.ask("Places, separated by ';' (e.g. London; Paris, FR): ")
            places = [p.strip() for p in text.split(";") if p.strip()]
            if not places:
                return
            choice = "compare"
        elif choice in ("forecast", "trends"):
            place = self.ask("Place (e.g. Paris, FR): ")
            if not place:
                return
            places = [place]
        report, warnings = self.service.build_report(choice, places)
        for warning in warnings:
            self.say(f"Warning: {warning}")
        self.say()
        self.say(report.to_table_string())
        if report.rows and self.confirm("Save this report?"):
            self.save_report(report, choice)

    def save_report(self, report: WeatherReport, name: str) -> None:
        fmt = self.ask(f"Format ({', '.join(REPORT_FORMATS)}) [txt]: ").lower() or "txt"
        if fmt not in REPORT_FORMATS:
            raise InputError(f"Choose one of: {', '.join(REPORT_FORMATS)}.")
        default = f"meteormind-{name}-{datetime.now():%Y%m%d-%H%M}.{fmt}"
        path = self.ask(f"File name [{default}]: ") or default
        self.say(f"Saved to {write_report(report, Path(path), fmt)}")

    # Settings ------------------------------------------------------------------

    def settings_menu(self) -> None:
        while True:
            units = self.service.preferences.units
            choice = self.choose(
                "Settings",
                [
                    ("temperature", f"Temperature unit ({units.temperature.symbol})"),
                    ("wind", f"Wind speed unit ({units.wind_speed.symbol})"),
                    ("pressure", f"Pressure unit ({units.pressure.symbol})"),
                    ("distance", f"Distance unit ({units.distance.symbol})"),
                    ("metric", "Use metric units"),
                    ("imperial", "Use imperial units"),
                    ("history", f"History size ({self.service.preferences.history_limit})"),
                    ("cache", f"Cache lifetime ({self.service.preferences.cache_minutes} min)"),
                    ("data", "Show data files"),
                    ("clear-cache", "Clear cached responses"),
                    ("backup", "Back up favorites, history and settings"),
                    ("reset", "Delete all data"),
                ],
            )
            if not choice:
                return
            self.guard(self._settings_action, choice)

    def choose_unit(self, title: str, current: E) -> E:
        members = list(type(current))
        options = [(m.value, f"{UNIT_NAMES[m]} ({m.symbol})") for m in members]
        choice = self.choose(title, options)
        return type(current)(choice) if choice else current

    def _settings_action(self, choice: str) -> None:
        service = self.service
        prefs = service.preferences
        units = replace(prefs.units)
        if choice == "temperature":
            units.temperature = self.choose_unit("Temperature unit", units.temperature)
        elif choice == "wind":
            units.wind_speed = self.choose_unit("Wind speed unit", units.wind_speed)
        elif choice == "pressure":
            units.pressure = self.choose_unit("Pressure unit", units.pressure)
        elif choice == "distance":
            units.distance = self.choose_unit("Distance unit", units.distance)
        elif choice == "metric":
            units = create_metric_preferences()
        elif choice == "imperial":
            units = create_imperial_preferences()
        elif choice == "history":
            low, high = HISTORY_LIMIT_RANGE
            limit = self.ask_number(f"Keep how many queries? [{low}-{high}] ", low, high)
            if limit:
                service.update_preferences(replace(prefs, history_limit=limit))
            return
        elif choice == "cache":
            low, high = CACHE_MINUTES_RANGE
            minutes = self.ask_number(
                f"Cache responses for how many minutes? [{low}-{high}] ", low, high
            )
            if minutes is not None:
                service.update_preferences(replace(prefs, cache_minutes=minutes))
            return
        elif choice == "data":
            self.show_data_files()
            return
        elif choice == "clear-cache":
            service.clear_cache()
            self.say("Cache cleared.")
            return
        elif choice == "backup":
            self.say(f"Backed up to {service.backup()}")
            return
        elif choice == "reset":
            if self.ask("Type DELETE to remove all favorites, history and settings: ") == "DELETE":
                service.clear_all_data()
                self.say("All data deleted.")
            else:
                self.say("Nothing was deleted.")
            return
        if units != prefs.units:
            service.set_units(units)
            self.say("Saved.")

    def show_data_files(self) -> None:
        self.say(f"Data folder: {self.service.store.directory}")
        pairs = []
        for info in self.service.store.file_info():
            if info.exists and info.modified:
                detail = (
                    f"{format_file_size(info.size_bytes)}, changed {info.modified:%Y-%m-%d %H:%M}"
                )
            else:
                detail = "not created yet"
            pairs.append((info.name, detail))
        self.say(format_pairs(pairs))
        self.say(f"Cached responses: {self.service.cached_responses()}")

    # API key -------------------------------------------------------------------

    def api_key_menu(self) -> None:
        while True:
            lookup = self.service.config.find_api_key()
            status = f"from {lookup.source}" if lookup.found else "not set"
            choice = self.choose(
                f"API key ({status})",
                [
                    ("set", "Enter a key"),
                    ("test", "Test the connection"),
                    ("clear", "Remove the saved key"),
                    ("help", "How to get a key"),
                ],
            )
            if not choice:
                return
            self.guard(self._api_key_action, choice)

    def _api_key_action(self, choice: str) -> None:
        service = self.service
        if choice == "set":
            key = self.ask("Paste your API key: ")
            if key:
                self.say(f"Saved to {service.set_api_key(key)}")
        elif choice == "test":
            self.say("Connected." if service.test_connection() else "The key was rejected.")
        elif choice == "clear":
            self.say("Removed." if service.clear_api_key() else "No key was saved.")
            lookup = service.config.find_api_key()
            if lookup.found:
                self.say(f"A key is still provided by {lookup.source}.")
        elif choice == "help":
            self.say(service.config.get_setup_instructions())
