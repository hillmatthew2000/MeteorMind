"""Core data models: locations, weather observations, forecasts and favorites.

All models serialise to plain JSON-compatible dictionaries with ``to_dict``
and are rebuilt with ``from_dict``. Fields added after the first release are
optional in ``from_dict`` so files written by older versions still load.

Favorites are kept in a small singly linked list. The list is ordered by most
recent use: opening a favorite moves its node to the head, which is a constant
time relink once the node is found, and new favorites are pushed onto the head.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def _parse_datetime(value: Any) -> datetime:
    """Parse an ISO-8601 timestamp, falling back to "now" for missing values."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        return datetime.fromisoformat(value)
    return datetime.now()


@dataclass
class Location:
    """A named place with coordinates, as resolved by the geocoding API."""

    city: str
    country: str
    latitude: float
    longitude: float
    added_date: datetime = field(default_factory=datetime.now)
    state: str = ""

    @property
    def key(self) -> tuple[str, str]:
        """Case-insensitive identity used to detect duplicates."""
        return self.city.casefold(), self.country.casefold()

    def matches(self, city: str, country: str) -> bool:
        return self.key == (city.casefold(), country.casefold())

    @property
    def display_name(self) -> str:
        """``City, State, CC`` when a state/region is known, else ``City, CC``."""
        parts = [self.city, self.state, self.country]
        return ", ".join(part for part in parts if part)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "city": self.city,
            "country": self.country,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "added_date": self.added_date.isoformat(),
        }
        if self.state:
            data["state"] = self.state
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Location:
        return cls(
            city=data["city"],
            country=data["country"],
            latitude=float(data["latitude"]),
            longitude=float(data["longitude"]),
            added_date=_parse_datetime(data.get("added_date")),
            state=data.get("state", ""),
        )

    def __str__(self) -> str:
        return f"{self.city}, {self.country}"


@dataclass
class WeatherData:
    """Current conditions in canonical metric units (°C, m/s, hPa, metres)."""

    city: str
    country: str
    temperature: float
    feels_like: float
    humidity: int
    pressure: int
    wind_speed: float
    wind_direction: int
    description: str
    timestamp: datetime = field(default_factory=datetime.now)
    icon: str = ""
    visibility: int | None = None
    temp_min: float | None = None
    temp_max: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "city": self.city,
            "country": self.country,
            "temperature": self.temperature,
            "feels_like": self.feels_like,
            "humidity": self.humidity,
            "pressure": self.pressure,
            "wind_speed": self.wind_speed,
            "wind_direction": self.wind_direction,
            "description": self.description,
            "timestamp": self.timestamp.isoformat(),
            "icon": self.icon,
            "visibility": self.visibility,
            "temp_min": self.temp_min,
            "temp_max": self.temp_max,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WeatherData:
        return cls(
            city=data["city"],
            country=data["country"],
            temperature=float(data["temperature"]),
            feels_like=float(data["feels_like"]),
            humidity=int(data["humidity"]),
            pressure=int(data["pressure"]),
            wind_speed=float(data["wind_speed"]),
            wind_direction=int(data["wind_direction"]),
            description=data["description"],
            timestamp=_parse_datetime(data.get("timestamp")),
            icon=data.get("icon", ""),
            visibility=data.get("visibility"),
            temp_min=data.get("temp_min"),
            temp_max=data.get("temp_max"),
        )


@dataclass
class ForecastData:
    """A one-day forecast summary in canonical metric units."""

    date: datetime
    temperature_min: float
    temperature_max: float
    humidity: int
    wind_speed: float
    description: str
    precipitation_chance: int = 0
    icon: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date.isoformat(),
            "temperature_min": self.temperature_min,
            "temperature_max": self.temperature_max,
            "humidity": self.humidity,
            "wind_speed": self.wind_speed,
            "description": self.description,
            "precipitation_chance": self.precipitation_chance,
            "icon": self.icon,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ForecastData:
        return cls(
            date=datetime.fromisoformat(data["date"]),
            temperature_min=float(data["temperature_min"]),
            temperature_max=float(data["temperature_max"]),
            humidity=int(data["humidity"]),
            wind_speed=float(data["wind_speed"]),
            description=data["description"],
            precipitation_chance=int(data.get("precipitation_chance", 0)),
            icon=data.get("icon", ""),
        )


@dataclass
class WeatherQuery:
    """One entry in the query history."""

    location: Location
    query_time: datetime
    weather_data: WeatherData | None = None
    query_type: str = "current"  # "current" or "forecast"

    def to_dict(self) -> dict[str, Any]:
        return {
            "location": self.location.to_dict(),
            "query_time": self.query_time.isoformat(),
            "weather_data": self.weather_data.to_dict() if self.weather_data else None,
            "query_type": self.query_type,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WeatherQuery:
        weather = data.get("weather_data")
        return cls(
            location=Location.from_dict(data["location"]),
            query_time=datetime.fromisoformat(data["query_time"]),
            weather_data=WeatherData.from_dict(weather) if weather else None,
            query_type=data.get("query_type", "current"),
        )


class LocationNode:
    """A node in :class:`FavoriteLocationsLinkedList`."""

    __slots__ = ("location", "next")

    def __init__(self, location: Location) -> None:
        self.location = location
        self.next: LocationNode | None = None


class FavoriteLocationsLinkedList:
    """Favorite locations as a singly linked list, most recently used first.

    The container supports ``len()``, iteration and ``in`` (by location
    identity), alongside the explicit methods used by the interfaces.
    """

    def __init__(self, locations: list[Location] | None = None) -> None:
        self.head: LocationNode | None = None
        self.size = 0
        for location in reversed(locations or []):
            self.add_location(location)

    def __len__(self) -> int:
        return self.size

    def __iter__(self) -> Iterator[Location]:
        node = self.head
        while node is not None:
            yield node.location
            node = node.next

    def __contains__(self, item: object) -> bool:
        if not isinstance(item, Location):
            return False
        return self.find_location(item.city, item.country) is not None

    def add_location(self, location: Location) -> bool:
        """Push ``location`` onto the front. Returns False if it is already present."""
        if location in self:
            return False
        node = LocationNode(location)
        node.next = self.head
        self.head = node
        self.size += 1
        return True

    def _unlink(self, city: str, country: str) -> LocationNode | None:
        """Remove and return the node for ``city``/``country``, or None if absent."""
        previous: LocationNode | None = None
        node = self.head
        while node is not None:
            if node.location.matches(city, country):
                if previous is None:
                    self.head = node.next
                else:
                    previous.next = node.next
                node.next = None
                self.size -= 1
                return node
            previous, node = node, node.next
        return None

    def remove_location(self, city: str, country: str) -> bool:
        """Remove a location. Returns False if it was not in the list."""
        return self._unlink(city, country) is not None

    def find_location(self, city: str, country: str) -> Location | None:
        return next((loc for loc in self if loc.matches(city, country)), None)

    def move_to_front(self, city: str, country: str) -> bool:
        """Move a location to the head of the list. Returns False if absent."""
        node = self._unlink(city, country)
        if node is None:
            return False
        node.next = self.head
        self.head = node
        self.size += 1
        return True

    def get_all_locations(self) -> list[Location]:
        return list(self)

    def is_empty(self) -> bool:
        return self.head is None

    def get_size(self) -> int:
        return self.size

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [location.to_dict() for location in self]

    @classmethod
    def from_dict_list(cls, data_list: list[dict[str, Any]]) -> FavoriteLocationsLinkedList:
        return cls([Location.from_dict(item) for item in data_list])
