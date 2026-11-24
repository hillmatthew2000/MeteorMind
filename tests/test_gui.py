"""Tests for the desktop app. Window tests are skipped when no display is available."""

from __future__ import annotations

import contextlib
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from meteormind.gui.theme import DARK, LIGHT, resolve_palette
from meteormind.gui.widgets import weather_symbol
from meteormind.gui.worker import BackgroundWorker
from meteormind.preferences import Preferences
from meteormind.service import WeatherService
from meteormind.storage import DataStore
from meteormind.units import create_imperial_preferences

from .test_service import FlakyProvider


class FakeScheduler:
    def __init__(self) -> None:
        self.calls: list[Callable[[], None]] = []

    def __call__(self, _delay: int, callback: Callable[[], None]) -> None:
        self.calls.append(callback)

    def run_until_idle(self, worker: BackgroundWorker, timeout: float = 5) -> None:
        deadline = time.monotonic() + timeout
        while worker.busy:
            assert time.monotonic() < deadline, "background job did not finish"
            time.sleep(0.005)
            while self.calls:
                self.calls.pop(0)()


class TestBackgroundWorker:
    def test_delivers_results_and_errors_on_the_calling_thread(self) -> None:
        scheduler = FakeScheduler()
        worker = BackgroundWorker(scheduler)
        results: list[Any] = []
        main = threading.get_ident()

        def record(value: Any) -> None:
            results.append((value, threading.get_ident() == main))

        worker.submit(lambda: threading.get_ident() != main, record, record)
        worker.submit(lambda: 1 / 0, record, lambda e: record(type(e).__name__))
        assert worker.busy
        scheduler.run_until_idle(worker)
        assert results == [(True, True), ("ZeroDivisionError", True)]
        worker.close()

    def test_jobs_run_in_order(self) -> None:
        scheduler = FakeScheduler()
        worker = BackgroundWorker(scheduler)
        seen: list[int] = []
        for n in range(5):
            worker.submit(lambda n=n: n, seen.append, pytest.fail)
        scheduler.run_until_idle(worker)
        assert seen == [0, 1, 2, 3, 4]
        worker.close()

    def test_broken_callback_does_not_stop_others(self) -> None:
        scheduler = FakeScheduler()
        worker = BackgroundWorker(scheduler)
        seen: list[int] = []

        def broken(_value: int) -> None:
            raise RuntimeError("bug")

        worker.submit(lambda: 1, broken, pytest.fail)
        worker.submit(lambda: 2, seen.append, pytest.fail)
        scheduler.run_until_idle(worker)
        assert seen == [2]
        worker.close()

    def test_nothing_is_delivered_after_close(self) -> None:
        scheduler = FakeScheduler()
        worker = BackgroundWorker(scheduler)
        worker.close()
        worker.submit(lambda: 1, pytest.fail, pytest.fail)
        assert not worker.busy and not scheduler.calls


def test_weather_symbols() -> None:
    assert weather_symbol("01d") == "☀"
    assert weather_symbol("01n") == "☾"
    assert weather_symbol("10n") == "☂"
    assert weather_symbol("") == "·"
    assert all(
        ord(ch) <= 0xFFFF for code in ("02d", "11d", "13d", "50d") for ch in weather_symbol(code)
    )


def test_palette_choice() -> None:
    assert resolve_palette("light") is LIGHT
    assert resolve_palette("dark") is DARK
    assert resolve_palette("system") in (LIGHT, DARK)


# Window tests ------------------------------------------------------------------

tk = pytest.importorskip("tkinter")


@pytest.fixture(scope="session")
def tk_root() -> Iterator[Any]:
    # One interpreter for the whole run: creating many Tk() instances in one
    # process is unreliable on some platforms.
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no display: {exc}")
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def root(tk_root: Any) -> Iterator[Any]:
    window = tk.Toplevel(tk_root)
    window.withdraw()
    yield window
    with contextlib.suppress(tk.TclError):
        window.destroy()


@pytest.fixture
def provider() -> FlakyProvider:
    return FlakyProvider()


@pytest.fixture
def service(tmp_path: Path, provider: FlakyProvider) -> WeatherService:
    service = WeatherService(DataStore(tmp_path / "data"), provider)
    service.update_preferences(Preferences(theme="light"))
    return service


@pytest.fixture
def app(root: Any, service: WeatherService) -> Any:
    from meteormind.gui.app import MeteorMindApp

    window = MeteorMindApp(root, service)
    pump(window)
    return window


def pump(app: Any, timeout: float = 5) -> None:
    """Process Tk events until background work has been delivered."""
    deadline = time.monotonic() + timeout
    app.root.update()
    while app.worker.busy:
        assert time.monotonic() < deadline, "background job did not finish"
        time.sleep(0.005)
        app.root.update()
    app.root.update()


def test_starts_with_the_first_favorite(app: Any) -> None:
    panel = app.weather_panel
    assert panel.current_state is panel.content
    assert panel.place_label.cget("text") == "London, England, GB"
    assert panel.favorite_button.cget("text") == "★ Favorite"
    assert app.favorites_tree.selection() == ("0",)
    assert "°C" in panel.temperature.cget("text")
    assert len([c for c in panel.cards if c.winfo_manager()]) == 5
    assert app.root.title() == "MeteorMind — demo data"


