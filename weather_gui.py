"""
Tkinter GUI for the weather application.

This module provides a simple but functional graphical user interface using Tkinter.
Features include:
- City entry and weather display
- Unit selection and preferences
- Favorite locations management
- Weather forecasts
- Query history viewing
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
from typing import Optional, List
from datetime import datetime

# Import our custom modules
from data_structures import FavoriteLocationsLinkedList, Location, WeatherData
from api_handler import WeatherAPIHandler, APIError
from data_manager import DataManager
from history_manager import HistoryManager
from unit_converter import WeatherFormatter, UnitPreferences, create_metric_preferences, create_imperial_preferences
from validation import InputValidator, ErrorHandler
from config_manager import ConfigManager


class WeatherGUI:
    """
    Tkinter GUI for the weather application.
    
    Features:
    - Clean, user-friendly interface
    - Tabbed layout for different functions
    - Real-time weather fetching
    - Unit preferences management
    - Favorites management
    - History viewing
    """
    
    def __init__(self, root):
        """Initialize the GUI application."""
        self.root = root
        self.root.title("🌤️ Weather Application")
        self.root.geometry("800x600")
        self.root.minsize(600, 400)
        
        # Initialize backend components
        self.data_manager = DataManager()
        self.history_manager = HistoryManager(self.data_manager)
        self.config_manager = ConfigManager()
        
        # Load user preferences
        user_prefs = self.data_manager.get_user_preferences()
        unit_prefs_data = user_prefs.get('units', {})
        
        if isinstance(unit_prefs_data, str):
            if unit_prefs_data == 'imperial':
                self.unit_preferences = create_imperial_preferences()
            else:
                self.unit_preferences = create_metric_preferences()
        else:
            try:
                self.unit_preferences = UnitPreferences.from_dict(unit_prefs_data)
            except (KeyError, ValueError):
                self.unit_preferences = create_metric_preferences()
        
        self.formatter = WeatherFormatter(self.unit_preferences)
        
        # Load favorite locations
        self.favorite_locations = self.data_manager.load_favorite_locations()
        
        # Initialize API handler
        self.api_handler = None
        self._init_api_handler()
        
        # Create the GUI
        self.create_widgets()
        
        # Update favorites display
        self.update_favorites_list()
    
    def _init_api_handler(self) -> bool:
        """Initialize the API handler with error handling."""
        try:
            self.api_handler = WeatherAPIHandler()
            return True
        except APIError as e:
            messagebox.showerror(
                "API Configuration Error",
                f"API key not configured properly.\n\n{e}\n\n"
                "Please configure your OpenWeatherMap API key in the Settings tab."
            )
            return False
    
    def create_widgets(self):
        """Create the main GUI widgets."""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create tabs
        self.create_current_weather_tab()
        self.create_forecast_tab()
        self.create_favorites_tab()
        self.create_history_tab()
        self.create_settings_tab()
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief='sunken')
        self.status_bar.pack(side='bottom', fill='x')
    
    def create_current_weather_tab(self):
        """Create the current weather tab."""
        self.current_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.current_tab, text="🌡️ Current Weather")
        
        # Input frame
        input_frame = ttk.LabelFrame(self.current_tab, text="Location Input")
        input_frame.pack(fill='x', padx=10, pady=5)
        
        # City entry
        ttk.Label(input_frame, text="City:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.city_entry = ttk.Entry(input_frame, width=30)
        self.city_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        self.city_entry.bind('<Return>', lambda e: self.get_current_weather())
        
        # Country entry
        ttk.Label(input_frame, text="Country (optional):").grid(row=0, column=2, padx=5, pady=5, sticky='w')
        self.country_entry = ttk.Entry(input_frame, width=10)
        self.country_entry.grid(row=0, column=3, padx=5, pady=5, sticky='ew')
        self.country_entry.bind('<Return>', lambda e: self.get_current_weather())
        
        # Get weather button
        self.get_weather_btn = ttk.Button(input_frame, text="Get Weather", command=self.get_current_weather)
        self.get_weather_btn.grid(row=0, column=4, padx=10, pady=5)
        
        input_frame.columnconfigure(1, weight=1)
        input_frame.columnconfigure(3, weight=1)
        
        # Weather display frame
        self.weather_frame = ttk.LabelFrame(self.current_tab, text="Current Weather")
        self.weather_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Weather information display
        self.weather_info = scrolledtext.ScrolledText(self.weather_frame, height=15, wrap='word')
        self.weather_info.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Action buttons frame
        action_frame = ttk.Frame(self.current_tab)
        action_frame.pack(fill='x', padx=10, pady=5)
        
        self.add_favorite_btn = ttk.Button(action_frame, text="Add to Favorites", 
                                         command=self.add_current_to_favorites, state='disabled')
        self.add_favorite_btn.pack(side='left', padx=5)
        
        self.clear_weather_btn = ttk.Button(action_frame, text="Clear", command=self.clear_weather_display)
        self.clear_weather_btn.pack(side='left', padx=5)
        
        # Store current location for adding to favorites
        self.current_location = None
    
    def create_forecast_tab(self):
        """Create the weather forecast tab."""
        self.forecast_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.forecast_tab, text="📅 Forecast")
        
        # Input frame
        input_frame = ttk.LabelFrame(self.forecast_tab, text="Forecast Input")
        input_frame.pack(fill='x', padx=10, pady=5)
        
        # City entry
        ttk.Label(input_frame, text="City:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.forecast_city_entry = ttk.Entry(input_frame, width=30)
        self.forecast_city_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        self.forecast_city_entry.bind('<Return>', lambda e: self.get_forecast())
        
        # Country entry
        ttk.Label(input_frame, text="Country (optional):").grid(row=0, column=2, padx=5, pady=5, sticky='w')
        self.forecast_country_entry = ttk.Entry(input_frame, width=10)
        self.forecast_country_entry.grid(row=0, column=3, padx=5, pady=5, sticky='ew')
        self.forecast_country_entry.bind('<Return>', lambda e: self.get_forecast())
        
        # Days selection
        ttk.Label(input_frame, text="Days:").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        self.days_var = tk.StringVar(value="5")
        days_combo = ttk.Combobox(input_frame, textvariable=self.days_var, values=["1", "2", "3", "4", "5"], 
                                width=5, state='readonly')
        days_combo.grid(row=1, column=1, padx=5, pady=5, sticky='w')
        
        # Get forecast button
        self.get_forecast_btn = ttk.Button(input_frame, text="Get Forecast", command=self.get_forecast)
        self.get_forecast_btn.grid(row=1, column=4, padx=10, pady=5)
        
        input_frame.columnconfigure(1, weight=1)
        input_frame.columnconfigure(3, weight=1)
        
        # Forecast display
        self.forecast_frame = ttk.LabelFrame(self.forecast_tab, text="Weather Forecast")
        self.forecast_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.forecast_info = scrolledtext.ScrolledText(self.forecast_frame, height=15, wrap='word')
        self.forecast_info.pack(fill='both', expand=True, padx=5, pady=5)
    
    def create_favorites_tab(self):
        """Create the favorites management tab."""
        self.favorites_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.favorites_tab, text="⭐ Favorites")
        
        # Favorites list frame
        list_frame = ttk.LabelFrame(self.favorites_tab, text="Favorite Locations")
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Treeview for favorites
        columns = ('City', 'Country', 'Date Added')
        self.favorites_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)
        
        # Define headings
        self.favorites_tree.heading('City', text='City')
        self.favorites_tree.heading('Country', text='Country')
        self.favorites_tree.heading('Date Added', text='Date Added')
        
        # Configure column widths
        self.favorites_tree.column('City', width=200)
        self.favorites_tree.column('Country', width=100)
        self.favorites_tree.column('Date Added', width=150)
        
        # Scrollbar for treeview
        favorites_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.favorites_tree.yview)
        self.favorites_tree.configure(yscrollcommand=favorites_scrollbar.set)
        
        self.favorites_tree.pack(side='left', fill='both', expand=True, padx=(5, 0), pady=5)
        favorites_scrollbar.pack(side='right', fill='y', pady=5)
        
        # Buttons frame
        buttons_frame = ttk.Frame(self.favorites_tab)
        buttons_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(buttons_frame, text="Get Weather", 
                  command=self.get_weather_for_selected_favorite).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Add Favorite", 
                  command=self.show_add_favorite_dialog).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Remove Selected", 
                  command=self.remove_selected_favorite).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Refresh List", 
                  command=self.update_favorites_list).pack(side='left', padx=5)
    
    def create_history_tab(self):
        """Create the query history tab."""
        self.history_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.history_tab, text="📊 History")
        
        # History display
        history_frame = ttk.LabelFrame(self.history_tab, text="Query History")
        history_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.history_info = scrolledtext.ScrolledText(history_frame, height=15, wrap='word')
        self.history_info.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Buttons frame
        buttons_frame = ttk.Frame(self.history_tab)
        buttons_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(buttons_frame, text="Refresh History", 
                  command=self.update_history_display).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Generate Report", 
                  command=self.generate_history_report).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Clear History", 
                  command=self.clear_history).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Export History", 
                  command=self.export_history).pack(side='left', padx=5)
        
        # Load initial history
        self.update_history_display()
    
    def create_settings_tab(self):
        """Create the settings and preferences tab."""
        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_tab, text="⚙️ Settings")
        
        # Units frame
        units_frame = ttk.LabelFrame(self.settings_tab, text="Unit Preferences")
        units_frame.pack(fill='x', padx=10, pady=5)
        
        # Temperature units
        ttk.Label(units_frame, text="Temperature:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.temp_var = tk.StringVar(value=self.unit_preferences.temperature.value)
        temp_combo = ttk.Combobox(units_frame, textvariable=self.temp_var, 
                                values=['celsius', 'fahrenheit', 'kelvin'], state='readonly')
        temp_combo.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        temp_combo.bind('<<ComboboxSelected>>', self.update_unit_preferences)
        
        # Wind speed units
        ttk.Label(units_frame, text="Wind Speed:").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        self.wind_var = tk.StringVar(value=self.unit_preferences.wind_speed.value)
        wind_combo = ttk.Combobox(units_frame, textvariable=self.wind_var, 
                                values=['mps', 'kmh', 'mph', 'knots'], state='readonly')
        wind_combo.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        wind_combo.bind('<<ComboboxSelected>>', self.update_unit_preferences)
        
        # Pressure units
        ttk.Label(units_frame, text="Pressure:").grid(row=2, column=0, padx=5, pady=5, sticky='w')
        self.pressure_var = tk.StringVar(value=self.unit_preferences.pressure.value)
        pressure_combo = ttk.Combobox(units_frame, textvariable=self.pressure_var, 
                                    values=['hpa', 'inhg', 'mbar', 'atm'], state='readonly')
        pressure_combo.grid(row=2, column=1, padx=5, pady=5, sticky='ew')
        pressure_combo.bind('<<ComboboxSelected>>', self.update_unit_preferences)
        
        # Quick presets
        presets_frame = ttk.Frame(units_frame)
        presets_frame.grid(row=3, column=0, columnspan=2, pady=10, sticky='ew')
        
        ttk.Button(presets_frame, text="Metric", command=self.set_metric_units).pack(side='left', padx=5)
        ttk.Button(presets_frame, text="Imperial", command=self.set_imperial_units).pack(side='left', padx=5)
        
        units_frame.columnconfigure(1, weight=1)
        
        # API Configuration frame
        api_frame = ttk.LabelFrame(self.settings_tab, text="API Configuration")
        api_frame.pack(fill='x', padx=10, pady=5)
        
        self.api_status_var = tk.StringVar()
        self.update_api_status()
        ttk.Label(api_frame, textvariable=self.api_status_var).pack(padx=5, pady=5)
        
        api_buttons_frame = ttk.Frame(api_frame)
        api_buttons_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(api_buttons_frame, text="Test API", command=self.test_api).pack(side='left', padx=5)
        ttk.Button(api_buttons_frame, text="Configure API Key", 
                  command=self.show_api_config_dialog).pack(side='left', padx=5)
        
        # Data Management frame
        data_frame = ttk.LabelFrame(self.settings_tab, text="Data Management")
        data_frame.pack(fill='x', padx=10, pady=5)
        
        data_buttons_frame = ttk.Frame(data_frame)
        data_buttons_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(data_buttons_frame, text="Clear Cache", command=self.clear_cache).pack(side='left', padx=5)
        ttk.Button(data_buttons_frame, text="Backup Data", command=self.backup_data).pack(side='left', padx=5)
        ttk.Button(data_buttons_frame, text="View Statistics", 
                  command=self.show_data_statistics).pack(side='left', padx=5)
    
    def get_current_weather(self):
        """Get current weather for entered location."""
        if not self.api_handler:
            messagebox.showerror("Error", "API not configured. Please configure your API key in Settings.")
            return
        
        city = self.city_entry.get().strip()
        country = self.country_entry.get().strip() or None
        
        if not city:
            messagebox.showerror("Error", "Please enter a city name.")
            return
        
        # Validate inputs
        city_result = InputValidator.validate_city_name(city)
        if not city_result.is_valid:
            messagebox.showerror("Invalid Input", city_result.error_message)
            return
        
        if country:
            country_result = InputValidator.validate_country_code(country)
            if not country_result.is_valid:
                messagebox.showerror("Invalid Input", country_result.error_message)
                return
            country = country_result.value
        
        # Update status and disable button
        self.status_var.set(f"Fetching weather for {city}...")
        self.get_weather_btn.config(state='disabled')
        
        def fetch_weather():
            try:
                weather_data, location = self.api_handler.get_current_weather_by_name(city, country)
                
                # Cache and track
                self.history_manager.cache_weather_data(location, weather_data)
                self.history_manager.add_query(location, weather_data, "current")
                
                # Update GUI in main thread
                self.root.after(0, lambda: self.display_current_weather(weather_data, location))
                
            except APIError as e:
                error_msg, suggestions = ErrorHandler.handle_api_error(e)
                self.root.after(0, lambda: messagebox.showerror("API Error", f"{error_msg}\n\nSuggestions:\n" + "\n".join(suggestions)))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Unexpected error: {e}"))
            finally:
                self.root.after(0, lambda: self.status_var.set("Ready"))
                self.root.after(0, lambda: self.get_weather_btn.config(state='normal'))
        
        # Run in background thread
        threading.Thread(target=fetch_weather, daemon=True).start()
    
    def display_current_weather(self, weather_data: WeatherData, location: Location):
        """Display current weather data."""
        self.current_location = location
        
        # Clear previous content
        self.weather_info.delete(1.0, tk.END)
        
        # Format weather information
        weather_text = f"🌤️ CURRENT WEATHER FOR {location}\n"
        weather_text += "=" * 50 + "\n\n"
        weather_text += f"🌡️  Temperature: {self.formatter.format_temperature(weather_data.temperature)}\n"
        weather_text += f"🌡️  Feels like: {self.formatter.format_temperature(weather_data.feels_like)}\n"
        weather_text += f"💧 Humidity: {self.formatter.format_humidity(weather_data.humidity)}\n"
        weather_text += f"🏋️  Pressure: {self.formatter.format_pressure(weather_data.pressure)}\n"
        weather_text += f"💨 Wind Speed: {self.formatter.format_wind_speed(weather_data.wind_speed)}\n"
        
        if weather_data.wind_direction > 0:
            weather_text += f"🧭 Wind Direction: {self.formatter.format_wind_direction(weather_data.wind_direction)}\n"
        
        weather_text += f"☁️  Conditions: {weather_data.description}\n"
        weather_text += f"🕐 Updated: {weather_data.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
        weather_text += f"📍 Coordinates: {location.latitude:.2f}, {location.longitude:.2f}\n"
        
        self.weather_info.insert(1.0, weather_text)
        
        # Enable add to favorites button if not already in favorites
        if not self.favorite_locations.find_location(location.city, location.country):
            self.add_favorite_btn.config(state='normal')
        else:
            self.add_favorite_btn.config(state='disabled')
    
    def get_forecast(self):
        """Get weather forecast for entered location."""
        if not self.api_handler:
            messagebox.showerror("Error", "API not configured. Please configure your API key in Settings.")
            return
        
        city = self.forecast_city_entry.get().strip()
        country = self.forecast_country_entry.get().strip() or None
        days = int(self.days_var.get())
        
        if not city:
            messagebox.showerror("Error", "Please enter a city name.")
            return
        
        # Validate inputs
        city_result = InputValidator.validate_city_name(city)
        if not city_result.is_valid:
            messagebox.showerror("Invalid Input", city_result.error_message)
            return
        
        if country:
            country_result = InputValidator.validate_country_code(country)
            if not country_result.is_valid:
                messagebox.showerror("Invalid Input", country_result.error_message)
                return
            country = country_result.value
        
        # Update status and disable button
        self.status_var.set(f"Fetching {days}-day forecast for {city}...")
        self.get_forecast_btn.config(state='disabled')
        
        def fetch_forecast():
            try:
                forecast_data, location = self.api_handler.get_forecast_by_name(city, country, days)
                
                # Cache and track
                self.history_manager.cache_forecast_data(location, forecast_data)
                self.history_manager.add_query(location, None, "forecast")
                
                # Update GUI in main thread
                self.root.after(0, lambda: self.display_forecast(forecast_data, location))
                
            except APIError as e:
                error_msg, suggestions = ErrorHandler.handle_api_error(e)
                self.root.after(0, lambda: messagebox.showerror("API Error", f"{error_msg}\n\nSuggestions:\n" + "\n".join(suggestions)))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Unexpected error: {e}"))
            finally:
                self.root.after(0, lambda: self.status_var.set("Ready"))
                self.root.after(0, lambda: self.get_forecast_btn.config(state='normal'))
        
        # Run in background thread
        threading.Thread(target=fetch_forecast, daemon=True).start()
    
    def display_forecast(self, forecast_data: List, location: Location):
        """Display forecast data."""
        # Clear previous content
        self.forecast_info.delete(1.0, tk.END)
        
        # Format forecast information
        forecast_text = f"📅 {len(forecast_data)}-DAY FORECAST FOR {location}\n"
        forecast_text += "=" * 70 + "\n\n"
        
        for i, forecast in enumerate(forecast_data, 1):
            date_str = forecast.date.strftime('%A, %B %d, %Y')
            forecast_text += f"Day {i}: {date_str}\n"
            forecast_text += "-" * 30 + "\n"
            
            high_temp = self.formatter.format_temperature(forecast.temperature_max)
            low_temp = self.formatter.format_temperature(forecast.temperature_min)
            forecast_text += f"🌡️  Temperature: {low_temp} - {high_temp}\n"
            
            forecast_text += f"💧 Humidity: {self.formatter.format_humidity(forecast.humidity)}\n"
            forecast_text += f"💨 Wind: {self.formatter.format_wind_speed(forecast.wind_speed)}\n"
            forecast_text += f"☁️  Conditions: {forecast.description}\n"
            
            if forecast.precipitation_chance > 0:
                forecast_text += f"🌧️  Precipitation: {forecast.precipitation_chance}%\n"
            
            forecast_text += "\n"
        
        # Show units legend
        temp_unit = "°F" if self.unit_preferences.temperature.value == "fahrenheit" else "°C"
        wind_unit = self.formatter.format_wind_speed(0, show_unit=True).split()[-1]
        forecast_text += f"💡 Temperature in {temp_unit}, Wind speed in {wind_unit}\n"
        
        self.forecast_info.insert(1.0, forecast_text)
    
    def update_favorites_list(self):
        """Update the favorites list display."""
        # Clear existing items
        for item in self.favorites_tree.get_children():
            self.favorites_tree.delete(item)
        
        # Add favorites
        locations = self.favorite_locations.get_all_locations()
        for location in locations:
            date_added = location.added_date.strftime('%Y-%m-%d')
            self.favorites_tree.insert('', 'end', values=(location.city, location.country, date_added))
    
    def get_weather_for_selected_favorite(self):
        """Get weather for the selected favorite location."""
        selection = self.favorites_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a favorite location.")
            return
        
        # Get selected location
        item = self.favorites_tree.item(selection[0])
        city, country = item['values'][0], item['values'][1]
        
        # Find the location object
        location = self.favorite_locations.find_location(city, country)
        if not location:
            messagebox.showerror("Error", "Location not found in favorites.")
            return
        
        if not self.api_handler:
            messagebox.showerror("Error", "API not configured.")
            return
        
        # Switch to current weather tab
        self.notebook.select(self.current_tab)
        
        # Fill in the location
        self.city_entry.delete(0, tk.END)
        self.city_entry.insert(0, location.city)
        self.country_entry.delete(0, tk.END)
        self.country_entry.insert(0, location.country)
        
        # Get the weather
        self.get_current_weather()
        
        # Move to front of favorites
        self.favorite_locations.move_to_front(location.city, location.country)
        self.data_manager.save_favorite_locations(self.favorite_locations)
        self.update_favorites_list()
    
    def show_add_favorite_dialog(self):
        """Show dialog to add a new favorite location."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Favorite Location")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Input fields
        ttk.Label(dialog, text="City:").grid(row=0, column=0, padx=10, pady=10, sticky='w')
        city_entry = ttk.Entry(dialog, width=30)
        city_entry.grid(row=0, column=1, padx=10, pady=10, sticky='ew')
        city_entry.focus()
        
        ttk.Label(dialog, text="Country Code (optional):").grid(row=1, column=0, padx=10, pady=10, sticky='w')
        country_entry = ttk.Entry(dialog, width=10)
        country_entry.grid(row=1, column=1, padx=10, pady=10, sticky='w')
        
        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=2, column=0, columnspan=2, pady=20)
        
        def add_favorite():
            city = city_entry.get().strip()
            country = country_entry.get().strip() or None
            
            if not city:
                messagebox.showerror("Error", "Please enter a city name.")
                return
            
            # Validate inputs
            city_result = InputValidator.validate_city_name(city)
            if not city_result.is_valid:
                messagebox.showerror("Invalid Input", city_result.error_message)
                return
            
            if country:
                country_result = InputValidator.validate_country_code(country)
                if not country_result.is_valid:
                    messagebox.showerror("Invalid Input", country_result.error_message)
                    return
                country = country_result.value
            
            if not self.api_handler:
                messagebox.showerror("Error", "API not configured.")
                return
            
            try:
                location = self.api_handler.get_location_by_name(city, country)
                if not location:
                    messagebox.showerror("Error", f"Could not find location: {city}")
                    return
                
                if self.favorite_locations.add_location(location):
                    self.data_manager.save_favorite_locations(self.favorite_locations)
                    self.update_favorites_list()
                    messagebox.showinfo("Success", f"Added {location} to favorites!")
                    dialog.destroy()
                else:
                    messagebox.showinfo("Info", f"{location} is already in favorites.")
                    
            except APIError as e:
                error_msg, suggestions = ErrorHandler.handle_api_error(e)
                messagebox.showerror("API Error", f"{error_msg}\n\nSuggestions:\n" + "\n".join(suggestions))
            except Exception as e:
                messagebox.showerror("Error", f"Unexpected error: {e}")
        
        ttk.Button(button_frame, text="Add", command=add_favorite).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)
        
        dialog.columnconfigure(1, weight=1)
        
        # Bind Enter key
        city_entry.bind('<Return>', lambda e: add_favorite())
        country_entry.bind('<Return>', lambda e: add_favorite())
    
    def remove_selected_favorite(self):
        """Remove the selected favorite location."""
        selection = self.favorites_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a favorite location to remove.")
            return
        
        # Get selected location
        item = self.favorites_tree.item(selection[0])
        city, country = item['values'][0], item['values'][1]
        
        # Confirm removal
        if messagebox.askyesno("Confirm Removal", f"Remove '{city}, {country}' from favorites?"):
            if self.favorite_locations.remove_location(city, country):
                self.data_manager.save_favorite_locations(self.favorite_locations)
                self.update_favorites_list()
                messagebox.showinfo("Success", f"Removed {city}, {country} from favorites.")
            else:
                messagebox.showerror("Error", f"Could not remove {city}, {country}.")
    
    def update_history_display(self):
        """Update the history display."""
        self.history_info.delete(1.0, tk.END)
        
        # Get recent queries
        recent_queries = self.history_manager.get_recent_queries(20)
        
        if not recent_queries:
            self.history_info.insert(1.0, "No query history found.\n\nStart by getting weather for some locations!")
            return
        
        history_text = f"📊 RECENT QUERIES ({len(recent_queries)} shown)\n"
        history_text += "=" * 60 + "\n\n"
        
        for i, query in enumerate(reversed(recent_queries), 1):
            time_str = query.query_time.strftime("%Y-%m-%d %H:%M:%S")
            location_str = f"{query.location.city}, {query.location.country}"
            history_text += f"{i:2d}. {time_str} | {location_str:25s} | {query.query_type}\n"
            
            if query.weather_data:
                temp = self.formatter.format_temperature(query.weather_data.temperature)
                desc = query.weather_data.description
                history_text += f"     └── {temp}, {desc}\n"
            
            history_text += "\n"
        
        # Add statistics
        stats = self.history_manager.get_query_statistics()
        history_text += "\n" + "=" * 60 + "\n"
        history_text += "📈 STATISTICS\n"
        history_text += "=" * 60 + "\n"
        history_text += f"Total Queries: {stats['total_queries']}\n"
        
        if stats['most_queried_locations']:
            history_text += "\nMost Queried Locations:\n"
            for location, count in stats['most_queried_locations'][:5]:
                history_text += f"  • {location}: {count} queries\n"
        
        cache_stats = stats['cache_stats']
        history_text += f"\nCache: {cache_stats['valid_entries']} valid entries\n"
        
        self.history_info.insert(1.0, history_text)
    
    def generate_history_report(self):
        """Generate and display a formatted history report."""
        # Create a new window for the report
        report_window = tk.Toplevel(self.root)
        report_window.title("📊 Weather History Report")
        report_window.geometry("800x600")
        report_window.transient(self.root)
        
        # Center the window
        report_window.update_idletasks()
        x = (report_window.winfo_screenwidth() // 2) - (report_window.winfo_width() // 2)
        y = (report_window.winfo_screenheight() // 2) - (report_window.winfo_height() // 2)
        report_window.geometry(f"+{x}+{y}")
        
        # Create notebook for different report types
        report_notebook = ttk.Notebook(report_window)
        report_notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Query History Report
        history_frame = ttk.Frame(report_notebook)
        report_notebook.add(history_frame, text="📊 Query History")
        
        history_text_widget = scrolledtext.ScrolledText(history_frame, wrap='word')
        history_text_widget.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Generate history report
        queries = self.history_manager.get_recent_queries(100)
        if queries:
            from weather_reporting import WeatherReportGenerator
            report_gen = WeatherReportGenerator(self.formatter)
            history_report = report_gen.generate_query_history_report(queries, 100)
            history_text_widget.insert(1.0, history_report.to_table_string())
        else:
            history_text_widget.insert(1.0, "No query history available.")
        
        # Location Statistics Report
        stats_frame = ttk.Frame(report_notebook)
        report_notebook.add(stats_frame, text="📍 Location Stats")
        
        stats_text_widget = scrolledtext.ScrolledText(stats_frame, wrap='word')
        stats_text_widget.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Generate location statistics
        if queries:
            location_report = report_gen.generate_location_statistics_report(queries)
            stats_text_widget.insert(1.0, location_report.to_table_string())
        else:
            stats_text_widget.insert(1.0, "No location statistics available.")
        
        # Favorites Comparison Report
        if self.favorite_locations.size > 0:
            comparison_frame = ttk.Frame(report_notebook)
            report_notebook.add(comparison_frame, text="⭐ Favorites Weather")
            
            comparison_text_widget = scrolledtext.ScrolledText(comparison_frame, wrap='word')
            comparison_text_widget.pack(fill='both', expand=True, padx=5, pady=5)
            
            # Get current weather for favorites (if API is available)
            if self.api_handler:
                self.status_var.set("Generating favorites weather report...")
                
                def generate_favorites_report():
                    try:
                        locations_data = []
                        for location in self.favorite_locations.get_all_locations():
                            try:
                                weather_data, _ = self.api_handler.get_current_weather_by_name(
                                    location.city, location.country
                                )
                                locations_data.append((location, weather_data))
                            except Exception:
                                pass  # Skip failed locations
                        
                        if locations_data:
                            favorites_report = report_gen.generate_current_weather_report(locations_data)
                            self.root.after(0, lambda: comparison_text_widget.insert(1.0, favorites_report.to_table_string()))
                        else:
                            self.root.after(0, lambda: comparison_text_widget.insert(1.0, "No weather data available for favorites."))
                        
                        self.root.after(0, lambda: self.status_var.set("Ready"))
                    except Exception as e:
                        self.root.after(0, lambda: comparison_text_widget.insert(1.0, f"Error generating report: {e}"))
                        self.root.after(0, lambda: self.status_var.set("Ready"))
                
                # Run in background
                threading.Thread(target=generate_favorites_report, daemon=True).start()
            else:
                comparison_text_widget.insert(1.0, "API not configured. Cannot fetch current weather for favorites.")
        
        # Export button frame
        export_frame = ttk.Frame(report_window)
        export_frame.pack(fill='x', padx=10, pady=5)
        
        def export_current_report():
            """Export the currently selected report."""
            current_tab = report_notebook.tab(report_notebook.select(), "text")
            
            filename = filedialog.asksaveasfilename(
                title=f"Export {current_tab}",
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("CSV files", "*.csv"), ("JSON files", "*.json"), ("All files", "*.*")]
            )
            
            if filename:
                try:
                    if current_tab == "📊 Query History" and queries:
                        report = history_report
                    elif current_tab == "📍 Location Stats" and queries:
                        report = location_report
                    else:
                        messagebox.showwarning("Export Error", "No report data available to export.")
                        return
                    
                    from weather_reporting import ReportExporter
                    if ReportExporter.export_to_file(report, filename):
                        messagebox.showinfo("Export Success", f"Report exported to:\n{filename}")
                    else:
                        messagebox.showerror("Export Error", "Failed to export report.")
                        
                except Exception as e:
                    messagebox.showerror("Export Error", f"Error exporting report: {e}")
        
        ttk.Button(export_frame, text="💾 Export Current Report", 
                  command=export_current_report).pack(side='left', padx=5)
        ttk.Button(export_frame, text="Close", command=report_window.destroy).pack(side='right', padx=5)
    
    def clear_history(self):
        """Clear query history with confirmation."""
        if messagebox.askyesno("Confirm Clear", "Clear all query history? This cannot be undone."):
            if self.history_manager.clear_history():
                self.update_history_display()
                messagebox.showinfo("Success", "Query history cleared.")
            else:
                messagebox.showerror("Error", "Failed to clear history.")
    
    def export_history(self):
        """Export query history to a file."""
        filename = filedialog.asksaveasfilename(
            title="Export History",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            if self.history_manager.export_history(filename):
                messagebox.showinfo("Success", f"History exported to:\n{filename}")
            else:
                messagebox.showerror("Error", "Failed to export history.")
    
    def update_unit_preferences(self, event=None):
        """Update unit preferences when combobox selection changes."""
        from unit_converter import TemperatureUnit, WindSpeedUnit, PressureUnit
        
        try:
            # Update preferences
            self.unit_preferences.temperature = TemperatureUnit(self.temp_var.get())
            self.unit_preferences.wind_speed = WindSpeedUnit(self.wind_var.get())
            self.unit_preferences.pressure = PressureUnit(self.pressure_var.get())
            
            # Update formatter
            self.formatter = WeatherFormatter(self.unit_preferences)
            
            # Save preferences
            self.save_preferences()
            
            self.status_var.set("Unit preferences updated")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update preferences: {e}")
    
    def save_preferences(self):
        """Save current preferences to storage."""
        user_prefs = self.data_manager.get_user_preferences()
        user_prefs['units'] = self.unit_preferences.to_dict()
        self.data_manager.save_user_preferences(user_prefs)
    
    def set_metric_units(self):
        """Set metric unit preset."""
        self.unit_preferences = create_metric_preferences()
        self.formatter = WeatherFormatter(self.unit_preferences)
        
        # Update combobox values
        self.temp_var.set(self.unit_preferences.temperature.value)
        self.wind_var.set(self.unit_preferences.wind_speed.value)
        self.pressure_var.set(self.unit_preferences.pressure.value)
        
        self.save_preferences()
        messagebox.showinfo("Success", "Switched to metric units")
    
    def set_imperial_units(self):
        """Set imperial unit preset."""
        self.unit_preferences = create_imperial_preferences()
        self.formatter = WeatherFormatter(self.unit_preferences)
        
        # Update combobox values
        self.temp_var.set(self.unit_preferences.temperature.value)
        self.wind_var.set(self.unit_preferences.wind_speed.value)
        self.pressure_var.set(self.unit_preferences.pressure.value)
        
        self.save_preferences()
        messagebox.showinfo("Success", "Switched to imperial units")
    
    def update_api_status(self):
        """Update the API status display."""
        status = self.config_manager.check_configuration()
        
        if status['api_key_found']:
            if status['api_key_valid_format']:
                self.api_status_var.set("✅ API Key: Configured")
            else:
                self.api_status_var.set("⚠️ API Key: Invalid format")
        else:
            self.api_status_var.set("❌ API Key: Not configured")
    
    def test_api(self):
        """Test API connection."""
        if not self.api_handler:
            messagebox.showerror("Error", "API not configured.")
            return
        
        self.status_var.set("Testing API connection...")
        
        def test_connection():
            try:
                if self.api_handler.validate_api_key():
                    # Test a simple request
                    weather_data, location = self.api_handler.get_current_weather_by_name("London", "GB")
                    self.root.after(0, lambda: messagebox.showinfo("Success", 
                        f"API connection successful!\n\nTest query: {weather_data.temperature}°C in {location}"))
                else:
                    self.root.after(0, lambda: messagebox.showerror("Error", "API key validation failed."))
            except APIError as e:
                error_msg, suggestions = ErrorHandler.handle_api_error(e)
                self.root.after(0, lambda: messagebox.showerror("API Error", 
                    f"{error_msg}\n\nSuggestions:\n" + "\n".join(suggestions)))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Unexpected error: {e}"))
            finally:
                self.root.after(0, lambda: self.status_var.set("Ready"))
        
        threading.Thread(target=test_connection, daemon=True).start()
    
    def show_api_config_dialog(self):
        """Show API configuration dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Configure API Key")
        dialog.geometry("500x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Instructions
        instructions = """
To use this weather application, you need a free OpenWeatherMap API key.

1. Visit: https://openweathermap.org/api
2. Sign up for a free account
3. Navigate to API keys section  
4. Copy your API key (32-character hex string)
5. Enter it below

Your API key will be saved securely for future use.
        """
        
        ttk.Label(dialog, text=instructions, justify='left').pack(padx=20, pady=10)
        
        # API key entry
        ttk.Label(dialog, text="API Key:").pack(padx=20, pady=(10, 5), anchor='w')
        api_key_entry = ttk.Entry(dialog, width=50, show='*')
        api_key_entry.pack(padx=20, pady=5, fill='x')
        api_key_entry.focus()
        
        # Show/hide button
        show_var = tk.BooleanVar()
        def toggle_show():
            if show_var.get():
                api_key_entry.config(show='')
            else:
                api_key_entry.config(show='*')
        
        ttk.Checkbutton(dialog, text="Show API key", variable=show_var, 
                       command=toggle_show).pack(padx=20, pady=5, anchor='w')
        
        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)
        
        def save_api_key():
            api_key = api_key_entry.get().strip()
            if not api_key:
                messagebox.showerror("Error", "Please enter an API key.")
                return
            
            if not self.config_manager.validate_api_key(api_key):
                messagebox.showerror("Error", "Invalid API key format. Expected 32-character hexadecimal string.")
                return
            
            # Save to config file
            if self.config_manager.setup_config_file(api_key, overwrite=True):
                messagebox.showinfo("Success", "API key saved successfully!")
                
                # Reinitialize API handler
                self._init_api_handler()
                self.update_api_status()
                dialog.destroy()
            else:
                messagebox.showerror("Error", "Failed to save API key.")
        
        ttk.Button(button_frame, text="Save", command=save_api_key).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)
        
        # Bind Enter key
        api_key_entry.bind('<Return>', lambda e: save_api_key())
    
    def clear_cache(self):
        """Clear weather cache."""
        if messagebox.askyesno("Confirm Clear", "Clear weather cache?"):
            if self.history_manager.clear_cache():
                messagebox.showinfo("Success", "Cache cleared successfully.")
            else:
                messagebox.showerror("Error", "Failed to clear cache.")
    
    def backup_data(self):
        """Create a data backup."""
        if self.data_manager.backup_all_data():
            messagebox.showinfo("Success", "Data backup created successfully.")
        else:
            messagebox.showerror("Error", "Failed to create backup.")
    
    def show_data_statistics(self):
        """Show data statistics in a dialog."""
        stats = self.data_manager.get_data_statistics()
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Data Statistics")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        
        # Create scrolled text for statistics
        stats_text = scrolledtext.ScrolledText(dialog, wrap='word')
        stats_text.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Format statistics
        from data_manager import format_file_size
        
        stats_content = f"📊 DATA STATISTICS\n"
        stats_content += "=" * 40 + "\n\n"
        stats_content += f"Data Directory: {stats['data_directory']}\n"
        stats_content += f"Total Size: {format_file_size(stats['total_size_bytes'])}\n\n"
        stats_content += "Files:\n"
        
        for name, file_info in stats["files"].items():
            if file_info["exists"]:
                if "error" in file_info:
                    stats_content += f"  {name}: ERROR - {file_info['error']}\n"
                else:
                    size = format_file_size(file_info["size_bytes"])
                    modified = file_info["last_modified"][:19].replace('T', ' ')
                    stats_content += f"  {name}: {size} (modified: {modified})\n"
            else:
                stats_content += f"  {name}: Not found\n"
        
        stats_text.insert(1.0, stats_content)
        stats_text.config(state='disabled')
        
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
    
    def add_current_to_favorites(self):
        """Add the current weather location to favorites."""
        if not self.current_location:
            messagebox.showerror("Error", "No current location to add.")
            return
        
        if self.favorite_locations.add_location(self.current_location):
            self.data_manager.save_favorite_locations(self.favorite_locations)
            self.update_favorites_list()
            messagebox.showinfo("Success", f"Added {self.current_location} to favorites!")
            self.add_favorite_btn.config(state='disabled')
        else:
            messagebox.showinfo("Info", f"{self.current_location} is already in favorites.")
    
    def clear_weather_display(self):
        """Clear the weather display."""
        self.weather_info.delete(1.0, tk.END)
        self.current_location = None
        self.add_favorite_btn.config(state='disabled')


def main():
    """Main entry point for the GUI application."""
    root = tk.Tk()
    app = WeatherGUI(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("Application interrupted.")
    except Exception as e:
        messagebox.showerror("Fatal Error", f"An unexpected error occurred:\n{e}")


if __name__ == "__main__":
    main()