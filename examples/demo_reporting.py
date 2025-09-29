#!/usr/bin/env python3
"""
Weather Reporting System Demonstration

This script demonstrates the comprehensive weather reporting capabilities
without requiring an API key or network connection.
"""

from datetime import datetime, timedelta
import random

# Import our reporting modules
from weather_reporting import WeatherReportGenerator, WeatherReport, ReportExporter
from unit_converter import WeatherFormatter, create_metric_preferences, create_imperial_preferences
from data_structures import WeatherData, Location, ForecastData, WeatherQuery


def create_sample_weather_data():
    """Create sample weather data for demonstration."""
    
    # Sample locations
    locations = [
        Location("London", "GB", 51.5074, -0.1278),
        Location("Paris", "FR", 48.8566, 2.3522),
        Location("Tokyo", "JP", 35.6762, 139.6503),
        Location("New York", "US", 40.7128, -74.0060),
        Location("Sydney", "AU", -33.8688, 151.2093)
    ]
    
    # Sample weather data for each location
    weather_data = []
    
    for location in locations:
        # Create realistic weather data
        base_temp = random.uniform(10, 25)  # Base temperature
        humidity = random.randint(40, 90)
        pressure = random.randint(990, 1030)
        wind_speed = random.uniform(1, 15)
        wind_direction = random.randint(0, 360)
        
        conditions = random.choice([
            "clear sky", "few clouds", "scattered clouds", 
            "overcast clouds", "light rain", "moderate rain",
            "partly cloudy", "sunny", "drizzle"
        ])
        
        weather = WeatherData(
            city=location.city,
            country=location.country,
            temperature=base_temp,
            feels_like=base_temp + random.uniform(-3, 3),
            humidity=humidity,
            pressure=pressure,
            wind_speed=wind_speed,
            wind_direction=wind_direction,
            description=conditions,
            timestamp=datetime.now()
        )
        
        weather_data.append((location, weather))
    
    return weather_data


def create_sample_forecast_data():
    """Create sample forecast data."""
    
    location = Location("London", "GB", 51.5074, -0.1278)
    forecast_data = []
    
    base_date = datetime.now().date()
    
    for i in range(5):
        date = base_date + timedelta(days=i)
        
        # Create realistic forecast
        temp_min = random.uniform(10, 20)
        temp_max = temp_min + random.uniform(5, 15)
        humidity = random.randint(40, 90)
        wind_speed = random.uniform(2, 12)
        precip_chance = random.randint(0, 80)
        
        conditions = random.choice([
            "clear sky", "partly cloudy", "cloudy", "light rain",
            "moderate rain", "sunny", "overcast", "drizzle"
        ])
        
        forecast = ForecastData(
            date=date,
            temperature_min=temp_min,
            temperature_max=temp_max,
            humidity=humidity,
            wind_speed=wind_speed,
            description=conditions,
            precipitation_chance=precip_chance
        )
        
        forecast_data.append(forecast)
    
    return location, forecast_data


def create_sample_query_history():
    """Create sample query history."""
    
    locations = [
        Location("London", "GB", 51.5074, -0.1278),
        Location("Paris", "FR", 48.8566, 2.3522),
        Location("Tokyo", "JP", 35.6762, 139.6503),
        Location("New York", "US", 40.7128, -74.0060),
        Location("Berlin", "DE", 52.5200, 13.4050)
    ]
    
    queries = []
    base_time = datetime.now()
    
    # Generate 50 sample queries over the past month
    for i in range(50):
        # Random time in the past month
        hours_ago = random.randint(1, 30 * 24)  # Up to 30 days ago
        query_time = base_time - timedelta(hours=hours_ago)
        
        # Random location
        location = random.choice(locations)
        
        # Random weather data (some queries might not have weather data)
        weather_data = None
        query_type = random.choice(["current", "forecast", "current", "current"])  # Bias towards current
        
        if query_type == "current" and random.random() > 0.2:  # 80% of current queries have data
            weather_data = WeatherData(
                city=location.city,
                country=location.country,
                temperature=random.uniform(10, 30),
                feels_like=random.uniform(10, 30),
                humidity=random.randint(30, 95),
                pressure=random.randint(990, 1030),
                wind_speed=random.uniform(0, 20),
                wind_direction=random.randint(0, 360),
                description=random.choice(["clear", "cloudy", "rainy", "sunny", "overcast"]),
                timestamp=query_time
            )
        
        query = WeatherQuery(
            location=location,
            query_time=query_time,
            weather_data=weather_data,
            query_type=query_type
        )
        
        queries.append(query)
    
    # Sort by time (most recent first)
    queries.sort(key=lambda q: q.query_time, reverse=True)
    
    return queries


