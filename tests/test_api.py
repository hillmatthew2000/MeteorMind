from datetime import datetime

import pytest
import requests

from meteormind.api import (
    APIError,
    AuthenticationError,
    LocationNotFoundError,
    MissingAPIKeyError,
    NetworkError,
    RateLimitError,
    ServiceError,
    WeatherAPIHandler,
    build_session,
    describe_error,
    parse_forecast,
)
from meteormind.config import ConfigManager
from meteormind.models import Location

from .conftest import (
    API_KEY,
    FORECAST_PATH,
    GEO_PATH,
    WEATHER_PATH,
    FakeTransport,
    load_fixture,
)


class TestConstruction:
    def test_missing_key_is_a_clear_error(self, tmp_path):
        config = ConfigManager(config_dir=tmp_path / "cfg", legacy_dirs=[])
        with pytest.raises(MissingAPIKeyError) as excinfo:
            WeatherAPIHandler(config=config)
        assert excinfo.value.suggestions

    def test_key_is_read_from_config(self, tmp_path):
        config = ConfigManager(config_dir=tmp_path / "cfg", legacy_dirs=[])
        config.save_api_key(API_KEY)
        assert WeatherAPIHandler(config=config).api_key == API_KEY

    def test_default_session_retries_transient_failures_but_not_rate_limits(self):
        adapter = build_session(retries=3).get_adapter("https://api.openweathermap.org")
        retry = adapter.max_retries  # type: ignore[attr-defined]
        assert retry.total == 3
        assert 503 in retry.status_forcelist
        assert 429 not in retry.status_forcelist


class TestGeocoding:
    def test_resolves_location(self, client, transport: FakeTransport):
        location = client.get_location_by_name("London", "GB")
        assert (location.city, location.country, location.state) == ("London", "GB", "England")
        assert location.latitude == pytest.approx(51.507, abs=1e-3)
        query = transport.calls(GEO_PATH)[0]
        assert query["q"] == ["London,GB"]
        assert query["appid"] == [API_KEY]

    def test_empty_result_raises_not_found(self, client, transport: FakeTransport):
        transport.add(GEO_PATH, (200, []))
        with pytest.raises(LocationNotFoundError, match="Atlantis"):
            client.get_location_by_name("Atlantis")

    def test_auth_errors_are_not_reported_as_not_found(self, client, transport: FakeTransport):
        # Previously every geocoding error was swallowed and shown as "not found".
        transport.add(GEO_PATH, (401, {"cod": 401, "message": "Invalid API key"}))
        with pytest.raises(AuthenticationError):
            client.get_location_by_name("London")

    def test_malformed_response(self, client, transport: FakeTransport):
        transport.add(GEO_PATH, (200, {"unexpected": True}))
        with pytest.raises(ServiceError):
            client.search_locations("London")


class TestCurrentWeather:
    def test_parses_response(self, client):
        weather, location = client.get_current_weather_by_name("London")
        # The name comes from geocoding, not the nearest station ("Clerkenwell").
        assert (weather.city, weather.country) == ("London", "GB")
        assert weather.temperature == pytest.approx(11.62)
        assert weather.humidity == 81
        assert weather.wind_direction == 240
        assert weather.description == "Light rain"
        assert weather.icon == "10d"
        assert weather.visibility == 10000
        assert weather.timestamp == datetime.fromtimestamp(1763900400)
        assert location.city == "London"

    def test_requests_metric_units_by_coordinates(self, client, transport: FakeTransport):
        client.get_current_weather(Location("London", "GB", 51.5, -0.12))
        query = transport.calls(WEATHER_PATH)[0]
        assert query["units"] == ["metric"]
        assert query["lat"] == ["51.5"]

    def test_responses_are_cached(self, client, transport: FakeTransport):
        location = Location("London", "GB", 51.5, -0.12)
        first = client.get_current_weather(location)
        second = client.get_current_weather(location)
        assert first == second
        assert len(transport.calls(WEATHER_PATH)) == 1

    def test_api_key_is_not_part_of_the_cache_key(self, client):
        client.get_current_weather(Location("London", "GB", 51.5, -0.12))
        assert all(API_KEY not in key for key in client.cache._entries)

    def test_missing_fields_raise_service_error(self, client, transport: FakeTransport):
        transport.add(WEATHER_PATH, (200, {"weather": []}))
        with pytest.raises(ServiceError):
            client.get_current_weather(Location("London", "GB", 51.5, -0.12))


