import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from meteormind.history import HistoryManager
from meteormind.models import Location, WeatherQuery
from meteormind.preferences import Preferences
from meteormind.storage import (
    DataStore,
    StorageError,
    default_favorites,
    format_file_size,
    migrate_legacy_data,
)
from meteormind.units import (
    PressureUnit,
    TemperatureUnit,
    UnitPreferences,
    WindSpeedUnit,
    create_imperial_preferences,
)

from .test_models import make_location, make_weather

NOW = datetime(2025, 6, 1, 12, 0)

# Files exactly as written by the version that stored data in ./data
LEGACY_FAVORITES = {
    "version": "1.0",
    "saved_at": "2025-05-01T10:00:00",
    "locations": [
        {
            "city": "Oslo",
            "country": "NO",
            "latitude": 59.91,
            "longitude": 10.75,
            "added_date": "2025-04-01T09:00:00",
        }
    ],
}
LEGACY_PREFERENCES = {
    "version": "1.0",
    "saved_at": "2025-05-01T10:00:00",
    "preferences": {
        "units": "imperial",
        "temperature_unit": "celsius",
        "max_recent_queries": 50,
        "cache_duration_minutes": 15,
        "auto_refresh": False,
        "theme": "dark",
    },
}


def legacy_queries(now: datetime) -> dict[str, object]:
    recent = WeatherQuery(make_location("Oslo", "NO"), now - timedelta(days=1), make_weather())
    old = WeatherQuery(make_location("Bergen", "NO"), now - timedelta(days=45))
    return {
        "version": "1.0",
        "saved_at": now.isoformat(),
        "queries": [old.to_dict(), recent.to_dict(), {"location": "not a location"}],
    }


@pytest.fixture
def store(tmp_path: Path) -> DataStore:
    return DataStore(tmp_path / "app")


class TestFavorites:
    def test_first_run_gets_defaults_without_writing(self, store: DataStore) -> None:
        favorites = store.load_favorite_locations()
        assert [loc.city for loc in favorites] == [loc.city for loc in default_favorites()]
        assert not store.favorites_file.exists()

    def test_round_trip_keeps_order(self, store: DataStore) -> None:
        places = [make_location("York"), make_location("Bath"), make_location("Ely")]
        store.save_favorite_locations(places)
        assert list(store.load_favorite_locations()) == places

    def test_saved_empty_list_stays_empty(self, store: DataStore) -> None:
        store.save_favorite_locations([])
        assert len(store.load_favorite_locations()) == 0

    def test_reads_legacy_format(self, store: DataStore) -> None:
        store.directory.mkdir(parents=True)
        store.favorites_file.write_text(json.dumps(LEGACY_FAVORITES), encoding="utf-8")
        (oslo,) = store.load_favorite_locations()
        assert (oslo.city, oslo.country, oslo.added_date) == ("Oslo", "NO", datetime(2025, 4, 1, 9))

    def test_corrupt_file_is_kept_aside(self, store: DataStore) -> None:
        store.directory.mkdir(parents=True)
        store.favorites_file.write_text("{oops", encoding="utf-8")
        assert len(store.load_favorite_locations()) == 0
        assert list(store.directory.glob("favorites.json.corrupt-*"))

    def test_write_failure_raises_storage_error(self, tmp_path: Path) -> None:
        blocker = tmp_path / "file"
        blocker.write_text("", encoding="utf-8")
        with pytest.raises(StorageError):
            DataStore(blocker / "app").save_favorite_locations([])


class TestHistoryFile:
    def test_drops_old_and_invalid_entries(self, store: DataStore) -> None:
        store.directory.mkdir(parents=True)
        store.history_file.write_text(json.dumps(legacy_queries(NOW)), encoding="utf-8")
        (query,) = store.load_history(now=NOW)
        assert query.location.city == "Oslo"
        assert query.weather_data is not None

    def test_missing_file(self, store: DataStore) -> None:
        assert store.load_history() == []