def demonstrate_reporting():
    """Demonstrate all reporting features."""
    print("🌤️ WEATHER REPORTING SYSTEM DEMONSTRATION")
    print("=" * 60)
    print()
    
    # Create formatters for both unit systems
    metric_preferences = create_metric_preferences()
    imperial_preferences = create_imperial_preferences()
    
    metric_formatter = WeatherFormatter(metric_preferences)
    imperial_formatter = WeatherFormatter(imperial_preferences)
    
    # Create report generators
    metric_generator = WeatherReportGenerator(metric_formatter)
    imperial_generator = WeatherReportGenerator(imperial_formatter)
    
    print("📊 1. CURRENT WEATHER COMPARISON REPORT (Metric)")
    print("-" * 60)
    
    # Generate current weather comparison
    current_weather_data = create_sample_weather_data()
    current_report = metric_generator.generate_current_weather_report(current_weather_data)
    print(current_report.to_table_string())
    print()
    
    print("📅 2. DETAILED FORECAST REPORT (Imperial)")
    print("-" * 60)
    
    # Generate forecast report
    forecast_location, forecast_data = create_sample_forecast_data()
    forecast_report = imperial_generator.generate_detailed_forecast_report(forecast_location, forecast_data)
    print(forecast_report.to_table_string())
    print()
    
    print("📊 3. QUERY HISTORY REPORT")
    print("-" * 60)
    
    # Generate query history report
    query_history = create_sample_query_history()
    history_report = metric_generator.generate_query_history_report(query_history, 20)
    print(history_report.to_table_string())
    print()
    
    print("📍 4. LOCATION STATISTICS REPORT")
    print("-" * 60)
    
    # Generate location statistics
    location_stats_report = metric_generator.generate_location_statistics_report(query_history)
    print(location_stats_report.to_table_string())
    print()
    
    print("📈 5. TEMPERATURE TRENDS REPORT")
    print("-" * 60)
    
    # Create temperature trend data for London
    london = Location("London", "GB", 51.5074, -0.1278)
    trend_data = []
    base_time = datetime.now()
    base_temp = 15.0
    
    # Generate 10 data points over 5 days with realistic temperature variation
    for i in range(10):
        timestamp = base_time - timedelta(hours=i * 12)  # Every 12 hours
        temp_variation = random.uniform(-3, 3)
        temperature = base_temp + temp_variation + (i * 0.5)  # Slight warming trend
        
        weather = WeatherData(
            city="London",
            country="GB",
            temperature=temperature,
            feels_like=temperature + random.uniform(-2, 2),
            humidity=random.randint(60, 85),
            pressure=random.randint(1010, 1025),
            wind_speed=random.uniform(2, 8),
            wind_direction=random.randint(180, 270),
            description=random.choice(["partly cloudy", "overcast", "light rain", "clear"]),
            timestamp=timestamp
        )
        
        trend_data.append((timestamp, weather))
    
    trend_report = metric_generator.generate_temperature_trend_report(london, trend_data)
    print(trend_report.to_table_string())
    print()
    
    print("💾 6. EXPORT DEMONSTRATIONS")
    print("-" * 60)
    
    # Demonstrate exports
    print("Exporting reports to various formats...")
    
    # Export to different formats
    reports = {
        "current_weather": current_report,
        "forecast": forecast_report,
        "query_history": history_report,
        "location_stats": location_stats_report,
        "temperature_trends": trend_report
    }
    
    # Export each report in all formats
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    for report_name, report in reports.items():
        for format_type in ["txt", "csv", "json"]:
            filename = f"demo_{report_name}_{timestamp}.{format_type}"
            try:
                if ReportExporter.export_to_file(report, filename, format_type):
                    print(f"  ✅ {filename}")
                else:
                    print(f"  ❌ Failed: {filename}")
            except Exception as e:
                print(f"  ❌ Error exporting {filename}: {e}")
    
    print()
    print("📈 7. REPORT FORMAT DEMONSTRATIONS")
    print("-" * 60)
    
    # Show different formats for the same report
    sample_report = current_report
    
    print("📄 Plain Text Format:")
    print(sample_report.to_table_string(max_width=80))
    print()
    
    print("📊 CSV Format (first 5 lines):")
    csv_content = sample_report.to_csv()
    csv_lines = csv_content.split('\n')[:5]
    for line in csv_lines:
        print(line)
    print("...")
    print()
    
    print("📋 JSON Format (structure):")
    json_data = sample_report.to_dict()
    print(f"Title: {json_data['title']}")
    print(f"Headers: {json_data['headers']}")
    print(f"Rows: {len(json_data['rows'])} rows")
    print(f"Summary: {json_data['summary']}")
    print(f"Generated: {json_data['generated_at']}")
    print()
    
    print("🎉 DEMONSTRATION COMPLETE!")
    print("=" * 60)
    print("Features demonstrated:")
    print("  ✅ Current weather comparison reports")
    print("  ✅ Detailed forecast reports")
    print("  ✅ Query history analysis")
    print("  ✅ Location usage statistics")
    print("  ✅ Temperature trend analysis")
    print("  ✅ Multiple export formats (TXT, CSV, JSON)")
    print("  ✅ Unit system support (Metric/Imperial)")
    print("  ✅ Formatted table output")
    print("  ✅ Summary statistics")
    print()
    print("All reports have been exported to files for your review!")
    print("Check the current directory for demo_*.txt, demo_*.csv, and demo_*.json files.")


def main():
    """Main demonstration entry point."""
    try:
        demonstrate_reporting()
    except Exception as e:
        print(f"❌ Error during demonstration: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()