"""Report building and rendering, plus the committed sample reports."""

from __future__ import annotations

import csv
import importlib.util
import io
import json
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType

import pytest

from meteormind.models import ForecastData, Location, WeatherData, WeatherQuery
from meteormind.reporting import (
    WeatherReport,
    WeatherReportGenerator,
    describe_span,
    render_report,
    write_report,
)
from meteormind.units import WeatherFormatter, create_imperial_preferences

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
NOW = datetime(2026, 3, 1, 12, 0)
LONDON = Location("London", "GB", 51.5, -0.13, state="England")
TOKYO = Location("東京", "JP", 35.68, 139.76)


def weather(temperature: float, description: str = "clear sky") -> WeatherData:
    return WeatherData(
        city="London",
        country="GB",
        temperature=temperature,
        feels_like=temperature - 1,
        humidity=70,
        pressure=1012,
        wind_speed=3.0,
        wind_direction=200,
        description=description,
        timestamp=NOW,
    )


def forecast_day(offset: int, low: float, high: float) -> ForecastData:
    return ForecastData(NOW + timedelta(days=offset), low, high, 60, 2.0, "light rain", 40)


@pytest.fixture
def metric() -> WeatherReportGenerator:
    return WeatherReportGenerator(WeatherFormatter(), clock=lambda: NOW)


@pytest.fixture
def imperial() -> WeatherReportGenerator:
    return WeatherReportGenerator(
        WeatherFormatter(create_imperial_preferences()), clock=lambda: NOW
    )


class TestRendering:
    def test_text_aligns_wide_characters_and_numbers(self) -> None:
        report = WeatherReport(
            "Title", ["Place", "Temp"], [["東京", "5"], ["Paris", "12"]], align="<>"
        )
        lines = report.to_table_string().splitlines()
        assert lines[:2] == ["Title", "====="]
        assert lines[3:7] == ["Place  Temp", "-----  ----", "東京      5", "Paris    12"]
        assert lines[-1].startswith("Generated ")

    def test_multiline_cells_keep_their_columns(self) -> None:
        report = WeatherReport("T", ["A", "B"], [["one\ntwo", "x"], ["three", "y"]])
        table = report.to_table_string().splitlines()[3:]
        assert table[:6] == ["A      B", "-----  -", "one    x", "two", "", "three  y"]

    def test_csv_quotes_commas_quotes_and_line_breaks(self) -> None:
        rows = [["Paris, FR", 'say "hi"', "line one\nline two"]]
        report = WeatherReport("T", ["Place", "Note", "Forecast"], rows)
        text = report.to_csv()
        assert list(csv.reader(io.StringIO(text))) == [["Place", "Note", "Forecast"], *rows]
        assert not text.startswith("#")

    def test_json_includes_generation_time(self) -> None:
        report = WeatherReport("T", ["A"], [["1"]], "sum", generated_at=NOW)
        data = json.loads(render_report(report, "json"))
        assert data == {
            "title": "T",
            "headers": ["A"],
            "rows": [["1"]],
            "summary": "sum",
            "generated_at": "2026-03-01T12:00:00",
        }

    def test_empty_report(self) -> None:
        text = WeatherReport("Nothing", ["A"], []).to_table_string()
        assert "No data available." in text

    @pytest.mark.parametrize(
        ("name", "fmt", "check"),
        [
            ("r.csv", None, lambda s: s.startswith("A\n")),
            ("r.json", None, lambda s: json.loads(s)["rows"] == [["1"]]),
            ("r.out", None, lambda s: s.startswith("T\n=")),
            ("r.txt", "csv", lambda s: s.startswith("A\n")),
        ],
    )
    def test_write_report_picks_format(self, tmp_path: Path, name, fmt, check) -> None:
        path = write_report(WeatherReport("T", ["A"], [["1"]]), tmp_path / name, fmt)
        assert check(path.read_text(encoding="utf-8"))


