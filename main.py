"""
Main entry point for the Weather Application.

This application provides comprehensive weather information with multiple interfaces:
- CLI: Command-line interface with full functionality
- GUI: Tkinter-based graphical interface
- API Integration: OpenWeatherMap for real-time data
- Data Management: Persistent storage with favorites and history

Features:
- Multiple location management using linked lists
- Persistent file storage with JSON format
- Weather query history tracking
- Secure API key management
- Unit conversion system (metric/imperial)
- Robust input validation and error handling
- Menu-driven interfaces
- Weather reporting and export functionality

Quick Start:
1. Get OpenWeatherMap API key from https://openweathermap.org/api
2. Run: python main.py
3. Choose interface mode (CLI or GUI)
4. Configure API key when prompted
5. Start exploring weather data!

Requirements:
- Python 3.7+
- requests library
- tkinter (usually included with Python)
"""

import sys
import argparse
from typing import Optional


def main():
    """Main entry point with command line argument support."""
    parser = argparse.ArgumentParser(
        description="Weather Application - Get current weather and forecasts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Show interface selection menu
  python main.py --cli              # Start CLI interface directly
  python main.py --gui              # Start GUI interface directly
  python main.py --help             # Show this help message

For more information, visit: https://openweathermap.org/api
        """
    )
    
    parser.add_argument(
        '--cli', 
        action='store_true',
        help='Start command-line interface directly'
    )
    
    parser.add_argument(
        '--gui', 
        action='store_true', 
        help='Start graphical user interface directly'
    )
    
    parser.add_argument(
        '--version', 
        action='version', 
        version='Weather Application v2.0.0'
    )
    
    args = parser.parse_args()
    
    # If specific interface is requested
    if args.cli:
        start_cli()
    elif args.gui:
        start_gui()
    else:
        # Show selection menu
        show_interface_selection()


def show_interface_selection():
    """Show interface selection menu."""
    print("🌤️  WEATHER APPLICATION")
    print("=" * 50)
    print()
    print("Welcome to the comprehensive weather application!")
    print("Choose your preferred interface:")
    print()
    print("1. 💻 Command Line Interface (CLI)")
    print("   - Full-featured text-based interface")
    print("   - Menu-driven navigation")
    print("   - Great for terminal users")
    print()
    print("2. 🖥️  Graphical User Interface (GUI)")
    print("   - User-friendly windows interface")
    print("   - Tabbed layout with visual elements")
    print("   - Mouse and keyboard navigation")
    print()
    print("3. ❓ Help - View documentation")
    print()
    print("4. 🚪 Exit")
    print()
    
    while True:
        try:
            choice = input("Enter your choice (1-4): ").strip()
            
            if choice == '1':
                start_cli()
                break
            elif choice == '2':
                start_gui()
                break
            elif choice == '3':
                show_help()
            elif choice == '4':
                print("\nGoodbye! Stay weather-aware! 🌈")
                sys.exit(0)
            else:
                print("❌ Invalid choice. Please enter 1, 2, 3, or 4.")
                
        except KeyboardInterrupt:
            print("\n\nGoodbye! Stay weather-aware! 🌈")
            sys.exit(0)
        except EOFError:
            print("\n\nGoodbye! Stay weather-aware! 🌈")
            sys.exit(0)


def start_cli():
    """Start the command-line interface."""
    try:
        from weather_cli import WeatherCLI
        print("\n🚀 Starting Command Line Interface...")
        print("=" * 50)
        
        cli = WeatherCLI()
        cli.run()
        
    except ImportError as e:
        print(f"❌ Error importing CLI module: {e}")
        print("Please ensure all required files are present.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting CLI: {e}")
        sys.exit(1)


def start_gui():
    """Start the graphical user interface."""
    try:
        import tkinter as tk
        from weather_gui import WeatherGUI
        
        print("\n🚀 Starting Graphical User Interface...")
        print("=" * 50)
        
        # Create root window
        root = tk.Tk()
        app = WeatherGUI(root)
        
        # Start the GUI main loop
        root.mainloop()
        
    except ImportError as e:
        print(f"❌ Error importing GUI modules: {e}")
        print("Please ensure tkinter is installed and all required files are present.")
        print("\nTo install tkinter:")
        print("- On Ubuntu/Debian: sudo apt-get install python3-tk")
        print("- On macOS: tkinter is usually included with Python")
        print("- On Windows: tkinter is usually included with Python")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting GUI: {e}")
        sys.exit(1)


def show_help():
    """Show help information."""
    print("\n📖 WEATHER APPLICATION HELP")
    print("=" * 50)
    print()
    print("🌟 FEATURES:")
    print("• Current weather for any city worldwide")
    print("• 5-day weather forecasts")
    print("• Favorite locations management")
    print("• Weather query history and analytics")
    print("• Unit conversion (metric/imperial)")
    print("• Data export functionality")
    print("• Secure API key management")
    print()
    print("🔧 SETUP:")
    print("1. Get a free API key from: https://openweathermap.org/api")
    print("2. Sign up for an account")
    print("3. Navigate to 'API keys' section")
    print("4. Copy your API key")
    print("5. Configure it in the application when prompted")
    print()
    print("💡 TIPS:")
    print("• City names can include country codes (e.g., 'London,GB')")
    print("• Use favorites for frequently checked locations")
    print("• Check history for past queries and statistics")
    print("• Export data for external analysis")
    print()
    print("🆘 TROUBLESHOOTING:")
    print("• API errors: Check your internet connection and API key")
    print("• City not found: Try alternative spellings or add country code")
    print("• Slow responses: OpenWeatherMap may be experiencing high load")
    print()
    print("📧 For more help, visit: https://openweathermap.org/api")
    print()
    input("Press Enter to continue...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nApplication interrupted. Goodbye! 🌈")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        print("Please check your installation and try again.")
        sys.exit(1)