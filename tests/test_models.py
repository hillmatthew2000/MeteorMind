from datetime import datetime

import pytest

from meteormind.models import (
    FavoriteLocationsLinkedList,
    ForecastData,
    Location,
    WeatherData,
    WeatherQuery,
)


def make_location(city: str, country: str = "GB") -> Location:
    return Location(city, country, 51.5, -0.1, added_date=datetime(2025, 1, 1, 12, 0))


def make_weather(**overrides: object) -> WeatherData:
    fields: dict[str, object] = {
        "city": "London",
        "country": "GB",
        "temperature": 15.5,
        "feels_like": 14.2,
        "humidity": 72,
        "pressure": 1013,
        "wind_speed": 4.1,
        "wind_direction": 230,
        "description": "Light rain",
        "timestamp": datetime(2025, 1, 1, 12, 0),
        "icon": "10d",
        "visibility": 9000,
    }
    fields.update(overrides)
    return WeatherData(**fields)  # type: ignore[arg-type]


class TestLocation:
    def test_round_trip(self) -> None:
        location = Location("Portland", "US", 45.5, -122.6, datetime(2025, 3, 1), state="Oregon")
        assert Location.from_dict(location.to_dict()) == location

    def test_from_dict_tolerates_missing_optional_fields(self) -> None:
        location = Location.from_dict(
            {"city": "Oslo", "country": "NO", "latitude": 59.9, "longitude": 10.7}
        )
        assert location.state == ""
        assert isinstance(location.added_date, datetime)

    def test_matches_ignores_case(self) -> None:
        assert make_location("London").matches("LONDON", "gb")

    def test_display_name_includes_state_when_known(self) -> None:
        assert Location("Portland", "US", 0, 0, state="Maine").display_name == "Portland, Maine, US"
        assert make_location("London").display_name == "London, GB"
        assert str(make_location("London")) == "London, GB"


class TestWeatherData:
    def test_round_trip(self) -> None:
        weather = make_weather(temp_min=12.0, temp_max=17.0)
        assert WeatherData.from_dict(weather.to_dict()) == weather

    def test_loads_records_written_before_optional_fields_existed(self) -> None:
        legacy = {
            "city": "London",
            "country": "GB",
            "temperature": 15.5,
            "feels_like": 14.2,
            "humidity": 72,
            "pressure": 1013,
            "wind_speed": 4.1,
            "wind_direction": 230,
            "description": "Light rain",
            "timestamp": "2025-01-01T12:00:00",
        }
        weather = WeatherData.from_dict(legacy)
        assert weather.icon == ""
        assert weather.visibility is None


def test_forecast_round_trip() -> None:
    forecast = ForecastData(datetime(2025, 1, 2), 3.0, 9.5, 80, 5.5, "Rain", 70, "10d")
    assert ForecastData.from_dict(forecast.to_dict()) == forecast


def test_query_round_trip_with_and_without_weather() -> None:
    location = make_location("London")
    with_weather = WeatherQuery(location, datetime(2025, 1, 1, 9, 0), make_weather())
    forecast_only = WeatherQuery(location, datetime(2025, 1, 1, 9, 5), None, "forecast")
    assert WeatherQuery.from_dict(with_weather.to_dict()) == with_weather
    assert WeatherQuery.from_dict(forecast_only.to_dict()) == forecast_only


class TestFavoritesList:
    @pytest.fixture
    def favorites(self) -> FavoriteLocationsLinkedList:
        favorites = FavoriteLocationsLinkedList()
        for city in ("Paris", "Tokyo", "London"):
            favorites.add_location(make_location(city))
        return favorites

    @staticmethod
    def cities(favorites: FavoriteLocationsLinkedList) -> list[str]:
        return [location.city for location in favorites]

    def test_new_locations_go_to_the_front(self, favorites: FavoriteLocationsLinkedList) -> None:
        assert self.cities(favorites) == ["London", "Tokyo", "Paris"]
        assert len(favorites) == favorites.get_size() == 3

    def test_duplicates_are_rejected_case_insensitively(
        self, favorites: FavoriteLocationsLinkedList
    ) -> None:
        assert not favorites.add_location(make_location("london", "gb"))
        assert len(favorites) == 3

    @pytest.mark.parametrize("city", ["London", "Tokyo", "Paris"])
    def test_remove_head_middle_and_tail(
        self, favorites: FavoriteLocationsLinkedList, city: str
    ) -> None:
        assert favorites.remove_location(city, "GB")
        assert city not in self.cities(favorites)
        assert len(favorites) == 2

    def test_remove_missing_returns_false(self, favorites: FavoriteLocationsLinkedList) -> None:
        assert not favorites.remove_location("Berlin", "DE")
        assert not FavoriteLocationsLinkedList().remove_location("Berlin", "DE")

    def test_move_to_front(self, favorites: FavoriteLocationsLinkedList) -> None:
        assert favorites.move_to_front("Paris", "gb")
        assert self.cities(favorites) == ["Paris", "London", "Tokyo"]
        assert favorites.move_to_front("Paris", "GB")  # already first
        assert self.cities(favorites) == ["Paris", "London", "Tokyo"]
        assert len(favorites) == 3
        assert not favorites.move_to_front("Berlin", "DE")

    def test_contains_and_find(self, favorites: FavoriteLocationsLinkedList) -> None:
        assert make_location("TOKYO") in favorites
        assert "Tokyo" not in favorites  # only Location objects are members
        found = favorites.find_location("tokyo", "GB")
        assert found is not None and found.city == "Tokyo"
        assert favorites.find_location("Berlin", "DE") is None

    def test_serialisation_preserves_order(self, favorites: FavoriteLocationsLinkedList) -> None:
        restored = FavoriteLocationsLinkedList.from_dict_list(favorites.to_dict_list())
        assert self.cities(restored) == self.cities(favorites)
        assert restored.get_all_locations() == favorites.get_all_locations()

    def test_empty_list(self) -> None:
        favorites = FavoriteLocationsLinkedList()
        assert favorites.is_empty()
        assert list(favorites) == []
        assert len(favorites) == 0