class TestErrors:
    @pytest.mark.parametrize(
        ("status", "error_type"),
        [
            (401, AuthenticationError),
            (404, LocationNotFoundError),
            (429, RateLimitError),
            (500, ServiceError),
            (503, ServiceError),
            (400, APIError),
        ],
    )
    def test_http_status_mapping(self, client, transport, status, error_type):
        transport.add(WEATHER_PATH, (status, {"cod": status, "message": "boom"}))
        with pytest.raises(error_type) as excinfo:
            client.get_current_weather(Location("London", "GB", 51.5, -0.12))
        message, suggestions = describe_error(excinfo.value)
        assert message and suggestions

    @pytest.mark.parametrize(
        "exception",
        [requests.exceptions.ConnectTimeout(), requests.exceptions.ConnectionError()],
    )
    def test_network_failures(self, client, transport, exception):
        transport.add(WEATHER_PATH, exception)
        with pytest.raises(NetworkError):
            client.get_current_weather(Location("London", "GB", 51.5, -0.12))

    def test_invalid_json(self, client, transport):
        transport.add(WEATHER_PATH, (200, b"<html>gateway</html>"))
        with pytest.raises(ServiceError):
            client.get_current_weather(Location("London", "GB", 51.5, -0.12))

    def test_errors_are_not_cached(self, client, transport):
        location = Location("London", "GB", 51.5, -0.12)
        transport.add(WEATHER_PATH, (503, {}))
        with pytest.raises(ServiceError):
            client.get_current_weather(location)
        transport.add(WEATHER_PATH, (200, load_fixture("weather_london.json")))
        assert client.get_current_weather(location).temperature == pytest.approx(11.62)

    def test_validate_api_key(self, client, transport):
        assert client.validate_api_key()
        transport.add(GEO_PATH, (401, {}))
        assert not client.validate_api_key()
        transport.add(GEO_PATH, (503, {}))
        with pytest.raises(ServiceError):
            client.validate_api_key()


class TestForecast:
    def test_groups_into_days(self, client):
        forecast, location = client.get_forecast_by_name("London", days=5)
        assert location.city == "London"
        assert len(forecast) == 5
        assert [f.date.day for f in forecast] == [23, 24, 25, 26, 27]
        first = forecast[0]
        assert first.temperature_min == pytest.approx(5.0)
        assert first.temperature_max == pytest.approx(10.0)
        assert first.description == "Light rain"
        assert first.icon == "10d"
        assert first.precipitation_chance == 40
        assert 0 <= first.humidity <= 100

    def test_limits_days(self, client):
        assert len(client.get_forecast(Location("London", "GB", 51.5, -0.1), days=2)) == 2
        with pytest.raises(ValueError):
            client.get_forecast(Location("London", "GB", 51.5, -0.1), days=6)

    def test_days_follow_the_locations_timezone(self):
        # 15:00 UTC on 23 Nov is already 24 Nov in Tokyo (UTC+9).
        def item(ts: int, temp: float) -> dict:
            return {
                "dt": ts,
                "main": {"temp": temp, "humidity": 50},
                "weather": [{"description": "clear sky", "icon": "01d"}],
            }

        data = {
            "list": [item(1763906400, 10.0), item(1763910000, 20.0)],  # 14:00 and 15:00 UTC
            "city": {"timezone": 9 * 3600},
        }
        days = parse_forecast(data)
        assert [d.date.day for d in days] == [23, 24]
        assert [d.temperature_max for d in days] == [10.0, 20.0]

    def test_malformed_forecast(self):
        with pytest.raises(ServiceError):
            parse_forecast({"list": [{"dt": 1}]})

    def test_forecast_path_is_used(self, client, transport):
        client.get_forecast(Location("London", "GB", 51.5, -0.1))
        assert transport.calls(FORECAST_PATH)
