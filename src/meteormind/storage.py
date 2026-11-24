"""Persistent user data: favorite locations, query history and preferences.

Everything lives in the per-user application directory (see
:mod:`meteormind.paths`) next to ``config.json``:

- ``favorites.json``: favorite locations, most recently used first
- ``history.json``: recent weather queries
- ``preferences.json``: units, theme and limits (see :mod:`meteormind.preferences`)
- ``cache.json``: recent API responses (see :mod:`meteormind.cache`)

Earlier versions kept these files in a ``data`` folder under whatever
directory the app was started from. :func:`migrate_legacy_data` copies them
into the application directory the first time the new version runs; the
loaders accept both the old and the new file layouts.

Files are written atomically. A file that cannot be parsed is moved aside
(see :func:`meteormind.jsonio.read_json`) rather than overwritten.
"""

from __future__ import annotations

import logging
import shutil
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, TypeVar

from .jsonio import atomic_write_json, read_json
from .models import FavoriteLocationsLinkedList, Location, WeatherQuery
from .paths import app_dir
from .preferences import Preferences

logger = logging.getLogger(__name__)

T = TypeVar("T")

FORMAT_VERSION = 2

FAVORITES_FILE = "favorites.json"
HISTORY_FILE = "history.json"
PREFERENCES_FILE = "preferences.json"
CACHE_FILE = "cache.json"

# File names used by versions that stored data in ./data
LEGACY_FILE_NAMES = {
    "favorite_locations.json": FAVORITES_FILE,
    "recent_queries.json": HISTORY_FILE,
    "user_preferences.json": PREFERENCES_FILE,
}

# Queries older than this are dropped when history is loaded.
HISTORY_MAX_AGE = timedelta(days=30)


def default_favorites() -> list[Location]:
    """A few well-known cities so a first run has something to show."""
    return [
        Location("London", "GB", 51.5074, -0.1278, state="England"),
        Location("New York", "US", 40.7128, -74.0060, state="New York"),
        Location("Tokyo", "JP", 35.6762, 139.6503),
        Location("Paris", "FR", 48.8566, 2.3522, state="Ile-de-France"),
        Location("Sydney", "AU", -33.8688, 151.2093, state="New South Wales"),
    ]


class StorageError(Exception):
    """Raised when user data cannot be written; ``str(error)`` is user-facing."""


@dataclass(frozen=True)
class DataFileInfo:
    """Size and modification time of one data file, for status displays."""

    name: str
    path: Path
    exists: bool
    size_bytes: int = 0
    modified: datetime | None = None


