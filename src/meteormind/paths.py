"""Where MeteorMind keeps its configuration and data files.

Everything lives in one per-user directory:

- Windows: ``%APPDATA%\\MeteorMind``
- macOS: ``~/Library/Application Support/MeteorMind``
- Linux and others: ``$XDG_CONFIG_HOME/meteormind`` (default ``~/.config/meteormind``)

Set ``METEORMIND_HOME`` to use a different directory, for example to keep a
separate profile for testing.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "MeteorMind"
HOME_ENV_VAR = "METEORMIND_HOME"


def app_dir() -> Path:
    """Return the per-user application directory (not created here)."""
    override = os.environ.get(HOME_ENV_VAR)
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / APP_NAME.lower()
