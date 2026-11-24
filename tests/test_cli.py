import io
import json
from pathlib import Path

import pytest

from meteormind import cli
from meteormind.config import ConfigManager
from meteormind.console import configure_stream, display_width, format_pairs, format_table
from meteormind.service import InputError, WeatherService

from .conftest import API_KEY
from .test_service import FlakyProvider


def run(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str, str]:
    code = cli.main(list(args))
    out, err = capsys.readouterr()
    return code, out, err


class TestWeatherCommands:
    def test_current(self, capsys: pytest.CaptureFixture[str]) -> None:
        code, out, _ = run(capsys, "--demo", "current", "London")
        assert code == cli.EXIT_OK
        assert out.startswith("London, England, GB\n")
        assert "Temperature" in out and "°C" in out

    def test_multi_word_place_and_options_after_command(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, out, _ = run(capsys, "current", "New", "York", "--demo", "--units", "imperial")
        assert code == 0
        assert out.startswith("New York, New York, US")
        assert "°F" in out and "mph" in out

    def test_current_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        code, out, _ = run(capsys, "--demo", "current", "Paris, FR", "--json")
        data = json.loads(out)
        assert code == 0
        assert data["location"]["country"] == "FR"
        assert isinstance(data["weather"]["temperature"], float)

    def test_forecast(self, capsys: pytest.CaptureFixture[str]) -> None:
        code, out, _ = run(capsys, "--demo", "forecast", "Tokyo", "--days", "3")
        lines = out.splitlines()
        assert code == 0
        assert lines[0] == "3-day forecast for Tokyo, JP"
        assert lines[1].split() == [
            "Day",
            "High",
            "Low",
            "Precip",
            "Humidity",
            "Wind",
            "Conditions",
        ]
        assert len(lines) == 2 + 1 + 3
        # Numbers are right-aligned: every row's "High" column ends at the same place.
        ends = {line.index("°C") for line in lines[3:]}
        assert len(ends) == 1

    def test_forecast_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        _, out, _ = run(capsys, "--demo", "forecast", "Tokyo", "-d", "2", "--json")
        assert len(json.loads(out)["forecast"]) == 2

    def test_without_api_key(self, capsys: pytest.CaptureFixture[str]) -> None:
        code, out, err = run(capsys, "current", "London")
        assert code == cli.EXIT_ERROR
        assert out == ""
        assert err.startswith("Error: No OpenWeatherMap API key")
        assert "OPENWEATHER_API_KEY" in err

    def test_invalid_place(self, capsys: pytest.CaptureFixture[str]) -> None:
        code, _, err = run(capsys, "--demo", "current", "Lon<don")
        assert code == cli.EXIT_USAGE
        assert "invalid characters" in err

    def test_unknown_place(self, capsys: pytest.CaptureFixture[str]) -> None:
        code, _, err = run(capsys, "--demo", "current", "London, FR")
        assert code == cli.EXIT_ERROR
        assert "London, FR" in err

    def test_bad_arguments(self, capsys: pytest.CaptureFixture[str]) -> None:
        for args in (["forecast", "Paris", "--days", "9"], ["nonsense"], ["current"]):
            with pytest.raises(SystemExit) as info:
                cli.main(args)
            assert info.value.code == cli.EXIT_USAGE
        capsys.readouterr()


class TestAmbiguousPlaces:
    @pytest.fixture(autouse=True)
    def ambiguous_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("meteormind.service.DemoWeatherClient", FlakyProvider)

    def test_scripts_get_the_first_match_and_a_note(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, out, err = run(capsys, "--demo", "current", "Springfield")
        assert code == 0 and out.startswith("Springfield, Illinois, US\n")
        assert "matches 2 places" in err and "2. Springfield, Missouri, US" in err

    def test_pick(self, capsys: pytest.CaptureFixture[str]) -> None:
        code, out, err = run(capsys, "--demo", "forecast", "Springfield", "--pick", "2", "-d", "1")
        assert code == 0 and "Springfield, Missouri, US" in out and not err
        code, out, _ = run(capsys, "--demo", "favorites", "add", "Springfield", "-p", "2")
        assert out == "Added Springfield, Missouri, US to favorites.\n"
        code, _, err = run(capsys, "--demo", "current", "Springfield", "--pick", "3")
        assert code == cli.EXIT_USAGE and "1. Springfield, Illinois, US" in err

    def test_interactive_sessions_ask(self) -> None:
        service = WeatherService.create(demo=True)
        out, err = io.StringIO(), io.StringIO()
        app = cli.App(service, out, err, io.StringIO("9\nwhat\n2\n"), interactive=True)
        assert cli.resolve_place(app, ["Springfield"]).state == "Missouri"
        assert err.getvalue().count("Which one?") == 3
        assert "Enter a number from 1 to 2." in err.getvalue() and not out.getvalue()

        app.inp = io.StringIO("\n")
        assert cli.resolve_place(app, ["Springfield"]).state == "Illinois"
        app.inp = io.StringIO("")
        with pytest.raises(InputError):
            cli.resolve_place(app, ["Springfield"])

    def test_single_matches_never_ask(self) -> None:
        app = cli.App(WeatherService.create(demo=True), inp=io.StringIO(), interactive=True)
        assert cli.resolve_place(app, ["Cairo"]).country == "EG"


class TestFavorites:
    def test_list_add_remove(self, capsys: pytest.CaptureFixture[str]) -> None:
        code, out, _ = run(capsys, "favorites")
        assert code == 0
        assert out.splitlines()[0].split() == ["#", "Place", "Coordinates", "Added"]
        assert "Sydney, New South Wales, AU" in out

        code, out, _ = run(capsys, "--demo", "favorites", "add", "Cape", "Town")
        assert (code, out) == (0, "Added Cape Town, Western Cape, ZA to favorites.\n")
        _, out, _ = run(capsys, "--demo", "favorites", "add", "cape town")
        assert "already a favorite" in out

        code, out, _ = run(capsys, "favorites", "remove", "Cape Town")
        assert (code, out) == (0, "Removed Cape Town, Western Cape, ZA from favorites.\n")
        code, _, err = run(capsys, "favorites", "remove", "Cape Town")
        assert code == cli.EXIT_ERROR and "not one of your favorites" in err

    def test_json_and_empty(self, capsys: pytest.CaptureFixture[str]) -> None:
        _, out, _ = run(capsys, "favorites", "--json")
        assert len(json.loads(out)) == 5
        for place in ("London", "New York", "Tokyo", "Paris", "Sydney"):
            run(capsys, "favorites", "remove", place)
        _, out, _ = run(capsys, "favorites", "list")
        assert out.startswith("No favorites yet")


class TestHistory:
    def test_list_search_export_clear(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        _, out, _ = run(capsys, "history")
        assert out == "No queries yet.\n"
        run(capsys, "--demo", "current", "London")
        run(capsys, "--demo", "forecast", "Paris")

        _, out, _ = run(capsys, "history")
        newest, oldest = out.splitlines()[2:]
        assert "Paris, Ile-de-France, FR" in newest and "forecast" in newest
        assert "London, England, GB" in oldest and "°C" in oldest
        _, out, _ = run(capsys, "history", "--search", "england", "--json")
        assert [q["location"]["city"] for q in json.loads(out)] == ["London"]
        _, out, _ = run(capsys, "history", "-s", "nowhere")
        assert out == "No matching queries.\n"

        target = tmp_path / "history.json"
        code, out, _ = run(capsys, "history", "export", str(target))
        assert code == 0 and json.loads(target.read_text(encoding="utf-8"))["queries"]

        code, _, err = run(capsys, "history", "clear")
        assert code == cli.EXIT_USAGE and "--yes" in err
        code, out, _ = run(capsys, "history", "clear", "--yes")
        assert (code, out) == (0, "History cleared.\n")
        assert run(capsys, "history")[1] == "No queries yet.\n"


class TestReports:
    def test_compare_favorites_as_csv(self, capsys: pytest.CaptureFixture[str]) -> None:
        code, out, _ = run(capsys, "--demo", "report", "compare", "--format", "csv")
        assert code == 0
        assert "Location" in out and "London" in out

    def test_report_to_file(self, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
        target = tmp_path / "forecast.json"
        code, out, _ = run(
            capsys, "--demo", "report", "forecast", "Cairo", "-d", "2", "-o", str(target)
        )
        assert code == 0 and out == f"Saved the report to {target}\n"
        assert len(json.loads(target.read_text(encoding="utf-8"))["rows"]) == 2

    def test_trends_need_history(self, capsys: pytest.CaptureFixture[str]) -> None:
        code, _, err = run(capsys, "--demo", "report", "trends", "London")
        assert code == cli.EXIT_USAGE and "at least two" in err
        run(capsys, "--demo", "current", "London")
        run(capsys, "--demo", "current", "London")
        code, out, _ = run(capsys, "report", "trends", "London, GB")
        assert code == 0 and "Temperature Trends" in out

    def test_unwritable_output(self, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
        target = tmp_path / "missing" / "report.txt"
        code, _, err = run(capsys, "report", "history", "-o", str(target))
        assert code == cli.EXIT_ERROR and "Could not write" in err


class TestConfig:
    def test_set_show_clear_key(
        self, capsys: pytest.CaptureFixture[str], isolated_environment: Path
    ) -> None:
        code, out, _ = run(capsys, "config", "set-key", API_KEY)
        assert code == 0 and str(isolated_environment / "config.json") in out
        assert ConfigManager(isolated_environment).get_api_key() == API_KEY

        _, out, _ = run(capsys, "config")
        assert API_KEY not in out
        assert "cdef" in out and "Data folder" in out

        _, out, _ = run(capsys, "config", "clear-key")
        assert out == "Removed the saved API key.\n"
        _, out, _ = run(capsys, "config", "clear-key")
        assert out == "No API key was saved.\n"

    def test_set_key_from_stdin(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO(API_KEY + "\n"))
        assert run(capsys, "config", "set-key")[0] == 0

    def test_rejects_bad_key(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert run(capsys, "config", "set-key", "nope")[0] == cli.EXIT_USAGE
        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        assert run(capsys, "config", "set-key")[0] == cli.EXIT_USAGE


class TestEntryPoints:
    def test_menu_ends_with_input(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO("8\n"))
        for args in ([], ["--cli"], ["menu"]):
            code, out, _ = run(capsys, "--demo", *args)
            assert code == 0
            assert "Main menu" in out

    def test_gui_command_starts_gui(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[list[str]] = []

        def fake_gui(argv: list[str]) -> int:
            calls.append(argv)
            return 0

        monkeypatch.setattr("meteormind.gui.main", fake_gui)
        assert cli.main(["gui", "--demo"]) == 0
        assert cli.main(["--gui"]) == 0
        assert calls == [["--demo"], []]

    def test_interrupt(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def interrupt(*args: object) -> None:
            raise KeyboardInterrupt

        monkeypatch.setattr(WeatherService, "search", interrupt)
        assert run(capsys, "--demo", "current", "London")[0] == cli.EXIT_INTERRUPTED


class TestConsole:
    def test_unencodable_output_does_not_crash(self) -> None:
        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding="cp1252", newline="\n")
        configure_stream(stream)
        print("東京 ⛅ 20°C", file=stream)
        stream.flush()
        assert raw.getvalue() == "?? ? 20°C\n".encode("cp1252")

    def test_utf8_streams_are_left_alone(self) -> None:
        stream = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        configure_stream(stream)
        assert stream.errors == "strict"

    def test_display_width(self) -> None:
        assert display_width("Paris") == 5
        assert display_width("東京") == 4
        assert display_width("Kraków") == 6
        assert display_width("Kraków") == 6

    def test_table_alignment(self) -> None:
        table = format_table(["Place", "Temp"], [["東京", "5"], ["Paris", "12"]], align="<>")
        assert table.splitlines() == [
            "Place  Temp",
            "-----  ----",
            "東京      5",
            "Paris    12",
        ]

    def test_table_multiline_cells(self) -> None:
        table = format_table(["A", "B"], [["one\ntwo", "x"]])
        assert table.splitlines()[2:] == ["one  x", "two"]

    def test_pairs(self) -> None:
        assert format_pairs([("A", "1"), ("Long", "2")]) == "  A     1\n  Long  2"
