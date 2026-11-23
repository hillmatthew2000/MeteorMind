"""API key discovery and storage.

The OpenWeatherMap API key is looked up in this order:

1. the ``OPENWEATHER_API_KEY`` environment variable
2. the ``WEATHER_API_KEY`` environment variable
3. ``config.json`` in the application directory (see :mod:`meteormind.paths`)
4. ``config.json`` or ``.env`` in the current working directory, the
   locations used by earlier versions

Keys entered through the CLI or GUI are saved to the application directory
with owner-only permissions, never next to the source code.
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .jsonio import atomic_write_json, read_json
from .paths import app_dir

API_KEY_ENV_VARS = ("OPENWEATHER_API_KEY", "WEATHER_API_KEY")
_DOTENV_KEYS = (*API_KEY_ENV_VARS, "API_KEY")
_API_KEY_PATTERN = re.compile(r"^[0-9a-fA-F]{32}$")

SIGNUP_URL = "https://home.openweathermap.org/users/sign_up"
API_KEYS_URL = "https://home.openweathermap.org/api_keys"


class ConfigError(Exception):
    """Raised when the configuration cannot be saved."""


@dataclass(frozen=True)
class ApiKeyLookup:
    """Where (if anywhere) an API key was found."""

    key: str | None
    source: str | None

    @property
    def found(self) -> bool:
        return self.key is not None


def mask_api_key(key: str) -> str:
    """Show only the last four characters of a key, e.g. ``••••…3f9a``."""
    return f"••••…{key[-4:]}" if len(key) > 4 else "••••"


def _read_dotenv(path: Path) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip().removeprefix("export ").strip()
        value = value.strip().strip("\"'")
        if name in _DOTENV_KEYS and value:
            return value
    return None


def _read_config_key(path: Path) -> str | None:
    data = read_json(path)
    if isinstance(data, dict):
        key = data.get("api_key")
        if isinstance(key, str) and key.strip():
            return key.strip()
    return None


class ConfigManager:
    """Finds, validates and stores the OpenWeatherMap API key."""

    def __init__(
        self,
        config_dir: Path | str | None = None,
        legacy_dirs: Sequence[Path | str] | None = None,
    ) -> None:
        self.config_dir = Path(config_dir) if config_dir is not None else app_dir()
        self.config_file = self.config_dir / "config.json"
        self.legacy_dirs = [
            Path(d) for d in (legacy_dirs if legacy_dirs is not None else [Path.cwd()])
        ]

    def find_api_key(self) -> ApiKeyLookup:
        for name in API_KEY_ENV_VARS:
            value = os.environ.get(name, "").strip()
            if value:
                return ApiKeyLookup(value, f"{name} environment variable")
        key = _read_config_key(self.config_file)
        if key:
            return ApiKeyLookup(key, str(self.config_file))
        for directory in self.legacy_dirs:
            if directory.resolve() == self.config_dir.resolve():
                continue
            key = _read_config_key(directory / "config.json")
            if key:
                return ApiKeyLookup(key, str(directory / "config.json"))
            key = _read_dotenv(directory / ".env")
            if key:
                return ApiKeyLookup(key, str(directory / ".env"))
        return ApiKeyLookup(None, None)

    def get_api_key(self) -> str | None:
        return self.find_api_key().key

    @staticmethod
    def validate_api_key(api_key: object) -> bool:
        """OpenWeatherMap keys are 32 hexadecimal characters."""
        return isinstance(api_key, str) and bool(_API_KEY_PATTERN.match(api_key.strip()))

    def save_api_key(self, api_key: str) -> Path:
        """Store ``api_key`` in the application config file and return its path."""
        api_key = api_key.strip()
        if not self.validate_api_key(api_key):
            raise ConfigError("An OpenWeatherMap API key is 32 hexadecimal characters.")
        existing = read_json(self.config_file)
        data = existing if isinstance(existing, dict) else {}
        data["api_key"] = api_key
        try:
            atomic_write_json(self.config_file, data, private=True)
        except OSError as exc:
            raise ConfigError(f"Could not write {self.config_file}: {exc}") from exc
        return self.config_file

    def clear_api_key(self) -> bool:
        """Remove a saved key from the application config. Returns True if one was removed."""
        data = read_json(self.config_file)
        if not isinstance(data, dict) or "api_key" not in data:
            return False
        del data["api_key"]
        try:
            atomic_write_json(self.config_file, data, private=True)
        except OSError as exc:
            raise ConfigError(f"Could not write {self.config_file}: {exc}") from exc
        return True

    def check_configuration(self) -> dict[str, object]:
        """Summarise the key configuration for status displays (the key itself is masked)."""
        lookup = self.find_api_key()
        return {
            "api_key_found": lookup.found,
            "api_key_source": lookup.source,
            "api_key_masked": mask_api_key(lookup.key) if lookup.key else None,
            "api_key_valid_format": self.validate_api_key(lookup.key),
            "config_file": str(self.config_file),
            "environment_variables": {
                name: bool(os.environ.get(name)) for name in API_KEY_ENV_VARS
            },
        }

    @staticmethod
    def get_setup_instructions() -> str:
        return f"""\
MeteorMind needs a free OpenWeatherMap API key.

1. Create an account: {SIGNUP_URL}
2. Copy your key from: {API_KEYS_URL}
   (new keys can take up to two hours to activate)
3. Then either enter it in Setup & Configuration, or set an
   environment variable:
       PowerShell:  $env:OPENWEATHER_API_KEY = "YOUR_KEY"
       bash/zsh:    export OPENWEATHER_API_KEY="YOUR_KEY"

Keys are stored in your user profile, never in the project folder."""
