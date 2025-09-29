"""
Configuration and API key management for the weather application.

This module provides secure handling of API keys and application configuration.
It supports multiple methods for storing sensitive information safely.
"""

import os
import json
from typing import Optional, Dict, Any
from pathlib import Path


class ConfigManager:
    """
    Manages application configuration and secure API key storage.
    
    Security Features:
    - Environment variable priority for API keys
    - No hardcoded credentials
    - Config file validation
    - Secure file permissions where possible
    - Clear instructions for setup
    """
    
    def __init__(self, config_dir: str = "."):
        """
        Initialize configuration manager.
        
        Args:
            config_dir: Directory to look for configuration files
        """
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "config.json"
        self.env_file = self.config_dir / ".env"
        
    def get_api_key(self) -> Optional[str]:
        """
        Get OpenWeatherMap API key from various sources.
        
        Priority order:
        1. Environment variable OPENWEATHER_API_KEY
        2. Environment variable WEATHER_API_KEY  
        3. config.json file
        4. .env file
        
        Returns:
            API key string or None if not found
        """
        # Try environment variables first (most secure)
        api_key = os.getenv('OPENWEATHER_API_KEY')
        if api_key:
            return api_key.strip()
        
        api_key = os.getenv('WEATHER_API_KEY')
        if api_key:
            return api_key.strip()
        
        # Try config.json file
        api_key = self._load_from_config_file()
        if api_key:
            return api_key
        
        # Try .env file
        api_key = self._load_from_env_file()
        if api_key:
            return api_key
        
        return None
    
    def _load_from_config_file(self) -> Optional[str]:
        """Load API key from config.json file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    api_key = config.get('api_key', '').strip()
                    return api_key if api_key else None
        except (json.JSONDecodeError, IOError, KeyError):
            pass
        return None
    
    def _load_from_env_file(self) -> Optional[str]:
        """Load API key from .env file."""
        try:
            if self.env_file.exists():
                with open(self.env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('#') or '=' not in line:
                            continue
                        
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"\'')
                        
                        if key in ['OPENWEATHER_API_KEY', 'WEATHER_API_KEY', 'API_KEY']:
                            return value if value else None
        except IOError:
            pass
        return None
    
    def validate_api_key(self, api_key: str) -> bool:
        """
        Validate API key format.
        
        Args:
            api_key: API key to validate
            
        Returns:
            True if format appears valid, False otherwise
        """
        if not api_key or not isinstance(api_key, str):
            return False
        
        # OpenWeatherMap API keys are typically 32 character hex strings
        api_key = api_key.strip()
        if len(api_key) != 32:
            return False
        
        # Check if it's hexadecimal
        try:
            int(api_key, 16)
            return True
        except ValueError:
            return False
    
    def setup_config_file(self, api_key: str, overwrite: bool = False) -> bool:
        """
        Create or update config.json file with API key.
        
        Args:
            api_key: OpenWeatherMap API key
            overwrite: Whether to overwrite existing config
            
        Returns:
            True if successful, False otherwise
        """
        if self.config_file.exists() and not overwrite:
            print(f"Config file already exists: {self.config_file}")
            return False
        
        if not self.validate_api_key(api_key):
            print("Invalid API key format. Expected 32-character hexadecimal string.")
            return False
        
        config = {
            "api_key": api_key,
            "default_units": "metric",
            "cache_duration_minutes": 10,
            "max_recent_queries": 50,
            "auto_refresh": False
        }
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            
            # Try to set secure permissions (Unix-like systems)
            try:
                os.chmod(self.config_file, 0o600)  # Owner read/write only
            except (OSError, AttributeError):
                pass  # Not supported on Windows
            
            print(f"Configuration saved to: {self.config_file}")
            return True
            
        except IOError as e:
            print(f"Error saving config file: {e}")
            return False
    
    def setup_env_file(self, api_key: str, overwrite: bool = False) -> bool:
        """
        Create or update .env file with API key.
        
        Args:
            api_key: OpenWeatherMap API key
            overwrite: Whether to overwrite existing .env file
            
        Returns:
            True if successful, False otherwise
        """
        if self.env_file.exists() and not overwrite:
            print(f"Environment file already exists: {self.env_file}")
            return False
        
        if not self.validate_api_key(api_key):
            print("Invalid API key format. Expected 32-character hexadecimal string.")
            return False
        
        env_content = f"""# OpenWeatherMap API Configuration
# Get your free API key from: https://openweathermap.org/api
OPENWEATHER_API_KEY={api_key}

# Optional: Set units preference
WEATHER_UNITS=metric

# Optional: Cache duration in minutes
WEATHER_CACHE_DURATION=10
"""
        
        try:
            with open(self.env_file, 'w', encoding='utf-8') as f:
                f.write(env_content)
            
            # Try to set secure permissions (Unix-like systems)
            try:
                os.chmod(self.env_file, 0o600)  # Owner read/write only
            except (OSError, AttributeError):
                pass  # Not supported on Windows
            
            print(f"Environment file saved to: {self.env_file}")
            return True
            
        except IOError as e:
            print(f"Error saving .env file: {e}")
            return False
    
    def get_setup_instructions(self) -> str:
        """
        Get setup instructions for API key configuration.
        
        Returns:
            Formatted setup instructions
        """
        return """
🌤️  Weather App API Key Setup Instructions

You need a free OpenWeatherMap API key to use this application.

STEP 1: Get your API key
1. Visit: https://openweathermap.org/api
2. Sign up for a free account
3. Navigate to API keys section
4. Copy your API key (32-character hex string)

