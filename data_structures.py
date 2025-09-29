"""
Core data structures for the Weather Application.

This module defines the fundamental data structures used throughout the application:
- WeatherData: Represents current weather information
- Location: Represents a geographic location with coordinates
- ForecastData: Represents forecast information
- LinkedList: Dynamic storage for favorite locations

Why Linked Lists over Arrays:
Linked lists provide several advantages for managing favorite locations:
1. Dynamic size - can grow/shrink without pre-allocated memory
2. Efficient insertions/deletions at any position (O(1) if we have the node reference)
3. No memory waste - only allocate what's needed
4. Easy reordering of favorite locations
5. No need to handle array resizing complexities
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Any
import json


@dataclass
class WeatherData:
    """Represents current weather data for a location."""
    city: str
    country: str
    temperature: float  # in Celsius by default
    feels_like: float
    humidity: int  # percentage
    pressure: int  # hPa
    wind_speed: float  # m/s by default
    wind_direction: int  # degrees
    description: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'city': self.city,
            'country': self.country,
            'temperature': self.temperature,
            'feels_like': self.feels_like,
            'humidity': self.humidity,
            'pressure': self.pressure,
            'wind_speed': self.wind_speed,
            'wind_direction': self.wind_direction,
            'description': self.description,
            'timestamp': self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'WeatherData':
        """Create WeatherData from dictionary."""
        timestamp = datetime.fromisoformat(data['timestamp']) if 'timestamp' in data else datetime.now()
        return cls(
            city=data['city'],
            country=data['country'],
            temperature=data['temperature'],
            feels_like=data['feels_like'],
            humidity=data['humidity'],
            pressure=data['pressure'],
            wind_speed=data['wind_speed'],
            wind_direction=data['wind_direction'],
            description=data['description'],
            timestamp=timestamp
        )


@dataclass
class Location:
    """Represents a geographic location."""
    city: str
    country: str
    latitude: float
    longitude: float
    added_date: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'city': self.city,
            'country': self.country,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'added_date': self.added_date.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Location':
        """Create Location from dictionary."""
        added_date = datetime.fromisoformat(data['added_date']) if 'added_date' in data else datetime.now()
        return cls(
            city=data['city'],
            country=data['country'],
            latitude=data['latitude'],
            longitude=data['longitude'],
            added_date=added_date
        )
    
    def __str__(self) -> str:
        return f"{self.city}, {self.country}"


@dataclass
class ForecastData:
    """Represents forecast data for a specific date."""
    date: datetime
    temperature_min: float
    temperature_max: float
    humidity: int
    wind_speed: float
    description: str
    precipitation_chance: int = 0  # percentage
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'date': self.date.isoformat(),
            'temperature_min': self.temperature_min,
            'temperature_max': self.temperature_max,
            'humidity': self.humidity,
            'wind_speed': self.wind_speed,
            'description': self.description,
            'precipitation_chance': self.precipitation_chance
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ForecastData':
        """Create ForecastData from dictionary."""
        return cls(
            date=datetime.fromisoformat(data['date']),
            temperature_min=data['temperature_min'],
            temperature_max=data['temperature_max'],
            humidity=data['humidity'],
            wind_speed=data['wind_speed'],
            description=data['description'],
            precipitation_chance=data.get('precipitation_chance', 0)
        )


class LocationNode:
    """Node for the linked list containing a Location and reference to next node."""
    
    def __init__(self, location: Location):
        self.location = location
        self.next: Optional['LocationNode'] = None


class FavoriteLocationsLinkedList:
    """
    Linked list implementation for managing favorite locations.
    
    Benefits over arrays:
    - Dynamic size: No need to pre-allocate fixed memory
    - Efficient insertions/deletions: O(1) at head, O(n) at arbitrary position
    - Memory efficient: Only allocates memory for actual data
    - Easy reordering: Can easily move nodes around
    - No array resizing overhead when adding/removing locations
    """
    
    def __init__(self):
        self.head: Optional[LocationNode] = None
        self.size = 0
    
    def add_location(self, location: Location) -> bool:
        """
        Add a location to the beginning of the list.
        Returns True if successful, False if location already exists.
        """
        # Check if location already exists
        if self.find_location(location.city, location.country):
            return False
        
        new_node = LocationNode(location)
        new_node.next = self.head
        self.head = new_node
        self.size += 1
        return True
    
    def remove_location(self, city: str, country: str) -> bool:
        """
        Remove a location from the list.
        Returns True if successful, False if not found.
        """
        if not self.head:
            return False
        
        # If head node contains the location to remove
        if self.head.location.city.lower() == city.lower() and \
           self.head.location.country.lower() == country.lower():
            self.head = self.head.next
            self.size -= 1
            return True
        
        # Search for the location in the rest of the list
        current = self.head
        while current.next:
            if current.next.location.city.lower() == city.lower() and \
               current.next.location.country.lower() == country.lower():
                current.next = current.next.next
                self.size -= 1
                return True
            current = current.next
        
        return False
    
    def find_location(self, city: str, country: str) -> Optional[Location]:
        """Find a location in the list. Returns None if not found."""
        current = self.head
        while current:
            if current.location.city.lower() == city.lower() and \
               current.location.country.lower() == country.lower():
                return current.location
            current = current.next
        return None
    
    def get_all_locations(self) -> List[Location]:
        """Return a list of all locations."""
        locations = []
        current = self.head
        while current:
            locations.append(current.location)
            current = current.next
        return locations
    
    def is_empty(self) -> bool:
        """Check if the list is empty."""
        return self.head is None
    
    def get_size(self) -> int:
        """Get the number of locations in the list."""
        return self.size
    
    def move_to_front(self, city: str, country: str) -> bool:
        """
        Move a location to the front of the list (most recently accessed).
        Returns True if successful, False if not found.
        """
        if not self.head:
            return False
        
        # If already at front
        if self.head.location.city.lower() == city.lower() and \
           self.head.location.country.lower() == country.lower():
            return True
        
        # Find the location and remove it
        current = self.head
        while current.next:
            if current.next.location.city.lower() == city.lower() and \
               current.next.location.country.lower() == country.lower():
                # Remove the node
                node_to_move = current.next
                current.next = current.next.next
                
                # Add it to the front
                node_to_move.next = self.head
                self.head = node_to_move
                return True
            current = current.next
        
        return False
    
    def to_dict_list(self) -> List[dict]:
        """Convert all locations to a list of dictionaries for JSON serialization."""
        return [location.to_dict() for location in self.get_all_locations()]
    
    def from_dict_list(self, data_list: List[dict]) -> None:
        """Load locations from a list of dictionaries."""
        # Clear existing list
        self.head = None
        self.size = 0
        
        # Add locations in reverse order to maintain original order
        for data in reversed(data_list):
            location = Location.from_dict(data)
            self.add_location(location)


@dataclass
class WeatherQuery:
    """Represents a historical weather query for tracking user searches."""
    location: Location
    query_time: datetime
    weather_data: Optional[WeatherData] = None
    query_type: str = "current"  # "current", "forecast", "historical"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'location': self.location.to_dict(),
            'query_time': self.query_time.isoformat(),
            'weather_data': self.weather_data.to_dict() if self.weather_data else None,
            'query_type': self.query_type
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'WeatherQuery':
        """Create WeatherQuery from dictionary."""
        weather_data = WeatherData.from_dict(data['weather_data']) if data.get('weather_data') else None
        return cls(
            location=Location.from_dict(data['location']),
            query_time=datetime.fromisoformat(data['query_time']),
            weather_data=weather_data,
            query_type=data.get('query_type', 'current')
        )