"""Small helpers for reading and atomically writing JSON files."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def atomic_write_json(path: Path, data: Any, *, private: bool = False) -> None:
    """Write ``data`` as JSON so readers only ever see the old or the new file.

    The content goes to a temporary file in the same directory which then
    replaces the target. With ``private=True`` the file is made readable by
    the owner only (where the platform supports it). Raises ``OSError``.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        if private:
            os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def read_json(path: Path) -> Any | None:
    """Return the parsed contents of ``path``, or None if it is missing or empty.

    A file that cannot be parsed is renamed to ``<name>.corrupt-<timestamp>``
    so the user's data is kept for inspection and the application can start
    fresh instead of failing on every launch.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return None
    if not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        quarantine = path.with_name(f"{path.name}.corrupt-{datetime.now():%Y%m%d-%H%M%S}")
        logger.warning("%s is not valid JSON (%s); moved it to %s", path, exc, quarantine.name)
        try:
            os.replace(path, quarantine)
        except OSError:
            logger.warning("Could not move %s aside", path)
        return None