STEP 2: Configure the API key (choose ONE method):

Method A - Environment Variable (Recommended):
   Set environment variable in your shell:
   
   Windows (PowerShell):
   $env:OPENWEATHER_API_KEY="your_api_key_here"
   
   Windows (Command Prompt):
   set OPENWEATHER_API_KEY=your_api_key_here
   
   Linux/Mac:
   export OPENWEATHER_API_KEY="your_api_key_here"

Method B - Configuration File:
   Create config.json in the app directory:
   {
     "api_key": "your_api_key_here",
     "default_units": "metric"
   }

Method C - Environment File:
   Create .env file in the app directory:
   OPENWEATHER_API_KEY=your_api_key_here

STEP 3: Test the setup
   Run the weather app to verify your API key works.

🔒 Security Notes:
- Never commit API keys to version control
- Use environment variables for production
- Keep your API key secret
- The free tier allows 1,000 calls/day

Need help? Check that your API key is exactly 32 characters and hexadecimal.
"""
    
    def check_configuration(self) -> Dict[str, Any]:
        """
        Check current configuration status.
        
        Returns:
            Dictionary with configuration status information
        """
        status = {
            "api_key_found": False,
            "api_key_source": None,
            "api_key_valid_format": False,
            "config_file_exists": self.config_file.exists(),
            "env_file_exists": self.env_file.exists(),
            "environment_variables": {
                "OPENWEATHER_API_KEY": bool(os.getenv('OPENWEATHER_API_KEY')),
                "WEATHER_API_KEY": bool(os.getenv('WEATHER_API_KEY'))
            }
        }
        
        # Check for API key
        api_key = self.get_api_key()
        if api_key:
            status["api_key_found"] = True
            status["api_key_valid_format"] = self.validate_api_key(api_key)
            
            # Determine source
            if os.getenv('OPENWEATHER_API_KEY'):
                status["api_key_source"] = "OPENWEATHER_API_KEY environment variable"
            elif os.getenv('WEATHER_API_KEY'):
                status["api_key_source"] = "WEATHER_API_KEY environment variable"
            elif self._load_from_config_file():
                status["api_key_source"] = "config.json file"
            elif self._load_from_env_file():
                status["api_key_source"] = ".env file"
        
        return status
    
    def print_configuration_status(self) -> None:
        """Print current configuration status in a formatted way."""
        status = self.check_configuration()
        
        print("🔧 Configuration Status:")
        print(f"   API Key Found: {'✅' if status['api_key_found'] else '❌'}")
        
        if status['api_key_found']:
            print(f"   Source: {status['api_key_source']}")
            print(f"   Format Valid: {'✅' if status['api_key_valid_format'] else '❌'}")
        
        print(f"   Config File: {'✅' if status['config_file_exists'] else '❌'} ({self.config_file})")
        print(f"   Environment File: {'✅' if status['env_file_exists'] else '❌'} ({self.env_file})")
        
        env_vars = status['environment_variables']
        print("   Environment Variables:")
        for var, exists in env_vars.items():
            print(f"      {var}: {'✅' if exists else '❌'}")
        
        if not status['api_key_found']:
            print("\n❗ No API key configured. Run setup to configure one.")
        elif not status['api_key_valid_format']:
            print("\n⚠️  API key format appears invalid. Check your key.")


def interactive_setup():
    """Interactive setup wizard for API key configuration."""
    config_manager = ConfigManager()
    
    print("🌤️  Welcome to Weather App Setup!")
    print("=" * 50)
    
    # Check current status
    config_manager.print_configuration_status()
    
    # If already configured, ask if user wants to reconfigure
    if config_manager.get_api_key():
        reconfigure = input("\nAPI key already configured. Reconfigure? (y/N): ").lower().strip()
        if reconfigure not in ['y', 'yes']:
            print("Setup cancelled.")
            return
    
    print("\n" + config_manager.get_setup_instructions())
    
    # Get API key from user
    while True:
        api_key = input("Enter your OpenWeatherMap API key: ").strip()
        
        if not api_key:
            print("Setup cancelled.")
            return
        
        if config_manager.validate_api_key(api_key):
            break
        else:
            print("❌ Invalid API key format. Expected 32-character hexadecimal string.")
            retry = input("Try again? (y/N): ").lower().strip()
            if retry not in ['y', 'yes']:
                print("Setup cancelled.")
                return
    
    # Choose configuration method
    print("\nChoose configuration method:")
    print("1. Environment variable (recommended)")
    print("2. Configuration file (config.json)")
    print("3. Environment file (.env)")
    
    while True:
        choice = input("Enter choice (1-3): ").strip()
        
        if choice == "1":
            print(f"\nSet this environment variable in your shell:")
            print(f"OPENWEATHER_API_KEY={api_key}")
            print("\nFor PowerShell:")
            print(f"$env:OPENWEATHER_API_KEY=\"{api_key}\"")
            break
        elif choice == "2":
            if config_manager.setup_config_file(api_key, overwrite=True):
                print("✅ Configuration file created successfully!")
            else:
                print("❌ Failed to create configuration file.")
            break
        elif choice == "3":
            if config_manager.setup_env_file(api_key, overwrite=True):
                print("✅ Environment file created successfully!")
            else:
                print("❌ Failed to create environment file.")
            break
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")
    
    print("\n🎉 Setup complete! You can now use the weather app.")


if __name__ == "__main__":
    # Run interactive setup if called directly
    interactive_setup()