"""
Input validation and error handling for the weather application.

This module provides comprehensive validation for user inputs including:
- City names and location validation
- Date and time validation
- API response validation
- User preference validation
- Graceful error handling with user-friendly messages
"""

import re
import datetime
from typing import Optional, Tuple, List, Any, Dict
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    is_valid: bool
    value: Any = None
    error_message: str = ""
    suggestions: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.suggestions is None:
            self.suggestions = []


class InputValidator:
    """
    Comprehensive input validation for weather application.
    
    Features:
    - City name validation with common pattern checking
    - Country code validation
    - Date and time validation
    - Numeric input validation
    - API response validation
    - User-friendly error messages with suggestions
    """
    
    # Common city name patterns
    CITY_NAME_PATTERN = re.compile(r'^[a-zA-Z\s\-\.\'\u00C0-\u017F]+$')
    
    # Country code patterns (ISO 3166-1 alpha-2)
    COUNTRY_CODE_PATTERN = re.compile(r'^[A-Z]{2}$')
    
    # Common invalid city name patterns to catch
    INVALID_PATTERNS = [
        (re.compile(r'^\d+$'), "City name cannot be only numbers"),
        (re.compile(r'^[^a-zA-Z]+$'), "City name must contain letters"),
        (re.compile(r'.{100,}'), "City name is too long (max 100 characters)"),
        (re.compile(r'^$'), "City name cannot be empty"),
    ]
    
    # Common country codes for suggestions
    COMMON_COUNTRIES = {
        'US': 'United States',
        'GB': 'United Kingdom', 
        'CA': 'Canada',
        'AU': 'Australia',
        'DE': 'Germany',
        'FR': 'France',
        'IT': 'Italy',
        'ES': 'Spain',
        'JP': 'Japan',
        'CN': 'China',
        'IN': 'India',
        'BR': 'Brazil',
        'MX': 'Mexico',
        'RU': 'Russia',
        'ZA': 'South Africa',
        'NZ': 'New Zealand',
        'NL': 'Netherlands',
        'SE': 'Sweden',
        'NO': 'Norway',
        'DK': 'Denmark'
    }
    
    @classmethod
    def validate_city_name(cls, city_name: str) -> ValidationResult:
        """
        Validate city name input.
        
        Args:
            city_name: City name to validate
            
        Returns:
            ValidationResult with validation status and suggestions
        """
        if not isinstance(city_name, str):
            return ValidationResult(
                is_valid=False,
                error_message="City name must be text",
                suggestions=["Enter a valid city name like 'London' or 'New York'"]
            )
        
        # Trim whitespace
        city_name = city_name.strip()
        
        # Check for common invalid patterns
        for pattern, message in cls.INVALID_PATTERNS:
            if pattern.match(city_name):
                return ValidationResult(
                    is_valid=False,
                    error_message=message,
                    suggestions=["Try entering a valid city name like 'Paris', 'Tokyo', or 'Sydney'"]
                )
        
        # Check basic pattern
        if not cls.CITY_NAME_PATTERN.match(city_name):
            return ValidationResult(
                is_valid=False,
                error_message="City name contains invalid characters",
                suggestions=[
                    "City names can only contain letters, spaces, hyphens, periods, and apostrophes",
                    "Examples: 'New York', 'São Paulo', 'Al-Qāhirah'"
                ]
            )
        
        # Additional checks
        if len(city_name) < 2:
            return ValidationResult(
                is_valid=False,
                error_message="City name is too short",
                suggestions=["Enter at least 2 characters"]
            )
        
        # Check for obvious typos or test inputs
        test_patterns = ['test', 'asdf', 'qwerty', 'aaaaa']
        if city_name.lower() in test_patterns:
            return ValidationResult(
                is_valid=False,
                error_message="Please enter a real city name",
                suggestions=["Try: London, Paris, New York, Tokyo, Sydney"]
            )
        
        return ValidationResult(
            is_valid=True,
            value=city_name.title(),  # Capitalize properly
            suggestions=[]
        )
    
    @classmethod
    def validate_country_code(cls, country_code: Optional[str]) -> ValidationResult:
        """
        Validate country code input.
        
        Args:
            country_code: Country code to validate (optional)
            
        Returns:
            ValidationResult with validation status
        """
        if country_code is None or country_code.strip() == "":
            return ValidationResult(
                is_valid=True,
                value=None,
                suggestions=["Country code is optional but can improve search accuracy"]
            )
        
        if not isinstance(country_code, str):
            return ValidationResult(
                is_valid=False,
                error_message="Country code must be text",
                suggestions=["Use 2-letter codes like 'US', 'GB', 'CA'"]
            )
        
        country_code = country_code.strip().upper()
        
        if not cls.COUNTRY_CODE_PATTERN.match(country_code):
            return ValidationResult(
                is_valid=False,
                error_message="Country code must be exactly 2 letters",
                suggestions=[
                    "Use ISO 3166-1 alpha-2 codes",
                    f"Common codes: {', '.join(list(cls.COMMON_COUNTRIES.keys())[:10])}"
                ]
            )
        
        # Provide friendly name if available
        suggestions = []
        if country_code in cls.COMMON_COUNTRIES:
            suggestions.append(f"{country_code} = {cls.COMMON_COUNTRIES[country_code]}")
        else:
            suggestions.append("Make sure you're using the correct 2-letter country code")
        
        return ValidationResult(
            is_valid=True,
            value=country_code,
            suggestions=suggestions
        )
    
    @classmethod
    def validate_date_input(cls, date_input: str) -> ValidationResult:
        """
        Validate date input with multiple format support.
        
        Args:
            date_input: Date string to validate
            
        Returns:
            ValidationResult with parsed date
        """
        if not isinstance(date_input, str) or not date_input.strip():
            return ValidationResult(
                is_valid=False,
                error_message="Date cannot be empty",
                suggestions=["Format: YYYY-MM-DD, MM/DD/YYYY, or DD/MM/YYYY"]
            )
        
        date_input = date_input.strip()
        
        # Supported date formats
        date_formats = [
            ('%Y-%m-%d', 'YYYY-MM-DD'),
            ('%m/%d/%Y', 'MM/DD/YYYY'),
            ('%d/%m/%Y', 'DD/MM/YYYY'),
            ('%Y/%m/%d', 'YYYY/MM/DD'),
            ('%d-%m-%Y', 'DD-MM-YYYY'),
            ('%m-%d-%Y', 'MM-DD-YYYY')
        ]
        
        parsed_date = None
        for date_format, format_name in date_formats:
            try:
                parsed_date = datetime.datetime.strptime(date_input, date_format).date()
                break
            except ValueError:
                continue
        
        if parsed_date is None:
            return ValidationResult(
                is_valid=False,
                error_message="Invalid date format",
                suggestions=[
                    "Supported formats:",
                    "  • YYYY-MM-DD (2024-01-15)",
                    "  • MM/DD/YYYY (01/15/2024)",
                    "  • DD/MM/YYYY (15/01/2024)"
                ]
            )
        
        # Check if date is reasonable
        today = datetime.date.today()
        min_date = today - datetime.timedelta(days=365 * 5)  # 5 years ago
        max_date = today + datetime.timedelta(days=30)  # 30 days in future
        
        if parsed_date < min_date:
            return ValidationResult(
                is_valid=False,
                error_message="Date is too far in the past",
                suggestions=[f"Please use a date after {min_date}"]
            )
        
        if parsed_date > max_date:
            return ValidationResult(
                is_valid=False,
                error_message="Date is too far in the future",
                suggestions=[f"Please use a date before {max_date}"]
            )
        
        return ValidationResult(
            is_valid=True,
            value=parsed_date,
            suggestions=[]
        )
    
    @classmethod
    def validate_numeric_input(cls, value: str, min_value: Optional[float] = None,
                             max_value: Optional[float] = None, 
                             allow_negative: bool = True,
                             decimal_places: Optional[int] = None) -> ValidationResult:
        """
        Validate numeric input with constraints.
        
        Args:
            value: String value to validate
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            allow_negative: Whether negative values are allowed
            decimal_places: Maximum decimal places allowed
            
        Returns:
            ValidationResult with parsed numeric value
        """
        if not isinstance(value, str) or not value.strip():
            return ValidationResult(
                is_valid=False,
                error_message="Value cannot be empty",
                suggestions=["Enter a valid number"]
            )
        
        value = value.strip()
        
        try:
            numeric_value = float(value)
        except ValueError:
            return ValidationResult(
                is_valid=False,
                error_message="Invalid number format",
                suggestions=["Enter a valid number (e.g., 25, 25.5, -10)"]
            )
        
        # Check constraints
        if not allow_negative and numeric_value < 0:
            return ValidationResult(
                is_valid=False,
                error_message="Negative values are not allowed",
                suggestions=["Enter a positive number"]
            )
        
        if min_value is not None and numeric_value < min_value:
            return ValidationResult(
                is_valid=False,
                error_message=f"Value must be at least {min_value}",
                suggestions=[f"Enter a value >= {min_value}"]
            )
        
        if max_value is not None and numeric_value > max_value:
            return ValidationResult(
                is_valid=False,
                error_message=f"Value must be at most {max_value}",
                suggestions=[f"Enter a value <= {max_value}"]
            )
        
        # Check decimal places
        if decimal_places is not None:
            decimal_part = str(numeric_value).split('.')[-1] if '.' in str(numeric_value) else ""
            if len(decimal_part) > decimal_places:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Too many decimal places (max {decimal_places})",
                    suggestions=[f"Round to {decimal_places} decimal places"]
                )
        
        return ValidationResult(
            is_valid=True,
            value=numeric_value,
            suggestions=[]
        )
    
    @classmethod
    def validate_unit_preference(cls, unit_type: str, unit_value: str) -> ValidationResult:
        """
        Validate unit preference selection.
        
        Args:
            unit_type: Type of unit (temperature, wind_speed, pressure, distance)
            unit_value: Unit value to validate
            
        Returns:
            ValidationResult with validation status
        """
        valid_units = {
            'temperature': ['celsius', 'fahrenheit', 'kelvin'],
            'wind_speed': ['mps', 'kmh', 'mph', 'knots'],
            'pressure': ['hpa', 'inhg', 'mbar', 'atm'],
            'distance': ['km', 'miles', 'm', 'ft']
        }
        
        if unit_type not in valid_units:
            return ValidationResult(
                is_valid=False,
                error_message=f"Unknown unit type: {unit_type}",
                suggestions=[f"Valid types: {', '.join(valid_units.keys())}"]
            )
        
        if not isinstance(unit_value, str):
            return ValidationResult(
                is_valid=False,
                error_message="Unit value must be text",
                suggestions=[]
            )
        
        unit_value = unit_value.lower().strip()
        
        if unit_value not in valid_units[unit_type]:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid {unit_type} unit: {unit_value}",
                suggestions=[f"Valid options: {', '.join(valid_units[unit_type])}"]
            )
        
        return ValidationResult(
            is_valid=True,
            value=unit_value,
            suggestions=[]
        )


