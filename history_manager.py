"""
Historical weather query management and caching system.

This module handles:
- Storage and retrieval of recent weather queries
- Query history with timestamps
- Smart caching to reduce API calls
- Query statistics and analytics
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from collections import defaultdict
import json
from data_structures import WeatherQuery, WeatherData, Location, ForecastData
from data_manager import DataManager


class HistoryManager:
    """
    Manages historical weather queries and provides caching functionality.
    
    Features:
    - Query history tracking with timestamps
    - Smart caching to reduce API calls
    - Query analytics and statistics
    - Automatic cleanup of old queries
    - Search functionality within history
    """
    
    def __init__(self, data_manager: DataManager):
        """
        Initialize the history manager.
        
        Args:
            data_manager: DataManager instance for persistence
        """
        self.data_manager = data_manager
        self.recent_queries: List[WeatherQuery] = []
        self.cache: Dict[str, Any] = {}
        self.max_queries = 100
        self.cache_duration = timedelta(minutes=10)
        
        # Load existing data
        self._load_history()
        self._load_cache()
    
    def _load_history(self) -> None:
        """Load query history from storage."""
        try:
            self.recent_queries = self.data_manager.load_recent_queries()
            print(f"Loaded {len(self.recent_queries)} historical queries")
        except Exception as e:
            print(f"Error loading query history: {e}")
            self.recent_queries = []
    
    def _load_cache(self) -> None:
        """Load cache from storage."""
        try:
            self.cache = self.data_manager.load_weather_cache()
            # Clean expired cache entries
            self._clean_expired_cache()
        except Exception as e:
            print(f"Error loading cache: {e}")
            self.cache = {}
    
    def _save_history(self) -> None:
        """Save query history to storage."""
        try:
            self.data_manager.save_recent_queries(self.recent_queries)
        except Exception as e:
            print(f"Error saving query history: {e}")
    
    def _save_cache(self) -> None:
        """Save cache to storage."""
        try:
            self.data_manager.save_weather_cache(self.cache)
        except Exception as e:
            print(f"Error saving cache: {e}")
    
    def _generate_cache_key(self, location: Location, query_type: str) -> str:
        """
        Generate a unique cache key for a location and query type.
        
        Args:
            location: Location object
            query_type: Type of query ('current', 'forecast', etc.)
            
        Returns:
            Unique cache key string
        """
        return f"{location.city}_{location.country}_{query_type}_{location.latitude:.2f}_{location.longitude:.2f}"
    
    def _clean_expired_cache(self) -> None:
        """Remove expired entries from cache."""
        current_time = datetime.now()
        expired_keys = []
        
        for key, cached_data in self.cache.items():
            if 'timestamp' in cached_data:
                cache_time = datetime.fromisoformat(cached_data['timestamp'])
                if current_time - cache_time > self.cache_duration:
                    expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            print(f"Cleaned {len(expired_keys)} expired cache entries")
            self._save_cache()
    
    def add_query(self, location: Location, weather_data: Optional[WeatherData] = None, 
                  query_type: str = "current") -> None:
        """
        Add a new query to the history.
        
        Args:
            location: Location that was queried
            weather_data: Weather data retrieved (if any)
            query_type: Type of query performed
        """
        query = WeatherQuery(
            location=location,
            query_time=datetime.now(),
            weather_data=weather_data,
            query_type=query_type
        )
        
        self.recent_queries.append(query)
        
        # Trim to max queries
        if len(self.recent_queries) > self.max_queries:
            self.recent_queries = self.recent_queries[-self.max_queries:]
        
        # Save to storage
        self._save_history()
    
    def cache_weather_data(self, location: Location, weather_data: WeatherData, 
                          query_type: str = "current") -> None:
        """
        Cache weather data for a location.
        
        Args:
            location: Location for the data
            weather_data: Weather data to cache
            query_type: Type of query
        """
        cache_key = self._generate_cache_key(location, query_type)
        
        cache_entry = {
            'timestamp': datetime.now().isoformat(),
            'data': weather_data.to_dict(),
            'location': location.to_dict(),
            'query_type': query_type
        }
        
        self.cache[cache_key] = cache_entry
        self._save_cache()
    
    def cache_forecast_data(self, location: Location, forecast_data: List[ForecastData]) -> None:
        """
        Cache forecast data for a location.
        
        Args:
            location: Location for the forecast
            forecast_data: List of forecast data to cache
        """
        cache_key = self._generate_cache_key(location, "forecast")
        
        cache_entry = {
            'timestamp': datetime.now().isoformat(),
            'data': [forecast.to_dict() for forecast in forecast_data],
            'location': location.to_dict(),
            'query_type': 'forecast'
        }
        
        self.cache[cache_key] = cache_entry
        self._save_cache()
    
    def get_cached_weather(self, location: Location, query_type: str = "current") -> Optional[WeatherData]:
        """
        Get cached weather data for a location if available and not expired.
        
        Args:
            location: Location to check
            query_type: Type of query
            
        Returns:
            WeatherData if cached and valid, None otherwise
        """
        cache_key = self._generate_cache_key(location, query_type)
        
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            cache_time = datetime.fromisoformat(cached_data['timestamp'])
            
            if datetime.now() - cache_time <= self.cache_duration:
                try:
                    return WeatherData.from_dict(cached_data['data'])
                except (KeyError, ValueError) as e:
                    print(f"Error parsing cached weather data: {e}")
                    del self.cache[cache_key]
        
        return None
    
    def get_cached_forecast(self, location: Location) -> Optional[List[ForecastData]]:
        """
        Get cached forecast data for a location if available and not expired.
        
        Args:
            location: Location to check
            
        Returns:
            List of ForecastData if cached and valid, None otherwise
        """
        cache_key = self._generate_cache_key(location, "forecast")
        
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            cache_time = datetime.fromisoformat(cached_data['timestamp'])
            
            if datetime.now() - cache_time <= self.cache_duration:
                try:
                    forecast_list = []
                    for forecast_dict in cached_data['data']:
                        forecast_list.append(ForecastData.from_dict(forecast_dict))
                    return forecast_list
                except (KeyError, ValueError) as e:
                    print(f"Error parsing cached forecast data: {e}")
                    del self.cache[cache_key]
        
        return None
    
    def get_recent_queries(self, limit: int = 20) -> List[WeatherQuery]:
        """
        Get recent queries.
        
        Args:
            limit: Maximum number of queries to return
            
        Returns:
            List of recent WeatherQuery objects
        """
        return self.recent_queries[-limit:] if self.recent_queries else []
    
    def get_queries_for_location(self, location: Location, limit: int = 10) -> List[WeatherQuery]:
        """
        Get queries for a specific location.
        
        Args:
            location: Location to search for
            limit: Maximum number of queries to return
            
        Returns:
            List of WeatherQuery objects for the location
        """
        matching_queries = []
        
        for query in reversed(self.recent_queries):
            if (query.location.city.lower() == location.city.lower() and 
                query.location.country.lower() == location.country.lower()):
                matching_queries.append(query)
                if len(matching_queries) >= limit:
                    break
        
        return matching_queries
    
    def get_queries_by_date(self, start_date: datetime, end_date: datetime) -> List[WeatherQuery]:
        """
        Get queries within a date range.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            List of WeatherQuery objects within the date range
        """
        matching_queries = []
        
        for query in self.recent_queries:
            if start_date <= query.query_time <= end_date:
                matching_queries.append(query)
        
        return sorted(matching_queries, key=lambda q: q.query_time, reverse=True)
    
    def search_queries(self, search_term: str, limit: int = 20) -> List[WeatherQuery]:
        """
        Search queries by city name or country.
        
        Args:
            search_term: Term to search for
            limit: Maximum number of results
            
        Returns:
            List of matching WeatherQuery objects
        """
        search_term = search_term.lower()
        matching_queries = []
        
        for query in reversed(self.recent_queries):
            if (search_term in query.location.city.lower() or 
                search_term in query.location.country.lower()):
                matching_queries.append(query)
                if len(matching_queries) >= limit:
                    break
        
        return matching_queries
    
    def get_query_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about query history.
        
        Returns:
            Dictionary with query statistics
        """
        if not self.recent_queries:
            return {
                "total_queries": 0,
                "date_range": None,
                "most_queried_locations": [],
                "query_types": {},
                "queries_by_day": {},
                "cache_stats": self._get_cache_statistics()
            }
        
        # Basic stats
        total_queries = len(self.recent_queries)
        first_query = min(self.recent_queries, key=lambda q: q.query_time)
        last_query = max(self.recent_queries, key=lambda q: q.query_time)
        
        # Location frequency
        location_counts = defaultdict(int)
        for query in self.recent_queries:
            location_key = f"{query.location.city}, {query.location.country}"
            location_counts[location_key] += 1
        
        # Query type frequency
        type_counts = defaultdict(int)
        for query in self.recent_queries:
            type_counts[query.query_type] += 1
        
        # Queries by day
        day_counts = defaultdict(int)
        for query in self.recent_queries:
            day_key = query.query_time.date().isoformat()
            day_counts[day_key] += 1
        
        return {
            "total_queries": total_queries,
            "date_range": {
                "first_query": first_query.query_time.isoformat(),
                "last_query": last_query.query_time.isoformat(),
                "days_span": (last_query.query_time.date() - first_query.query_time.date()).days
            },
            "most_queried_locations": sorted(
                [(location, count) for location, count in location_counts.items()],
                key=lambda x: x[1], reverse=True
            )[:10],
            "query_types": dict(type_counts),
            "queries_by_day": dict(day_counts),
            "cache_stats": self._get_cache_statistics()
        }
    
    def _get_cache_statistics(self) -> Dict[str, Any]:
        """Get cache statistics."""
        current_time = datetime.now()
        valid_entries = 0
        expired_entries = 0
        
        for cached_data in self.cache.values():
            if 'timestamp' in cached_data:
                cache_time = datetime.fromisoformat(cached_data['timestamp'])
                if current_time - cache_time <= self.cache_duration:
                    valid_entries += 1
                else:
                    expired_entries += 1
        
        return {
            "total_entries": len(self.cache),
            "valid_entries": valid_entries,
            "expired_entries": expired_entries,
            "cache_duration_minutes": self.cache_duration.total_seconds() / 60
        }
    
    def clear_history(self) -> bool:
        """
        Clear all query history.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.recent_queries = []
            self._save_history()
            print("Query history cleared")
            return True
        except Exception as e:
            print(f"Error clearing history: {e}")
            return False
    
    def clear_cache(self) -> bool:
        """
        Clear all cached data.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.cache = {}
            self.data_manager.clear_weather_cache()
            print("Cache cleared")
            return True
        except Exception as e:
            print(f"Error clearing cache: {e}")
            return False
    
    def export_history(self, filepath: str) -> bool:
        """
        Export query history to a JSON file.
        
        Args:
            filepath: Path to save the export
            
        Returns:
            True if successful, False otherwise
        """
        try:
            export_data = {
                "export_date": datetime.now().isoformat(),
                "total_queries": len(self.recent_queries),
                "queries": [query.to_dict() for query in self.recent_queries],
                "statistics": self.get_query_statistics()
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            print(f"History exported to: {filepath}")
            return True
            
        except Exception as e:
            print(f"Error exporting history: {e}")
            return False
    
    def print_recent_queries(self, limit: int = 10) -> None:
        """Print recent queries in a formatted way."""
        recent = self.get_recent_queries(limit)
        
        if not recent:
            print("No recent queries found.")
            return
        
        print(f"\n📊 Recent Queries (Last {len(recent)}):")
        print("=" * 60)
        
        for i, query in enumerate(reversed(recent), 1):
            time_str = query.query_time.strftime("%Y-%m-%d %H:%M:%S")
            location_str = f"{query.location.city}, {query.location.country}"
            
            print(f"{i:2d}. {time_str} | {location_str:25s} | {query.query_type}")
            
            if query.weather_data:
                temp = query.weather_data.temperature
                desc = query.weather_data.description
                print(f"     └── {temp}°C, {desc}")
    
    def print_statistics(self) -> None:
        """Print query statistics in a formatted way."""
        stats = self.get_query_statistics()
        
        print("\n📈 Query Statistics:")
        print("=" * 40)
        
        if stats["total_queries"] == 0:
            print("No queries recorded yet.")
            return
        
        print(f"Total Queries: {stats['total_queries']}")
        
        if stats["date_range"]:
            print(f"Date Range: {stats['date_range']['first_query'][:10]} to {stats['date_range']['last_query'][:10]}")
            print(f"Days Active: {stats['date_range']['days_span']}")
        
        print("\nMost Queried Locations:")
        for location, count in stats["most_queried_locations"][:5]:
            print(f"  {location}: {count} queries")
        
        print(f"\nQuery Types: {stats['query_types']}")
        
        cache_stats = stats["cache_stats"]
        print(f"\nCache: {cache_stats['valid_entries']} valid, {cache_stats['expired_entries']} expired")


if __name__ == "__main__":
    # Test the history manager
    from data_manager import DataManager
    
    dm = DataManager()
    hm = HistoryManager(dm)
    
    # Print statistics
    hm.print_statistics()
    hm.print_recent_queries()