class TestPreferences:
    def test_defaults(self, store: DataStore) -> None:
        prefs = store.load_preferences()
        assert prefs == Preferences()
        assert prefs.cache_seconds == 600

    def test_round_trip(self, store: DataStore) -> None:
        prefs = Preferences(create_imperial_preferences(), "dark", 250, 5)
        store.save_preferences(prefs)
        assert store.load_preferences() == prefs
        assert json.loads(store.preferences_file.read_text(encoding="utf-8"))["version"] == 2

    def test_reads_legacy_format(self) -> None:
        prefs = Preferences.from_dict(LEGACY_PREFERENCES)
        assert prefs.units == create_imperial_preferences()
        assert (prefs.theme, prefs.history_limit, prefs.cache_minutes) == ("dark", 50, 15)

    def test_legacy_unit_dict(self) -> None:
        data = {"preferences": {"units": {"temperature": "kelvin", "wind_speed": "knots"}}}
        units = Preferences.from_dict(data).units
        assert units.temperature is TemperatureUnit.KELVIN
        assert units.wind_speed is WindSpeedUnit.KNOTS
        assert units.pressure is PressureUnit.HECTOPASCAL

    @pytest.mark.parametrize(
        "data",
        [
            None,
            [],
            {"theme": "neon", "history_limit": "lots", "cache_minutes": True},
            {"units": 42},
        ],
    )
    def test_bad_values_fall_back_to_defaults(self, data: object) -> None:
        assert Preferences.from_dict(data) == Preferences()

    def test_limits_are_clamped(self) -> None:
        prefs = Preferences.from_dict({"history_limit": 5, "cache_minutes": 10_000})
        assert (prefs.history_limit, prefs.cache_minutes) == (10, 120)


class TestMigration:
    @pytest.fixture
    def legacy_dir(self, tmp_path: Path) -> Path:
        legacy = tmp_path / "data"
        legacy.mkdir()
        (legacy / "favorite_locations.json").write_text(
            json.dumps(LEGACY_FAVORITES), encoding="utf-8"
        )
        (legacy / "user_preferences.json").write_text(
            json.dumps(LEGACY_PREFERENCES), encoding="utf-8"
        )
        (legacy / "recent_queries.json").write_text(
            json.dumps(legacy_queries(datetime.now())), encoding="utf-8"
        )
        (legacy / "weather_cache.json").write_text("{}", encoding="utf-8")
        return legacy

    def test_copies_files_and_loaders_read_them(self, legacy_dir: Path, store: DataStore) -> None:
        created = migrate_legacy_data(legacy_dir, store.directory)
        assert sorted(p.name for p in created) == [
            "favorites.json",
            "history.json",
            "preferences.json",
        ]
        assert [loc.city for loc in store.load_favorite_locations()] == ["Oslo"]
        assert store.load_preferences().theme == "dark"
        assert [q.location.city for q in store.load_history()] == ["Oslo"]
        # The originals are left alone and the old cache is not carried over.
        assert (legacy_dir / "favorite_locations.json").exists()
        assert not store.cache_file.exists()

    def test_never_overwrites_new_data(self, legacy_dir: Path, store: DataStore) -> None:
        store.save_favorite_locations([make_location("Leeds")])
        created = migrate_legacy_data(legacy_dir, store.directory)
        assert store.favorites_file not in created
        assert [loc.city for loc in store.load_favorite_locations()] == ["Leeds"]
        assert migrate_legacy_data(legacy_dir, store.directory) == []

    def test_missing_or_same_directory(self, tmp_path: Path, store: DataStore) -> None:
        assert migrate_legacy_data(tmp_path / "nowhere", store.directory) == []
        store.directory.mkdir(parents=True)
        assert migrate_legacy_data(store.directory, store.directory) == []