class APIResponseValidator:
    """Validates API responses and handles API errors gracefully."""
    
    @staticmethod
    def validate_weather_response(response_data: Dict[str, Any]) -> ValidationResult:
        """
        Validate weather API response data.
        
        Args:
            response_data: Raw API response data
            
        Returns:
            ValidationResult indicating if response is valid
        """
        required_fields = ['name', 'main', 'weather', 'sys']
        required_main_fields = ['temp', 'humidity', 'pressure']
        
        # Check top-level fields
        for field in required_fields:
            if field not in response_data:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Missing required field: {field}",
                    suggestions=["API response is incomplete"]
                )
        
        # Check main weather data
        main_data = response_data.get('main', {})
        for field in required_main_fields:
            if field not in main_data:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Missing weather data: {field}",
                    suggestions=["Weather data is incomplete"]
                )
        
        # Validate weather array
        weather_array = response_data.get('weather', [])
        if not weather_array or not isinstance(weather_array, list):
            return ValidationResult(
                is_valid=False,
                error_message="Missing weather description",
                suggestions=["Weather description is unavailable"]
            )
        
        return ValidationResult(
            is_valid=True,
            value=response_data,
            suggestions=[]
        )
    
    @staticmethod
    def validate_forecast_response(response_data: Dict[str, Any]) -> ValidationResult:
        """
        Validate forecast API response data.
        
        Args:
            response_data: Raw forecast API response data
            
        Returns:
            ValidationResult indicating if response is valid
        """
        if 'list' not in response_data:
            return ValidationResult(
                is_valid=False,
                error_message="Missing forecast data",
                suggestions=["Forecast data is unavailable"]
            )
        
        forecast_list = response_data['list']
        if not isinstance(forecast_list, list) or len(forecast_list) == 0:
            return ValidationResult(
                is_valid=False,
                error_message="Empty forecast data",
                suggestions=["No forecast data available"]
            )
        
        # Validate first forecast item
        first_item = forecast_list[0]
        required_fields = ['dt', 'main', 'weather']
        
        for field in required_fields:
            if field not in first_item:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Invalid forecast data: missing {field}",
                    suggestions=["Forecast data is malformed"]
                )
        
        return ValidationResult(
            is_valid=True,
            value=response_data,
            suggestions=[]
        )


