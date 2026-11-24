"""The ``meteormind`` command: one-shot subcommands and an interactive menu.

Exit codes: 0 success, 1 the request failed (network, API, storage), 2 the
command line or input was invalid, 130 interrupted with Ctrl+C.
"""

from __future__ import annotations

import argparse
import getpass
import json
import logging
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from . import __version__
from .api import MAX_FORECAST_DAYS, APIError
from .config import ConfigError
from .console import (
    configure_stream,
    describe_error,
    describe_forecast,
    describe_weather,
    favorites_table,
    history_table,
)
from .reporting import REPORT_FORMATS, ReportError, render_report, write_report
from .service import REPORT_KINDS, InputError, WeatherService
from .storage import StorageError
from .units import WeatherFormatter, create_imperial_preferences, create_metric_preferences

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_INTERRUPTED = 130


@dataclass
class App:
    """What a command handler needs: the service and where to write."""

    service: WeatherService
    out: TextIO = field(default_factory=lambda: sys.stdout)
    err: TextIO = field(default_factory=lambda: sys.stderr)

    def print(self, text: str = "") -> None:
        print(text, file=self.out)

    def warn(self, text: str) -> None:
        print(text, file=self.err)

    @property
    def fmt(self) -> WeatherFormatter:
        return self.service.formatter


Handler = Callable[[App, argparse.Namespace], int]


def _place(words: Sequence[str]) -> str:
    return " ".join(words).strip()


def _dump_json(app: App, data: object) -> None:
    app.print(json.dumps(data, indent=2, ensure_ascii=False))


# Weather ---------------------------------------------------------------------


def cmd_current(app: App, args: argparse.Namespace) -> int:
    location = app.service.locate(_place(args.place))
    weather = app.service.current_weather(location)
    if args.json:
        _dump_json(app, {"location": location.to_dict(), "weather": weather.to_dict()})
    else:
        app.print(describe_weather(weather, location, app.fmt))
    return EXIT_OK


def cmd_forecast(app: App, args: argparse.Namespace) -> int:
    location = app.service.locate(_place(args.place))
    forecast = app.service.forecast(location, args.days)
    if args.json:
        _dump_json(
            app, {"location": location.to_dict(), "forecast": [d.to_dict() for d in forecast]}
        )
    else:
        app.print(f"{len(forecast)}-day forecast for {location.display_name}")
        app.print(describe_forecast(forecast, app.fmt))
    return EXIT_OK


# Favorites -------------------------------------------------------------------


def cmd_favorites_list(app: App, args: argparse.Namespace) -> int:
    favorites = list(app.service.favorites)
    if args.json:
        _dump_json(app, [loc.to_dict() for loc in favorites])
    elif favorites:
        app.print(favorites_table(favorites))
    else:
        app.print("No favorites yet. Add one with: meteormind favorites add PLACE")
    return EXIT_OK


def cmd_favorites_add(app: App, args: argparse.Namespace) -> int:
    location = app.service.locate(_place(args.place))
    if app.service.add_favorite(location):
        app.print(f"Added {location.display_name} to favorites.")
    else:
        app.print(f"{location.display_name} is already a favorite.")
    return EXIT_OK


def cmd_favorites_remove(app: App, args: argparse.Namespace) -> int:
    query = _place(args.place)
    location = app.service.find_favorite(query)
    if location is None:
        app.warn(f"Error: '{query}' is not one of your favorites.")
        return EXIT_ERROR
    app.service.remove_favorite(location)
    app.print(f"Removed {location.display_name} from favorites.")
    return EXIT_OK


# History ---------------------------------------------------------------------


def cmd_history_list(app: App, args: argparse.Namespace) -> int:
    history = app.service.history
    if args.search:
        queries = history.search_queries(args.search, args.limit)
    else:
        queries = history.get_recent_queries(args.limit)
    if args.json:
        _dump_json(app, [q.to_dict() for q in queries])
    elif queries:
        app.print(history_table(queries, app.fmt))
    else:
        app.print("No matching queries." if args.search else "No queries yet.")
    return EXIT_OK


def cmd_history_clear(app: App, args: argparse.Namespace) -> int:
    if not args.yes:
        if not sys.stdin.isatty():
            app.warn("Error: pass --yes to clear the history without a prompt.")
            return EXIT_USAGE
        answer = input(f"Delete all {len(app.service.history)} queries? [y/N] ")
        if answer.strip().lower() not in {"y", "yes"}:
            app.print("Cancelled.")
            return EXIT_OK
    app.service.history.clear_history()
    app.print("History cleared.")
    return EXIT_OK


