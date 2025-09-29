"""
API Handler for OpenWeatherMap API integration.

This module handles all HTTP requests to the OpenWeatherMap API,
including current weather, forecasts, and historical data.
Provides comprehensive error handling and response validation.
"""

import requests
import json
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from data_structures import WeatherData, Location, ForecastData


class APIError(Exception):
    """Custom exception for API-related errors."""
    pass


class WeatherAPIHandler:
    """
    Handles all interactions with the OpenWeatherMap API.
    
    Features:
    - Current weather data retrieval
    - 5-day weather forecast
    - Geocoding for city name to coordinates conversion
    - Comprehensive error handling
    - Rate limiting awareness
    - Secure API key management
    """
    
    BASE_URL = "https://api.openweathermap.org/data/2.5"
    GEO_URL = "https://api.openweathermap.org/geo/1.0"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the API handler.
        
        Args:
            api_key: OpenWeatherMap API key. If None, will try to load from environment.
        """
        self.api_key = api_key or self._load_api_key()
        self.session = requests.Session()
        self.timeout = 10  # 10 second timeout
        
        if not self.api_key:
            raise APIError(
                "API key not found. Please set OPENWEATHER_API_KEY environment variable "
                "or provide it directly to the constructor."
            )
    
    def _load_api_key(self) -> Optional[str]:
        """
        Load API key from environment variables or config file.
        
        Priority:
        1. Environment variable OPENWEATHER_API_KEY
        2. Environment variable WEATHER_API_KEY
        3. config.json file
        4. .env file (simple key=value format)
        """
        # Try environment variables first
        api_key = os.getenv('OPENWEATHER_API_KEY') or os.getenv('WEATHER_API_KEY')
        if api_key:
            return api_key
        
        # Try config.json file
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
                return config.get('api_key')
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass
        
        # Try .env file
        try:
            with open('.env', 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('OPENWEATHER_API_KEY=') or line.startswith('API_KEY='):
                        return line.split('=', 1)[1].strip().strip('"\'')
        except FileNotFoundError:
            pass
        
        return None
    
    def _make_request(self, url: str, params: dict) -> dict:
        """
        Make a request to the API with error handling.
        
        Args:
            url: The API endpoint URL
            params: Query parameters for the request
            
        Returns:
            Parsed JSON response
            
        Raises:
            APIError: For various API-related errors
        """
        params['appid'] = self.api_key
        
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for API-specific error codes
            if 'cod' in data and str(data['cod']) != '200':
                error_msg = data.get('message', 'Unknown API error')
                raise APIError(f"API Error {data['cod']}: {error_msg}")
            
            return data
            
        except requests.exceptions.Timeout:
            raise APIError("Request timed out. Please check your internet connection.")
        except requests.exceptions.ConnectionError:
            raise APIError("Connection error. Please check your internet connection.")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise APIError("Invalid API key. Please check your OpenWeatherMap API key.")
            elif e.response.status_code == 404:
                raise APIError("Location not found. Please check the city name.")
            elif e.response.status_code == 429:
                raise APIError("API rate limit exceeded. Please try again later.")
            else:
                raise APIError(f"HTTP Error {e.response.status_code}: {e.response.reason}")
        except requests.exceptions.RequestException as e:
            raise APIError(f"Request failed: {str(e)}")
        except json.JSONDecodeError:
            raise APIError("Invalid response format from API.")
    
    def get_location_by_name(self, city_name: str, country_code: Optional[str] = None) -> Optional[Location]:
        """
        Get location coordinates by city name using geocoding API.
        
        Args:
            city_name: Name of the city
            country_code: Optional country code (e.g., 'US', 'GB')
            
        Returns:
            Location object with coordinates, or None if not found
        """
        query = city_name
        if country_code:
            query += f",{country_code}"
        
        url = f"{self.GEO_URL}/direct"
        params = {
            'q': query,
            'limit': 1
        }
        
        try:
            data = self._make_request(url, params)
            
            if not data:
                return None
            
            location_data = data[0]
            return Location(
                city=location_data['name'],
                country=location_data['country'],
                latitude=location_data['lat'],
                longitude=location_data['lon']
            )
            
        except APIError:
            return None
    
    def get_current_weather(self, location: Location) -> WeatherData:
        """
        Get current weather data for a location.
        
        Args:
            location: Location object with coordinates
            
        Returns:
            WeatherData object with current weather information
        """
        url = f"{self.BASE_URL}/weather"
        params = {
            'lat': location.latitude,
            'lon': location.longitude,
            'units': 'metric'  # Always use metric, conversion handled elsewhere
        }
        
        data = self._make_request(url, params)
        
        return WeatherData(
            city=data['name'],
            country=data['sys']['country'],
            temperature=data['main']['temp'],
            feels_like=data['main']['feels_like'],
            humidity=data['main']['humidity'],
            pressure=data['main']['pressure'],
            wind_speed=data.get('wind', {}).get('speed', 0),
            wind_direction=data.get('wind', {}).get('deg', 0),
            description=data['weather'][0]['description'].title(),
            timestamp=datetime.now()
        )
    
    def get_current_weather_by_name(self, city_name: str, country_code: Optional[str] = None) -> tuple[WeatherData, Location]:
        """
        Get current weather by city name.
        
        Args:
            city_name: Name of the city
            country_code: Optional country code
            
        Returns:
            Tuple of (WeatherData, Location)
        """
        location = self.get_location_by_name(city_name, country_code)
        if not location:
            raise APIError(f"Location '{city_name}' not found.")
        
        weather_data = self.get_current_weather(location)
        return weather_data, location
    
    def get_forecast(self, location: Location, days: int = 5) -> List[ForecastData]:
        """
        Get weather forecast for a location.
        
        Args:
            location: Location object with coordinates
            days: Number of days to forecast (max 5 for free API)
            
        Returns:
            List of ForecastData objects
        """
        url = f"{self.BASE_URL}/forecast"
        params = {
            'lat': location.latitude,
            'lon': location.longitude,
            'units': 'metric'
        }
        
        data = self._make_request(url, params)
        
        # Group forecast data by day
        daily_forecasts = {}
        
        for item in data['list']:
            dt = datetime.fromtimestamp(item['dt'])
            date_key = dt.date()
            
            if date_key not in daily_forecasts:
                daily_forecasts[date_key] = {
                    'temps': [],
                    'humidity': [],
                    'wind_speed': [],
                    'descriptions': [],
                    'precipitation': []
                }
            
            daily_forecasts[date_key]['temps'].append(item['main']['temp'])
            daily_forecasts[date_key]['humidity'].append(item['main']['humidity'])
            daily_forecasts[date_key]['wind_speed'].append(item.get('wind', {}).get('speed', 0))
            daily_forecasts[date_key]['descriptions'].append(item['weather'][0]['description'])
            
            # Calculate precipitation probability
            pop = item.get('pop', 0) * 100  # Convert to percentage
            daily_forecasts[date_key]['precipitation'].append(pop)
        
        # Convert to ForecastData objects
        forecasts = []
        for date_key in sorted(daily_forecasts.keys())[:days]:
            day_data = daily_forecasts[date_key]
            
            # Get most common description
            descriptions = day_data['descriptions']
            most_common_desc = max(set(descriptions), key=descriptions.count)
            
            forecast = ForecastData(
                date=datetime.combine(date_key, datetime.min.time()),
                temperature_min=min(day_data['temps']),
                temperature_max=max(day_data['temps']),
                humidity=int(sum(day_data['humidity']) / len(day_data['humidity'])),
                wind_speed=sum(day_data['wind_speed']) / len(day_data['wind_speed']),
                description=most_common_desc.title(),
                precipitation_chance=int(max(day_data['precipitation'])) if day_data['precipitation'] else 0
            )
            forecasts.append(forecast)
        
        return forecasts
    
    def get_forecast_by_name(self, city_name: str, country_code: Optional[str] = None, days: int = 5) -> tuple[List[ForecastData], Location]:
        """
        Get weather forecast by city name.
        
        Args:
            city_name: Name of the city
            country_code: Optional country code
            days: Number of days to forecast
            
        Returns:
            Tuple of (List[ForecastData], Location)
        """
        location = self.get_location_by_name(city_name, country_code)
        if not location:
            raise APIError(f"Location '{city_name}' not found.")
        
        forecast_data = self.get_forecast(location, days)
        return forecast_data, location
    
    def validate_api_key(self) -> bool:
        """
        Validate the API key by making a simple request.
        
        Returns:
            True if API key is valid, False otherwise
        """
        try:
            url = f"{self.BASE_URL}/weather"
            params = {
                'q': 'London',
                'units': 'metric'
            }
            self._make_request(url, params)
            return True
        except APIError:
            return False
    
    def get_api_usage_info(self) -> dict:
        """
        Get information about API usage and limits.
        Note: This is limited in the free tier.
        
        Returns:
            Dictionary with usage information
        """
        # For the free tier, we can only estimate based on response headers
        # This would be enhanced with a paid plan
        return {
            'plan': 'Free',
            'calls_per_minute': 60,
            'calls_per_month': 1000000,
            'note': 'Exact usage tracking requires paid plan'
        }


def create_sample_config():
    """Create a sample configuration file for API key setup."""
    config = {
        "api_key": "your_openweathermap_api_key_here",
        "default_units": "metric",
        "cache_duration_minutes": 10
    }
    
    with open('config.json.sample', 'w') as f:
        json.dump(config, f, indent=2)
    
    print("Sample configuration file created: config.json.sample")
    print("Copy it to config.json and add your API key.")


def create_sample_env():
    """Create a sample .env file for API key setup."""
    env_content = """# OpenWeatherMap API Configuration
# Get your free API key from: https://openweathermap.org/api
OPENWEATHER_API_KEY=your_api_key_here
"""
    
    with open('.env.sample', 'w') as f:
        f.write(env_content)
    
    print("Sample environment file created: .env.sample")
    print("Copy it to .env and add your API key.")


if __name__ == "__main__":
    # Test the API handler if run directly
    try:
        api = WeatherAPIHandler()
        print("API key loaded successfully!")
        
        if api.validate_api_key():
            print("API key is valid!")
            
            # Test current weather
            weather, location = api.get_current_weather_by_name("London")
            print(f"Current weather in {location}: {weather.temperature}°C, {weather.description}")
            
        else:
            print("API key is invalid!")
            
    except APIError as e:
        print(f"API Error: {e}")
        print("\nTo set up your API key:")
        print("1. Get a free API key from https://openweathermap.org/api")
        print("2. Set environment variable: OPENWEATHER_API_KEY=your_key")
        print("3. Or create a config.json file with your API key")
        
        create_sample_config()
        create_sample_env()