class ErrorHandler:
    """Centralized error handling with user-friendly messages."""
    
    ERROR_MESSAGES = {
        'network_error': "Network connection failed. Please check your internet connection.",
        'api_key_invalid': "Invalid API key. Please check your OpenWeatherMap API key.",
        'api_rate_limit': "API rate limit exceeded. Please try again in a few minutes.",
        'location_not_found': "Location not found. Please check the city name and try again.",
        'api_timeout': "Request timed out. Please try again.",
        'api_server_error': "Weather service is temporarily unavailable. Please try again later.",
        'invalid_response': "Received invalid data from weather service.",
        'file_error': "Error reading or writing data files.",
        'config_error': "Configuration error. Please check your settings.",
        'unknown_error': "An unexpected error occurred."
    }
    
    @classmethod
    def get_user_friendly_error(cls, error_type: str, details: str = "") -> str:
        """
        Get user-friendly error message.
        
        Args:
            error_type: Type of error
            details: Additional error details
            
        Returns:
            Formatted error message
        """
        base_message = cls.ERROR_MESSAGES.get(error_type, cls.ERROR_MESSAGES['unknown_error'])
        
        if details:
            return f"{base_message}\nDetails: {details}"
        
        return base_message
    
    @classmethod
    def handle_api_error(cls, error: Exception) -> Tuple[str, List[str]]:
        """
        Handle API errors and provide recovery suggestions.
        
        Args:
            error: Exception that occurred
            
        Returns:
            Tuple of (error_message, suggestions)
        """
        error_str = str(error).lower()
        
        if 'timeout' in error_str:
            return (
                cls.get_user_friendly_error('api_timeout'),
                [
                    "Check your internet connection",
                    "Try again in a few moments",
                    "Use cached data if available"
                ]
            )
        elif 'rate limit' in error_str or '429' in error_str:
            return (
                cls.get_user_friendly_error('api_rate_limit'),
                [
                    "Wait a few minutes before trying again",
                    "The free API allows 60 calls per minute",
                    "Consider upgrading your API plan for higher limits"
                ]
            )
        elif 'unauthorized' in error_str or '401' in error_str:
            return (
                cls.get_user_friendly_error('api_key_invalid'),
                [
                    "Check your API key in settings",
                    "Make sure your API key is active",
                    "Get a new key from openweathermap.org"
                ]
            )
        elif 'not found' in error_str or '404' in error_str:
            return (
                cls.get_user_friendly_error('location_not_found'),
                [
                    "Check the spelling of the city name",
                    "Try adding a country code (e.g., 'Paris, FR')",
                    "Use a more specific location name"
                ]
            )
        elif 'connection' in error_str:
            return (
                cls.get_user_friendly_error('network_error'),
                [
                    "Check your internet connection",
                    "Try again in a few moments",
                    "Check if openweathermap.org is accessible"
                ]
            )
        else:
            return (
                cls.get_user_friendly_error('unknown_error', str(error)),
                [
                    "Try again in a few moments",
                    "Check the application logs for details",
                    "Report this issue if it persists"
                ]
            )