def cmd_history_export(app: App, args: argparse.Namespace) -> int:
    path = app.service.history.export_history(args.file)
    app.print(f"Exported {len(app.service.history)} queries to {path}")
    return EXIT_OK


# Reports ---------------------------------------------------------------------


def cmd_report(app: App, args: argparse.Namespace) -> int:
    report, warnings = app.service.build_report(args.kind, args.places, args.days)
    for warning in warnings:
        app.warn(f"Warning: {warning}")
    if args.output:
        path = write_report(report, args.output, args.format)
        app.print(f"Saved the report to {path}")
    else:
        app.print(render_report(report, args.format or "txt"))
    return EXIT_OK


# Configuration ---------------------------------------------------------------


def cmd_config_show(app: App, args: argparse.Namespace) -> int:
    service = app.service
    status = service.config.check_configuration()
    if status["api_key_found"]:
        key = f"{status['api_key_masked']} (from {status['api_key_source']})"
        if not status["api_key_valid_format"]:
            key += "; this does not look like an OpenWeatherMap key"
    else:
        key = "not set (run: meteormind config set-key)"
    units = service.preferences.units
    app.print(f"API key       {key}")
    app.print(f"Data folder   {service.store.directory}")
    app.print(
        f"Units         {units.temperature.symbol}, {units.wind_speed.symbol}, "
        f"{units.pressure.symbol}, {units.distance.symbol}"
    )
    app.print(f"Theme         {service.preferences.theme}")
    app.print(f"History size  {service.preferences.history_limit} queries")
    app.print(f"Cache         {service.preferences.cache_minutes} minutes")
    return EXIT_OK


def _read_key(app: App) -> str:
    if sys.stdin.isatty():
        app.print(app.service.config.get_setup_instructions())
        app.print()
        return getpass.getpass("API key (input is hidden): ")
    return sys.stdin.readline()


def cmd_config_set_key(app: App, args: argparse.Namespace) -> int:
    key = (args.key or _read_key(app)).strip()
    if not key:
        app.warn("Error: no key given.")
        return EXIT_USAGE
    if not app.service.config.validate_api_key(key):
        raise InputError("An OpenWeatherMap API key is 32 hexadecimal characters.")
    path = app.service.set_api_key(key)
    app.print(f"Saved the API key to {path}")
    return EXIT_OK


def cmd_config_clear_key(app: App, args: argparse.Namespace) -> int:
    if app.service.clear_api_key():
        app.print("Removed the saved API key.")
    else:
        app.print("No API key was saved.")
    lookup = app.service.config.find_api_key()
    if lookup.found:
        app.print(f"A key is still provided by {lookup.source}.")
    return EXIT_OK


# Parser ----------------------------------------------------------------------


def _add_common_options(parser: argparse.ArgumentParser, *, top_level: bool) -> None:
    # On subcommands the defaults are suppressed so they do not overwrite a
    # value given before the subcommand name.
    parser.add_argument(
        "--demo",
        action="store_true",
        default=False if top_level else argparse.SUPPRESS,
        help="use built-in sample data instead of OpenWeatherMap (no API key needed)",
    )
    parser.add_argument(
        "--units",
        choices=("metric", "imperial"),
        default=None if top_level else argparse.SUPPRESS,
        help="display units for this run (default: your saved preference)",
    )


