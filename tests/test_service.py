from datetime import date
from pathlib import Path

import pytest

from meteormind.api import (
    LocationNotFoundError,
    MissingAPIKeyError,
    NetworkError,
    WeatherAPIHandler,
)
from meteormind.cache import ResponseCache
from meteormind.demo import DemoWeatherClient
from meteormind.models import ForecastData, Location, WeatherData
from meteormind.preferences import Preferences
from meteormind.service import InputError, WeatherService, parse_place
from meteormind.storage import DataStore, StorageError
from meteormind.units import WindSpeedUnit, create_imperial_preferences

from .conftest import API_KEY


class FlakyProvider(DemoWeatherClient):
    """Demo data, except that some places fail and searches can be ambiguous."""

    def __init__(self) -> None:
        super().__init__(today=date(2025, 7, 1))
        self.failing: set[str] = set()

    def search_locations(
        self, city_name: str, country_code: str | None = None, limit: int = 5
    ) -> list[Location]:
        if city_name == "Springfield":
            places = [
                Location("Springfield", "US", 39.8, -89.6, state="Illinois"),
                Location("Springfield", "US", 39.8, -89.6, state="Illinois"),
                Location("Springfield", "US", 37.2, -93.3, state="Missouri"),
            ]
            return places[:limit]
        return super().search_locations(city_name, country_code, limit)

    def get_current_weather(self, location: Location) -> WeatherData:
        if location.city in self.failing:
            raise NetworkError("offline")
        return super().get_current_weather(location)

    def get_forecast(self, location: Location, days: int = 5) -> list[ForecastData]:
        if location.city in self.failing:
            raise NetworkError("offline")
        return super().get_forecast(location, days)


@pytest.fixture
def provider() -> FlakyProvider:
    return FlakyProvider()


@pytest.fixture
def service(tmp_path: Path, provider: FlakyProvider) -> WeatherService:
    return WeatherService(DataStore(tmp_path / "data"), provider)


class TestParsePlace:
    def test_city_and_country(self) -> None:
        assert parse_place(" paris ,  fr ") == ("paris", "FR")
        assert parse_place("New York") == ("New York", None)

    def test_invalid(self) -> None:
        with pytest.raises(InputError) as info:
            parse_place("12345")
        assert info.value.suggestions


