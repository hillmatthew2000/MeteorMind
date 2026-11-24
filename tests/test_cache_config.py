import json
import os
import sys
from pathlib import Path

import pytest

from meteormind import paths
from meteormind.cache import ResponseCache
from meteormind.config import ConfigError, ConfigManager, mask_api_key
from meteormind.jsonio import atomic_write_json, read_json

from .conftest import API_KEY


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


class TestResponseCache:
    def test_expires_after_ttl(self) -> None:
        clock = FakeClock()
        cache = ResponseCache(ttl_seconds=60, clock=clock)
        cache.set("k", {"v": 1})
        clock.now += 59
        assert cache.get("k") == {"v": 1}
        clock.now += 2
        assert cache.get("k") is None
        assert len(cache) == 0

    def test_persists_between_instances(self, tmp_path: Path) -> None:
        path = tmp_path / "cache.json"
        clock = FakeClock()
        ResponseCache(path, ttl_seconds=60, clock=clock).set("k", [1, 2])
        assert ResponseCache(path, ttl_seconds=60, clock=clock).get("k") == [1, 2]

    def test_bounded_size_evicts_oldest(self) -> None:
        clock = FakeClock()
        cache = ResponseCache(ttl_seconds=600, max_entries=2, clock=clock)
        for key in ("a", "b", "c"):
            cache.set(key, key)
            clock.now += 1
        assert cache.get("a") is None
        assert cache.get("c") == "c"

    def test_clear_removes_file(self, tmp_path: Path) -> None:
        path = tmp_path / "cache.json"
        cache = ResponseCache(path)
        cache.set("k", 1)
        assert path.exists()
        cache.clear()
        assert not path.exists()
        assert cache.get("k") is None

    def test_ignores_unknown_file_format(self, tmp_path: Path) -> None:
        path = tmp_path / "cache.json"
        path.write_text(json.dumps({"version": 99, "entries": {"k": [0, 1]}}), encoding="utf-8")
        assert ResponseCache(path).get("k") is None


class TestJsonIO:
    def test_round_trip_and_no_temp_files_left(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "data.json"
        atomic_write_json(path, {"city": "São Paulo"})
        assert read_json(path) == {"city": "São Paulo"}
        assert [p.name for p in path.parent.iterdir()] == ["data.json"]

    def test_missing_and_empty_files(self, tmp_path: Path) -> None:
        assert read_json(tmp_path / "missing.json") is None
        (tmp_path / "empty.json").write_text("  \n", encoding="utf-8")
        assert read_json(tmp_path / "empty.json") is None

    def test_corrupt_file_is_moved_aside(self, tmp_path: Path) -> None:
        path = tmp_path / "data.json"
        path.write_text("{not json", encoding="utf-8")
        assert read_json(path) is None
        assert not path.exists()
        (quarantined,) = tmp_path.glob("data.json.corrupt-*")
        assert quarantined.read_text(encoding="utf-8") == "{not json"


class TestPaths:
    def test_override(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("METEORMIND_HOME", str(tmp_path / "x"))
        assert paths.app_dir() == tmp_path / "x"

    def test_platform_default(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv("METEORMIND_HOME")
        if sys.platform == "win32":
            monkeypatch.setenv("APPDATA", str(tmp_path))
            assert paths.app_dir() == tmp_path / "MeteorMind"
        elif sys.platform != "darwin":
            monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
            assert paths.app_dir() == tmp_path / "meteormind"


class TestConfigManager:
    @pytest.fixture
    def config(self, tmp_path: Path) -> ConfigManager:
        return ConfigManager(config_dir=tmp_path / "cfg", legacy_dirs=[tmp_path / "legacy"])

    def test_no_key(self, config: ConfigManager) -> None:
        lookup = config.find_api_key()
        assert not lookup.found
        assert config.get_api_key() is None

    def test_environment_variables_win(
        self, config: ConfigManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config.save_api_key(API_KEY)
        monkeypatch.setenv("WEATHER_API_KEY", " env-key ")
        assert config.find_api_key().key == "env-key"
        monkeypatch.setenv("OPENWEATHER_API_KEY", "primary")
        lookup = config.find_api_key()
        assert lookup.key == "primary"
        assert lookup.source is not None and "OPENWEATHER_API_KEY" in lookup.source

    def test_save_and_clear(self, config: ConfigManager) -> None:
        path = config.save_api_key(f"  {API_KEY}  ")
        assert json.loads(path.read_text(encoding="utf-8")) == {"api_key": API_KEY}
        if os.name == "posix":
            assert path.stat().st_mode & 0o077 == 0
        assert config.get_api_key() == API_KEY
        assert config.clear_api_key()
        assert config.get_api_key() is None
        assert not config.clear_api_key()

    def test_save_keeps_other_settings(self, config: ConfigManager) -> None:
        atomic_write_json(config.config_file, {"theme": "dark"})
        config.save_api_key(API_KEY)
        assert read_json(config.config_file) == {"theme": "dark", "api_key": API_KEY}

    def test_rejects_malformed_key(self, config: ConfigManager) -> None:
        with pytest.raises(ConfigError):
            config.save_api_key("not-a-key")
        assert not config.config_file.exists()

    def test_reads_legacy_files(self, config: ConfigManager, tmp_path: Path) -> None:
        legacy = tmp_path / "legacy"
        legacy.mkdir()
        (legacy / ".env").write_text(
            '# comment\nexport OPENWEATHER_API_KEY="abc123"\n', encoding="utf-8"
        )
        assert config.find_api_key().key == "abc123"
        (legacy / "config.json").write_text(json.dumps({"api_key": "fromjson"}), encoding="utf-8")
        lookup = config.find_api_key()
        assert lookup.key == "fromjson"
        assert lookup.source == str(legacy / "config.json")

    def test_validate_format(self) -> None:
        assert ConfigManager.validate_api_key(API_KEY)
        assert ConfigManager.validate_api_key(API_KEY.upper())
        for bad in ("", "short", API_KEY + "0", "g" * 32, None):
            assert not ConfigManager.validate_api_key(bad)

    def test_status_never_contains_the_key(self, config: ConfigManager) -> None:
        config.save_api_key(API_KEY)
        status = config.check_configuration()
        assert status["api_key_found"]
        assert API_KEY not in json.dumps(status)
        assert status["api_key_masked"] == mask_api_key(API_KEY) == "••••…cdef"

    def test_instructions_mention_signup(self) -> None:
        assert "openweathermap.org" in ConfigManager.get_setup_instructions()