def test_search_and_favorite(app: Any) -> None:
    app.search_entry.set_value("Reykjavik")
    app.search()
    assert app.weather_panel.current_state is app.weather_panel.loading
    pump(app)
    assert app.weather_panel.place_label.cget("text") == "Reykjavik, IS"
    assert app.favorites_tree.selection() == ()
    app.toggle_favorite()
    assert app.service.favorites.find_location("Reykjavik", "IS") is not None
    assert app.favorites_tree.selection() == ("0",)
    app.toggle_favorite()
    assert app.service.favorites.find_location("Reykjavik", "IS") is None
    assert app.history_tree.get_children()


def test_invalid_and_unknown_places(app: Any) -> None:
    app.search_entry.set_value("12345")
    app.search()
    assert app.weather_panel.current_state is app.weather_panel.error
    assert "letters" in app.weather_panel.error_title.cget("text")
    app.search_entry.set_value("London, FR")
    app.search()
    pump(app)
    assert "No place called" in app.weather_panel.error_title.cget("text")


def test_place_picker(app: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    from meteormind.gui import app as app_module

    offered: list[list[str]] = []

    def pick(self: Any) -> Any:
        offered.append([p.display_name for p in self.places])
        self.destroy()
        return self.places[1]

    monkeypatch.setattr(app_module.PlacePicker, "ask", pick)
    app.search_entry.set_value("Springfield")
    app.search()
    pump(app)
    pump(app)
    assert offered == [["Springfield, Illinois, US", "Springfield, Missouri, US"]]
    assert app.weather_panel.place_label.cget("text") == "Springfield, Missouri, US"


def test_network_error_offers_retry(app: Any, provider: FlakyProvider) -> None:
    provider.failing.add("Paris")
    app.load_place(app.service.locate("Paris"))
    pump(app)
    panel = app.weather_panel
    assert panel.current_state is panel.error
    assert panel.error_title.cget("text") == "offline"
    assert panel.error_retry.winfo_manager()
    provider.failing.clear()
    panel.error_retry.invoke()
    pump(app)
    assert panel.place_label.cget("text") == "Paris, Ile-de-France, FR"


def test_units_and_theme(app: Any) -> None:
    app.set_units(create_imperial_preferences())
    assert "°F" in app.weather_panel.temperature.cget("text")
    assert app.unit_vars["wind_speed"].get() == "Miles per hour (mph)"
    app.unit_vars["temperature"].set("Kelvin (K)")
    app.apply_units_from_controls()
    assert app.service.store.load_preferences().units.temperature.value == "kelvin"
    app.toggle_theme()
    assert app.theme.palette is DARK
    assert app.service.store.load_preferences().theme == "dark"
    assert app.report_text.cget("background") == DARK.surface


def test_limits_are_clamped(app: Any) -> None:
    app.history_limit.set(5000)
    app.cache_minutes.set(3)
    app.apply_limits()
    assert (app.service.preferences.history_limit, app.service.preferences.cache_minutes) == (
        1000,
        3,
    )
    assert app.history_limit.get() == 1000


def test_reports(app: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from meteormind.gui import app as app_module

    app.report_kind.set(app_module.REPORT_LABELS["forecast"])
    app._update_report_controls()
    app.report_places.insert(0, "Cairo")
    app.report_days.set(2)
    app.generate_report()
    pump(app)
    assert "Cairo" in app.report_text.get("1.0", "end")
    assert len(app.report.rows) == 2

    target = tmp_path / "report.csv"
    monkeypatch.setattr(app_module.filedialog, "asksaveasfilename", lambda **_k: str(target))
    app.save_report()
    assert target.read_text(encoding="utf-8").count("Cairo") >= 1


def test_history_filter_and_export(
    app: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from meteormind.gui import app as app_module

    app.load_place(app.service.locate("Cairo"))
    pump(app)
    # Current weather and forecast for London (shown at start), then for Cairo.
    assert len(app.history_tree.get_children()) == 4
    app.history_filter.set_value("cairo")
    assert len(app.history_tree.get_children()) == 2
    target = tmp_path / "history.json"
    monkeypatch.setattr(app_module.filedialog, "asksaveasfilename", lambda **_k: str(target))
    app.export_history()
    assert target.exists()


def test_without_api_key(root: Any, tmp_path: Path) -> None:
    from meteormind.gui.app import MeteorMindApp

    service = WeatherService(DataStore(tmp_path), None)
    app = MeteorMindApp(root, service)
    pump(app)
    panel = app.weather_panel
    assert panel.current_state is panel.empty
    assert "key" in panel.empty_title.cget("text")
    assert app.banner.winfo_manager()
    app.open_key_settings()
    assert app.tabs.index("current") == 3


def test_close_destroys_the_window(app: Any) -> None:
    window = app.root
    app.close()
    assert not window.winfo_exists()
