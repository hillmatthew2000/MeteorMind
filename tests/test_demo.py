from datetime import date

import pytest

from meteormind.api import LocationNotFoundError
from meteormind.demo import DemoWeatherClient


@pytest.fixture
def demo() -> DemoWeatherClient:
    return DemoWeatherClient(today=date(2025, 7, 1))


def test_known_city_has_real_coordinates(demo: DemoWeatherClient) -> None:
    location = demo.get_location_by_name("london")
    assert (location.city, location.country) == ("London", "GB")
    assert location.latitude == pytest.approx(51.5, abs=0.1)


def test_country_filter(demo: DemoWeatherClient) -> None:
    with pytest.raises(LocationNotFoundError):
        demo.get_location_by_name("London", "FR")


def test_any_city_name_works_and_is_deterministic(demo: DemoWeatherClient) -> None:
    first, location = demo.get_current_weather_by_name("Springfield", "us")
    second, _ = demo.get_current_weather_by_name("Springfield", "US")
    assert first == second
    assert location.country == "US"
    assert -90 <= location.latitude <= 90


def test_plausible_values(demo: DemoWeatherClient) -> None:
    for city in ("Reykjavik", "Singapore", "Sydney", "Cairo"):
        weather, _ = demo.get_current_weather_by_name(city)
        assert -40 < weather.temperature < 50
        assert 0 <= weather.humidity <= 100
        assert 0 <= weather.wind_direction < 360
        assert weather.description and weather.icon


def test_forecast(demo: DemoWeatherClient) -> None:
    days, _ = demo.get_forecast_by_name("Paris", days=5)
    assert [d.date.date() for d in days] == [date(2025, 7, d) for d in range(1, 6)]
    assert all(d.temperature_min < d.temperature_max for d in days)
    assert all(0 <= d.precipitation_chance <= 100 for d in days)
    with pytest.raises(ValueError):
        demo.get_forecast_by_name("Paris", days=0)
