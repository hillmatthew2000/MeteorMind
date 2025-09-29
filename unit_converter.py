"""
Unit conversion system for weather data.

This module provides conversion between metric and imperial units
for temperature, wind speed, pressure, and other weather measurements.
Includes user preference management for display units.
"""

from enum import Enum
from typing import Union, Dict, Any, Optional
from dataclasses import dataclass


class TemperatureUnit(Enum):
    """Temperature unit options."""
    CELSIUS = "celsius"
    FAHRENHEIT = "fahrenheit" 
    KELVIN = "kelvin"


class WindSpeedUnit(Enum):
    """Wind speed unit options."""
    METERS_PER_SECOND = "mps"
    KILOMETERS_PER_HOUR = "kmh"
    MILES_PER_HOUR = "mph"
    KNOTS = "knots"


class PressureUnit(Enum):
    """Pressure unit options."""
    HECTOPASCAL = "hpa"
    INCHES_OF_MERCURY = "inHg"
    MILLIBARS = "mbar"
    ATMOSPHERES = "atm"


class DistanceUnit(Enum):
    """Distance unit options."""
    KILOMETERS = "km"
    MILES = "miles"
    METERS = "m"
    FEET = "ft"


@dataclass
class UnitPreferences:
    """User preferences for unit display."""
    temperature: TemperatureUnit = TemperatureUnit.CELSIUS
    wind_speed: WindSpeedUnit = WindSpeedUnit.METERS_PER_SECOND
    pressure: PressureUnit = PressureUnit.HECTOPASCAL
    distance: DistanceUnit = DistanceUnit.KILOMETERS
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for serialization."""
        return {
            "temperature": self.temperature.value,
            "wind_speed": self.wind_speed.value,
            "pressure": self.pressure.value,
            "distance": self.distance.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'UnitPreferences':
        """Create from dictionary."""
        return cls(
            temperature=TemperatureUnit(data.get("temperature", "celsius")),
            wind_speed=WindSpeedUnit(data.get("wind_speed", "mps")),
            pressure=PressureUnit(data.get("pressure", "hpa")),
            distance=DistanceUnit(data.get("distance", "km"))
        )


class UnitConverter:
    """
    Handles all unit conversions for weather data.
    
    Features:
    - Temperature conversions (Celsius, Fahrenheit, Kelvin)
    - Wind speed conversions (m/s, km/h, mph, knots)
    - Pressure conversions (hPa, inHg, mbar, atm)
    - Distance conversions (km, miles, m, ft)
    - Formatted string output with appropriate precision
    """
    
    @staticmethod
    def celsius_to_fahrenheit(celsius: float) -> float:
        """Convert Celsius to Fahrenheit."""
        return (celsius * 9/5) + 32
    
    @staticmethod
    def fahrenheit_to_celsius(fahrenheit: float) -> float:
        """Convert Fahrenheit to Celsius."""
        return (fahrenheit - 32) * 5/9
    
    @staticmethod
    def celsius_to_kelvin(celsius: float) -> float:
        """Convert Celsius to Kelvin."""
        return celsius + 273.15
    
    @staticmethod
    def kelvin_to_celsius(kelvin: float) -> float:
        """Convert Kelvin to Celsius."""
        return kelvin - 273.15
    
    @staticmethod
    def convert_temperature(value: float, from_unit: TemperatureUnit, 
                          to_unit: TemperatureUnit) -> float:
        """
        Convert temperature between units.
        
        Args:
            value: Temperature value to convert
            from_unit: Source temperature unit
            to_unit: Target temperature unit
            
        Returns:
            Converted temperature value
        """
        if from_unit == to_unit:
            return value
        
        # Convert to Celsius first
        if from_unit == TemperatureUnit.FAHRENHEIT:
            celsius = UnitConverter.fahrenheit_to_celsius(value)
        elif from_unit == TemperatureUnit.KELVIN:
            celsius = UnitConverter.kelvin_to_celsius(value)
        else:  # Already Celsius
            celsius = value
        
        # Convert from Celsius to target unit
        if to_unit == TemperatureUnit.FAHRENHEIT:
            return UnitConverter.celsius_to_fahrenheit(celsius)
        elif to_unit == TemperatureUnit.KELVIN:
            return UnitConverter.celsius_to_kelvin(celsius)
        else:  # Target is Celsius
            return celsius
    
    @staticmethod
    def mps_to_kmh(mps: float) -> float:
        """Convert meters per second to kilometers per hour."""
        return mps * 3.6
    
    @staticmethod
    def mps_to_mph(mps: float) -> float:
        """Convert meters per second to miles per hour."""
        return mps * 2.237
    
    @staticmethod
    def mps_to_knots(mps: float) -> float:
        """Convert meters per second to knots."""
        return mps * 1.944
    
    @staticmethod
    def convert_wind_speed(value: float, from_unit: WindSpeedUnit, 
                          to_unit: WindSpeedUnit) -> float:
        """
        Convert wind speed between units.
        
        Args:
            value: Wind speed value to convert
            from_unit: Source wind speed unit
            to_unit: Target wind speed unit
            
        Returns:
            Converted wind speed value
        """
        if from_unit == to_unit:
            return value
        
        # Convert to m/s first
        if from_unit == WindSpeedUnit.KILOMETERS_PER_HOUR:
            mps = value / 3.6
        elif from_unit == WindSpeedUnit.MILES_PER_HOUR:
            mps = value / 2.237
        elif from_unit == WindSpeedUnit.KNOTS:
            mps = value / 1.944
        else:  # Already m/s
            mps = value
        
        # Convert from m/s to target unit
        if to_unit == WindSpeedUnit.KILOMETERS_PER_HOUR:
            return UnitConverter.mps_to_kmh(mps)
        elif to_unit == WindSpeedUnit.MILES_PER_HOUR:
            return UnitConverter.mps_to_mph(mps)
        elif to_unit == WindSpeedUnit.KNOTS:
            return UnitConverter.mps_to_knots(mps)
        else:  # Target is m/s
            return mps
    
    @staticmethod
    def hpa_to_inhg(hpa: float) -> float:
        """Convert hectopascals to inches of mercury."""
        return hpa * 0.02953
    
    @staticmethod
    def hpa_to_atm(hpa: float) -> float:
        """Convert hectopascals to atmospheres."""
        return hpa / 1013.25
    
    @staticmethod
    def convert_pressure(value: float, from_unit: PressureUnit, 
                        to_unit: PressureUnit) -> float:
        """
        Convert pressure between units.
        
        Args:
            value: Pressure value to convert
            from_unit: Source pressure unit
            to_unit: Target pressure unit
            
        Returns:
            Converted pressure value
        """
        if from_unit == to_unit:
            return value
        
        # Convert to hPa first
        if from_unit == PressureUnit.INCHES_OF_MERCURY:
            hpa = value / 0.02953
        elif from_unit == PressureUnit.MILLIBARS:
            hpa = value  # mbar = hPa
        elif from_unit == PressureUnit.ATMOSPHERES:
            hpa = value * 1013.25
        else:  # Already hPa
            hpa = value
        
        # Convert from hPa to target unit
        if to_unit == PressureUnit.INCHES_OF_MERCURY:
            return UnitConverter.hpa_to_inhg(hpa)
        elif to_unit == PressureUnit.MILLIBARS:
            return hpa  # mbar = hPa
        elif to_unit == PressureUnit.ATMOSPHERES:
            return UnitConverter.hpa_to_atm(hpa)
        else:  # Target is hPa
            return hpa
    
    @staticmethod
    def km_to_miles(km: float) -> float:
        """Convert kilometers to miles."""
        return km * 0.621371
    
    @staticmethod
    def m_to_feet(m: float) -> float:
        """Convert meters to feet."""
        return m * 3.28084
    
    @staticmethod
    def convert_distance(value: float, from_unit: DistanceUnit, 
                        to_unit: DistanceUnit) -> float:
        """
        Convert distance between units.
        
        Args:
            value: Distance value to convert
            from_unit: Source distance unit
            to_unit: Target distance unit
            
        Returns:
            Converted distance value
        """
        if from_unit == to_unit:
            return value
        
        # Convert to meters first
        if from_unit == DistanceUnit.KILOMETERS:
            meters = value * 1000
        elif from_unit == DistanceUnit.MILES:
            meters = value * 1609.34
        elif from_unit == DistanceUnit.FEET:
            meters = value / 3.28084
        else:  # Already meters
            meters = value
        
        # Convert from meters to target unit
        if to_unit == DistanceUnit.KILOMETERS:
            return meters / 1000
        elif to_unit == DistanceUnit.MILES:
            return meters / 1609.34
        elif to_unit == DistanceUnit.FEET:
            return UnitConverter.m_to_feet(meters)
        else:  # Target is meters
            return meters


class WeatherFormatter:
    """
    Formats weather data with appropriate units and precision.
    
    Features:
    - Automatic unit conversion based on preferences
    - Appropriate decimal precision for each measurement type
    - Localized unit symbols and abbreviations
    - Formatted strings for display
    """
    
    def __init__(self, preferences: Optional[UnitPreferences] = None):
        """
        Initialize the formatter.
        
        Args:
            preferences: User unit preferences
        """
        self.preferences = preferences or UnitPreferences()
        self.converter = UnitConverter()
    
    def format_temperature(self, celsius: float, show_unit: bool = True) -> str:
        """
        Format temperature according to user preferences.
        
        Args:
            celsius: Temperature in Celsius
            show_unit: Whether to include unit symbol
            
        Returns:
            Formatted temperature string
        """
        converted = self.converter.convert_temperature(
            celsius, TemperatureUnit.CELSIUS, self.preferences.temperature
        )
        
        # Round to 1 decimal place
        rounded = round(converted, 1)
        
        if not show_unit:
            return f"{rounded}"
        
        unit_symbols = {
            TemperatureUnit.CELSIUS: "°C",
            TemperatureUnit.FAHRENHEIT: "°F",
            TemperatureUnit.KELVIN: "K"
        }
        
        symbol = unit_symbols[self.preferences.temperature]
        return f"{rounded}{symbol}"
    
    def format_wind_speed(self, mps: float, show_unit: bool = True) -> str:
        """
        Format wind speed according to user preferences.
        
        Args:
            mps: Wind speed in meters per second
            show_unit: Whether to include unit symbol
            
        Returns:
            Formatted wind speed string
        """
        converted = self.converter.convert_wind_speed(
            mps, WindSpeedUnit.METERS_PER_SECOND, self.preferences.wind_speed
        )
        
        # Round to 1 decimal place for most units, integer for km/h and mph
        if self.preferences.wind_speed in [WindSpeedUnit.KILOMETERS_PER_HOUR, 
                                         WindSpeedUnit.MILES_PER_HOUR]:
            rounded = round(converted)
            value_str = f"{rounded}"
        else:
            rounded = round(converted, 1)
            value_str = f"{rounded}"
        
        if not show_unit:
            return value_str
        
        unit_symbols = {
            WindSpeedUnit.METERS_PER_SECOND: "m/s",
            WindSpeedUnit.KILOMETERS_PER_HOUR: "km/h",
            WindSpeedUnit.MILES_PER_HOUR: "mph",
            WindSpeedUnit.KNOTS: "knots"
        }
        
        symbol = unit_symbols[self.preferences.wind_speed]
        return f"{value_str} {symbol}"
    
    def format_pressure(self, hpa: float, show_unit: bool = True) -> str:
        """
        Format atmospheric pressure according to user preferences.
        
        Args:
            hpa: Pressure in hectopascals
            show_unit: Whether to include unit symbol
            
        Returns:
            Formatted pressure string
        """
        converted = self.converter.convert_pressure(
            hpa, PressureUnit.HECTOPASCAL, self.preferences.pressure
        )
        
        # Different precision for different units
        if self.preferences.pressure == PressureUnit.INCHES_OF_MERCURY:
            rounded = round(converted, 2)
        elif self.preferences.pressure == PressureUnit.ATMOSPHERES:
            rounded = round(converted, 3)
        else:  # hPa, mbar
            rounded = round(converted)
        
        if not show_unit:
            return f"{rounded}"
        
        unit_symbols = {
            PressureUnit.HECTOPASCAL: "hPa",
            PressureUnit.INCHES_OF_MERCURY: "inHg",
            PressureUnit.MILLIBARS: "mbar",
            PressureUnit.ATMOSPHERES: "atm"
        }
        
        symbol = unit_symbols[self.preferences.pressure]
        return f"{rounded} {symbol}"
    
    def format_distance(self, km: float, show_unit: bool = True) -> str:
        """
        Format distance according to user preferences.
        
        Args:
            km: Distance in kilometers
            show_unit: Whether to include unit symbol
            
        Returns:
            Formatted distance string
        """
        converted = self.converter.convert_distance(
            km, DistanceUnit.KILOMETERS, self.preferences.distance
        )
        
        # Different precision for different units
        if self.preferences.distance in [DistanceUnit.METERS, DistanceUnit.FEET]:
            rounded = round(converted)
            value_str = f"{rounded}"
        else:  # km, miles
            rounded = round(converted, 1)
            value_str = f"{rounded}"
        
        if not show_unit:
            return value_str
        
        unit_symbols = {
            DistanceUnit.KILOMETERS: "km",
            DistanceUnit.MILES: "mi",
            DistanceUnit.METERS: "m",
            DistanceUnit.FEET: "ft"
        }
        
        symbol = unit_symbols[self.preferences.distance]
        return f"{value_str} {symbol}"
    
    def format_humidity(self, humidity: int) -> str:
        """Format humidity percentage."""
        return f"{humidity}%"
    
    def format_wind_direction(self, degrees: int) -> str:
        """
        Format wind direction from degrees to compass direction.
        
        Args:
            degrees: Wind direction in degrees (0-360)
            
        Returns:
            Compass direction string
        """
        if degrees < 0 or degrees > 360:
            return "N/A"
        
        directions = [
            "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"
        ]
        
        # Calculate index (each direction covers 22.5 degrees)
        index = round(degrees / 22.5) % 16
        return f"{directions[index]} ({degrees}°)"
    
    def get_unit_preferences_display(self) -> str:
        """Get a formatted string showing current unit preferences."""
        return f"""Current Unit Preferences:
  Temperature: {self.preferences.temperature.value.title()}
  Wind Speed: {self.preferences.wind_speed.value.upper()}
  Pressure: {self.preferences.pressure.value.upper()}
  Distance: {self.preferences.distance.value.title()}"""
    
    def get_available_units(self) -> Dict[str, list]:
        """Get all available units for each measurement type."""
        return {
            "temperature": [unit.value for unit in TemperatureUnit],
            "wind_speed": [unit.value for unit in WindSpeedUnit],
            "pressure": [unit.value for unit in PressureUnit],
            "distance": [unit.value for unit in DistanceUnit]
        }


def create_metric_preferences() -> UnitPreferences:
    """Create unit preferences for metric system."""
    return UnitPreferences(
        temperature=TemperatureUnit.CELSIUS,
        wind_speed=WindSpeedUnit.METERS_PER_SECOND,
        pressure=PressureUnit.HECTOPASCAL,
        distance=DistanceUnit.KILOMETERS
    )


def create_imperial_preferences() -> UnitPreferences:
    """Create unit preferences for imperial system."""
    return UnitPreferences(
        temperature=TemperatureUnit.FAHRENHEIT,
        wind_speed=WindSpeedUnit.MILES_PER_HOUR,
        pressure=PressureUnit.INCHES_OF_MERCURY,
        distance=DistanceUnit.MILES
    )


if __name__ == "__main__":
    # Test the unit conversion system
    print("🔄 Unit Conversion System Test")
    print("=" * 40)
    
    # Test temperature conversions
    print("\nTemperature Conversions:")
    celsius_temp = 25.0
    fahrenheit = UnitConverter.celsius_to_fahrenheit(celsius_temp)
    kelvin = UnitConverter.celsius_to_kelvin(celsius_temp)
    print(f"{celsius_temp}°C = {fahrenheit:.1f}°F = {kelvin:.1f}K")
    
    # Test wind speed conversions
    print("\nWind Speed Conversions:")
    mps = 10.0
    kmh = UnitConverter.mps_to_kmh(mps)
    mph = UnitConverter.mps_to_mph(mps)
    knots = UnitConverter.mps_to_knots(mps)
    print(f"{mps} m/s = {kmh:.1f} km/h = {mph:.1f} mph = {knots:.1f} knots")
    
    # Test formatting
    print("\nFormatting Examples:")
    
    # Metric formatting
    metric_prefs = create_metric_preferences()
    metric_formatter = WeatherFormatter(metric_prefs)
    print(f"Metric: {metric_formatter.format_temperature(25.5)}, {metric_formatter.format_wind_speed(5.2)}")
    
    # Imperial formatting
    imperial_prefs = create_imperial_preferences()
    imperial_formatter = WeatherFormatter(imperial_prefs)
    print(f"Imperial: {imperial_formatter.format_temperature(25.5)}, {imperial_formatter.format_wind_speed(5.2)}")
    
    # Wind direction
    print(f"Wind Direction: {metric_formatter.format_wind_direction(225)}")