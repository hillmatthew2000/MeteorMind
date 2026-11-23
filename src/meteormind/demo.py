"""An offline weather provider with plausible, deterministic sample data.

Used by the ``--demo`` option so the app can be explored without an API key
or network access, and by tests and screenshots. Values are derived from the
place name and date, so the same query always gives the same answer.
"""

from __future__ import annotations

import hashlib
import math
from datetime import date, datetime, timedelta

from .api import MAX_FORECAST_DAYS, LocationNotFoundError
from .models import ForecastData, Location, WeatherData

# name -> (country, state, latitude, longitude)
KNOWN_PLACES: dict[str, tuple[str, str, float, float]] = {
    "london": ("GB", "England", 51.5073, -0.1276),
    "paris": ("FR", "Ile-de-France", 48.8589, 2.3200),
    "tokyo": ("JP", "", 35.6828, 139.7595),
    "new york": ("US", "New York", 40.7127, -74.0060),
    "sydney": ("AU", "New South Wales", -33.8698, 151.2083),
    "cairo": ("EG", "", 30.0444, 31.2357),
    "reykjavik": ("IS", "", 64.1466, -21.9426),
    "singapore": ("SG", "", 1.2900, 103.8500),
    "cape town": ("ZA", "Western Cape", -33.9249, 18.4241),
    "toronto": ("CA", "Ontario", 43.6535, -79.3839),
}

# (description, day icon) pairs in rough order of how often they occur.
CONDITIONS = (
    ("Clear sky", "01d"),
    ("Few clouds", "02d"),
    ("Scattered clouds", "03d"),
    ("Broken clouds", "04d"),
    ("Light rain", "10d"),
    ("Overcast clouds", "04d"),
    ("Moderate rain", "10d"),
    ("Thunderstorm", "11d"),
    ("Light snow", "13d"),
    ("Mist", "50d"),
)


def _seed(*parts: object) -> int:
    digest = hashlib.sha256("|".join(str(p).casefold() for p in parts).encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _unit(seed: int, salt: int) -> float:
    """A stable pseudo-random number in [0, 1)."""
    return ((seed >> (salt % 48)) % 10_000) / 10_000


def _base_temperature(latitude: float, day: date) -> float:
    """A crude climate model: warm at the equator, seasonal away from it."""
    seasonal = math.cos(2 * math.pi * (day.timetuple().tm_yday - 196) / 365)
    hemisphere = 1 if latitude >= 0 else -1
    return 31 - 0.4 * abs(latitude) + 7 * seasonal * hemisphere * min(abs(latitude), 60) / 60


class DemoWeatherClient:
    """Implements :class:`meteormind.api.WeatherProvider` without network access."""

    is_demo = True

    def __init__(self, today: date | None = None) -> None:
        self._today = today

    @property
    def today(self) -> date:
        return self._today or date.today()

    def search_locations(
        self, city_name: str, country_code: str | None = None, limit: int = 5
    ) -> list[Location]:
        name = " ".join(city_name.split())
        if not name:
            return []
        known = KNOWN_PLACES.get(name.casefold())
        if known:
            country, state, lat, lon = known
            if country_code and country_code.upper() != country:
                return []
            return [Location(name.title(), country, lat, lon, state=state)][:limit]
        seed = _seed(name, country_code or "")
        latitude = round(_unit(seed, 3) * 120 - 55, 4)
        longitude = round(_unit(seed, 17) * 360 - 180, 4)
        return [Location(name, (country_code or "XX").upper(), latitude, longitude)][:limit]

    def get_location_by_name(self, city_name: str, country_code: str | None = None) -> Location:
        matches = self.search_locations(city_name, country_code, limit=1)
        if not matches:
            raise LocationNotFoundError(f"No place called '{city_name}' was found.")
        return matches[0]

    def _condition(self, location: Location, day: date) -> tuple[str, str]:
        seed = _seed(location.city, location.country, day.isoformat())
        weights = (18, 16, 14, 12, 10, 9, 8, 5, 4, 4)
        pick = _unit(seed, 5) * sum(weights)
        for (description, icon), weight in zip(CONDITIONS, weights, strict=True):
            if pick < weight:
                if description == "Light snow" and _base_temperature(location.latitude, day) > 4:
                    return "Light rain", "10d"
                return description, icon
            pick -= weight
        return CONDITIONS[0]

    def get_current_weather(self, location: Location) -> WeatherData:
        today = self.today
        seed = _seed(location.city, location.country, today.isoformat(), "now")
        temperature = round(_base_temperature(location.latitude, today) + _unit(seed, 1) * 6 - 3, 1)
        wind = round(1 + _unit(seed, 9) * 8, 1)
        description, icon = self._condition(location, today)
        return WeatherData(
            city=location.city,
            country=location.country,
            temperature=temperature,
            feels_like=round(temperature - wind * 0.4, 1),
            humidity=round(45 + _unit(seed, 13) * 50),
            pressure=round(1000 + _unit(seed, 21) * 30),
            wind_speed=wind,
            wind_direction=round(_unit(seed, 27) * 359),
            description=description,
            timestamp=datetime.combine(today, datetime.min.time()) + timedelta(hours=12),
            icon=icon,
            visibility=10_000 if "rain" not in description.lower() else 6_000,
            temp_min=round(temperature - 3, 1),
            temp_max=round(temperature + 3, 1),
        )

    def get_forecast(self, location: Location, days: int = MAX_FORECAST_DAYS) -> list[ForecastData]:
        if not 1 <= days <= MAX_FORECAST_DAYS:
            raise ValueError(f"days must be between 1 and {MAX_FORECAST_DAYS}")
        forecasts = []
        for offset in range(days):
            day = self.today + timedelta(days=offset)
            seed = _seed(location.city, location.country, day.isoformat())
            base = _base_temperature(location.latitude, day) + _unit(seed, 2) * 4 - 2
            description, icon = self._condition(location, day)
            wet = any(word in description for word in ("rain", "storm", "snow", "Thunder"))
            forecasts.append(
                ForecastData(
                    date=datetime.combine(day, datetime.min.time()),
                    temperature_min=round(base - 3 - _unit(seed, 7) * 3, 1),
                    temperature_max=round(base + 3 + _unit(seed, 11) * 3, 1),
                    humidity=round(50 + _unit(seed, 15) * 40),
                    wind_speed=round(1 + _unit(seed, 19) * 7, 1),
                    description=description,
                    precipitation_chance=round(40 + _unit(seed, 23) * 55)
                    if wet
                    else round(_unit(seed, 23) * 20),
                    icon=icon,
                )
            )
        return forecasts

    def get_current_weather_by_name(
        self, city_name: str, country_code: str | None = None
    ) -> tuple[WeatherData, Location]:
        location = self.get_location_by_name(city_name, country_code)
        return self.get_current_weather(location), location

    def get_forecast_by_name(
        self, city_name: str, country_code: str | None = None, days: int = MAX_FORECAST_DAYS
    ) -> tuple[list[ForecastData], Location]:
        location = self.get_location_by_name(city_name, country_code)
        return self.get_forecast(location, days), location

    def validate_api_key(self) -> bool:
        return True