def format_file_size(size_bytes: int) -> str:
    """Format a byte count as ``512 B``, ``1.5 KB``, ``2.0 MB`` ..."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    size = float(size_bytes)
    for unit in ("KB", "MB", "GB"):
        size /= 1024
        if size < 1024:
            return f"{size:.1f} {unit}"
    return f"{size / 1024:.1f} TB"


def migrate_legacy_data(legacy_dir: Path, data_dir: Path) -> list[Path]:
    """Copy data files from an old ``./data`` folder into ``data_dir``.

    A file is only copied when its new counterpart does not exist yet, so
    this is safe to call on every start. The old files are left in place.
    Returns the paths that were created.
    """
    if not legacy_dir.is_dir():
        return []
    try:
        if legacy_dir.resolve() == data_dir.resolve():
            return []
    except OSError:
        return []
    created = []
    for old_name, new_name in LEGACY_FILE_NAMES.items():
        source = legacy_dir / old_name
        target = data_dir / new_name
        if not source.is_file() or target.exists():
            continue
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        except OSError as exc:
            logger.warning("Could not migrate %s: %s", source, exc)
            continue
        logger.info("Migrated %s to %s", source, target)
        created.append(target)
    return created


class DataStore:
    """Reads and writes the user's data files in one directory."""

    def __init__(self, directory: Path | str | None = None) -> None:
        self.directory = Path(directory) if directory is not None else app_dir()
        self.favorites_file = self.directory / FAVORITES_FILE
        self.history_file = self.directory / HISTORY_FILE
        self.preferences_file = self.directory / PREFERENCES_FILE
        self.cache_file = self.directory / CACHE_FILE
        self.backups_dir = self.directory / "backups"

    @property
    def data_files(self) -> dict[str, Path]:
        return {
            "Favorites": self.favorites_file,
            "History": self.history_file,
            "Preferences": self.preferences_file,
            "Response cache": self.cache_file,
        }

    def _write(self, path: Path, data: Any) -> None:
        try:
            atomic_write_json(path, data)
        except OSError as exc:
            raise StorageError(f"Could not save {path}: {exc.strerror or exc}") from exc

    # Favorites ---------------------------------------------------------------

    def load_favorite_locations(self) -> FavoriteLocationsLinkedList:
        """Load favorites; a first run (no file yet) gets :func:`default_favorites`."""
        if not self.favorites_file.exists():
            return FavoriteLocationsLinkedList(default_favorites())
        data = read_json(self.favorites_file)
        items = data.get("locations") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return FavoriteLocationsLinkedList()
        return FavoriteLocationsLinkedList(_parse_items(items, Location.from_dict, "favorite"))

    def save_favorite_locations(self, favorites: Iterable[Location]) -> None:
        self._write(
            self.favorites_file,
            {"version": FORMAT_VERSION, "locations": [loc.to_dict() for loc in favorites]},
        )

    # History -----------------------------------------------------------------

    def load_history(self, now: datetime | None = None) -> list[WeatherQuery]:
        """Load queries, oldest first, dropping entries older than ``HISTORY_MAX_AGE``."""
        data = read_json(self.history_file)
        items = data.get("queries") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return []
        cutoff = (now or datetime.now()) - HISTORY_MAX_AGE
        queries = _parse_items(items, WeatherQuery.from_dict, "history entry")
        return sorted((q for q in queries if q.query_time >= cutoff), key=lambda q: q.query_time)

    def save_history(self, queries: Iterable[WeatherQuery]) -> None:
        self._write(
            self.history_file,
            {"version": FORMAT_VERSION, "queries": [query.to_dict() for query in queries]},
        )

    # Preferences -------------------------------------------------------------

    def load_preferences(self) -> Preferences:
        return Preferences.from_dict(read_json(self.preferences_file))

    def save_preferences(self, preferences: Preferences) -> None:
        self._write(self.preferences_file, preferences.to_dict())

    # Maintenance -------------------------------------------------------------

    def file_info(self) -> list[DataFileInfo]:
        infos = []
        for name, path in self.data_files.items():
            try:
                stat = path.stat()
            except OSError:
                infos.append(DataFileInfo(name, path, exists=False))
                continue
            modified = datetime.fromtimestamp(stat.st_mtime)
            infos.append(DataFileInfo(name, path, True, stat.st_size, modified))
        return infos

    def backup(self, now: datetime | None = None) -> Path:
        """Copy the data files (not the cache) into a new timestamped folder."""
        target = self.backups_dir / f"{now or datetime.now():%Y%m%d-%H%M%S}"
        try:
            target.mkdir(parents=True, exist_ok=True)
            for path in (self.favorites_file, self.history_file, self.preferences_file):
                if path.is_file():
                    shutil.copy2(path, target / path.name)
        except OSError as exc:
            raise StorageError(f"Could not create a backup in {target}: {exc}") from exc
        return target

    def clear_all(self) -> None:
        """Empty favorites and history, reset preferences and drop the cache."""
        self.save_favorite_locations([])
        self.save_history([])
        self.save_preferences(Preferences())
        try:
            self.cache_file.unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError(f"Could not delete {self.cache_file}: {exc}") from exc


def _parse_items(items: list[Any], parse: Callable[[Any], T], what: str) -> list[T]:
    parsed: list[T] = []
    for item in items:
        try:
            parsed.append(parse(item))
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            logger.warning("Skipping invalid %s: %r", what, exc)
    return parsed