def _add_days_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-d",
        "--days",
        type=int,
        choices=range(1, MAX_FORECAST_DAYS + 1),
        default=MAX_FORECAST_DAYS,
        metavar=f"1-{MAX_FORECAST_DAYS}",
        help=f"number of forecast days (default {MAX_FORECAST_DAYS})",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meteormind",
        description="Current weather and forecasts from OpenWeatherMap. "
        "Run without a command for the interactive menu.",
        epilog="Places can include a country code, e.g. 'Paris, FR'. "
        "Add --demo to any command to try it without an API key.",
    )
    parser.add_argument("--version", action="version", version=f"MeteorMind {__version__}")
    _add_common_options(parser, top_level=True)
    # Flags from earlier versions.
    parser.add_argument("--cli", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--gui", action="store_true", help=argparse.SUPPRESS)
    parser.set_defaults(handler=None)

    commands = parser.add_subparsers(title="commands", dest="command", metavar="COMMAND")

    def command(name: str, help_text: str, handler: Handler | None) -> argparse.ArgumentParser:
        sub = commands.add_parser(name, help=help_text, description=help_text)
        _add_common_options(sub, top_level=False)
        sub.set_defaults(handler=handler)
        return sub

    current = command("current", "show the current weather for a place", cmd_current)
    current.add_argument("place", nargs="+", help="for example: London, or New York, US")
    current.add_argument("--json", action="store_true", help="print JSON (metric units)")

    forecast = command("forecast", "show the daily forecast for a place", cmd_forecast)
    forecast.add_argument("place", nargs="+")
    _add_days_option(forecast)
    forecast.add_argument("--json", action="store_true", help="print JSON (metric units)")

    favorites = command("favorites", "list or change your favorite places", cmd_favorites_list)
    favorites.add_argument("--json", action="store_true")
    fav_commands = favorites.add_subparsers(dest="favorites_command", metavar="ACTION")
    fav_commands.add_parser("list", help="list favorites (the default)")
    fav_add = fav_commands.add_parser("add", help="add a place")
    fav_add.add_argument("place", nargs="+")
    fav_add.set_defaults(handler=cmd_favorites_add)
    fav_remove = fav_commands.add_parser("remove", help="remove a favorite")
    fav_remove.add_argument("place", nargs="+")
    fav_remove.set_defaults(handler=cmd_favorites_remove)

    history = command("history", "show, search, export or clear past queries", cmd_history_list)
    history.add_argument("-n", "--limit", type=int, default=20, help="how many (default 20)")
    history.add_argument("-s", "--search", metavar="TEXT", help="only places containing TEXT")
    history.add_argument("--json", action="store_true")
    hist_commands = history.add_subparsers(dest="history_command", metavar="ACTION")
    hist_commands.add_parser("list", help="show recent queries (the default)")
    hist_clear = hist_commands.add_parser("clear", help="delete the history")
    hist_clear.add_argument("-y", "--yes", action="store_true", help="do not ask to confirm")
    hist_clear.set_defaults(handler=cmd_history_clear)
    hist_export = hist_commands.add_parser("export", help="save the history as JSON")
    hist_export.add_argument("file", type=Path)
    hist_export.set_defaults(handler=cmd_history_export)

    report = command("report", "build a report and print or save it", cmd_report)
    report.add_argument(
        "kind",
        choices=REPORT_KINDS,
        metavar="KIND",
        help="; ".join(f"{name}: {text}" for name, text in REPORT_KINDS.items()),
    )
    report.add_argument("places", nargs="*", metavar="PLACE", help="quote names with spaces")
    report.add_argument(
        "-f", "--format", choices=REPORT_FORMATS, help="txt, csv or json (default: from FILE)"
    )
    report.add_argument("-o", "--output", type=Path, metavar="FILE", help="save instead of print")
    _add_days_option(report)

    config = command("config", "show or change settings", cmd_config_show)
    config_commands = config.add_subparsers(dest="config_command", metavar="ACTION")
    config_commands.add_parser("show", help="show the current settings (the default)")
    set_key = config_commands.add_parser(
        "set-key",
        help="save your OpenWeatherMap API key",
        description="Save your OpenWeatherMap API key. Without KEY it is read from a "
        "hidden prompt, or from standard input when that is not a terminal.",
    )
    set_key.add_argument("key", nargs="?", help="the key (prefer the prompt: shells keep history)")
    set_key.set_defaults(handler=cmd_config_set_key)
    clear_key = config_commands.add_parser("clear-key", help="remove the saved API key")
    clear_key.set_defaults(handler=cmd_config_clear_key)

    command("gui", "open the desktop app", None)
    command("menu", "start the interactive menu (the default)", None)
    return parser


def run_gui(demo: bool) -> int:
    try:
        from .gui import main as gui_main
    except ImportError as exc:  # pragma: no cover - depends on the Python build
        print(f"Error: the desktop app needs Tkinter ({exc}).", file=sys.stderr)
        return EXIT_ERROR
    return gui_main(["--demo"] if demo else [])


def main(argv: Sequence[str] | None = None) -> int:
    configure_stream(sys.stdout)
    configure_stream(sys.stderr)
    logging.basicConfig(level=logging.WARNING, format="Warning: %(message)s")
    args = build_parser().parse_args(argv)

    if args.command == "gui" or (args.gui and not args.command):
        return run_gui(args.demo)

    try:
        service = WeatherService.create(demo=args.demo)
        if args.units:
            presets = {"metric": create_metric_preferences, "imperial": create_imperial_preferences}
            service.preferences.units = presets[args.units]()
        if args.handler is None:
            from .menu import Menu

            return Menu(service).run()
        return int(args.handler(App(service), args))
    except KeyboardInterrupt:
        print(file=sys.stderr)
        return EXIT_INTERRUPTED
    except InputError as exc:
        print(describe_error(exc), file=sys.stderr)
        return EXIT_USAGE
    except (APIError, ConfigError, ReportError, StorageError) as exc:
        print(describe_error(exc), file=sys.stderr)
        return EXIT_ERROR
