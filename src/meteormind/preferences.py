"""User preferences: display units, theme, history size and cache lifetime.

Preferences are stored as a small versioned JSON document::

    {"version": 2, "units": {...}, "theme": "system", "history_limit": 100,
     "cache_minutes": 10}

Files written by earlier versions nest the values under ``"preferences"``,
use ``"max_recent_queries"``/``"cache_duration_minutes"`` and may give the
units as a preset name (``"metric"``/``"imperial"``). :meth:`Preferences.from_dict`
reads both layouts; unknown or out-of-range values fall back to defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .units import UnitPreferences

PREFERENCES_FORMAT_VERSION = 2

THEMES = ("system", "light", "dark")

HISTORY_LIMIT_RANGE = (10, 1000)
CACHE_MINUTES_RANGE = (0, 120)


def _bounded_int(value: Any, default: int, bounds: tuple[int, int]) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    low, high = bounds
    return min(max(int(value), low), high)


@dataclass
class Preferences:
    """Everything the user can change in Settings."""

    units: UnitPreferences = field(default_factory=UnitPreferences)
    theme: str = "system"
    history_limit: int = 100
    cache_minutes: int = 10

    @property
    def cache_seconds(self) -> int:
        return self.cache_minutes * 60

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": PREFERENCES_FORMAT_VERSION,
            "units": self.units.to_dict(),
            "theme": self.theme,
            "history_limit": self.history_limit,
            "cache_minutes": self.cache_minutes,
        }

    @classmethod
    def from_dict(cls, data: Any) -> Preferences:
        if not isinstance(data, dict):
            return cls()
        legacy = data.get("preferences")
        if isinstance(legacy, dict):
            data = {
                "units": legacy.get("units"),
                "theme": legacy.get("theme"),
                "history_limit": legacy.get("max_recent_queries"),
                "cache_minutes": legacy.get("cache_duration_minutes"),
            }
        defaults = cls()
        theme = data.get("theme")
        return cls(
            units=UnitPreferences.from_setting(data.get("units")),
            theme=theme if theme in THEMES else defaults.theme,
            history_limit=_bounded_int(
                data.get("history_limit"), defaults.history_limit, HISTORY_LIMIT_RANGE
            ),
            cache_minutes=_bounded_int(
                data.get("cache_minutes"), defaults.cache_minutes, CACHE_MINUTES_RANGE
            ),
        )
