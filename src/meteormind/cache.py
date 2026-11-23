"""A small time-limited cache for API responses, optionally persisted to disk.

Persisting the cache means repeated one-shot CLI commands (``meteormind
current London`` twice in a row) reuse the first response instead of
spending another API call.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .jsonio import atomic_write_json, read_json

logger = logging.getLogger(__name__)

CACHE_FORMAT_VERSION = 1


class ResponseCache:
    """Maps request keys to JSON payloads for ``ttl_seconds``.

    Thread-safe, so GUI worker threads can share one instance.
    """

    def __init__(
        self,
        path: Path | None = None,
        ttl_seconds: float = 600,
        max_entries: int = 256,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.path = path
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: dict[str, tuple[float, Any]] = {}
        self._loaded = path is None

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        assert self.path is not None
        data = read_json(self.path)
        if not isinstance(data, dict) or data.get("version") != CACHE_FORMAT_VERSION:
            return
        entries = data.get("entries", {})
        if isinstance(entries, dict):
            for key, value in entries.items():
                if isinstance(value, list) and len(value) == 2:
                    self._entries[key] = (float(value[0]), value[1])

    def _is_fresh(self, stored_at: float) -> bool:
        return 0 <= self._clock() - stored_at < self.ttl_seconds

    def get(self, key: str) -> Any | None:
        with self._lock:
            self._ensure_loaded()
            entry = self._entries.get(key)
            if entry is None:
                return None
            if not self._is_fresh(entry[0]):
                del self._entries[key]
                return None
            return entry[1]

    def set(self, key: str, payload: Any) -> None:
        with self._lock:
            self._ensure_loaded()
            self._entries[key] = (self._clock(), payload)
            self._prune()
            self._save()

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._loaded = True
            if self.path is not None:
                self.path.unlink(missing_ok=True)

    def __len__(self) -> int:
        with self._lock:
            self._ensure_loaded()
            return sum(1 for stored_at, _ in self._entries.values() if self._is_fresh(stored_at))

    def _prune(self) -> None:
        stale = [
            key for key, (stored_at, _) in self._entries.items() if not self._is_fresh(stored_at)
        ]
        for key in stale:
            del self._entries[key]
        overflow = len(self._entries) - self.max_entries
        if overflow > 0:
            oldest = sorted(self._entries, key=lambda key: self._entries[key][0])[:overflow]
            for key in oldest:
                del self._entries[key]

    def _save(self) -> None:
        if self.path is None:
            return
        data = {
            "version": CACHE_FORMAT_VERSION,
            "entries": {
                key: [stored_at, payload] for key, (stored_at, payload) in self._entries.items()
            },
        }
        try:
            atomic_write_json(self.path, data)
        except OSError as exc:  # a cache that cannot be written is not fatal
            logger.warning("Could not write response cache %s: %s", self.path, exc)
