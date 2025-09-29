"""
Weather reporting and table formatting utilities.

This module provides comprehensive formatting capabilities for weather data,
including tabular reports, summary views, and export functionality.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import json

from data_structures import WeatherData, Location, ForecastData, WeatherQuery
from unit_converter import WeatherFormatter, UnitPreferences


@dataclass
class WeatherReport:
    """Represents a formatted weather report."""
    title: str
    headers: List[str]
    rows: List[List[str]]
    summary: Optional[str] = None
    footer: Optional[str] = None
    
    def to_table_string(self, max_width: int = 120) -> str:
        """Convert report to formatted table string."""
        if not self.rows:
            return f"{self.title}\n{'=' * len(self.title)}\nNo data available.\n"
        
        # Calculate column widths
        col_widths = []
        for i in range(len(self.headers)):
            header_width = len(self.headers[i])
            max_data_width = max(len(str(row[i])) for row in self.rows) if self.rows else 0
            col_widths.append(max(header_width, max_data_width, 8))  # Minimum width of 8
        
        # Adjust widths if total exceeds max_width
        total_width = sum(col_widths) + (len(col_widths) - 1) * 3  # 3 chars for " | "
        if total_width > max_width:
            # Proportionally reduce column widths
            scale_factor = (max_width - (len(col_widths) - 1) * 3) / sum(col_widths)
            col_widths = [max(8, int(w * scale_factor)) for w in col_widths]
        
        # Build table
        result = []
        
        # Title
        result.append(self.title)
        result.append("=" * len(self.title))
        result.append("")
        
        # Headers
        header_row = " | ".join(h.ljust(w) for h, w in zip(self.headers, col_widths))
        result.append(header_row)
        result.append("-" * len(header_row))
        
        # Data rows
        for row in self.rows:
            data_row = " | ".join(str(cell).ljust(w)[:w] for cell, w in zip(row, col_widths))
            result.append(data_row)
        
        # Summary and footer
        if self.summary:
            result.append("")
            result.append(self.summary)
        
        if self.footer:
            result.append("")
            result.append(self.footer)
        
        return "\n".join(result)
    
    def to_csv(self) -> str:
        """Convert report to CSV format."""
        lines = []
        
        # Add title as comment
        lines.append(f"# {self.title}")
        
        # Headers
        lines.append(",".join(f'"{h}"' for h in self.headers))
        
        # Data rows
        for row in self.rows:
            csv_row = ",".join(f'"{str(cell)}"' for cell in row)
            lines.append(csv_row)
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary for JSON export."""
        return {
            "title": self.title,
            "headers": self.headers,
            "rows": self.rows,
            "summary": self.summary,
            "footer": self.footer,
            "generated_at": datetime.now().isoformat()
        }