class TestMaintenance:
    def test_file_info(self, store: DataStore) -> None:
        store.save_preferences(Preferences())
        info = {i.name: i for i in store.file_info()}
        assert info["Preferences"].exists and info["Preferences"].size_bytes > 0
        assert not info["History"].exists and info["History"].modified is None

    def test_backup_copies_data_but_not_cache(self, store: DataStore) -> None:
        store.save_favorite_locations([make_location("York")])
        store.save_preferences(Preferences())
        store.cache_file.write_text("{}", encoding="utf-8")
        target = store.backup(now=NOW)
        assert target == store.directory / "backups" / "20250601-120000"
        assert sorted(p.name for p in target.iterdir()) == ["favorites.json", "preferences.json"]

    def test_clear_all(self, store: DataStore) -> None:
        store.save_favorite_locations([make_location("York")])
        store.save_preferences(Preferences(theme="dark"))
        store.cache_file.write_text("{}", encoding="utf-8")
        store.clear_all()
        assert len(store.load_favorite_locations()) == 0
        assert store.load_history() == []
        assert store.load_preferences() == Preferences()
        assert not store.cache_file.exists()

    @pytest.mark.parametrize(
        ("size", "text"),
        [(0, "0 B"), (1023, "1023 B"), (1536, "1.5 KB"), (5 * 1024**2, "5.0 MB")],
    )
    def test_format_file_size(self, size: int, text: str) -> None:
        assert format_file_size(size) == text


class FakeClock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        self.now += timedelta(minutes=1)
        return self.now


class TestHistoryManager:
    @pytest.fixture
    def history(self, store: DataStore) -> HistoryManager:
        return HistoryManager(store, limit=3, clock=FakeClock())

    def test_add_saves_and_trims(self, history: HistoryManager, store: DataStore) -> None:
        for city in ("York", "Bath", "Ely", "Hull"):
            history.add_query(make_location(city), make_weather(city=city))
        assert [q.location.city for q in history.get_recent_queries()] == ["Hull", "Ely", "Bath"]
        reloaded = HistoryManager(store, limit=3, clock=FakeClock())
        assert [q.location.city for q in reloaded.get_recent_queries(2)] == ["Hull", "Ely"]

    def test_search_and_observations(self, history: HistoryManager) -> None:
        paris = Location("Paris", "FR", 48.9, 2.3, state="Ile-de-France")
        history.add_query(paris, make_weather(city="Paris", country="FR"))
        history.add_query(make_location("York"), None, "forecast")
        history.add_query(paris, None, "forecast")
        assert len(history.search_queries("ile-de")) == 2
        assert len(history.search_queries("fr")) == 2
        assert history.search_queries("nowhere") == []
        assert len(history.observations_for("paris")) == 1
        assert history.observations_for("Paris", "US") == []

    def test_statistics(self, history: HistoryManager) -> None:
        assert history.get_query_statistics().total_queries == 0
        history.add_query(make_location("York"), make_weather())
        history.add_query(make_location("York"), None, "forecast")
        history.add_query(make_location("Bath"), make_weather())
        stats = history.get_query_statistics()
        assert stats.total_queries == 3
        assert stats.top_locations == [("York, GB", 2), ("Bath, GB", 1)]
        assert stats.unique_locations == 2
        assert stats.query_types == {"current": 2, "forecast": 1}
        assert stats.first_query is not None and stats.last_query is not None
        assert stats.first_query < stats.last_query
        assert json.dumps(stats.to_dict())

    def test_set_limit_and_clear(self, history: HistoryManager, store: DataStore) -> None:
        for city in ("York", "Bath", "Ely"):
            history.add_query(make_location(city))
        history.set_limit(1)
        assert [q.location.city for q in store.load_history(now=NOW)] == ["Ely"]
        history.clear_history()
        assert len(history) == 0
        assert store.load_history(now=NOW) == []

    def test_export(self, history: HistoryManager, tmp_path: Path) -> None:
        history.add_query(make_location("York"), make_weather())
        path = history.export_history(tmp_path / "export.json")
        document = json.loads(path.read_text(encoding="utf-8"))
        assert document["statistics"]["total_queries"] == 1
        assert document["queries"][0]["location"]["city"] == "York"
        with pytest.raises(StorageError):
            history.export_history(tmp_path / "missing-dir" / "export.json")


def test_unit_preferences_default_is_metric() -> None:
    assert Preferences().units == UnitPreferences()
