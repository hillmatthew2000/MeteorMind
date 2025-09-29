"""
Command Line Interface (CLI) for the weather application.

This module provides a clear, numbered menu-driven interface that allows users to:
- Fetch current weather for any location
- Get weather forecasts
- Manage favorite locations
- View query history
- Change unit preferences
- Configure API settings
"""

import sys
import os
from typing import Optional, List
from datetime import datetime

# Import our custom modules
from data_structures import FavoriteLocationsLinkedList, Location, WeatherData
from api_handler import WeatherAPIHandler, APIError
from data_manager import DataManager
from history_manager import HistoryManager
from unit_converter import WeatherFormatter, UnitPreferences, create_metric_preferences, create_imperial_preferences
from validation import InputValidator, safe_input, ErrorHandler
from weather_reporting import WeatherReportGenerator, ReportExporter
from config_manager import ConfigManager


class WeatherCLI:
    """
    Command Line Interface for the weather application.
    
    Features:
    - Numbered menu system for easy navigation
    - Input validation and error handling
    - Unit preference management
    - Favorite location management
    - Query history tracking
    - Comprehensive help system
    """
    
    def __init__(self):
        """Initialize the CLI application."""
        self.running = True
        self.data_manager = DataManager()
        self.history_manager = HistoryManager(self.data_manager)
        self.config_manager = ConfigManager()
        
        # Load user preferences
        user_prefs = self.data_manager.get_user_preferences()
        unit_prefs_data = user_prefs.get('units', {})
        
        # Create unit preferences
        if isinstance(unit_prefs_data, str):
            # Handle legacy string format
            if unit_prefs_data == 'imperial':
                self.unit_preferences = create_imperial_preferences()
            else:
                self.unit_preferences = create_metric_preferences()
        else:
            # Handle new dict format
            try:
                self.unit_preferences = UnitPreferences.from_dict(unit_prefs_data)
            except (KeyError, ValueError):
                self.unit_preferences = create_metric_preferences()
        
        self.formatter = WeatherFormatter(self.unit_preferences)
        self.report_generator = WeatherReportGenerator(self.formatter)
        
        # Load favorite locations
        self.favorite_locations = self.data_manager.load_favorite_locations()
        
        # Initialize API handler
        self.api_handler = None
        self._init_api_handler()
    
    def _init_api_handler(self) -> bool:
        """
        Initialize the API handler with proper error handling.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.api_handler = WeatherAPIHandler()
            return True
        except APIError as e:
            print(f"⚠️  API Configuration Issue: {e}")
            print("\nTo fix this issue:")
            print("1. Get a free API key from https://openweathermap.org/api")
            print("2. Run the setup command to configure your API key")
            print("3. Or set the OPENWEATHER_API_KEY environment variable")
            return False
    
    def display_main_menu(self) -> None:
        """Display the main menu options."""
        print("\n" + "="*60)
        print("🌤️  WEATHER APPLICATION - MAIN MENU")
        print("="*60)
        print("1. 🌡️  Get Current Weather")
        print("2. 📅 Get Weather Forecast")
        print("3. ⭐ Manage Favorite Locations")
        print("4. 📊 View Query History")
        print("5. 📈 Weather Reports & Analysis")
        print("6. ⚙️  Settings & Preferences")
        print("7. 🔧 Setup & Configuration")
        print("8. ❓ Help & Information")
        print("9. 🚪 Exit")
        print("="*60)
    
    def display_favorites_menu(self) -> None:
        """Display the favorites management menu."""
        print("\n" + "="*50)
        print("⭐ FAVORITE LOCATIONS MENU")
        print("="*50)
        print("1. 📋 View All Favorites")
        print("2. ➕ Add New Favorite")
        print("3. ❌ Remove Favorite")
        print("4. 🌡️  Get Weather for Favorite")
        print("5. 🔄 Move Favorite to Top")
        print("6. ⬅️  Back to Main Menu")
        print("="*50)
    
    def display_settings_menu(self) -> None:
        """Display the settings and preferences menu."""
        print("\n" + "="*50)
        print("⚙️  SETTINGS & PREFERENCES")
        print("="*50)
        print("1. 🌡️  Change Temperature Units")
        print("2. 💨 Change Wind Speed Units")
        print("3. 🏋️  Change Pressure Units")
        print("4. 📏 Change Distance Units")
        print("5. 📦 Quick Unit Presets")
        print("6. 📊 View Current Settings")
        print("7. 🗑️  Clear Cache")
        print("8. 🗃️  Data Management")
        print("9. ⬅️  Back to Main Menu")
        print("="*50)
    
    def display_reports_menu(self) -> None:
        """Display the weather reports and analysis menu."""
        print("\n" + "="*50)
        print("📈 WEATHER REPORTS & ANALYSIS")
        print("="*50)
        print("1. 📊 Current Weather Comparison")
        print("2. 📅 Forecast Analysis Report")
        print("3. 📍 Location Statistics")
        print("4. 📈 Temperature Trends")
        print("5. 📋 Generate Custom Report")
        print("6. 💾 Export Report Data")
        print("7. 📊 Query Statistics")
        print("8. ⬅️  Back to Main Menu")
        print("="*50)
    
    def get_menu_choice(self, max_option: int) -> Optional[int]:
        """
        Get user menu choice with validation.
        
        Args:
            max_option: Maximum valid option number
            
        Returns:
            Selected option number or None if invalid
        """
        def validate_choice(choice_str: str):
            return InputValidator.validate_numeric_input(
                choice_str, min_value=1, max_value=max_option, 
                allow_negative=False, decimal_places=0
            )
        
        choice = safe_input(f"\nEnter your choice (1-{max_option}): ", validate_choice)
        return int(choice) if choice is not None else None
    
    def get_current_weather(self) -> None:
        """Get current weather for a location."""
        print("\n🌡️  GET CURRENT WEATHER")
        print("-" * 30)
        
        if not self.api_handler:
            print("❌ API not configured. Please run setup first.")
            return
        
        # Get city name
        city = safe_input("Enter city name: ", InputValidator.validate_city_name)
        if not city:
            return
        
        # Get optional country code
        country = safe_input("Enter country code (optional, e.g., 'US', 'GB'): ", 
                           InputValidator.validate_country_code)
        
        try:
            print(f"🔍 Fetching weather for {city}" + (f", {country}" if country else "") + "...")
            
            # Check cache first
            if country:
                temp_location = Location(city, country, 0, 0)
                cached_weather = self.history_manager.get_cached_weather(temp_location)
                if cached_weather:
                    print("📦 Using cached data...")
                    self.display_weather_data(cached_weather, temp_location)
                    return
            
            # Fetch from API
            weather_data, location = self.api_handler.get_current_weather_by_name(city, country)
            
            # Cache the data
            self.history_manager.cache_weather_data(location, weather_data)
            
            # Add to query history
            self.history_manager.add_query(location, weather_data, "current")
            
            # Display the weather
            self.display_weather_data(weather_data, location)
            
            # Ask if user wants to add to favorites
            if not self.favorite_locations.find_location(location.city, location.country):
                add_favorite = input(f"\n💾 Add {location} to favorites? (y/N): ").lower().strip()
                if add_favorite in ['y', 'yes']:
                    if self.favorite_locations.add_location(location):
                        self.data_manager.save_favorite_locations(self.favorite_locations)
                        print(f"✅ Added {location} to favorites!")
                    else:
                        print(f"ℹ️  {location} is already in favorites.")
            
        except APIError as e:
            error_msg, suggestions = ErrorHandler.handle_api_error(e)
            print(f"❌ {error_msg}")
            for suggestion in suggestions:
                print(f"   💡 {suggestion}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
    
    def display_weather_data(self, weather_data: WeatherData, location: Location) -> None:
        """
        Display weather data in a formatted way.
        
        Args:
            weather_data: Weather data to display
            location: Location information
        """
        print(f"\n🌤️  CURRENT WEATHER FOR {location}")
        print("=" * 50)
        print(f"🌡️  Temperature: {self.formatter.format_temperature(weather_data.temperature)}")
        print(f"🌡️  Feels like: {self.formatter.format_temperature(weather_data.feels_like)}")
        print(f"💧 Humidity: {self.formatter.format_humidity(weather_data.humidity)}")
        print(f"🏋️  Pressure: {self.formatter.format_pressure(weather_data.pressure)}")
        print(f"💨 Wind: {self.formatter.format_wind_speed(weather_data.wind_speed)}")
        
        if weather_data.wind_direction > 0:
            print(f"🧭 Wind Direction: {self.formatter.format_wind_direction(weather_data.wind_direction)}")
        
        print(f"☁️  Conditions: {weather_data.description}")
        print(f"🕐 Updated: {weather_data.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
    
    def get_weather_forecast(self) -> None:
        """Get weather forecast for a location."""
        print("\n📅 GET WEATHER FORECAST")
        print("-" * 30)
        
        if not self.api_handler:
            print("❌ API not configured. Please run setup first.")
            return
        
        # Get city name
        city = safe_input("Enter city name: ", InputValidator.validate_city_name)
        if not city:
            return
        
        # Get optional country code
        country = safe_input("Enter country code (optional): ", 
                           InputValidator.validate_country_code)
        
        # Get number of days
        def validate_days(days_str):
            return InputValidator.validate_numeric_input(
                days_str, min_value=1, max_value=5, allow_negative=False, decimal_places=0
            )
        
        days = safe_input("Number of days (1-5, default 5): ", validate_days)
        if days is None:
            days = 5
        days = int(days)
        
        try:
            print(f"🔍 Fetching {days}-day forecast for {city}" + (f", {country}" if country else "") + "...")
            
            forecast_data, location = self.api_handler.get_forecast_by_name(city, country, days)
            
            # Cache the data
            self.history_manager.cache_forecast_data(location, forecast_data)
            
            # Add to query history
            self.history_manager.add_query(location, None, "forecast")
            
            # Display the forecast
            self.display_forecast_data(forecast_data, location)
            
        except APIError as e:
            error_msg, suggestions = ErrorHandler.handle_api_error(e)
            print(f"❌ {error_msg}")
            for suggestion in suggestions:
                print(f"   💡 {suggestion}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
    
    def display_forecast_data(self, forecast_data: List, location: Location) -> None:
        """
        Display forecast data in a formatted table.
        
        Args:
            forecast_data: List of forecast data
            location: Location information
        """
        print(f"\n📅 {len(forecast_data)}-DAY FORECAST FOR {location}")
        print("=" * 80)
        print(f"{'Date':<12} {'High':<8} {'Low':<8} {'Humidity':<10} {'Wind':<12} {'Conditions':<20}")
        print("-" * 80)
        
        for forecast in forecast_data:
            date_str = forecast.date.strftime('%m/%d')
            high_temp = self.formatter.format_temperature(forecast.temperature_max, show_unit=False)
            low_temp = self.formatter.format_temperature(forecast.temperature_min, show_unit=False)
            humidity = self.formatter.format_humidity(forecast.humidity)
            wind = self.formatter.format_wind_speed(forecast.wind_speed, show_unit=False)
            conditions = forecast.description[:18] + "..." if len(forecast.description) > 18 else forecast.description
            
            print(f"{date_str:<12} {high_temp:<8} {low_temp:<8} {humidity:<10} {wind:<12} {conditions:<20}")
            
            if forecast.precipitation_chance > 0:
                print(f"{'':12} 🌧️  {forecast.precipitation_chance}% chance of precipitation")
        
        print("=" * 80)
        
        # Show units legend
        temp_unit = "°F" if self.unit_preferences.temperature.value == "fahrenheit" else "°C"
        wind_unit = self.formatter.format_wind_speed(0, show_unit=True).split()[-1]
        print(f"💡 Temperature in {temp_unit}, Wind speed in {wind_unit}")
    
    def manage_favorites(self) -> None:
        """Manage favorite locations submenu."""
        while True:
            self.display_favorites_menu()
            choice = self.get_menu_choice(6)
            
            if choice == 1:
                self.view_favorites()
            elif choice == 2:
                self.add_favorite()
            elif choice == 3:
                self.remove_favorite()
            elif choice == 4:
                self.get_weather_for_favorite()
            elif choice == 5:
                self.move_favorite_to_top()
            elif choice == 6:
                break
            else:
                print("❌ Invalid choice. Please try again.")
    
    def view_favorites(self) -> None:
        """Display all favorite locations."""
        locations = self.favorite_locations.get_all_locations()
        
        if not locations:
            print("\n📭 No favorite locations saved.")
            print("💡 Add some favorites to quickly access weather for your preferred cities!")
            return
        
        print(f"\n⭐ YOUR FAVORITE LOCATIONS ({len(locations)} total)")
        print("=" * 60)
        
        for i, location in enumerate(locations, 1):
            added_date = location.added_date.strftime('%Y-%m-%d')
            print(f"{i:2d}. {location.city:<20} {location.country:<5} (Added: {added_date})")
            print(f"    📍 {location.latitude:.2f}, {location.longitude:.2f}")
        
        print("=" * 60)
    
    def add_favorite(self) -> None:
        """Add a new favorite location."""
        print("\n➕ ADD NEW FAVORITE LOCATION")
        print("-" * 30)
        
        if not self.api_handler:
            print("❌ API not configured. Cannot verify location.")
            return
        
        # Get city name
        city = safe_input("Enter city name: ", InputValidator.validate_city_name)
        if not city:
            return
        
        # Get optional country code
        country = safe_input("Enter country code (optional, recommended): ", 
                           InputValidator.validate_country_code)
        
        try:
            print(f"🔍 Verifying location: {city}" + (f", {country}" if country else "") + "...")
            
            # Verify location exists by fetching its coordinates
            location = self.api_handler.get_location_by_name(city, country)
            if not location:
                print(f"❌ Could not find location: {city}")
                return
            
            # Try to add to favorites
            if self.favorite_locations.add_location(location):
                self.data_manager.save_favorite_locations(self.favorite_locations)
                print(f"✅ Added {location} to favorites!")
                print(f"📍 Coordinates: {location.latitude:.2f}, {location.longitude:.2f}")
            else:
                print(f"ℹ️  {location} is already in your favorites.")
                
        except APIError as e:
            error_msg, suggestions = ErrorHandler.handle_api_error(e)
            print(f"❌ {error_msg}")
            for suggestion in suggestions:
                print(f"   💡 {suggestion}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
    
    def remove_favorite(self) -> None:
        """Remove a favorite location."""
        locations = self.favorite_locations.get_all_locations()
        
        if not locations:
            print("\n📭 No favorite locations to remove.")
            return
        
        print("\n❌ REMOVE FAVORITE LOCATION")
        print("-" * 30)
        
        # Display numbered list
        for i, location in enumerate(locations, 1):
            print(f"{i}. {location}")
        
        def validate_selection(selection_str):
            return InputValidator.validate_numeric_input(
                selection_str, min_value=1, max_value=len(locations), 
                allow_negative=False, decimal_places=0
            )
        
        selection = safe_input(f"Enter number to remove (1-{len(locations)}): ", validate_selection)
        if selection is None:
            return
        
        selection = int(selection) - 1
        location_to_remove = locations[selection]
        
        # Confirm removal
        confirm = input(f"❓ Really remove '{location_to_remove}' from favorites? (y/N): ").lower().strip()
        if confirm in ['y', 'yes']:
            if self.favorite_locations.remove_location(location_to_remove.city, location_to_remove.country):
                self.data_manager.save_favorite_locations(self.favorite_locations)
                print(f"✅ Removed {location_to_remove} from favorites.")
            else:
                print(f"❌ Could not remove {location_to_remove}.")
        else:
            print("❌ Removal cancelled.")
    
    def get_weather_for_favorite(self) -> None:
        """Get weather for a favorite location."""
        locations = self.favorite_locations.get_all_locations()
        
        if not locations:
            print("\n📭 No favorite locations available.")
            return
        
        if not self.api_handler:
            print("❌ API not configured.")
            return
        
        print("\n🌡️  GET WEATHER FOR FAVORITE")
        print("-" * 30)
        
        # Display numbered list
        for i, location in enumerate(locations, 1):
            print(f"{i}. {location}")
        
        def validate_selection(selection_str):
            return InputValidator.validate_numeric_input(
                selection_str, min_value=1, max_value=len(locations), 
                allow_negative=False, decimal_places=0
            )
        
        selection = safe_input(f"Select location (1-{len(locations)}): ", validate_selection)
        if selection is None:
            return
        
        selection = int(selection) - 1
        location = locations[selection]
        
        try:
            print(f"🔍 Fetching weather for {location}...")
            
            # Check cache first
            cached_weather = self.history_manager.get_cached_weather(location)
            if cached_weather:
                print("📦 Using cached data...")
                self.display_weather_data(cached_weather, location)
                
                # Move to front of favorites (most recently accessed)
                self.favorite_locations.move_to_front(location.city, location.country)
                self.data_manager.save_favorite_locations(self.favorite_locations)
                return
            
            # Fetch from API
            weather_data = self.api_handler.get_current_weather(location)
            
            # Cache and track
            self.history_manager.cache_weather_data(location, weather_data)
            self.history_manager.add_query(location, weather_data, "current")
            
            # Display weather
            self.display_weather_data(weather_data, location)
            
            # Move to front of favorites
            self.favorite_locations.move_to_front(location.city, location.country)
            self.data_manager.save_favorite_locations(self.favorite_locations)
            
        except APIError as e:
            error_msg, suggestions = ErrorHandler.handle_api_error(e)
            print(f"❌ {error_msg}")
            for suggestion in suggestions:
                print(f"   💡 {suggestion}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
    
    def move_favorite_to_top(self) -> None:
        """Move a favorite location to the top of the list."""
        locations = self.favorite_locations.get_all_locations()
        
        if len(locations) <= 1:
            print("\n📭 Need at least 2 favorites to reorder.")
            return
        
        print("\n🔄 MOVE FAVORITE TO TOP")
        print("-" * 30)
        
        # Display numbered list (skip first item since it's already at top)
        for i, location in enumerate(locations, 1):
            print(f"{i}. {location}")
        
        def validate_selection(selection_str):
            return InputValidator.validate_numeric_input(
                selection_str, min_value=2, max_value=len(locations), 
                allow_negative=False, decimal_places=0
            )
        
        selection = safe_input(f"Select location to move to top (2-{len(locations)}): ", validate_selection)
        if selection is None:
            return
        
        selection = int(selection) - 1
        location = locations[selection]
        
        if self.favorite_locations.move_to_front(location.city, location.country):
            self.data_manager.save_favorite_locations(self.favorite_locations)
            print(f"✅ Moved {location} to top of favorites.")
        else:
            print(f"❌ Could not move {location}.")
    
    def view_query_history(self) -> None:
        """Display query history and statistics."""
        print("\n📊 QUERY HISTORY & STATISTICS")
        print("=" * 50)
        
        # Print recent queries
        self.history_manager.print_recent_queries(15)
        
        # Print statistics
        self.history_manager.print_statistics()
        
        # Options for history management
        print("\nHistory Options:")
        print("1. Export history to file")
        print("2. Clear history")
        print("3. Search history")
        print("4. Back to main menu")
        
        choice = self.get_menu_choice(4)
        if choice == 1:
            self.export_history()
        elif choice == 2:
            self.clear_history()
        elif choice == 3:
            self.search_history()
    
    def export_history(self) -> None:
        """Export query history to a file."""
        filename = f"weather_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = safe_input(f"Enter filename (default: {filename}): ")
        
        if not filepath:
            filepath = filename
        
        if self.history_manager.export_history(filepath):
            print(f"✅ History exported to: {filepath}")
        else:
            print("❌ Failed to export history.")
    
    def clear_history(self) -> None:
        """Clear query history with confirmation."""
        confirm = input("❓ Really clear all query history? This cannot be undone. (y/N): ").lower().strip()
        if confirm in ['y', 'yes']:
            if self.history_manager.clear_history():
                print("✅ Query history cleared.")
            else:
                print("❌ Failed to clear history.")
        else:
            print("❌ History clearing cancelled.")
    
    def search_history(self) -> None:
        """Search query history."""
        search_term = safe_input("Enter city or country to search for: ")
        if not search_term:
            return
        
        results = self.history_manager.search_queries(search_term, limit=20)
        
        if not results:
            print(f"❌ No queries found for '{search_term}'.")
            return
        
        print(f"\n🔍 SEARCH RESULTS FOR '{search_term}' ({len(results)} found)")
        print("-" * 60)
        
        for i, query in enumerate(results, 1):
            time_str = query.query_time.strftime("%Y-%m-%d %H:%M")
            location_str = f"{query.location.city}, {query.location.country}"
            print(f"{i:2d}. {time_str} | {location_str} | {query.query_type}")
    
    def manage_settings(self) -> None:
        """Manage settings and preferences submenu."""
        while True:
            self.display_settings_menu()
            choice = self.get_menu_choice(9)
            
            if choice == 1:
                self.change_temperature_units()
            elif choice == 2:
                self.change_wind_speed_units()
            elif choice == 3:
                self.change_pressure_units()
            elif choice == 4:
                self.change_distance_units()
            elif choice == 5:
                self.quick_unit_presets()
            elif choice == 6:
                self.view_current_settings()
            elif choice == 7:
                self.clear_cache()
            elif choice == 8:
                self.data_management()
            elif choice == 9:
                break
            else:
                print("❌ Invalid choice. Please try again.")
    
    def change_temperature_units(self) -> None:
        """Change temperature units."""
        from unit_converter import TemperatureUnit
        
        print("\n🌡️  CHANGE TEMPERATURE UNITS")
        print("-" * 30)
        print("1. Celsius (°C)")
        print("2. Fahrenheit (°F)")
        print("3. Kelvin (K)")
        
        choice = self.get_menu_choice(3)
        if choice is None:
            return
        
        unit_map = {
            1: TemperatureUnit.CELSIUS,
            2: TemperatureUnit.FAHRENHEIT,
            3: TemperatureUnit.KELVIN
        }
        
        self.unit_preferences.temperature = unit_map[choice]
        self.formatter = WeatherFormatter(self.unit_preferences)
        self.save_preferences()
        print(f"✅ Temperature units changed to {self.unit_preferences.temperature.value.title()}")
    
    def save_preferences(self) -> None:
        """Save current preferences to storage."""
        user_prefs = self.data_manager.get_user_preferences()
        user_prefs['units'] = self.unit_preferences.to_dict()
        self.data_manager.save_user_preferences(user_prefs)
    
    def quick_unit_presets(self) -> None:
        """Set quick unit presets (metric/imperial)."""
        print("\n📦 QUICK UNIT PRESETS")
        print("-" * 25)
        print("1. Metric (°C, m/s, hPa, km)")
        print("2. Imperial (°F, mph, inHg, miles)")
        
        choice = self.get_menu_choice(2)
        if choice is None:
            return
        
        if choice == 1:
            self.unit_preferences = create_metric_preferences()
            print("✅ Switched to metric units")
        elif choice == 2:
            self.unit_preferences = create_imperial_preferences()
            print("✅ Switched to imperial units")
        
        self.formatter = WeatherFormatter(self.unit_preferences)
        self.save_preferences()
    
    def view_current_settings(self) -> None:
        """Display current settings and preferences."""
        print("\n📊 CURRENT SETTINGS")
        print("=" * 40)
        print(self.formatter.get_unit_preferences_display())
        
        # Show data statistics
        print("\n" + "="*40)
        from data_manager import print_data_statistics
        print_data_statistics(self.data_manager)
        
        # Show configuration status
        print("\n" + "="*40)
        self.config_manager.print_configuration_status()
    
    def clear_cache(self) -> None:
        """Clear weather data cache."""
        confirm = input("❓ Clear weather cache? (y/N): ").lower().strip()
        if confirm in ['y', 'yes']:
            if self.history_manager.clear_cache():
                print("✅ Cache cleared successfully.")
            else:
                print("❌ Failed to clear cache.")
        else:
            print("❌ Cache clearing cancelled.")
    
    def data_management(self) -> None:
        """Data management options."""
        print("\n🗃️  DATA MANAGEMENT")
        print("-" * 25)
        print("1. Backup all data")
        print("2. View data statistics")
        print("3. Clear all application data")
        print("4. Back to settings")
        
        choice = self.get_menu_choice(4)
        
        if choice == 1:
            if self.data_manager.backup_all_data():
                print("✅ Data backup created successfully.")
            else:
                print("❌ Failed to create backup.")
        elif choice == 2:
            from data_manager import print_data_statistics
            print_data_statistics(self.data_manager)
        elif choice == 3:
            self.clear_all_data()
    
    def clear_all_data(self) -> None:
        """Clear all application data with confirmation."""
        print("\n⚠️  WARNING: This will delete ALL application data including:")
        print("   • Favorite locations")
        print("   • Query history")
        print("   • User preferences")
        print("   • Cached weather data")
        print("\nThis action CANNOT be undone!")
        
        confirm1 = input("\nType 'DELETE' to confirm: ").strip()
        if confirm1 != 'DELETE':
            print("❌ Data clearing cancelled.")
            return
        
        confirm2 = input("Are you absolutely sure? (yes/no): ").lower().strip()
        if confirm2 != 'yes':
            print("❌ Data clearing cancelled.")
            return
        
        try:
            # Clear favorites
            self.favorite_locations = FavoriteLocationsLinkedList()
            self.data_manager.save_favorite_locations(self.favorite_locations)
            
            # Clear history and cache
            self.history_manager.clear_history()
            self.history_manager.clear_cache()
            
            # Reset preferences
            self.unit_preferences = create_metric_preferences()
            self.save_preferences()
            
            print("✅ All application data has been cleared.")
            
        except Exception as e:
            print(f"❌ Error clearing data: {e}")
    
    def show_help(self) -> None:
        """Display help and information."""
        help_text = """
