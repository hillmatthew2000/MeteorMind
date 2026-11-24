"""The application logic shared by the command line and the desktop interface.

:class:`WeatherService` ties together the weather provider (OpenWeatherMap or
the offline demo), the user's favorites, query history and preferences. The
interfaces only deal with input and presentation.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from .api import (
    MAX_FORECAST_DAYS,
    APIError,
    LocationNotFoundError,
    MissingAPIKeyError,
    WeatherAPIHandler,
    WeatherProvider,
)
from .cache import ResponseCache
from .config import ConfigManager
from .demo import DemoWeatherClient
from .history import HistoryManager
from .models import FavoriteLocationsLinkedList, ForecastData, Location, WeatherData
from .preferences import Preferences
from .reporting import WeatherReport, WeatherReportGenerator
from .storage import DataStore, StorageError, migrate_legacy_data
from .units import UnitPreferences, WeatherFormatter
from .validation import InputValidator

logger = logging.getLogger(__name__)


REPORT_KINDS = {
    "compare": "current weather side by side (the places given, or all favorites)",
    "forecast": "a detailed forecast for one place",
    "forecast-compare": "daily forecasts side by side (the places given, or all favorites)",
    "locations": "which places you look up most",
    "trends": "temperature changes for one place, from your history",
    "history": "your recent queries",
}


class InputError(ValueError):
    """Raised for input the user can correct; ``str(error)`` is user-facing."""

    def __init__(self, message: str, suggestions: list[str] | None = None) -> None:
        super().__init__(message)
        self.suggestions = suggestions or []


@dataclass(frozen=True)
class FetchResult:
    """The outcome of fetching weather for one place in a batch."""

    location: Location
    weather: WeatherData | None = None
    forecast: list[ForecastData] | None = None
    error: APIError | None = None


def parse_place(query: str) -> tuple[str, str | None]:
    """Split ``"City"`` or ``"City, CC"`` into a validated name and country code."""
    result = InputValidator.parse_location_query(query)
    if not result.is_valid:
        raise InputError(result.error_message, result.suggestions)
    city, country = result.value
    return city, country


def parse_place_loosely(query: str) -> tuple[str, str | None]:
    """Split ``"City, CC"`` without validating, for matching against history."""
    city, _, country = query.rpartition(",")
    if city and len(country.strip()) == 2:
        return city.strip(), country.strip()
    return query.strip(), None


def _unique_places(locations: Iterable[Location]) -> list[Location]:
    """Drop repeated geocoding results for the same named place."""
    seen: set[str] = set()
    unique = []
    for location in locations:
        key = location.display_name.casefold()
        if key not in seen:
            seen.add(key)
            unique.append(location)
    return unique


class WeatherService:
    """Weather lookups plus the user's favorites, history and preferences."""

    def __init__(
        self,
        store: DataStore,
        provider: WeatherProvider | None,
        config: ConfigManager | None = None,
        cache: ResponseCache | None = None,
    ) -> None:
        self.store = store
        self.config = config or ConfigManager(store.directory)
        self.cache = cache
        self._provider = provider
        self.preferences = store.load_preferences()
        self.favorites: FavoriteLocationsLinkedList = store.load_favorite_locations()
        self.history = HistoryManager(store, self.preferences.history_limit)

    @classmethod
    def create(
        cls,
        *,
        demo: bool = False,
        data_dir: Path | None = None,
        legacy_dir: Path | None = None,
    ) -> WeatherService:
        """Open the user's data (migrating an old ``./data`` folder) and pick a provider.

        Without an API key the service is still usable for favorites,
        history and settings; weather lookups raise :class:`MissingAPIKeyError`.
        """
        store = DataStore(data_dir)
        migrate_legacy_data(legacy_dir or Path.cwd() / "data", store.directory)
        config = ConfigManager(store.directory)
        service = cls(store, None, config)
        if demo:
            service._provider = DemoWeatherClient()
        else:
            service.cache = ResponseCache(
                store.cache_file, ttl_seconds=service.preferences.cache_seconds
            )
            service.connect()
        return service

    # Provider ------------------------------------------------------------------

    @property
    def is_demo(self) -> bool:
        return isinstance(self._provider, DemoWeatherClient)

    @property
    def has_provider(self) -> bool:
        return self._provider is not None

    @property
    def provider(self) -> WeatherProvider:
        if self._provider is None:
            raise MissingAPIKeyError("No OpenWeatherMap API key is configured.")
        return self._provider

    def connect(self) -> bool:
        """(Re)create the OpenWeatherMap client from the configured key."""
        if self.is_demo:
            return True
        try:
            self._provider = WeatherAPIHandler(cache=self.cache, config=self.config)
        except MissingAPIKeyError:
            self._provider = None
            return False
        return True

    def set_api_key(self, key: str) -> Path:
        """Save an API key (raises :class:`ConfigError`) and reconnect."""
        path = self.config.save_api_key(key)
        self.connect()
        return path

    def clear_api_key(self) -> bool:
        removed = self.config.clear_api_key()
        self.connect()
        return removed

    def test_connection(self) -> bool:
        """True when the provider accepts the key; raises :class:`APIError` otherwise."""
        provider = self.provider
        if isinstance(provider, WeatherAPIHandler):
            return provider.validate_api_key()
        return True

    # Lookups -------------------------------------------------------------------

    def search(self, query: str, limit: int = 5) -> list[Location]:
        """Places matching ``"City"`` or ``"City, CC"``, best match first."""
        city, country = parse_place(query)
        return _unique_places(self.provider.search_locations(city, country, limit))

    def locate(self, query: str) -> Location:
        """The best match for ``query``; raises :class:`LocationNotFoundError`.

        Asks for the same results as :meth:`search`, so the cached geocoding
        response is shared with it.
        """
        matches = self.search(query)
        if not matches:
            raise LocationNotFoundError(f"No place called '{query.strip()}' was found.")
        return matches[0]

    def current_weather(self, location: Location) -> WeatherData:
        weather = self.provider.get_current_weather(location)
        self._record(location, weather, "current")
        return weather

    def forecast(self, location: Location, days: int = MAX_FORECAST_DAYS) -> list[ForecastData]:
        if not 1 <= days <= MAX_FORECAST_DAYS:
            raise InputError(f"Choose between 1 and {MAX_FORECAST_DAYS} forecast days.")
        forecast = self.provider.get_forecast(location, days)
        self._record(location, None, "forecast")
        return forecast

    def current_weather_for_many(self, locations: Iterable[Location]) -> list[FetchResult]:
        """Current weather for several places; failures are returned, not raised."""
        results = []
        for location in list(locations):
            try:
                results.append(FetchResult(location, weather=self.current_weather(location)))
            except APIError as exc:
                if isinstance(exc, MissingAPIKeyError):
                    raise
                results.append(FetchResult(location, error=exc))
        return results

    def forecast_for_many(
        self, locations: Iterable[Location], days: int = MAX_FORECAST_DAYS
    ) -> list[FetchResult]:
        results = []
        for location in list(locations):
            try:
                results.append(FetchResult(location, forecast=self.forecast(location, days)))
            except APIError as exc:
                if isinstance(exc, MissingAPIKeyError):
                    raise
                results.append(FetchResult(location, error=exc))
        return results

    def _record(self, location: Location, weather: WeatherData | None, kind: str) -> None:
        """Add a query to the history; a full disk should not hide the weather."""
        try:
            self.history.add_query(location, weather, kind)
        except StorageError as exc:
            logger.warning("Could not save the query history: %s", exc)

    # Favorites -----------------------------------------------------------------

    def add_favorite(self, location: Location) -> bool:
        """Add a place; False if it is already a favorite. Raises :class:`StorageError`."""
        if not self.favorites.add_location(location):
            return False
        self.store.save_favorite_locations(self.favorites)
        return True

    def remove_favorite(self, location: Location) -> bool:
        if not self.favorites.remove_location(location.city, location.country):
            return False
        self.store.save_favorite_locations(self.favorites)
        return True

    def move_favorite_to_top(self, location: Location) -> bool:
        if not self.favorites.move_to_front(location.city, location.country):
            return False
        self.store.save_favorite_locations(self.favorites)
        return True

    def find_favorite(self, query: str) -> Location | None:
        """A favorite matching ``"City"`` or ``"City, CC"`` (case-insensitive)."""
        city, country = parse_place(query)
        for location in self.favorites:
            if location.city.casefold() == city.casefold() and (
                country is None or location.country.casefold() == country.casefold()
            ):
                return location
        return None

    def touch_favorite(self, location: Location) -> None:
        """Mark a favorite as just used (favorites are kept most recently used first)."""
        if self.favorites.move_to_front(location.city, location.country):
            try:
                self.store.save_favorite_locations(self.favorites)
            except StorageError as exc:
                logger.warning("Could not save favorites: %s", exc)

    # Preferences ---------------------------------------------------------------

    @property
    def formatter(self) -> WeatherFormatter:
        return WeatherFormatter(self.preferences.units)

    @property
    def reports(self) -> WeatherReportGenerator:
        return WeatherReportGenerator(self.formatter)

    def update_preferences(self, preferences: Preferences) -> None:
        """Save new preferences and apply them. Raises :class:`StorageError`."""
        self.store.save_preferences(preferences)
        self.preferences = preferences
        self.history.set_limit(preferences.history_limit)
        if self.cache is not None:
            self.cache.ttl_seconds = preferences.cache_seconds

    def set_units(self, units: UnitPreferences) -> None:
        self.update_preferences(replace(self.preferences, units=units))

    # Reports -------------------------------------------------------------------

    def build_report(
        self, kind: str, places: Sequence[str] = (), days: int = MAX_FORECAST_DAYS
    ) -> tuple[WeatherReport, list[str]]:
        """Build one of :data:`REPORT_KINDS`; returns it with warnings about places that failed."""
        generator = self.reports

        def targets() -> list[Location]:
            if places:
                return [self.locate(place) for place in places]
            if not self.favorites:
                raise InputError("Name some places, or add favorites to compare.")
            return list(self.favorites)

        def one_place() -> str:
            if len(places) != 1:
                raise InputError(f"The {kind} report needs exactly one place.")
            return places[0]

        if kind == "compare":
            results = self.current_weather_for_many(targets())
            report = generator.generate_current_weather_report(
                [(r.location, r.weather) for r in results if r.weather]
            )
        elif kind == "forecast-compare":
            results = self.forecast_for_many(targets(), days)
            report = generator.generate_forecast_comparison_report(
                [(r.location, r.forecast) for r in results if r.forecast]
            )
        elif kind == "forecast":
            location = self.locate(one_place())
            forecast = self.forecast(location, days)
            return generator.generate_detailed_forecast_report(location, forecast), []
        elif kind == "trends":
            city, country = parse_place_loosely(one_place())
            observations = self.history.observations_for(city, country)
            if len(observations) < 2:
                raise InputError(
                    f"Trends need at least two current-weather lookups for {city}.",
                    ["Look up its current weather a few times first."],
                )
            samples = [(q.query_time, q.weather_data) for q in observations if q.weather_data]
            return generator.generate_temperature_trend_report(
                observations[-1].location, samples
            ), []
        elif kind == "locations":
            queries = self.history.get_recent_queries()
            return generator.generate_location_statistics_report(queries), []
        else:
            queries = self.history.get_recent_queries()
            return generator.generate_query_history_report(queries), []
        return report, [f"{r.location.display_name}: {r.error}" for r in results if r.error]

    # Maintenance ---------------------------------------------------------------

    def clear_cache(self) -> None:
        if self.cache is not None:
            self.cache.clear()

    def cached_responses(self) -> int:
        return len(self.cache) if self.cache is not None else 0

    def backup(self) -> Path:
        return self.store.backup()

    def clear_all_data(self) -> None:
        """Delete favorites, history, preferences and cached responses."""
        self.store.clear_all()
        if self.cache is not None:
            self.cache.clear()
        self.preferences = Preferences()
        self.favorites = FavoriteLocationsLinkedList()
        self.history = HistoryManager(self.store, self.preferences.history_limit)
