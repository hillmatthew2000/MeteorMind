"""The MeteorMind desktop app (Tkinter).

Start it with ``meteormind gui`` or ``meteormind-gui``; add ``--demo`` to use
built-in sample data instead of OpenWeatherMap.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence


def _enable_high_dpi() -> None:
    """Render crisply on scaled Windows displays instead of being bitmap-stretched."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


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
    MeteorMindApp(root, WeatherService.create(demo=args.demo))
    root.mainloop()
    return 0