🌤️  WEATHER APPLICATION HELP

GETTING STARTED:
1. First time? Run 'Setup & Configuration' to set up your API key
2. Get a free API key from: https://openweathermap.org/api
3. Add some favorite locations for quick access

MAIN FEATURES:
• Current Weather: Get real-time weather for any city
• Weather Forecast: 5-day weather forecast with details
• Favorites: Save frequently checked locations
• History: Track your weather queries over time
• Units: Switch between metric and imperial units

TIPS:
• Use country codes (US, GB, CA) for better location accuracy
• Data is cached for 10 minutes to reduce API calls
• Favorites are sorted by most recently accessed
• Export your query history for analysis

KEYBOARD SHORTCUTS:
• Ctrl+C: Cancel current operation
• Enter: Accept default values when available

TROUBLESHOOTING:
• "API key invalid": Check your OpenWeatherMap API key
• "Location not found": Try using a country code
• "Rate limit exceeded": Wait a few minutes, free tier allows 60 calls/minute
• "Network error": Check your internet connection

DATA STORAGE:
• All data is stored locally in the 'data' folder
• Favorites, history, and preferences are automatically saved
• Use 'Data Management' to backup or clear data

For more help, visit: https://openweathermap.org/api
"""
        print(help_text)
        input("\nPress Enter to continue...")
    
    def setup_configuration(self) -> None:
        """Setup and configuration menu."""
        print("\n🔧 SETUP & CONFIGURATION")
        print("-" * 30)
        
        # Show current status
        self.config_manager.print_configuration_status()
        
        print("\nSetup Options:")
        print("1. Configure API key")
        print("2. Test API connection")
        print("3. View setup instructions")
        print("4. Reset configuration")
        print("5. Back to main menu")
        
        choice = self.get_menu_choice(5)
        
        if choice == 1:
            self.configure_api_key()
        elif choice == 2:
            self.test_api_connection()
        elif choice == 3:
            print(self.config_manager.get_setup_instructions())
            input("\nPress Enter to continue...")
        elif choice == 4:
            self.reset_configuration()
        elif choice == 5:
            return
    
    def configure_api_key(self) -> None:
        """Configure API key interactively."""
        from config_manager import interactive_setup
        interactive_setup()
        
        # Reinitialize API handler
        self._init_api_handler()
    
    def test_api_connection(self) -> None:
        """Test API connection and key validity."""
        if not self.api_handler:
            print("❌ API handler not initialized. Please configure your API key first.")
            return
        
        print("🔍 Testing API connection...")
        
        try:
            if self.api_handler.validate_api_key():
                print("✅ API connection successful!")
                
                # Test a simple request
                weather_data, location = self.api_handler.get_current_weather_by_name("London", "GB")
                print(f"✅ Test query successful: {weather_data.temperature}°C in {location}")
                
            else:
                print("❌ API key validation failed.")
                
        except APIError as e:
            error_msg, suggestions = ErrorHandler.handle_api_error(e)
            print(f"❌ {error_msg}")
            for suggestion in suggestions:
                print(f"   💡 {suggestion}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
    
    def reset_configuration(self) -> None:
        """Reset all configuration with confirmation."""
        confirm = input("❓ Reset all configuration? This will clear API key settings. (y/N): ").lower().strip()
        if confirm in ['y', 'yes']:
            # Clear config files
            try:
                if os.path.exists('config.json'):
                    os.remove('config.json')
                if os.path.exists('.env'):
                    os.remove('.env')
                print("✅ Configuration reset. Please reconfigure your API key.")
                self.api_handler = None
            except Exception as e:
                print(f"❌ Error resetting configuration: {e}")
        else:
            print("❌ Configuration reset cancelled.")
    
    def run(self) -> None:
        """Main application loop."""
        print("🌤️  Welcome to the Weather Application!")
        print("Get current weather, forecasts, and manage your favorite locations.")
        
        # Show initial setup message if API not configured
        if not self.api_handler:
            print("\n⚠️  First time setup required:")
            print("Please configure your OpenWeatherMap API key to get started.")
            print("Choose 'Setup & Configuration' from the main menu.")
        
        while self.running:
            try:
                self.display_main_menu()
                choice = self.get_menu_choice(9)
                
                if choice == 1:
                    self.get_current_weather()
                elif choice == 2:
                    self.get_weather_forecast()
                elif choice == 3:
                    self.manage_favorites()
                elif choice == 4:
                    self.view_query_history()
                elif choice == 5:
                    self.manage_reports()
                elif choice == 6:
                    self.manage_settings()
                elif choice == 7:
                    self.setup_configuration()
                elif choice == 8:
                    self.show_help()
                elif choice == 9:
                    self.running = False
                else:
                    print("❌ Invalid choice. Please try again.")
                    
            except KeyboardInterrupt:
                print("\n\n👋 Application interrupted. Goodbye!")
                self.running = False
            except Exception as e:
                print(f"\n❌ Unexpected error: {e}")
                print("The application will continue running.")
        
        print("\n👋 Thank you for using the Weather Application!")
        print("Have a great day! 🌤️")

    def manage_reports(self) -> None:
        """Handle weather reports and analysis menu."""
        while True:
            try:
                self.display_reports_menu()
                choice = self.get_menu_choice(8)
                
                if choice == 1:
                    self.generate_weather_comparison_report()
                elif choice == 2:
                    self.generate_forecast_analysis_report()
                elif choice == 3:
                    self.generate_location_statistics_report()
                elif choice == 4:
                    self.generate_temperature_trends_report()
                elif choice == 5:
                    self.generate_custom_report()
                elif choice == 6:
                    self.export_report_data()
                elif choice == 7:
                    self.view_query_statistics()
                elif choice == 8:
                    break
                else:
                    print("❌ Invalid choice. Please try again.")
                    
            except KeyboardInterrupt:
                print("\n⚠️  Operation cancelled.")
                break
            except Exception as e:
                print(f"❌ Error in reports menu: {e}")
    
    def generate_weather_comparison_report(self) -> None:
        """Generate a current weather comparison report."""
        print("\n📊 CURRENT WEATHER COMPARISON REPORT")
        print("=" * 50)
        
        if not self.api_handler:
            print("❌ API not configured. Please configure your API key first.")
            return
        
        if self.favorite_locations.size == 0:
            print("❌ No favorite locations found.")
            print("Add some favorites first to generate a comparison report.")
            return
        
        locations_data = []
        print("Fetching current weather for all favorite locations...")
        
        # Get weather for all favorites
        for location in self.favorite_locations.get_all_locations():
            try:
                print(f"  • Fetching {location.city}, {location.country}...")
                weather_data, _ = self.api_handler.get_current_weather_by_name(
                    location.city, location.country
                )
                locations_data.append((location, weather_data))
                
                # Cache the data
                self.history_manager.cache_weather_data(location, weather_data)
                
            except Exception as e:
                print(f"    ⚠️  Failed to fetch {location.city}: {e}")
        
        if not locations_data:
            print("❌ No weather data could be retrieved.")
            return
        
        # Generate and display report
        report = self.report_generator.generate_current_weather_report(locations_data)
        print("\n" + report.to_table_string())
        
        # Ask if user wants to export
        export_choice = safe_input("\n💾 Export this report? (y/N): ")
        if export_choice and export_choice.lower() == 'y':
            self._export_report(report, "weather_comparison")
    
    def generate_forecast_analysis_report(self) -> None:
        """Generate a forecast analysis report."""
        print("\n📅 FORECAST ANALYSIS REPORT")
        print("=" * 50)
        
        # Get location
        location_name = safe_input("Enter city name: ").strip()
        if not location_name:
            print("❌ City name is required.")
            return
        
        country = safe_input("Enter country code (optional): ").strip() or None
        
        # Validate inputs
        city_result = InputValidator.validate_city_name(location_name)
        if not city_result.is_valid:
            print(f"❌ Invalid city name: {city_result.error_message}")
            return
        
        if country:
            country_result = InputValidator.validate_country_code(country)
            if not country_result.is_valid:
                print(f"❌ Invalid country code: {country_result.error_message}")
                return
            country = country_result.value
        
        try:
            print(f"Fetching 5-day forecast for {location_name}...")
            forecast_data, location = self.api_handler.get_forecast_by_name(
                location_name, country, 5
            )
            
            # Generate and display report
            report = self.report_generator.generate_detailed_forecast_report(location, forecast_data)
            print("\n" + report.to_table_string())
            
            # Cache the data
            self.history_manager.cache_forecast_data(location, forecast_data)
            self.history_manager.add_query(location, None, "forecast")
            
            # Ask if user wants to export
            export_choice = safe_input("\n💾 Export this report? (y/N): ").lower()
            if export_choice == 'y':
                self._export_report(report, f"forecast_{location.city.lower()}")
                
        except APIError as e:
            error_msg, suggestions = ErrorHandler.handle_api_error(e)
            print(f"❌ API Error: {error_msg}")
            if suggestions:
                print("💡 Suggestions:")
                for suggestion in suggestions:
                    print(f"  • {suggestion}")
        except Exception as e:
            print(f"❌ Error generating forecast report: {e}")
    
    def generate_location_statistics_report(self) -> None:
        """Generate a location usage statistics report."""
        print("\n📍 LOCATION STATISTICS REPORT")
        print("=" * 50)
        
        queries = self.history_manager.get_recent_queries(1000)  # Get lots of history
        
        if not queries:
            print("❌ No query history found.")
            print("Make some weather queries first to generate statistics.")
            return
        
        # Generate and display report
        report = self.report_generator.generate_location_statistics_report(queries)
        print("\n" + report.to_table_string())
        
        # Ask if user wants to export
        export_choice = safe_input("\n💾 Export this report? (y/N): ").lower()
        if export_choice == 'y':
            self._export_report(report, "location_statistics")
    
    def generate_temperature_trends_report(self) -> None:
        """Generate a temperature trends report for a location."""
        print("\n📈 TEMPERATURE TRENDS REPORT")
        print("=" * 50)
        
        # Get location
        location_name = safe_input("Enter city name: ").strip()
        if not location_name:
            print("❌ City name is required.")
            return
        
        country = safe_input("Enter country code (optional): ").strip() or None
        
        # Validate inputs
        city_result = InputValidator.validate_city_name(location_name)
        if not city_result.is_valid:
            print(f"❌ Invalid city name: {city_result.error_message}")
            return
        
        if country:
            country_result = InputValidator.validate_country_code(country)
            if not country_result.is_valid:
                print(f"❌ Invalid country code: {country_result.error_message}")
                return
            country = country_result.value
        
        # Find matching queries in history
        queries = self.history_manager.get_recent_queries(1000)
        matching_queries = []
        
        for query in queries:
            if (query.location.city.lower() == location_name.lower() and 
                (not country or query.location.country.lower() == country.lower()) and
                query.weather_data):
                matching_queries.append((query.query_time, query.weather_data))
        
        if len(matching_queries) < 2:
            print(f"❌ Not enough historical data for {location_name}.")
            print("At least 2 weather queries are needed for trend analysis.")
            return
        
        # Create a location object for the report
        try:
            location = self.api_handler.get_location_by_name(location_name, country)
        except:
            # Fallback location if API fails
            from data_structures import Location
            location = Location(location_name, country or "Unknown", 0, 0)
        
        # Generate and display report
        report = self.report_generator.generate_temperature_trend_report(location, matching_queries)
        print("\n" + report.to_table_string())
        
        # Ask if user wants to export
        export_choice = safe_input("\n💾 Export this report? (y/N): ").lower()
        if export_choice == 'y':
            self._export_report(report, f"temperature_trends_{location.city.lower()}")
    
    def generate_custom_report(self) -> None:
        """Generate a custom report based on user selection."""
        print("\n📋 CUSTOM REPORT GENERATOR")
        print("=" * 50)
        print("1. 🌍 Multi-location current weather")
        print("2. 📅 Multi-location forecast comparison")
        print("3. 📊 Historical query analysis")
        print("4. ⬅️  Back to reports menu")
        
        choice = self.get_menu_choice(4)
        
        if choice == 1:
            self._generate_multi_location_current_report()
        elif choice == 2:
            self._generate_multi_location_forecast_report()
        elif choice == 3:
            self._generate_historical_analysis_report()
        elif choice == 4:
            return
    
    def _generate_multi_location_current_report(self) -> None:
        """Generate current weather report for multiple user-specified locations."""
        print("\n🌍 MULTI-LOCATION CURRENT WEATHER REPORT")
        print("=" * 50)
        
        locations_input = safe_input("Enter cities (comma-separated, e.g., 'London,GB Paris,FR Tokyo,JP'): ").strip()
        if not locations_input:
            print("❌ No locations entered.")
            return
        
        locations_data = []
        city_entries = [city.strip() for city in locations_input.split(',')]
        
        for city_entry in city_entries:
            parts = city_entry.split(',')
            city = parts[0].strip()
            country = parts[1].strip() if len(parts) > 1 else None
            
            if not city:
                continue
            
            try:
                print(f"  • Fetching {city}...")
                weather_data, location = self.api_handler.get_current_weather_by_name(city, country)
                locations_data.append((location, weather_data))
                
                # Cache and track
                self.history_manager.cache_weather_data(location, weather_data)
                self.history_manager.add_query(location, weather_data, "current")
                
            except Exception as e:
                print(f"    ⚠️  Failed to fetch {city}: {e}")
        
        if not locations_data:
            print("❌ No weather data could be retrieved.")
            return
        
        # Generate and display report
        report = self.report_generator.generate_current_weather_report(locations_data)
        print("\n" + report.to_table_string())
        
        # Ask if user wants to export
        export_choice = safe_input("\n💾 Export this report? (y/N): ").lower()
        if export_choice == 'y':
            self._export_report(report, "multi_location_current")
    
    def _generate_multi_location_forecast_report(self) -> None:
        """Generate forecast comparison for multiple locations."""
        print("\n📅 MULTI-LOCATION FORECAST COMPARISON")
        print("=" * 50)
        
        locations_input = safe_input("Enter cities (comma-separated): ").strip()
        if not locations_input:
            print("❌ No locations entered.")
            return
        
        forecasts_data = []
        city_entries = [city.strip() for city in locations_input.split(',')]
        
        for city_entry in city_entries:
            parts = city_entry.split(',')
            city = parts[0].strip()
            country = parts[1].strip() if len(parts) > 1 else None
            
            if not city:
                continue
            
            try:
                print(f"  • Fetching 5-day forecast for {city}...")
                forecast_data, location = self.api_handler.get_forecast_by_name(city, country, 5)
                forecasts_data.append((location, forecast_data))
                
                # Cache the data
                self.history_manager.cache_forecast_data(location, forecast_data)
                self.history_manager.add_query(location, None, "forecast")
                
            except Exception as e:
                print(f"    ⚠️  Failed to fetch forecast for {city}: {e}")
        
        if not forecasts_data:
            print("❌ No forecast data could be retrieved.")
            return
        
        # Generate and display report
        report = self.report_generator.generate_forecast_comparison_report(forecasts_data)
        print("\n" + report.to_table_string())
        
        # Ask if user wants to export
        export_choice = safe_input("\n💾 Export this report? (y/N): ").lower()
        if export_choice == 'y':
            self._export_report(report, "multi_location_forecast")
    
    def _generate_historical_analysis_report(self) -> None:
        """Generate historical query analysis report."""
        print("\n📊 HISTORICAL QUERY ANALYSIS")
        print("=" * 50)
        
        limit_input = safe_input("Number of recent queries to analyze (default 50): ").strip()
        try:
            limit = int(limit_input) if limit_input else 50
            limit = max(1, min(limit, 1000))  # Clamp between 1 and 1000
        except ValueError:
            limit = 50
        
        queries = self.history_manager.get_recent_queries(limit)
        
        if not queries:
            print("❌ No query history found.")
            return
        
        # Generate and display report
        report = self.report_generator.generate_query_history_report(queries, limit)
        print("\n" + report.to_table_string())
        
        # Ask if user wants to export
        export_choice = safe_input("\n💾 Export this report? (y/N): ").lower()
        if export_choice == 'y':
            self._export_report(report, "historical_analysis")
    
    def export_report_data(self) -> None:
        """Export weather data in various formats."""
        print("\n💾 EXPORT REPORT DATA")
        print("=" * 50)
        print("1. 📄 Export recent queries (JSON)")
        print("2. 📊 Export favorites list (CSV)")
        print("3. 📈 Export query statistics (JSON)")
        print("4. 💾 Export all data (Backup)")
        print("5. ⬅️  Back to reports menu")
        
        choice = self.get_menu_choice(5)
        
        if choice == 1:
            self._export_recent_queries()
        elif choice == 2:
            self._export_favorites_list()
        elif choice == 3:
            self._export_query_statistics()
        elif choice == 4:
            self._export_all_data()
        elif choice == 5:
            return
    
    def view_query_statistics(self) -> None:
        """Display detailed query statistics."""
        print("\n📊 QUERY STATISTICS")
        print("=" * 50)
        
        stats = self.history_manager.get_query_statistics()
        
        print(f"Total Queries: {stats['total_queries']}")
        print(f"Unique Locations: {len(stats.get('unique_locations', []))}")
        
        if stats.get('most_queried_locations'):
            print("\n🏆 Most Queried Locations:")
            for i, (location, count) in enumerate(stats['most_queried_locations'][:10], 1):
                print(f"  {i:2d}. {location}: {count} queries")
        
        cache_stats = stats.get('cache_stats', {})
        if cache_stats:
            print(f"\n💾 Cache Statistics:")
            print(f"  Valid Entries: {cache_stats.get('valid_entries', 0)}")
            print(f"  Expired Entries: {cache_stats.get('expired_entries', 0)}")
            print(f"  Cache Hit Rate: {cache_stats.get('hit_rate', 0):.1f}%")
        
        if stats.get('query_types'):
            print(f"\n📊 Query Types:")
            for query_type, count in stats['query_types'].items():
                print(f"  {query_type.title()}: {count}")
        
        print("\n" + "=" * 50)
        input("Press Enter to continue...")
    
    def _export_report(self, report, base_filename: str) -> None:
        """Export a report to file with format selection."""
        print("\n💾 EXPORT REPORT")
        print("=" * 30)
        print("1. 📄 Plain Text (.txt)")
        print("2. 📊 CSV (.csv)")
        print("3. 📋 JSON (.json)")
        
        format_choice = self.get_menu_choice(3)
        
        if format_choice == 1:
            format_type = "txt"
        elif format_choice == 2:
            format_type = "csv"
        elif format_choice == 3:
            format_type = "json"
        else:
            print("❌ Invalid choice.")
            return
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{base_filename}_{timestamp}.{format_type}"
        
        try:
            from weather_reporting import ReportExporter
            if ReportExporter.export_to_file(report, filename, format_type):
                print(f"✅ Report exported to: {filename}")
            else:
                print("❌ Failed to export report.")
        except Exception as e:
            print(f"❌ Error exporting report: {e}")
    
    def _export_recent_queries(self) -> None:
        """Export recent queries to JSON."""
        try:
            filename = f"weather_queries_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            if self.history_manager.export_history(filename):
                print(f"✅ Recent queries exported to: {filename}")
            else:
                print("❌ Failed to export queries.")
        except Exception as e:
            print(f"❌ Error exporting queries: {e}")
    
    def _export_favorites_list(self) -> None:
        """Export favorites list to CSV."""
        try:
            favorites = self.favorite_locations.get_all_locations()
            filename = f"weather_favorites_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("City,Country,Latitude,Longitude,Date Added\n")
                for location in favorites:
                    f.write(f'"{location.city}","{location.country}",{location.latitude},{location.longitude},"{location.added_date.strftime("%Y-%m-%d")}"\n')
            
            print(f"✅ Favorites exported to: {filename}")
        except Exception as e:
            print(f"❌ Error exporting favorites: {e}")
    
    def _export_query_statistics(self) -> None:
        """Export query statistics to JSON."""
        try:
            stats = self.history_manager.get_query_statistics()
            filename = f"weather_statistics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            import json
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"✅ Query statistics exported to: {filename}")
        except Exception as e:
            print(f"❌ Error exporting statistics: {e}")
    
    def _export_all_data(self) -> None:
        """Create a complete data backup."""
        try:
            if self.data_manager.backup_all_data():
                print("✅ Complete data backup created successfully.")
            else:
                print("❌ Failed to create data backup.")
        except Exception as e:
            print(f"❌ Error creating backup: {e}")


def main():
    """Main entry point for the CLI application."""
    try:
        app = WeatherCLI()
        app.run()
    except KeyboardInterrupt:
        print("\n\n👋 Application interrupted. Goodbye!")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        print("Please report this issue if it persists.")
        sys.exit(1)


if __name__ == "__main__":
    main()