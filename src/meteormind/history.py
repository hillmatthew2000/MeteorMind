"""The query history: what was looked up, when, and what the weather was.

API responses are cached by :class:`meteormind.cache.ResponseCache` inside
the weather client; this module only records queries for the History view
and the reports.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from .models import Location, WeatherData, WeatherQuery
from .storage import DataStore, StorageError


@dataclass(frozen=True)
class HistoryStatistics:
    """Summary of the query history."""

    total_queries: int = 0
    first_query: datetime | None = None
    last_query: datetime | None = None
    top_locations: list[tuple[str, int]] = field(default_factory=list)
    query_types: dict[str, int] = field(default_factory=dict)
    queries_by_day: dict[date, int] = field(default_factory=dict)

    @property
    def unique_locations(self) -> int:
        return len(self.top_locations)

    def to_dict(self) -> dict[str, object]:
        return {
            "total_queries": self.total_queries,
            "first_query": self.first_query.isoformat() if self.first_query else None,
            "last_query": self.last_query.isoformat() if self.last_query else None,
            "top_locations": [list(item) for item in self.top_locations],
            "query_types": self.query_types,
            "queries_by_day": {day.isoformat(): n for day, n in self.queries_by_day.items()},
        }


class HistoryManager:
    """Keeps the most recent ``limit`` queries, oldest first, saved after each change."""

    def __init__(
        self,
        store: DataStore,
        limit: int = 100,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.store = store
        self.limit = limit
        self._clock = clock
        self.queries: list[WeatherQuery] = store.load_history(now=clock())[-limit:]

    def __len__(self) -> int:
        return len(self.queries)

    def add_query(
        self,
        location: Location,
        weather_data: WeatherData | None = None,
        query_type: str = "current",
    ) -> WeatherQuery:
        """Record a query and save the history. Raises :class:`StorageError`."""
        query = WeatherQuery(location, self._clock(), weather_data, query_type)
        self.queries.append(query)
        del self.queries[: -self.limit]
        self.store.save_history(self.queries)
        return query

    def set_limit(self, limit: int) -> None:
        self.limit = limit
        if len(self.queries) > limit:
            del self.queries[:-limit]
            self.store.save_history(self.queries)

    def get_recent_queries(self, limit: int | None = None) -> list[WeatherQuery]:
        """The most recent queries, newest first."""
        newest_first = self.queries[::-1]
        return newest_first if limit is None else newest_first[:limit]

    def search_queries(self, term: str, limit: int | None = None) -> list[WeatherQuery]:
        """Queries whose city, region or country contains ``term``, newest first."""
        needle = term.strip().casefold()
        matches = [
            q
            for q in self.get_recent_queries()
            if needle in q.location.display_name.casefold()
            or needle == q.location.country.casefold()
        ]
        return matches if limit is None else matches[:limit]

    def observations_for(self, city: str, country: str | None = None) -> list[WeatherQuery]:
        """Current-weather queries for a place, oldest first, for trend reports."""
        return [
            q
            for q in self.queries
            if q.weather_data is not None
            and q.location.city.casefold() == city.casefold()
            and (not country or q.location.country.casefold() == country.casefold())
        ]

    def get_query_statistics(self) -> HistoryStatistics:
        if not self.queries:
            return HistoryStatistics()
        places = Counter(q.location.display_name for q in self.queries)
        return HistoryStatistics(
            total_queries=len(self.queries),
            first_query=min(q.query_time for q in self.queries),
            last_query=max(q.query_time for q in self.queries),
            top_locations=places.most_common(),
            query_types=dict(Counter(q.query_type for q in self.queries)),
            queries_by_day=dict(sorted(Counter(q.query_time.date() for q in self.queries).items())),
        )

    def clear_history(self) -> None:
        self.queries.clear()
        self.store.save_history(self.queries)

    def export_history(self, path: Path | str) -> Path:
        """Write the history and its statistics to a JSON file. Raises :class:`StorageError`."""
        target = Path(path)
        document = {
            "exported_at": self._clock().isoformat(timespec="seconds"),
            "statistics": self.get_query_statistics().to_dict(),
            "queries": [q.to_dict() for q in self.get_recent_queries()],
        }
        try:
            target.write_text(
                json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
        except OSError as exc:
            raise StorageError(f"Could not write {target}: {exc.strerror or exc}") from exc
        return target
