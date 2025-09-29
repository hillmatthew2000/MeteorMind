#!/usr/bin/env python3
"""
Quick test script to verify the weather application components.

This script performs basic validation of all modules without requiring
an API key or network connection.
"""

import sys
import os
from datetime import datetime


def test_imports():
    """Test that all modules can be imported successfully."""
    print("🧪 Testing module imports...")
    
    modules_to_test = [
        'data_structures',
        'api_handler', 
        'data_manager',
        'history_manager',
        'unit_converter',
        'validation',
        'config_manager',
        'weather_cli',
        'weather_gui',
        'weather_reporting'
    ]
    
    failed_imports = []
    
    for module_name in modules_to_test:
        try:
            __import__(module_name)
            print(f"  ✅ {module_name}")
        except ImportError as e:
            print(f"  ❌ {module_name}: {e}")
            failed_imports.append(module_name)
        except Exception as e:
            print(f"  ⚠️  {module_name}: {e}")
    
    if failed_imports:
        print(f"\n❌ Failed to import: {', '.join(failed_imports)}")
        return False
    else:
        print("\n✅ All modules imported successfully!")
        return True


def test_data_structures():
    """Test basic data structure functionality."""
    print("\n🧪 Testing data structures...")
    
    try:
        from data_structures import Location, WeatherData, FavoriteLocationsLinkedList
        
        # Test Location
        location = Location("London", "GB", 51.5074, -0.1278)
        assert location.city == "London"
        assert location.country == "GB"
        print("  ✅ Location creation")
        
        # Test WeatherData
        weather = WeatherData(
            city="London",
            country="GB", 
            temperature=20.5,
            feels_like=19.2,
            humidity=65,
            pressure=1013,
            wind_speed=3.5,
            wind_direction=180,
            description="clear sky"
        )
        assert weather.temperature == 20.5
        print("  ✅ WeatherData creation")
        
        # Test LinkedList
        favorites = FavoriteLocationsLinkedList()
        assert favorites.size == 0
        
        favorites.add_location(location)
        assert favorites.size == 1
        print("  ✅ LinkedList operations")
        
        # Test serialization
        location_dict = location.to_dict()
        assert 'city' in location_dict
        
        weather_dict = weather.to_dict()
        assert 'temperature' in weather_dict
        print("  ✅ Data serialization")
        
        print("✅ Data structures test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Data structures test failed: {e}")
        return False


def test_unit_converter():
    """Test unit conversion functionality."""
    print("\n🧪 Testing unit conversion...")
    
    try:
        from unit_converter import WeatherFormatter, create_metric_preferences, create_imperial_preferences
        
        # Test metric preferences
        metric_prefs = create_metric_preferences()
        metric_formatter = WeatherFormatter(metric_prefs)
        
        temp_str = metric_formatter.format_temperature(20.5)
        assert "°C" in temp_str
        print("  ✅ Metric temperature formatting")
        
        # Test imperial preferences  
        imperial_prefs = create_imperial_preferences()
        imperial_formatter = WeatherFormatter(imperial_prefs)
        
        temp_str = imperial_formatter.format_temperature(20.5)
        assert "°F" in temp_str
        print("  ✅ Imperial temperature formatting")
        
        # Test wind speed
        wind_str = metric_formatter.format_wind_speed(5.2)
        assert "m/s" in wind_str
        print("  ✅ Wind speed formatting")
        
        # Test pressure
        pressure_str = metric_formatter.format_pressure(1013)
        assert "hPa" in pressure_str
        print("  ✅ Pressure formatting")
        
        print("✅ Unit conversion test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Unit conversion test failed: {e}")
        return False


def test_validation():
    """Test input validation functionality."""
    print("\n🧪 Testing input validation...")
    
    try:
        from validation import InputValidator
        
        # Test city name validation
        result = InputValidator.validate_city_name("London")
        assert result.is_valid
        print("  ✅ Valid city name")
        
        result = InputValidator.validate_city_name("")
        assert not result.is_valid
        print("  ✅ Invalid city name rejection")
        
        # Test country code validation
        result = InputValidator.validate_country_code("GB")
        assert result.is_valid
        print("  ✅ Valid country code")
        
        result = InputValidator.validate_country_code("INVALID")
        assert not result.is_valid
        print("  ✅ Invalid country code rejection")
        
        print("✅ Input validation test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Input validation test failed: {e}")
        return False


def test_config_manager():
    """Test configuration management."""
    print("\n🧪 Testing configuration management...")
    
    try:
        from config_manager import ConfigManager
        
        config_manager = ConfigManager()
        
        # Test API key validation
        valid_key = "1234567890abcdef1234567890abcdef"
        assert config_manager.validate_api_key(valid_key)
        print("  ✅ Valid API key format")
        
        invalid_key = "invalid"
        assert not config_manager.validate_api_key(invalid_key)
        print("  ✅ Invalid API key rejection")
        
        # Test configuration check
        status = config_manager.check_configuration()
        assert 'api_key_found' in status
        print("  ✅ Configuration status check")
        
        print("✅ Configuration management test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Configuration management test failed: {e}")
        return False


def test_weather_reporting():
    """Test weather reporting functionality."""
    print("\n🧪 Testing weather reporting...")
    
    try:
        from weather_reporting import WeatherReportGenerator, WeatherReport
        from unit_converter import create_metric_preferences, WeatherFormatter
        
        # Create formatter
        preferences = create_metric_preferences()
        formatter = WeatherFormatter(preferences)
        generator = WeatherReportGenerator(formatter)
        
        # Test report creation
        report = WeatherReport(
            title="Test Report",
            headers=["Column 1", "Column 2"],
            rows=[["Data 1", "Data 2"], ["Data 3", "Data 4"]]
        )
        
        # Test table string generation
        table_str = report.to_table_string()
        assert "Test Report" in table_str
        assert "Column 1" in table_str
        print("  ✅ Report table generation")
        
        # Test CSV generation
        csv_str = report.to_csv()
        assert "Column 1" in csv_str
        print("  ✅ CSV export")
        
        # Test JSON generation
        report_dict = report.to_dict()
        assert 'title' in report_dict
        print("  ✅ JSON export")
        
        print("✅ Weather reporting test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Weather reporting test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("🌤️ WEATHER APPLICATION - Component Test Suite")
    print("=" * 60)
    print()
    
    tests = [
        test_imports,
        test_data_structures,
        test_unit_converter,
        test_validation,
        test_config_manager,
        test_weather_reporting
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test_func.__name__} crashed: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS")
    print("=" * 60)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📈 Success Rate: {passed / (passed + failed) * 100:.1f}%")
    
    if failed == 0:
        print("\n🎉 All tests passed! The application is ready to use.")
        print("\nNext steps:")
        print("1. Get your API key from https://openweathermap.org/api")
        print("2. Run: python main.py")
        print("3. Choose your interface and configure the API key")
        print("4. Start exploring weather data!")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please check the error messages above.")
        print("Make sure all required files are present and Python version is 3.7+")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)