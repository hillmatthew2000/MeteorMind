"""OpenWeatherMap client: geocoding, current weather and five-day forecasts.

Requests use connect/read timeouts and retry transient server failures with
exponential backoff. Successful responses are kept in a :class:`ResponseCache`
so repeated lookups within the cache lifetime do not spend API calls.

Every failure is raised as an :class:`APIError` subclass whose message and
``suggestions`` are written for end users.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Protocol
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .cache import ResponseCache
from .config import ConfigManager
from .models import ForecastData, Location, WeatherData

logger = logging.getLogger(__name__)

MAX_FORECAST_DAYS = 5


class APIError(Exception):
    """Base class for weather service errors; ``str(error)`` is user-facing."""

    default_suggestions: tuple[str, ...] = ("Try again in a few moments.",)

    def __init__(self, message: str, suggestions: list[str] | None = None) -> None:
        super().__init__(message)
        self.suggestions = list(self.default_suggestions if suggestions is None else suggestions)


class MissingAPIKeyError(APIError):
    default_suggestions = (
        "Get a free key at https://home.openweathermap.org/users/sign_up",
        "Set the OPENWEATHER_API_KEY environment variable or save the key in the app settings.",
    )


class AuthenticationError(APIError):
    default_suggestions = (
        "Check the key in the app settings or your OPENWEATHER_API_KEY variable.",
        "Newly created keys can take up to two hours to activate.",
    )


class LocationNotFoundError(APIError):
    default_suggestions = (
        "Check the spelling of the city name.",
        "Add a country code, for example 'Paris, FR'.",
    )


class RateLimitError(APIError):
    default_suggestions = (
        "Wait a minute before trying again; the free plan allows 60 calls per minute.",
    )


class NetworkError(APIError):
    default_suggestions = (
        "Check your internet connection.",
        "Try again in a few moments.",
    )


class ServiceError(APIError):
    default_suggestions = ("OpenWeatherMap may be having problems; try again later.",)


def describe_error(error: APIError) -> tuple[str, list[str]]:
    """Return ``(message, suggestions)`` for showing ``error`` to a user."""
    return str(error), error.suggestions


class WeatherProvider(Protocol):
    """The operations the interfaces need from a weather source."""

    def search_locations(
        self, city_name: str, country_code: str | None = None, limit: int = 5
    ) -> list[Location]: ...

    def get_location_by_name(self, city_name: str, country_code: str | None = None) -> Location: ...

    def get_current_weather(self, location: Location) -> WeatherData: ...

    def get_forecast(
        self, location: Location, days: int = MAX_FORECAST_DAYS
    ) -> list[ForecastData]: ...


def build_session(retries: int = 2, backoff_factor: float = 0.5) -> requests.Session:
    """Create a session that retries idempotent requests on transient failures.

    Rate-limit responses (429) are not retried: the limit is per minute, so an
    immediate retry would only fail again.
    """
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=backoff_factor,
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers["User-Agent"] = "MeteorMind"
    return session


def _capitalize(text: str) -> str:
    return text[:1].upper() + text[1:]


def _local_time(timestamp: int, utc_offset_seconds: int) -> datetime:
    """Convert a UTC epoch to naive wall-clock time at a location."""
    moment = datetime.fromtimestamp(timestamp, tz=timezone.utc) + timedelta(
        seconds=utc_offset_seconds
    )
    return moment.replace(tzinfo=None)


def parse_locations(data: Any) -> list[Location]:
    """Parse a geocoding API response."""
    if not isinstance(data, list):
        raise ServiceError("Unexpected response from the geocoding service.")
    try:
        return [
            Location(
                city=item["name"],
                country=item.get("country", ""),
                latitude=float(item["lat"]),
                longitude=float(item["lon"]),
                state=item.get("state", ""),
            )
            for item in data
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise ServiceError("Unexpected response from the geocoding service.") from exc


def parse_current_weather(data: Any, location: Location) -> WeatherData:
    """Parse a current-weather response.

    The place name comes from the geocoded ``location``: the weather endpoint
    reports its nearest station, which is often a district (searching
    "London" can return "Clerkenwell").
    """
    try:
        main = data["main"]
        wind = data.get("wind", {})
        condition = data["weather"][0]
        return WeatherData(
            city=location.city,
            country=location.country,
            temperature=float(main["temp"]),
            feels_like=float(main["feels_like"]),
            humidity=int(main["humidity"]),
            pressure=int(main["pressure"]),
            wind_speed=float(wind.get("speed", 0.0)),
            wind_direction=int(wind.get("deg", 0)),
            description=_capitalize(condition["description"]),
            timestamp=datetime.fromtimestamp(data["dt"]) if "dt" in data else datetime.now(),
            icon=condition.get("icon", ""),
            visibility=data.get("visibility"),
            temp_min=main.get("temp_min"),
            temp_max=main.get("temp_max"),
        )
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ServiceError("Unexpected response from the weather service.") from exc


def parse_forecast(data: Any, days: int = MAX_FORECAST_DAYS) -> list[ForecastData]:
    """Summarise the 3-hourly forecast into one entry per local calendar day.

    Entries are grouped by the date *at the location* (using the city's UTC
    offset), not by the date on the machine running the app.
    """
    try:
        offset = int(data.get("city", {}).get("timezone", 0))
        by_day: dict[date, list[dict[str, Any]]] = defaultdict(list)
        for item in data["list"]:
            by_day[_local_time(int(item["dt"]), offset).date()].append(item)

        forecasts = []
        for day in sorted(by_day)[:days]:
            items = by_day[day]
            temps = [float(item["main"]["temp"]) for item in items]
            descriptions = Counter(item["weather"][0]["description"] for item in items)
            description = descriptions.most_common(1)[0][0]
            icons = [
                item["weather"][0].get("icon", "")
                for item in items
                if item["weather"][0]["description"] == description
            ]
            icon = next((i for i in icons if i.endswith("d")), icons[0] if icons else "")
            forecasts.append(
                ForecastData(
                    date=datetime.combine(day, datetime.min.time()),
                    temperature_min=min(temps),
                    temperature_max=max(temps),
                    humidity=round(sum(item["main"]["humidity"] for item in items) / len(items)),
                    wind_speed=sum(item.get("wind", {}).get("speed", 0.0) for item in items)
                    / len(items),
                    description=_capitalize(description),
                    precipitation_chance=round(max(item.get("pop", 0) for item in items) * 100),
                    icon=icon,
                )
            )
        return forecasts
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        raise ServiceError("Unexpected response from the forecast service.") from exc


class WeatherAPIHandler:
    """Client for the OpenWeatherMap current weather, forecast and geocoding APIs."""

    BASE_URL = "https://api.openweathermap.org/data/2.5"
    GEO_URL = "https://api.openweathermap.org/geo/1.0"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        session: requests.Session | None = None,
        cache: ResponseCache | None = None,
        timeout: tuple[float, float] = (5.0, 15.0),
        config: ConfigManager | None = None,
    ) -> None:
        key = api_key or (config or ConfigManager()).get_api_key()
        if not key:
            raise MissingAPIKeyError("No OpenWeatherMap API key is configured.")
        self.api_key = key.strip()
        self.session = session or build_session()
        self.cache = cache if cache is not None else ResponseCache()
        self.timeout = timeout

    def _get(self, url: str, params: dict[str, Any], *, use_cache: bool = True) -> Any:
        cache_key = f"{url}?{urlencode(sorted(params.items()))}"
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug("cache hit: %s", cache_key)
                return cached

        try:
            response = self.session.get(
                url, params={**params, "appid": self.api_key}, timeout=self.timeout
            )
        except requests.exceptions.Timeout as exc:
            raise NetworkError("The weather service took too long to respond.") from exc
        except requests.exceptions.ConnectionError as exc:
            raise NetworkError("Could not connect to the weather service.") from exc
        except requests.exceptions.RequestException as exc:
            raise NetworkError(f"The request failed: {exc.__class__.__name__}.") from exc

        status = response.status_code
        if status == 401:
            raise AuthenticationError("OpenWeatherMap rejected the API key.")
        if status == 404:
            raise LocationNotFoundError("That location was not found.")
        if status == 429:
            raise RateLimitError("The API rate limit has been reached.")
        if status >= 500:
            raise ServiceError(f"The weather service is unavailable (HTTP {status}).")
        if status >= 400:
            raise APIError(f"The weather service rejected the request (HTTP {status}).")

        try:
            data = response.json()
        except ValueError as exc:
            raise ServiceError("The weather service returned an invalid response.") from exc

        if use_cache:
            self.cache.set(cache_key, data)
        return data

    def search_locations(
        self, city_name: str, country_code: str | None = None, limit: int = 5
    ) -> list[Location]:
        """Return up to ``limit`` places matching the name, best match first."""
        query = f"{city_name},{country_code}" if country_code else city_name
        data = self._get(f"{self.GEO_URL}/direct", {"q": query, "limit": limit})
        return parse_locations(data)

    def get_location_by_name(self, city_name: str, country_code: str | None = None) -> Location:
        matches = self.search_locations(city_name, country_code, limit=1)
        if not matches:
            where = f"{city_name}, {country_code}" if country_code else city_name
            raise LocationNotFoundError(f"No place called '{where}' was found.")
        return matches[0]

    def get_current_weather(self, location: Location) -> WeatherData:
        params = {"lat": location.latitude, "lon": location.longitude, "units": "metric"}
        return parse_current_weather(self._get(f"{self.BASE_URL}/weather", params), location)

    def get_current_weather_by_name(
        self, city_name: str, country_code: str | None = None
    ) -> tuple[WeatherData, Location]:
        location = self.get_location_by_name(city_name, country_code)
        return self.get_current_weather(location), location

    def get_forecast(self, location: Location, days: int = MAX_FORECAST_DAYS) -> list[ForecastData]:
        if not 1 <= days <= MAX_FORECAST_DAYS:
            raise ValueError(f"days must be between 1 and {MAX_FORECAST_DAYS}")
        params = {"lat": location.latitude, "lon": location.longitude, "units": "metric"}
        return parse_forecast(self._get(f"{self.BASE_URL}/forecast", params), days)

    def get_forecast_by_name(
        self, city_name: str, country_code: str | None = None, days: int = MAX_FORECAST_DAYS
    ) -> tuple[list[ForecastData], Location]:
        location = self.get_location_by_name(city_name, country_code)
        return self.get_forecast(location, days), location

    def validate_api_key(self) -> bool:
        """Make one uncached request; False means the key was rejected.

        Network and service failures are raised rather than reported as an
        invalid key.
        """
        try:
            self._get(f"{self.GEO_URL}/direct", {"q": "London", "limit": 1}, use_cache=False)
        except AuthenticationError:
            return False
        return True