class TestGenerator:
    def test_current_weather(self, metric: WeatherReportGenerator) -> None:
        report = metric.generate_current_weather_report(
            [(LONDON, weather(10)), (TOKYO, weather(20, "few clouds"))]
        )
        assert report.rows[0][:4] == ["London, England, GB", "10.0°C", "9.0°C", "Clear sky"]
        assert report.summary == "2 places | average 15.0°C | range 10.0°C to 20.0°C"
        assert report.generated_at == NOW

    def test_forecast_comparison_uses_dates_and_common_days(
        self, metric: WeatherReportGenerator
    ) -> None:
        report = metric.generate_forecast_comparison_report(
            [
                (LONDON, [forecast_day(0, 1, 8), forecast_day(1, 2, 9)]),
                (TOKYO, [forecast_day(0, 5, 12)]),
                (LONDON, []),
            ]
        )
        assert report.headers == ["Location", "Sun 01 Mar"]
        assert report.rows[0][1] == "1.0°C to 8.0°C\nLight rain"
        assert len(report.rows) == 2

    def test_detailed_forecast(self, imperial: WeatherReportGenerator) -> None:
        report = imperial.generate_detailed_forecast_report(LONDON, [forecast_day(0, 0, 10)])
        assert report.rows == [
            ["2026-03-01", "Sun", "32.0°F", "50.0°F", "Light rain", "60%", "4 mph", "40%"]
        ]

    def test_trend_changes_are_converted_as_differences(
        self, imperial: WeatherReportGenerator
    ) -> None:
        samples = [(NOW, weather(10)), (NOW + timedelta(hours=6), weather(11))]
        report = imperial.generate_temperature_trend_report(LONDON, samples)
        # A 1 °C rise is 1.8 °F, not the 33.8 °F an absolute conversion would give.
        assert report.rows[1][4:] == ["+1.8°F", "↑"]
        assert report.summary == "Overall change: +1.8°F over 6 hours"

    def test_trend_marks_small_changes_as_steady(self, metric: WeatherReportGenerator) -> None:
        samples = [(NOW + timedelta(days=1), weather(10.2)), (NOW, weather(10))]
        report = metric.generate_temperature_trend_report(LONDON, samples)
        assert [row[0] for row in report.rows] == ["2026-03-01 12:00", "2026-03-02 12:00"]
        assert report.rows[1][4:] == ["+0.2°C", "→"]

    def test_single_trend_sample(self, metric: WeatherReportGenerator) -> None:
        report = metric.generate_temperature_trend_report(LONDON, [(NOW, weather(4))])
        assert report.summary is not None and "again" in report.summary

    def test_history_and_location_statistics(self, metric: WeatherReportGenerator) -> None:
        queries = [
            WeatherQuery(LONDON, NOW - timedelta(hours=2), weather(10)),
            WeatherQuery(TOKYO, NOW - timedelta(hours=1), None, "forecast"),
            WeatherQuery(LONDON, NOW, weather(14)),
        ]
        history = metric.generate_query_history_report(queries, limit=2)
        assert [row[1] for row in history.rows] == ["London, England, GB", "東京, JP"]
        assert history.rows[1][2:] == ["Forecast", "-", "-"]
        assert history.summary == "Showing the 2 most recent of 3 queries"

        stats = metric.generate_location_statistics_report(queries)
        assert stats.rows == [
            ["London, England, GB", "2", "2026-03-01 12:00", "12.0°C", "2"],
            ["東京, JP", "1", "2026-03-01 11:00", "-", "0"],
        ]

    @pytest.mark.parametrize(
        "method",
        [
            "generate_current_weather_report",
            "generate_forecast_comparison_report",
            "generate_query_history_report",
            "generate_location_statistics_report",
        ],
    )
    def test_empty_input(self, metric: WeatherReportGenerator, method: str) -> None:
        assert getattr(metric, method)([]).rows == []


@pytest.mark.parametrize(
    ("span", "text"),
    [
        (timedelta(minutes=5), "5 minutes"),
        (timedelta(minutes=70), "1 hour"),
        (timedelta(hours=30), "30 hours"),
        (timedelta(days=3, hours=4), "3 days"),
    ],
)
def test_describe_span(span: timedelta, text: str) -> None:
    assert describe_span(span) == text


def _load_sample_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("sample_reports", EXAMPLES / "sample_reports.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_sample_reports_are_up_to_date(tmp_path: Path) -> None:
    written = _load_sample_script().write_samples(tmp_path)
    committed = sorted(p.name for p in (EXAMPLES / "reports").iterdir())
    assert sorted(p.name for p in written) == committed
    for path in written:
        expected = (EXAMPLES / "reports" / path.name).read_text(encoding="utf-8")
        assert path.read_text(encoding="utf-8") == expected, (
            f"examples/reports/{path.name} is stale; run python examples/sample_reports.py"
        )
