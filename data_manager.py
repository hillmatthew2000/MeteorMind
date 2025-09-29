"""
File I/O manager for persistent storage of weather application data.

This module handles saving and loading of:
- Favorite locations
- Recent weather queries
- User preferences
- Application settings

All data is stored in JSON format for human readability and easy debugging.
"""

import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from data_structures import (
    FavoriteLocationsLinkedList, 
    WeatherQuery, 
    Location, 
    WeatherData
)


class DataManager:
    """
    Handles all file I/O operations for the weather application.
    
    Features:
    - Persistent storage of favorite locations
    - Recent query history with automatic cleanup
    - User preferences (units, display settings)
    - Backup and recovery functionality
    - JSON format for human readability
    """
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialize the data manager.
        
        Args:
            data_dir: Directory to store application data files
        """
        self.data_dir = data_dir
        self.favorites_file = os.path.join(data_dir, "favorite_locations.json")
        self.queries_file = os.path.join(data_dir, "recent_queries.json")
        self.preferences_file = os.path.join(data_dir, "user_preferences.json")
        self.cache_file = os.path.join(data_dir, "weather_cache.json")
        
        # Create data directory if it doesn't exist
        self._ensure_data_directory()
        
        # Default preferences
        self.default_preferences = {
            "units": "metric",  # "metric" or "imperial"
            "temperature_unit": "celsius",  # "celsius" or "fahrenheit"
            "wind_speed_unit": "mps",  # "mps" (meters per second) or "mph"
            "pressure_unit": "hpa",  # "hpa" or "inHg"
            "max_recent_queries": 50,
            "cache_duration_minutes": 10,
            "auto_refresh": False,
            "show_feels_like": True,
            "show_wind_direction": True,
            "date_format": "%Y-%m-%d %H:%M",
            "theme": "light"  # "light" or "dark"
        }
    
    def _ensure_data_directory(self) -> None:
        """Create the data directory if it doesn't exist."""
        if not os.path.exists(self.data_dir):
            try:
                os.makedirs(self.data_dir)
            except OSError as e:
                raise IOError(f"Could not create data directory '{self.data_dir}': {e}")
    
    def _safe_json_load(self, filepath: str, default_value: Any = None) -> Any:
        """
        Safely load JSON data from a file with error handling.
        
        Args:
            filepath: Path to the JSON file
            default_value: Value to return if file doesn't exist or is invalid
            
        Returns:
            Loaded data or default_value
        """
        try:
            if not os.path.exists(filepath):
                return default_value
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return default_value
                return json.loads(content)
                
        except (json.JSONDecodeError, IOError, UnicodeDecodeError) as e:
            print(f"Warning: Could not load {filepath}: {e}")
            # Backup the corrupted file
            backup_path = f"{filepath}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            try:
                if os.path.exists(filepath):
                    os.rename(filepath, backup_path)
                    print(f"Corrupted file backed up to: {backup_path}")
            except OSError:
                pass
            
            return default_value
    
    def _safe_json_save(self, filepath: str, data: Any) -> bool:
        """
        Safely save data to a JSON file with error handling.
        
        Args:
            filepath: Path to save the JSON file
            data: Data to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create a temporary file first to avoid corruption
            temp_filepath = f"{filepath}.tmp"
            
            with open(temp_filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            # Atomically replace the original file
            if os.path.exists(filepath):
                backup_path = f"{filepath}.bak"
                os.replace(filepath, backup_path)
            
            os.replace(temp_filepath, filepath)
            
            # Remove backup if save was successful
            backup_path = f"{filepath}.bak"
            if os.path.exists(backup_path):
                os.remove(backup_path)
            
            return True
            
        except (IOError, OSError) as e:
            print(f"Error saving {filepath}: {e}")
            # Clean up temporary file if it exists
            temp_filepath = f"{filepath}.tmp"
            if os.path.exists(temp_filepath):
                try:
                    os.remove(temp_filepath)
                except OSError:
                    pass
            return False
    
    def save_favorite_locations(self, locations_list: FavoriteLocationsLinkedList) -> bool:
        """
        Save favorite locations to file.
        
        Args:
            locations_list: LinkedList of favorite locations
            
        Returns:
            True if successful, False otherwise
        """
        try:
            data = {
                "version": "1.0",
                "saved_at": datetime.now().isoformat(),
                "locations": locations_list.to_dict_list()
            }
            
            return self._safe_json_save(self.favorites_file, data)
            
        except Exception as e:
            print(f"Error saving favorite locations: {e}")
            return False
    
    def load_favorite_locations(self) -> FavoriteLocationsLinkedList:
        """
        Load favorite locations from file.
        
        Returns:
            FavoriteLocationsLinkedList with loaded locations
        """
        locations_list = FavoriteLocationsLinkedList()
        
        try:
            data = self._safe_json_load(self.favorites_file, {})
            
            if data and "locations" in data:
                locations_list.from_dict_list(data["locations"])
                print(f"Loaded {locations_list.get_size()} favorite locations")
            else:
                # Create with some default locations for first-time users
                self._create_default_locations(locations_list)
                
        except Exception as e:
            print(f"Error loading favorite locations: {e}")
            # Create with defaults if loading fails
            self._create_default_locations(locations_list)
        
        return locations_list
    
    def _create_default_locations(self, locations_list: FavoriteLocationsLinkedList) -> None:
        """Create some default favorite locations for new users."""
        default_locations = [
            Location("London", "GB", 51.5074, -0.1278),
            Location("New York", "US", 40.7128, -74.0060),
            Location("Tokyo", "JP", 35.6762, 139.6503),
            Location("Paris", "FR", 48.8566, 2.3522),
            Location("Sydney", "AU", -33.8688, 151.2093)
        ]
        
        for location in default_locations:
            locations_list.add_location(location)
        
        # Save the defaults
        self.save_favorite_locations(locations_list)
        print("Created default favorite locations")
    
    def save_recent_queries(self, queries: List[WeatherQuery]) -> bool:
        """
        Save recent weather queries to file.
        
        Args:
            queries: List of recent weather queries
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Limit the number of queries saved
            max_queries = self.get_user_preferences().get("max_recent_queries", 50)
            queries_to_save = queries[-max_queries:] if len(queries) > max_queries else queries
            
            data = {
                "version": "1.0",
                "saved_at": datetime.now().isoformat(),
                "queries": [query.to_dict() for query in queries_to_save]
            }
            
            return self._safe_json_save(self.queries_file, data)
            
        except Exception as e:
            print(f"Error saving recent queries: {e}")
            return False
    
    def load_recent_queries(self) -> List[WeatherQuery]:
        """
        Load recent weather queries from file.
        
        Returns:
            List of WeatherQuery objects
        """
        try:
            data = self._safe_json_load(self.queries_file, {})
            
            if data and "queries" in data:
                queries = []
                for query_data in data["queries"]:
                    try:
                        query = WeatherQuery.from_dict(query_data)
                        queries.append(query)
                    except (KeyError, ValueError) as e:
                        print(f"Skipping invalid query data: {e}")
                        continue
                
                # Clean up old queries (older than 30 days)
                cutoff_date = datetime.now() - timedelta(days=30)
                recent_queries = [q for q in queries if q.query_time > cutoff_date]
                
                if len(recent_queries) != len(queries):
                    print(f"Cleaned up {len(queries) - len(recent_queries)} old queries")
                    self.save_recent_queries(recent_queries)
                
                return recent_queries
            
            return []
            
        except Exception as e:
            print(f"Error loading recent queries: {e}")
            return []
    
    def save_user_preferences(self, preferences: Dict[str, Any]) -> bool:
        """
        Save user preferences to file.
        
        Args:
            preferences: Dictionary of user preferences
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Merge with defaults to ensure all keys are present
            merged_prefs = self.default_preferences.copy()
            merged_prefs.update(preferences)
            
            data = {
                "version": "1.0",
                "saved_at": datetime.now().isoformat(),
                "preferences": merged_prefs
            }
            
            return self._safe_json_save(self.preferences_file, data)
            
        except Exception as e:
            print(f"Error saving user preferences: {e}")
            return False
    
    def get_user_preferences(self) -> Dict[str, Any]:
        """
        Load user preferences from file.
        
        Returns:
            Dictionary of user preferences with defaults for missing values
        """
        try:
            data = self._safe_json_load(self.preferences_file, {})
            
            if data and "preferences" in data:
                # Merge with defaults to ensure all keys are present
                preferences = self.default_preferences.copy()
                preferences.update(data["preferences"])
                return preferences
            
            # Save defaults if no preferences file exists
            self.save_user_preferences(self.default_preferences)
            return self.default_preferences.copy()
            
        except Exception as e:
            print(f"Error loading user preferences: {e}")
            return self.default_preferences.copy()
    
    def save_weather_cache(self, cache_data: Dict[str, Any]) -> bool:
        """
        Save weather data cache to file.
        
        Args:
            cache_data: Dictionary with cached weather data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            data = {
                "version": "1.0",
                "saved_at": datetime.now().isoformat(),
                "cache": cache_data
            }
            
            return self._safe_json_save(self.cache_file, data)
            
        except Exception as e:
            print(f"Error saving weather cache: {e}")
            return False
    
    def load_weather_cache(self) -> Dict[str, Any]:
        """
        Load weather data cache from file.
        
        Returns:
            Dictionary with cached weather data
        """
        try:
            data = self._safe_json_load(self.cache_file, {})
            
            if data and "cache" in data:
                # Check if cache is still valid
                cache_duration = self.get_user_preferences().get("cache_duration_minutes", 10)
                saved_at = datetime.fromisoformat(data["saved_at"])
                
                if datetime.now() - saved_at < timedelta(minutes=cache_duration):
                    return data["cache"]
                else:
                    print("Weather cache expired")
                    # Clear expired cache
                    self.clear_weather_cache()
            
            return {}
            
        except Exception as e:
            print(f"Error loading weather cache: {e}")
            return {}
    
    def clear_weather_cache(self) -> bool:
        """
        Clear the weather data cache.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
            return True
        except OSError as e:
            print(f"Error clearing weather cache: {e}")
            return False
    
    def backup_all_data(self, backup_dir: Optional[str] = None) -> bool:
        """
        Create a backup of all application data.
        
        Args:
            backup_dir: Directory to store backup files
            
        Returns:
            True if successful, False otherwise
        """
        if backup_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = os.path.join(self.data_dir, f"backup_{timestamp}")
        
        try:
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            
            files_to_backup = [
                self.favorites_file,
                self.queries_file,
                self.preferences_file,
                self.cache_file
            ]
            
            backed_up = 0
            for file_path in files_to_backup:
                if os.path.exists(file_path):
                    filename = os.path.basename(file_path)
                    backup_path = os.path.join(backup_dir, filename)
                    
                    with open(file_path, 'rb') as src, open(backup_path, 'wb') as dst:
                        dst.write(src.read())
                    
                    backed_up += 1
            
            print(f"Backed up {backed_up} files to {backup_dir}")
            return True
            
        except Exception as e:
            print(f"Error creating backup: {e}")
            return False
    
    def restore_from_backup(self, backup_dir: str) -> bool:
        """
        Restore application data from a backup directory.
        
        Args:
            backup_dir: Directory containing backup files
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.exists(backup_dir):
                print(f"Backup directory '{backup_dir}' does not exist")
                return False
            
            files_to_restore = [
                ("favorite_locations.json", self.favorites_file),
                ("recent_queries.json", self.queries_file),
                ("user_preferences.json", self.preferences_file),
                ("weather_cache.json", self.cache_file)
            ]
            
            restored = 0
            for backup_filename, target_path in files_to_restore:
                backup_path = os.path.join(backup_dir, backup_filename)
                
                if os.path.exists(backup_path):
                    # Create backup of current file before restoring
                    if os.path.exists(target_path):
                        current_backup = f"{target_path}.pre_restore"
                        os.replace(target_path, current_backup)
                    
                    with open(backup_path, 'rb') as src, open(target_path, 'wb') as dst:
                        dst.write(src.read())
                    
                    restored += 1
            
            print(f"Restored {restored} files from {backup_dir}")
            return True
            
        except Exception as e:
            print(f"Error restoring from backup: {e}")
            return False
    
    def get_data_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about stored data.
        
        Returns:
            Dictionary with data statistics
        """
        stats = {
            "data_directory": self.data_dir,
            "files": {},
            "total_size_bytes": 0
        }
        
        files_to_check = {
            "favorite_locations": self.favorites_file,
            "recent_queries": self.queries_file,
            "user_preferences": self.preferences_file,
            "weather_cache": self.cache_file
        }
        
        for name, filepath in files_to_check.items():
            if os.path.exists(filepath):
                try:
                    file_size = os.path.getsize(filepath)
                    modified_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                    
                    stats["files"][name] = {
                        "exists": True,
                        "size_bytes": file_size,
                        "last_modified": modified_time.isoformat(),
                        "path": filepath
                    }
                    
                    stats["total_size_bytes"] += file_size
                    
                except OSError:
                    stats["files"][name] = {
                        "exists": True,
                        "error": "Could not read file info"
                    }
            else:
                stats["files"][name] = {
                    "exists": False,
                    "path": filepath
                }
        
        return stats


# Utility functions for data management
def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    size = float(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def print_data_statistics(data_manager: DataManager) -> None:
    """Print data statistics in a formatted way."""
    stats = data_manager.get_data_statistics()
    
    print(f"\nData Directory: {stats['data_directory']}")
    print(f"Total Size: {format_file_size(stats['total_size_bytes'])}")
    print("\nFiles:")
    
    for name, file_info in stats["files"].items():
        if file_info["exists"]:
            if "error" in file_info:
                print(f"  {name}: ERROR - {file_info['error']}")
            else:
                size = format_file_size(file_info["size_bytes"])
                modified = file_info["last_modified"][:19].replace('T', ' ')
                print(f"  {name}: {size} (modified: {modified})")
        else:
            print(f"  {name}: Not found")


if __name__ == "__main__":
    # Test the data manager
    dm = DataManager()
    
    # Test preferences
    prefs = dm.get_user_preferences()
    print(f"Current units: {prefs['units']}")
    
    # Test locations
    locations = dm.load_favorite_locations()
    print(f"Loaded {locations.get_size()} favorite locations")
    
    # Print statistics
    print_data_statistics(dm)