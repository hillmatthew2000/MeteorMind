"""Unit conversion and display formatting for weather measurements.

Weather data is stored in canonical metric units (°C, m/s, hPa, metres) and
only converted when it is displayed, according to the user's
:class:`UnitPreferences`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

# Exact conversion factors.
_MPS_PER_KMH = 1000 / 3600
_MPS_PER_MPH = 1609.344 / 3600
_MPS_PER_KNOT = 1852 / 3600
_HPA_PER_INHG = 33.8638866667
_HPA_PER_ATM = 1013.25
_METRES_PER_MILE = 1609.344
_METRES_PER_FOOT = 0.3048


class _UnitEnum(str, Enum):
    """String-valued enum that also accepts its value in any letter case."""

    @classmethod
    def _missing_(cls, value: object) -> Any:
        if isinstance(value, str):
            folded = value.strip().casefold()
            for member in cls:
                if member.value.casefold() == folded:
                    return member
        return None

    @property
    def symbol(self) -> str:
        return _SYMBOLS[self]


class TemperatureUnit(_UnitEnum):
    CELSIUS = "celsius"
    FAHRENHEIT = "fahrenheit"
    KELVIN = "kelvin"


class WindSpeedUnit(_UnitEnum):
    METERS_PER_SECOND = "mps"
    KILOMETERS_PER_HOUR = "kmh"
    MILES_PER_HOUR = "mph"
    KNOTS = "knots"


class PressureUnit(_UnitEnum):
    HECTOPASCAL = "hpa"
    INCHES_OF_MERCURY = "inHg"
    MILLIBARS = "mbar"
    ATMOSPHERES = "atm"


class DistanceUnit(_UnitEnum):
    KILOMETERS = "km"
    MILES = "miles"
    METERS = "m"
    FEET = "ft"


_SYMBOLS: dict[_UnitEnum, str] = {
    TemperatureUnit.CELSIUS: "°C",
    TemperatureUnit.FAHRENHEIT: "°F",
    TemperatureUnit.KELVIN: "K",
    WindSpeedUnit.METERS_PER_SECOND: "m/s",
    WindSpeedUnit.KILOMETERS_PER_HOUR: "km/h",
    WindSpeedUnit.MILES_PER_HOUR: "mph",
    WindSpeedUnit.KNOTS: "kn",
    PressureUnit.HECTOPASCAL: "hPa",
    PressureUnit.INCHES_OF_MERCURY: "inHg",
    PressureUnit.MILLIBARS: "mbar",
    PressureUnit.ATMOSPHERES: "atm",
    DistanceUnit.KILOMETERS: "km",
    DistanceUnit.MILES: "mi",
    DistanceUnit.METERS: "m",
    DistanceUnit.FEET: "ft",
}

_E = TypeVar("_E", bound=_UnitEnum)


def _parse_unit(enum_type: type[_E], value: Any, default: _E) -> _E:
    try:
        return enum_type(value)
    except ValueError:
        return default


@dataclass
class UnitPreferences:
    """Which unit to display for each kind of measurement."""

    temperature: TemperatureUnit = TemperatureUnit.CELSIUS
    wind_speed: WindSpeedUnit = WindSpeedUnit.METERS_PER_SECOND
    pressure: PressureUnit = PressureUnit.HECTOPASCAL
    distance: DistanceUnit = DistanceUnit.KILOMETERS

    def to_dict(self) -> dict[str, str]:
        return {
            "temperature": self.temperature.value,
            "wind_speed": self.wind_speed.value,
            "pressure": self.pressure.value,
            "distance": self.distance.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UnitPreferences:
        """Build preferences from a dict; unknown or missing values fall back to metric."""
        d = cls()
        return cls(
            temperature=_parse_unit(TemperatureUnit, data.get("temperature"), d.temperature),
            wind_speed=_parse_unit(WindSpeedUnit, data.get("wind_speed"), d.wind_speed),
            pressure=_parse_unit(PressureUnit, data.get("pressure"), d.pressure),
            distance=_parse_unit(DistanceUnit, data.get("distance"), d.distance),
        )

    @classmethod
    def from_setting(cls, value: Any) -> UnitPreferences:
        """Accept a preset name (``"metric"``/``"imperial"``) or a per-unit dict."""
        if isinstance(value, str):
            return create_imperial_preferences() if value == "imperial" else cls()
        if isinstance(value, dict):
            return cls.from_dict(value)
        return cls()


def create_metric_preferences() -> UnitPreferences:
    return UnitPreferences()


def create_imperial_preferences() -> UnitPreferences:
    return UnitPreferences(
        temperature=TemperatureUnit.FAHRENHEIT,
        wind_speed=WindSpeedUnit.MILES_PER_HOUR,
        pressure=PressureUnit.INCHES_OF_MERCURY,
        distance=DistanceUnit.MILES,
    )


_WIND_TO_MPS: dict[WindSpeedUnit, float] = {
    WindSpeedUnit.METERS_PER_SECOND: 1.0,
    WindSpeedUnit.KILOMETERS_PER_HOUR: _MPS_PER_KMH,
    WindSpeedUnit.MILES_PER_HOUR: _MPS_PER_MPH,
    WindSpeedUnit.KNOTS: _MPS_PER_KNOT,
}
_PRESSURE_TO_HPA: dict[PressureUnit, float] = {
    PressureUnit.HECTOPASCAL: 1.0,
    PressureUnit.MILLIBARS: 1.0,
    PressureUnit.INCHES_OF_MERCURY: _HPA_PER_INHG,
    PressureUnit.ATMOSPHERES: _HPA_PER_ATM,
}
_DISTANCE_TO_M: dict[DistanceUnit, float] = {
    DistanceUnit.METERS: 1.0,
    DistanceUnit.KILOMETERS: 1000.0,
    DistanceUnit.MILES: _METRES_PER_MILE,
    DistanceUnit.FEET: _METRES_PER_FOOT,
}


class UnitConverter:
    """Pure conversion functions between supported units."""

    @staticmethod
    def celsius_to_fahrenheit(celsius: float) -> float:
        return celsius * 9 / 5 + 32

    @staticmethod
    def fahrenheit_to_celsius(fahrenheit: float) -> float:
        return (fahrenheit - 32) * 5 / 9

    @staticmethod
    def celsius_to_kelvin(celsius: float) -> float:
        return celsius + 273.15

    @staticmethod
    def kelvin_to_celsius(kelvin: float) -> float:
        return kelvin - 273.15

    @staticmethod
    def convert_temperature(
        value: float, from_unit: TemperatureUnit, to_unit: TemperatureUnit
    ) -> float:
        if from_unit == to_unit:
            return value
        if from_unit == TemperatureUnit.FAHRENHEIT:
            celsius = UnitConverter.fahrenheit_to_celsius(value)
        elif from_unit == TemperatureUnit.KELVIN:
            celsius = UnitConverter.kelvin_to_celsius(value)
        else:
            celsius = value
        if to_unit == TemperatureUnit.FAHRENHEIT:
            return UnitConverter.celsius_to_fahrenheit(celsius)
        if to_unit == TemperatureUnit.KELVIN:
            return UnitConverter.celsius_to_kelvin(celsius)
        return celsius

    @staticmethod
    def convert_temperature_delta(celsius_delta: float, to_unit: TemperatureUnit) -> float:
        """Convert a temperature *difference*; scale offsets do not apply to deltas."""
        if to_unit == TemperatureUnit.FAHRENHEIT:
            return celsius_delta * 9 / 5
        return celsius_delta

    @staticmethod
    def mps_to_kmh(mps: float) -> float:
        return mps / _MPS_PER_KMH

    @staticmethod
    def mps_to_mph(mps: float) -> float:
        return mps / _MPS_PER_MPH

    @staticmethod
    def mps_to_knots(mps: float) -> float:
        return mps / _MPS_PER_KNOT

    @staticmethod
    def convert_wind_speed(value: float, from_unit: WindSpeedUnit, to_unit: WindSpeedUnit) -> float:
        return value * _WIND_TO_MPS[from_unit] / _WIND_TO_MPS[to_unit]

    @staticmethod
    def hpa_to_inhg(hpa: float) -> float:
        return hpa / _HPA_PER_INHG

    @staticmethod
    def hpa_to_atm(hpa: float) -> float:
        return hpa / _HPA_PER_ATM

    @staticmethod
    def convert_pressure(value: float, from_unit: PressureUnit, to_unit: PressureUnit) -> float:
        return value * _PRESSURE_TO_HPA[from_unit] / _PRESSURE_TO_HPA[to_unit]

    @staticmethod
    def km_to_miles(km: float) -> float:
        return km * 1000 / _METRES_PER_MILE

    @staticmethod
    def m_to_feet(m: float) -> float:
        return m / _METRES_PER_FOOT

    @staticmethod
    def convert_distance(value: float, from_unit: DistanceUnit, to_unit: DistanceUnit) -> float:
        return value * _DISTANCE_TO_M[from_unit] / _DISTANCE_TO_M[to_unit]


COMPASS_POINTS = (
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
)  # fmt: skip


def compass_point(degrees: float) -> str:
    """Return the 16-point compass direction for a bearing in degrees."""
    return COMPASS_POINTS[round((degrees % 360) / 22.5) % 16]


def _number(value: float, decimals: int) -> str:
    """Format a number, never producing a negative zero such as ``-0.0``."""
    text = f"{value:.{decimals}f}"
    if text.startswith("-") and float(text) == 0:
        text = text[1:]
    return text


class WeatherFormatter:
    """Formats canonical metric values for display in the preferred units."""

    def __init__(self, preferences: UnitPreferences | None = None) -> None:
        self.preferences = preferences or UnitPreferences()

    @property
    def temperature_symbol(self) -> str:
        return self.preferences.temperature.symbol

    @property
    def wind_speed_symbol(self) -> str:
        return self.preferences.wind_speed.symbol

    def convert_temperature(self, celsius: float) -> float:
        return UnitConverter.convert_temperature(
            celsius, TemperatureUnit.CELSIUS, self.preferences.temperature
        )

    def format_temperature(self, celsius: float, show_unit: bool = True, decimals: int = 1) -> str:
        text = _number(self.convert_temperature(celsius), decimals)
        return f"{text}{self.temperature_symbol}" if show_unit else text

    def format_temperature_delta(self, celsius_delta: float, show_unit: bool = True) -> str:
        """Format a signed temperature change, e.g. ``+1.8°F``."""
        delta = UnitConverter.convert_temperature_delta(celsius_delta, self.preferences.temperature)
        text = _number(delta, 1)
        if float(text) > 0:
            text = f"+{text}"
        return f"{text}{self.temperature_symbol}" if show_unit else text

    def format_wind_speed(self, mps: float, show_unit: bool = True) -> str:
        unit = self.preferences.wind_speed
        value = UnitConverter.convert_wind_speed(mps, WindSpeedUnit.METERS_PER_SECOND, unit)
        whole = unit in (WindSpeedUnit.KILOMETERS_PER_HOUR, WindSpeedUnit.MILES_PER_HOUR)
        text = _number(value, 0 if whole else 1)
        return f"{text} {unit.symbol}" if show_unit else text

    def format_pressure(self, hpa: float, show_unit: bool = True) -> str:
        unit = self.preferences.pressure
        value = UnitConverter.convert_pressure(hpa, PressureUnit.HECTOPASCAL, unit)
        decimals = {PressureUnit.INCHES_OF_MERCURY: 2, PressureUnit.ATMOSPHERES: 3}.get(unit, 0)
        text = _number(value, decimals)
        return f"{text} {unit.symbol}" if show_unit else text

    def format_distance(self, km: float, show_unit: bool = True) -> str:
        unit = self.preferences.distance
        value = UnitConverter.convert_distance(km, DistanceUnit.KILOMETERS, unit)
        text = _number(value, 0 if unit in (DistanceUnit.METERS, DistanceUnit.FEET) else 1)
        return f"{text} {unit.symbol}" if show_unit else text

    def format_visibility(self, metres: int | None) -> str:
        return "—" if metres is None else self.format_distance(metres / 1000)

    @staticmethod
    def format_humidity(humidity: int) -> str:
        return f"{humidity}%"

    @staticmethod
    def format_wind_direction(degrees: int) -> str:
        if not 0 <= degrees <= 360:
            return "N/A"
        return f"{compass_point(degrees)} ({degrees}°)"

    def get_unit_preferences_display(self) -> str:
        prefs = self.preferences
        return (
            "Current unit preferences:\n"
            f"  Temperature: {prefs.temperature.value.title()} ({prefs.temperature.symbol})\n"
            f"  Wind speed:  {prefs.wind_speed.symbol}\n"
            f"  Pressure:    {prefs.pressure.symbol}\n"
            f"  Distance:    {prefs.distance.symbol}"
        )