class TestLookups:
    def test_search_removes_duplicates(self, service: WeatherService) -> None:
        names = [loc.display_name for loc in service.search("Springfield")]
        assert names == ["Springfield, Illinois, US", "Springfield, Missouri, US"]

    def test_locate(self, service: WeatherService) -> None:
        assert service.locate("london, gb").country == "GB"
        with pytest.raises(LocationNotFoundError):
            service.locate("London, FR")

    def test_lookups_are_recorded(self, service: WeatherService) -> None:
        london = service.locate("London")
        service.current_weather(london)
        service.forecast(london, 2)
        kinds = [q.query_type for q in service.history.get_recent_queries()]
        assert kinds == ["forecast", "current"]
        assert service.store.load_history()[0].weather_data is not None

    def test_forecast_days_checked(self, service: WeatherService) -> None:
        with pytest.raises(InputError):
            service.forecast(service.locate("London"), 6)

    def test_history_write_failure_does_not_hide_weather(
        self, service: WeatherService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail(*args: object) -> None:
            raise StorageError("disk full")

        monkeypatch.setattr(service.store, "save_history", fail)
        assert service.current_weather(service.locate("London")).city == "London"

    def test_batch_collects_failures(
        self, service: WeatherService, provider: FlakyProvider
    ) -> None:
        provider.failing.add("Paris")
        places = [service.locate("London"), service.locate("Paris")]
        results = service.current_weather_for_many(places)
        assert results[0].weather is not None and results[0].error is None
        assert isinstance(results[1].error, NetworkError)
        forecasts = service.forecast_for_many(places, 3)
        assert forecasts[0].forecast is not None and len(forecasts[0].forecast) == 3
        assert forecasts[1].error is not None

    def test_no_provider(self, tmp_path: Path) -> None:
        service = WeatherService(DataStore(tmp_path), None)
        assert not service.has_provider
        with pytest.raises(MissingAPIKeyError):
            service.locate("London")
        with pytest.raises(MissingAPIKeyError):
            service.current_weather_for_many(list(service.favorites))


class TestFavorites:
    def test_add_remove_and_reorder(self, service: WeatherService) -> None:
        service.clear_all_data()
        york = service.locate("York")
        bath = service.locate("Bath")
        assert service.add_favorite(york) and service.add_favorite(bath)
        assert not service.add_favorite(service.locate("york"))
        assert [loc.city for loc in service.favorites] == ["Bath", "York"]
        assert service.move_favorite_to_top(york)
        service.touch_favorite(bath)
        assert [loc.city for loc in service.store.load_favorite_locations()] == ["Bath", "York"]
        assert service.remove_favorite(york)
        assert not service.remove_favorite(york)
        assert [loc.city for loc in service.store.load_favorite_locations()] == ["Bath"]

    def test_find_favorite(self, service: WeatherService) -> None:
        found = service.find_favorite("new york")
        assert found is not None and found.country == "US"
        assert service.find_favorite("New York, GB") is None
        assert service.find_favorite("Atlantis") is None

    def test_comparing_favorites_keeps_their_order(self, service: WeatherService) -> None:
        before = [loc.city for loc in service.favorites]
        service.current_weather_for_many(service.favorites)
        assert [loc.city for loc in service.favorites] == before


class TestPreferences:
    def test_update_applies_and_saves(self, tmp_path: Path, provider: FlakyProvider) -> None:
        cache = ResponseCache(ttl_seconds=600)
        service = WeatherService(DataStore(tmp_path), provider, cache=cache)
        prefs = Preferences(create_imperial_preferences(), "dark", 10, 2)
        service.update_preferences(prefs)
        assert service.store.load_preferences() == prefs
        assert service.history.limit == 10
        assert cache.ttl_seconds == 120
        assert service.formatter.format_temperature(0) == "32.0°F"

    def test_set_units(self, service: WeatherService) -> None:
        units = create_imperial_preferences()
        units.wind_speed = WindSpeedUnit.KNOTS
        service.set_units(units)
        assert service.store.load_preferences().units.wind_speed is WindSpeedUnit.KNOTS


class TestCreate:
    def test_demo(self, tmp_path: Path) -> None:
        service = WeatherService.create(demo=True, data_dir=tmp_path)
        assert service.is_demo and service.has_provider
        assert service.test_connection()

    def test_without_key_then_set_key(self, tmp_path: Path) -> None:
        service = WeatherService.create(data_dir=tmp_path, legacy_dir=tmp_path / "none")
        assert not service.has_provider and not service.is_demo
        assert service.set_api_key(API_KEY) == tmp_path / "config.json"
        assert isinstance(service.provider, WeatherAPIHandler)
        assert service.provider.cache is service.cache
        assert service.cache is not None and service.cache.path == tmp_path / "cache.json"
        assert service.clear_api_key()
        assert not service.has_provider

    def test_migrates_legacy_folder(self, tmp_path: Path) -> None:
        legacy = tmp_path / "data"
        legacy.mkdir()
        (legacy / "user_preferences.json").write_text(
            '{"preferences": {"units": "imperial"}}', encoding="utf-8"
        )
        service = WeatherService.create(demo=True, data_dir=tmp_path / "app", legacy_dir=legacy)
        assert service.preferences.units == create_imperial_preferences()


class TestReports:
    def test_compare_favorites_with_a_failure(
        self, service: WeatherService, provider: FlakyProvider
    ) -> None:
        provider.failing.add("Tokyo")
        report, warnings = service.build_report("compare")
        assert len(report.rows) == len(service.favorites) - 1
        assert warnings == ["Tokyo, JP: offline"]

    def test_compare_needs_places_or_favorites(self, service: WeatherService) -> None:
        service.clear_all_data()
        with pytest.raises(InputError):
            service.build_report("compare")
        report, _ = service.build_report("forecast-compare", ["Paris", "Cairo"], days=3)
        assert len(report.rows) == 2

    def test_single_place_reports(self, service: WeatherService) -> None:
        with pytest.raises(InputError):
            service.build_report("forecast", ["Paris", "Rome"])
        report, _ = service.build_report("forecast", ["Paris"], days=2)
        assert len(report.rows) == 2

    def test_trends_need_history(self, service: WeatherService) -> None:
        with pytest.raises(InputError):
            service.build_report("trends", ["London"])
        london = service.locate("London")
        service.current_weather(london)
        service.current_weather(london)
        report, _ = service.build_report("trends", ["london, gb"])
        assert len(report.rows) == 2

    def test_history_reports(self, service: WeatherService) -> None:
        service.current_weather(service.locate("London"))
        locations, _ = service.build_report("locations")
        history, _ = service.build_report("history")
        assert len(locations.rows) == len(history.rows) == 1


class TestMaintenance:
    def test_clear_all_data(self, tmp_path: Path, provider: FlakyProvider) -> None:
        cache = ResponseCache(tmp_path / "cache.json")
        service = WeatherService(DataStore(tmp_path), provider, cache=cache)
        cache.set("k", 1)
        service.current_weather(service.locate("London"))
        service.update_preferences(Preferences(theme="dark"))
        service.clear_all_data()
        assert len(service.favorites) == 0
        assert len(service.history) == 0
        assert service.preferences == Preferences()
        assert service.cached_responses() == 0

    def test_backup(self, service: WeatherService) -> None:
        service.update_preferences(Preferences())
        assert (service.backup() / "preferences.json").exists()
