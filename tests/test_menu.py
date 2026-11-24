import io
from collections.abc import Iterable
from pathlib import Path

import pytest

from meteormind.menu import Menu
from meteormind.service import WeatherService
from meteormind.storage import DataStore
from meteormind.units import DistanceUnit, PressureUnit, TemperatureUnit, WindSpeedUnit

from .test_service import FlakyProvider


class Script:
    """Feeds scripted answers to the menu, then reports end of input."""

    def __init__(self, answers: Iterable[str]) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.answers:
            raise EOFError
        answer = self.answers.pop(0)
        if answer == "^C":
            raise KeyboardInterrupt
        return answer


@pytest.fixture
def service(tmp_path: Path) -> WeatherService:
    return WeatherService(DataStore(tmp_path / "data"), FlakyProvider())


def run_menu(service: WeatherService, *answers: str) -> str:
    out = io.StringIO()
    assert Menu(service, Script(answers), out).run() == 0
    return out.getvalue()


def test_end_of_input_leaves_cleanly(service: WeatherService) -> None:
    out = run_menu(service)
    assert "Main menu" in out


def test_quit_and_invalid_choice(service: WeatherService) -> None:
    out = run_menu(service, "42", "abc", "0")
    assert out.count("Please enter a number from 0 to 8.") == 2


def test_ctrl_c_at_main_menu_quits(service: WeatherService) -> None:
    run_menu(service, "^C", "1")  # the "1" is never read


def test_current_weather_and_add_favorite(service: WeatherService) -> None:
    service.clear_all_data()
    out = run_menu(service, "1", "Reykjavik", "y")
    assert "Reykjavik, IS" in out and "Temperature" in out
    assert [loc.city for loc in service.favorites] == ["Reykjavik"]
    assert len(service.history) == 1


def test_place_picker(service: WeatherService) -> None:
    out = run_menu(service, "1", "Springfield", "2", "n")
    assert "Several places match 'Springfield':" in out
    assert "Springfield, Missouri, US\n  Conditions" in out
    # Enter takes the best match.
    out = run_menu(service, "1", "Springfield", "", "n")
    assert "Springfield, Illinois, US\n  Conditions" in out


def test_errors_are_reported_and_the_menu_continues(service: WeatherService) -> None:
    out = run_menu(service, "1", "London, FR", "2", "12345", "1", "Cairo", "^C", "8", "0")
    assert "Error: No place called 'London, FR' was found." in out
    assert "Error: City name must contain letters" in out
    assert "Cancelled." in out
    assert "Places: type a city name" in out


def test_cancelled_prompt_goes_back(service: WeatherService) -> None:
    out = run_menu(service, "2", "", "0")
    assert out.count("Main menu") == 2


def test_forecast_days(service: WeatherService) -> None:
    out = run_menu(service, "2", "Cairo", "9", "3")
    assert "Please enter a whole number from 1 to 5." in out
    assert "3-day forecast for Cairo, EG" in out


def test_favorites_menu(service: WeatherService) -> None:
    out = run_menu(
        service,
        "3",
        "1",  # list
        "5", "3",  # move Tokyo to the top
        "4", "2", "y",  # remove the second (now London)
        "3", "Cairo",  # add
        "2", "1",  # weather for the first
        "0", "0",
    )  # fmt: skip
    assert "Sydney, New South Wales, AU" in out
    assert "Tokyo, JP is now first." in out
    assert "Removed London, England, GB." in out
    assert "Added Cairo, EG" in out
    assert [loc.city for loc in service.favorites][:2] == ["Cairo", "Tokyo"]


def test_unit_settings(service: WeatherService) -> None:
    run_menu(service, "6", "1", "2", "2", "3", "3", "2", "4", "2", "0")
    units = service.store.load_preferences().units
    assert units.temperature is TemperatureUnit.FAHRENHEIT
    assert units.wind_speed is WindSpeedUnit.MILES_PER_HOUR
    assert units.pressure is PressureUnit.INCHES_OF_MERCURY
    assert units.distance is DistanceUnit.MILES
    run_menu(service, "6", "5", "0")
    assert service.preferences.units.temperature is TemperatureUnit.CELSIUS


def test_other_settings(service: WeatherService) -> None:
    out = run_menu(service, "6", "7", "25", "8", "0", "9", "11", "12", "nope", "0")
    assert service.preferences.history_limit == 25
    assert service.preferences.cache_minutes == 0
    assert "Data folder:" in out and "Backed up to" in out
    assert "Nothing was deleted." in out
    run_menu(service, "6", "12", "DELETE")
    assert len(service.favorites) == 0


def test_history_menu(service: WeatherService, tmp_path: Path) -> None:
    target = tmp_path / "history.json"
    out = run_menu(service, "1", "Cairo", "n", "4", "1", "cairo", "2", str(target), "3", "y", "0")
    assert "Most recent of 1 queries:" in out
    assert target.exists()
    assert len(service.history) == 0


def test_reports_menu(service: WeatherService, tmp_path: Path) -> None:
    target = tmp_path / "report.csv"
    out = run_menu(service, "5", "2", "Paris; Cairo", "y", "csv", str(target), "6", "Paris", "0")
    assert "Current Weather Report" in out
    assert "Cairo" in target.read_text(encoding="utf-8")
    assert "Error: Trends need at least two current-weather lookups for Paris." in out


def test_api_key_menu(service: WeatherService) -> None:
    out = run_menu(service, "7", "1", "short", "4", "0")
    assert "Error: An OpenWeatherMap API key is 32 hexadecimal characters." in out
    assert "home.openweathermap.org" in out