class WeatherReportGenerator:
    """
    Generates various types of weather reports and formatted tables.
    
    Features:
    - Current weather summaries
    - Forecast comparisons
    - Location comparisons
    - Historical query reports
    - Statistical summaries
    """
    
    def __init__(self, formatter: WeatherFormatter):
        """Initialize with a weather formatter."""
        self.formatter = formatter
    
    def generate_current_weather_report(self, locations_data: List[tuple]) -> WeatherReport:
        """
        Generate a current weather comparison report.
        
        Args:
            locations_data: List of (location, weather_data) tuples
            
        Returns:
            WeatherReport with current weather for all locations
        """
        if not locations_data:
            return WeatherReport("Current Weather Report", [], [])
        
        headers = [
            "Location",
            "Temperature",
            "Feels Like",
            "Conditions",
            "Humidity",
            "Pressure", 
            "Wind Speed",
            "Updated"
        ]
        
        rows = []
        for location, weather_data in locations_data:
            row = [
                f"{location.city}, {location.country}",
                self.formatter.format_temperature(weather_data.temperature),
                self.formatter.format_temperature(weather_data.feels_like),
                weather_data.description.title(),
                self.formatter.format_humidity(weather_data.humidity),
                self.formatter.format_pressure(weather_data.pressure),
                self.formatter.format_wind_speed(weather_data.wind_speed),
                weather_data.timestamp.strftime("%H:%M")
            ]
            rows.append(row)
        
        # Generate summary
        temps = [wd.temperature for _, wd in locations_data]
        avg_temp = sum(temps) / len(temps)
        min_temp = min(temps)
        max_temp = max(temps)
        
        summary = f"Summary: {len(locations_data)} locations | "
        summary += f"Avg: {self.formatter.format_temperature(avg_temp)} | "
        summary += f"Range: {self.formatter.format_temperature(min_temp)} - {self.formatter.format_temperature(max_temp)}"
        
        footer = f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return WeatherReport(
            title="Current Weather Report",
            headers=headers,
            rows=rows,
            summary=summary,
            footer=footer
        )
    
    def generate_forecast_comparison_report(self, forecasts_data: List[tuple]) -> WeatherReport:
        """
        Generate a forecast comparison report.
        
        Args:
            forecasts_data: List of (location, forecast_list) tuples
            
        Returns:
            WeatherReport comparing forecasts across locations
        """
        if not forecasts_data:
            return WeatherReport("Forecast Comparison Report", [], [])
        
        # Find common forecast days
        min_days = min(len(forecast_list) for _, forecast_list in forecasts_data)
        
        headers = ["Location"] + [f"Day {i+1}" for i in range(min_days)]
        
        rows = []
        for location, forecast_list in forecasts_data:
            row = [f"{location.city}, {location.country}"]
            
            for i in range(min_days):
                forecast = forecast_list[i]
                temp_range = f"{self.formatter.format_temperature(forecast.temperature_min)}-{self.formatter.format_temperature(forecast.temperature_max)}"
                conditions = forecast.description.title()
                cell = f"{temp_range}\n{conditions}"
                row.append(cell)
            
            rows.append(row)
        
        summary = f"Forecast comparison for {len(forecasts_data)} locations over {min_days} days"
        footer = f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return WeatherReport(
            title="Forecast Comparison Report", 
            headers=headers,
            rows=rows,
            summary=summary,
            footer=footer
        )
    
    def generate_detailed_forecast_report(self, location: Location, forecast_data: List[ForecastData]) -> WeatherReport:
        """
        Generate a detailed forecast report for a single location.
        
        Args:
            location: Location object
            forecast_data: List of forecast data
            
        Returns:
            WeatherReport with detailed forecast information
        """
        if not forecast_data:
            return WeatherReport(f"Forecast Report - {location}", [], [])
        
        headers = [
            "Date",
            "Day",
            "High/Low",
            "Conditions",
            "Humidity",
            "Wind",
            "Precipitation"
        ]
        
        rows = []
        for forecast in forecast_data:
            date_str = forecast.date.strftime("%m/%d")
            day_str = forecast.date.strftime("%a")
            temp_range = f"{self.formatter.format_temperature(forecast.temperature_min)}/{self.formatter.format_temperature(forecast.temperature_max)}"
            conditions = forecast.description.title()
            humidity = self.formatter.format_humidity(forecast.humidity)
            wind = self.formatter.format_wind_speed(forecast.wind_speed)
            precip = f"{forecast.precipitation_chance}%" if forecast.precipitation_chance > 0 else "-"
            
            rows.append([date_str, day_str, temp_range, conditions, humidity, wind, precip])
        
        title = f"Detailed Forecast - {location.city}, {location.country}"
        summary = f"{len(forecast_data)}-day forecast starting {forecast_data[0].date.strftime('%B %d, %Y')}"
        footer = f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return WeatherReport(
            title=title,
            headers=headers, 
            rows=rows,
            summary=summary,
            footer=footer
        )
    
    def generate_query_history_report(self, query_history: List[WeatherQuery], limit: int = 50) -> WeatherReport:
        """
        Generate a query history report.
        
        Args:
            query_history: List of query history entries
            limit: Maximum number of entries to include
            
        Returns:
            WeatherReport with query history
        """
        if not query_history:
            return WeatherReport("Query History Report", [], [])
        
        # Limit and sort by most recent
        history = sorted(query_history, key=lambda q: q.query_time, reverse=True)[:limit]
        
        headers = [
            "Date/Time", 
            "Location",
            "Type",
            "Temperature",
            "Conditions"
        ]
        
        rows = []
        for query in history:
            time_str = query.query_time.strftime("%m/%d %H:%M")
            location_str = f"{query.location.city}, {query.location.country}"
            query_type = query.query_type.title()
            
            if query.weather_data:
                temp_str = self.formatter.format_temperature(query.weather_data.temperature)
                conditions = query.weather_data.description.title()
            else:
                temp_str = "-"
                conditions = "Forecast"
            
            rows.append([time_str, location_str, query_type, temp_str, conditions])
        
        title = f"Query History Report"
        summary = f"Showing {len(rows)} most recent queries out of {len(query_history)} total"
        footer = f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return WeatherReport(
            title=title,
            headers=headers,
            rows=rows,
            summary=summary,
            footer=footer
        )
    
    def generate_location_statistics_report(self, query_history: List[WeatherQuery]) -> WeatherReport:
        """
        Generate location usage statistics report.
        
        Args:
            query_history: List of query history entries
            
        Returns:
            WeatherReport with location statistics
        """
        if not query_history:
            return WeatherReport("Location Statistics Report", [], [])
        
        # Count queries by location
        location_counts = {}
        location_last_query = {}
        location_avg_temp = {}
        location_temp_count = {}
        
        for query in query_history:
            location_key = f"{query.location.city}, {query.location.country}"
            
            # Count queries
            location_counts[location_key] = location_counts.get(location_key, 0) + 1
            
            # Track last query time
            if location_key not in location_last_query or query.query_time > location_last_query[location_key]:
                location_last_query[location_key] = query.query_time
            
            # Track average temperature
            if query.weather_data:
                if location_key not in location_avg_temp:
                    location_avg_temp[location_key] = 0
                    location_temp_count[location_key] = 0
                location_avg_temp[location_key] += query.weather_data.temperature
                location_temp_count[location_key] += 1
        
        # Calculate averages
        for location_key in location_avg_temp:
            if location_temp_count[location_key] > 0:
                location_avg_temp[location_key] /= location_temp_count[location_key]
        
        # Sort by query count
        sorted_locations = sorted(location_counts.items(), key=lambda x: x[1], reverse=True)
        
        headers = [
            "Location",
            "Queries",
            "Last Query",
            "Avg Temp",
            "Temp Samples"
        ]
        
        rows = []
        for location_key, count in sorted_locations:
            last_query = location_last_query[location_key].strftime("%m/%d %H:%M")
            
            if location_key in location_avg_temp and location_temp_count[location_key] > 0:
                avg_temp = self.formatter.format_temperature(location_avg_temp[location_key])
                temp_samples = str(location_temp_count[location_key])
            else:
                avg_temp = "-"
                temp_samples = "0"
            
            rows.append([location_key, str(count), last_query, avg_temp, temp_samples])
        
        # Generate summary statistics
        total_queries = len(query_history)
        unique_locations = len(location_counts)
        most_popular = sorted_locations[0][0] if sorted_locations else "None"
        
        title = "Location Statistics Report"
        summary = f"Total: {total_queries} queries across {unique_locations} unique locations | "
        summary += f"Most popular: {most_popular}"
        footer = f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return WeatherReport(
            title=title,
            headers=headers,
            rows=rows,
            summary=summary,
            footer=footer
        )
    
    def generate_temperature_trend_report(self, location: Location, historical_data: List[tuple]) -> WeatherReport:
        """
        Generate a temperature trend report for a location.
        
        Args:
            location: Location object
            historical_data: List of (timestamp, weather_data) tuples
            
        Returns:
            WeatherReport showing temperature trends
        """
        if not historical_data:
            return WeatherReport(f"Temperature Trends - {location}", [], [])
        
        # Sort by timestamp
        sorted_data = sorted(historical_data, key=lambda x: x[0])
        
        headers = [
            "Date/Time",
            "Temperature", 
            "Feels Like",
            "Conditions",
            "Change",
            "Trend"
        ]
        
        rows = []
        prev_temp = None
        
        for i, (timestamp, weather_data) in enumerate(sorted_data):
            time_str = timestamp.strftime("%m/%d %H:%M")
            temp_str = self.formatter.format_temperature(weather_data.temperature)
            feels_like_str = self.formatter.format_temperature(weather_data.feels_like)
            conditions = weather_data.description.title()
            
            # Calculate temperature change
            if prev_temp is not None:
                change = weather_data.temperature - prev_temp
                if abs(change) < 0.5:
                    change_str = "~"
                    trend = "→"
                elif change > 0:
                    change_str = f"+{self.formatter.format_temperature(change, show_unit=False)}"
                    trend = "↑"
                else:
                    change_str = f"{self.formatter.format_temperature(change, show_unit=False)}"
                    trend = "↓"
            else:
                change_str = "-"
                trend = "-"
            
            rows.append([time_str, temp_str, feels_like_str, conditions, change_str, trend])
            prev_temp = weather_data.temperature
        
        # Calculate overall trend
        if len(sorted_data) >= 2:
            first_temp = sorted_data[0][1].temperature
            last_temp = sorted_data[-1][1].temperature
            overall_change = last_temp - first_temp
            time_span = sorted_data[-1][0] - sorted_data[0][0]
            
            title = f"Temperature Trends - {location.city}, {location.country}"
            summary = f"Overall change: {self.formatter.format_temperature(overall_change, show_unit=False)} over {time_span.days} days"
        else:
            title = f"Temperature Trends - {location.city}, {location.country}"
            summary = "Insufficient data for trend analysis"
        
        footer = f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return WeatherReport(
            title=title,
            headers=headers,
            rows=rows,
            summary=summary,
            footer=footer
        )