def safe_input(prompt: str, validator_func=None, max_attempts: int = 3) -> Optional[Any]:
    """
    Get user input with validation and error handling.
    
    Args:
        prompt: Input prompt to display
        validator_func: Function to validate input (returns ValidationResult)
        max_attempts: Maximum number of input attempts
        
    Returns:
        Validated input value or None if max attempts exceeded
    """
    for attempt in range(max_attempts):
        try:
            user_input = input(prompt).strip()
            
            if validator_func:
                result = validator_func(user_input)
                if result.is_valid:
                    if result.suggestions:
                        for suggestion in result.suggestions:
                            print(f"💡 {suggestion}")
                    return result.value
                else:
                    print(f"❌ {result.error_message}")
                    if result.suggestions:
                        for suggestion in result.suggestions:
                            print(f"   💡 {suggestion}")
                    
                    if attempt < max_attempts - 1:
                        print(f"   Try again ({max_attempts - attempt - 1} attempts remaining)...")
                    continue
            else:
                return user_input
                
        except (KeyboardInterrupt, EOFError):
            print("\nInput cancelled.")
            return None
        except Exception as e:
            print(f"Error reading input: {e}")
            if attempt < max_attempts - 1:
                print("Please try again...")
    
    print("❌ Too many failed attempts.")
    return None


if __name__ == "__main__":
    # Test the validation system
    print("🔍 Input Validation System Test")
    print("=" * 40)
    
    # Test city name validation
    test_cities = ["London", "New York", "123", "", "São Paulo", "test"]
    print("\nCity Name Validation:")
    for city in test_cities:
        result = InputValidator.validate_city_name(city)
        status = "✅" if result.is_valid else "❌"
        print(f"{status} '{city}': {result.error_message or 'Valid'}")
    
    # Test country code validation
    test_countries = ["US", "GB", "usa", "123", ""]
    print("\nCountry Code Validation:")
    for country in test_countries:
        result = InputValidator.validate_country_code(country)
        status = "✅" if result.is_valid else "❌"
        print(f"{status} '{country}': {result.error_message or 'Valid'}")
    
    # Test interactive input
    print("\n🎯 Interactive Input Test:")
    print("Enter a city name (test the validation):")
    city = safe_input("City: ", InputValidator.validate_city_name)
    if city:
        print(f"✅ Validated city: {city}")