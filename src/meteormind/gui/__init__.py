"""The MeteorMind desktop app (Tkinter).

Start it with ``meteormind gui`` or ``meteormind-gui``; add ``--demo`` to use
built-in sample data instead of OpenWeatherMap.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILE = "meteormind.log"


def _enable_high_dpi() -> None:
    """Render crisply on scaled Windows displays instead of being bitmap-stretched."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def _log_to_file(path: Path) -> None:
    """Keep warnings and errors in ``path``: started without a console, stderr goes nowhere."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(path, maxBytes=256_000, backupCount=1, encoding="utf-8")
    except OSError:
        return
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.setLevel(logging.WARNING)
    logging.getLogger().addHandler(handler)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="meteormind-gui", description="The MeteorMind desktop app."
    )
    parser.add_argument(
        "--demo", action="store_true", help="use built-in sample data (no API key needed)"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="Warning: %(message)s")

    import tkinter as tk

    from ..service import WeatherService
    from .app import MeteorMindApp

    _enable_high_dpi()
    try:
        root = tk.Tk(className="MeteorMind")
    except tk.TclError as exc:
        print(f"Error: could not open a window ({exc}).", file=sys.stderr)
        return 1
    service = WeatherService.create(demo=args.demo)
    _log_to_file(service.store.directory / LOG_FILE)
    app = MeteorMindApp(root, service)
    root.report_callback_exception = app.report_callback_exception
    root.mainloop()
    return 0