class ReportExporter:
    """
    Handles exporting reports to various formats.
    
    Supported formats:
    - Plain text (table format)
    - CSV
    - JSON
    """
    
    @staticmethod
    def export_to_file(report: WeatherReport, filename: str, format: str = "auto") -> bool:
        """
        Export report to a file.
        
        Args:
            report: WeatherReport to export
            filename: Output filename
            format: Export format ("txt", "csv", "json", "auto")
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            if format == "auto":
                # Detect format from filename
                if filename.lower().endswith(".csv"):
                    format = "csv"
                elif filename.lower().endswith(".json"):
                    format = "json" 
                else:
                    format = "txt"
            
            if format == "csv":
                content = report.to_csv()
            elif format == "json":
                content = json.dumps(report.to_dict(), indent=2, ensure_ascii=False)
            else:  # txt format
                content = report.to_table_string()
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True
            
        except Exception as e:
            print(f"Error exporting report: {e}")
            return False
    
    @staticmethod
    def export_multiple_reports(reports: Dict[str, WeatherReport], base_filename: str, format: str = "txt") -> Dict[str, bool]:
        """
        Export multiple reports to separate files.
        
        Args:
            reports: Dictionary of report_name -> WeatherReport
            base_filename: Base filename (will be modified for each report)
            format: Export format
            
        Returns:
            Dictionary of report_name -> success_status
        """
        results = {}
        
        for report_name, report in reports.items():
            # Generate filename
            safe_name = report_name.lower().replace(" ", "_").replace("/", "_")
            if format == "csv":
                filename = f"{base_filename}_{safe_name}.csv"
            elif format == "json":
                filename = f"{base_filename}_{safe_name}.json"
            else:
                filename = f"{base_filename}_{safe_name}.txt"
            
            # Export report
            results[report_name] = ReportExporter.export_to_file(report, filename, format)
        
        return results


def create_sample_reports(formatter: WeatherFormatter) -> Dict[str, WeatherReport]:
    """
    Create sample reports for demonstration purposes.
    
    Args:
        formatter: WeatherFormatter instance
        
    Returns:
        Dictionary of sample reports
    """
    generator = WeatherReportGenerator(formatter)
    
    # Sample data (normally would come from actual API calls)
    from data_structures import Location, WeatherData
    from datetime import datetime
    
    # Sample locations and weather data
    london = Location("London", "GB", 51.5074, -0.1278)
    paris = Location("Paris", "FR", 48.8566, 2.3522)
    tokyo = Location("Tokyo", "JP", 35.6762, 139.6503)
    
    london_weather = WeatherData(
        city="London",
        country="GB", 
        temperature=15.2,
        feels_like=14.1,
        humidity=78,
        pressure=1013,
        wind_speed=3.2,
        wind_direction=245,
        description="partly cloudy",
        timestamp=datetime.now()
    )
    
    paris_weather = WeatherData(
        city="Paris",
        country="FR",
        temperature=18.5,
        feels_like=17.8,
        humidity=65,
        pressure=1018,
        wind_speed=2.1,
        wind_direction=190,
        description="clear sky",
        timestamp=datetime.now()
    )
    
    tokyo_weather = WeatherData(
        city="Tokyo",
        country="JP",
        temperature=22.1,
        feels_like=24.3,
        humidity=85,
        pressure=1008,
        wind_speed=1.5,
        wind_direction=120,
        description="light rain",
        timestamp=datetime.now()
    )
    
    # Generate reports
    reports = {}
    
    # Current weather comparison
    current_data = [
        (london, london_weather),
        (paris, paris_weather),
        (tokyo, tokyo_weather)
    ]
    reports["Current Weather"] = generator.generate_current_weather_report(current_data)
    
    return reports


if __name__ == "__main__":
    """Demo the reporting functionality."""
    from unit_converter import create_metric_preferences, WeatherFormatter
    
    # Create formatter
    preferences = create_metric_preferences()
    formatter = WeatherFormatter(preferences)
    
    # Generate sample reports
    reports = create_sample_reports(formatter)
    
    # Display reports
    for name, report in reports.items():
        print(f"\n{name}:")
        print("=" * 60)
        print(report.to_table_string())
        print()