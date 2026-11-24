"""Weather reports: tables built from lookups and history, rendered as text, CSV or JSON.

:class:`WeatherReportGenerator` turns weather data into :class:`WeatherReport`
tables of display strings in the user's units; :func:`render_report` and
:func:`write_report` turn a report into text, CSV or JSON.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .console import display_width, format_table
from .models import ForecastData, Location, WeatherData, WeatherQuery
from .units import WeatherFormatter

REPORT_FORMATS = ("txt", "csv", "json")

# Temperature changes smaller than this (in °C) count as steady in trend reports.
STEADY_CHANGE = 0.5


@dataclass
class WeatherReport:
    """A titled table of display strings.

    Cells may contain line breaks. ``align`` holds one ``<`` or ``>`` per
    column for the text rendering; missing entries mean left-aligned.
    """

    title: str
    headers: list[str]
    rows: list[list[str]]
    summary: str | None = None
    align: str = ""
    generated_at: datetime = field(default_factory=datetime.now)

    def to_table_string(self) -> str:
        """The report as an aligned plain-text table."""
        lines = [self.title, "=" * display_width(self.title), ""]
        if self.rows:
            lines.append(format_table(self.headers, self.rows, self.align))
        else:
            lines.append("No data available.")
        if self.summary:
            lines += ["", self.summary]
        lines += ["", f"Generated {self.generated_at:%Y-%m-%d %H:%M}"]
        return "\n".join(lines)

    def to_csv(self) -> str:
        """The header row and data rows as CSV; multi-line cells are quoted."""
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(self.headers)
        writer.writerows(self.rows)
        return buffer.getvalue().removesuffix("\n")

    def to_dict(self) -> dict[str, Any]:
        """The report as JSON-compatible data."""
        return {
            "title": self.title,
            "headers": self.headers,
            "rows": self.rows,
            "summary": self.summary,
            "generated_at": self.generated_at.isoformat(timespec="seconds"),
        }


class ReportError(Exception):
    """Raised when a report cannot be saved; ``str(error)`` is user-facing."""


def render_report(report: WeatherReport, fmt: str = "txt") -> str:
    """Render a report as plain text, CSV or JSON."""
    if fmt == "csv":
        return report.to_csv()
    if fmt == "json":
        return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)
    return report.to_table_string()


def write_report(report: WeatherReport, path: Path | str, fmt: str | None = None) -> Path:
    """Save a report; the format defaults to the file extension (else text)."""
    target = Path(path)
    if fmt is None:
        suffix = target.suffix.lower().lstrip(".")
        fmt = suffix if suffix in REPORT_FORMATS else "txt"
    try:
        target.write_text(render_report(report, fmt) + "\n", encoding="utf-8", newline="")
    except OSError as exc:
        raise ReportError(f"Could not write {target}: {exc.strerror or exc}") from exc
    return target


def describe_span(span: timedelta) -> str:
    """A rough human-readable length of time, e.g. ``3 days`` or ``5 hours``."""
    if span >= timedelta(days=2):
        return f"{span.days} days"
    hours = round(span.total_seconds() / 3600)
    if hours >= 2:
        return f"{hours} hours"
    minutes = max(round(span.total_seconds() / 60), 0)
    return "1 hour" if minutes >= 60 else f"{minutes} minutes"


def _count(n: int, noun: str, plural: str | None = None) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {plural or noun + 's'}"


class WeatherReportGenerator:
    """Builds reports with values formatted in the user's units.

    ``clock`` supplies the generation time; pass a fixed one for
    reproducible output.
    """

    def __init__(
        self, formatter: WeatherFormatter, clock: Callable[[], datetime] = datetime.now
    ) -> None:
        self.formatter = formatter
        self.clock = clock

    def _report(
        self,
        title: str,
        headers: list[str],
        rows: list[list[str]],
        summary: str | None = None,
        align: str = "",
    ) -> WeatherReport:
        return WeatherReport(title, headers, rows, summary, align, self.clock())

    def _temperature(self, celsius: float) -> str:
        return self.formatter.format_temperature(celsius)

    def generate_current_weather_report(
        self, locations_data: Sequence[tuple[Location, WeatherData]]
    ) -> WeatherReport:
        """Current conditions for several places side by side."""
        title = "Current Weather Report"
        headers = [
            "Location",
            "Temperature",
            "Feels Like",
            "Conditions",
            "Humidity",
            "Pressure",
            "Wind Speed",
            "Updated",
        ]
        if not locations_data:
            return self._report(title, headers, [])

        fmt = self.formatter
        rows = [
            [
                location.display_name,
                self._temperature(weather.temperature),
                self._temperature(weather.feels_like),
                weather.description.capitalize(),
                fmt.format_humidity(weather.humidity),
                fmt.format_pressure(weather.pressure),
                fmt.format_wind_speed(weather.wind_speed),
                f"{weather.timestamp:%H:%M}",
            ]
            for location, weather in locations_data
        ]
        temps = [weather.temperature for _, weather in locations_data]
        summary = (
            f"{_count(len(rows), 'place')} | "
            f"average {self._temperature(sum(temps) / len(temps))} | "
            f"range {self._temperature(min(temps))} to {self._temperature(max(temps))}"
        )
        return self._report(title, headers, rows, summary, align="<>><>>>")

    def generate_forecast_comparison_report(
        self, forecasts_data: Sequence[tuple[Location, Sequence[ForecastData]]]
    ) -> WeatherReport:
        """Daily forecasts for several places side by side, one column per day."""
        title = "Forecast Comparison Report"
        forecasts_data = [(loc, days) for loc, days in forecasts_data if days]
        if not forecasts_data:
            return self._report(title, ["Location"], [])

        day_count = min(len(days) for _, days in forecasts_data)
        first = forecasts_data[0][1]
        headers = ["Location"] + [f"{first[i].date:%a %d %b}" for i in range(day_count)]
        rows = []
        for location, days in forecasts_data:
            row = [location.display_name]
            for day in days[:day_count]:
                low = self._temperature(day.temperature_min)
                high = self._temperature(day.temperature_max)
                row.append(f"{low} to {high}\n{day.description.capitalize()}")
            rows.append(row)

        summary = (
            f"{_count(len(rows), 'place')} over {_count(day_count, 'day')}, "
            "lows to highs with the expected conditions"
        )
        return self._report(title, headers, rows, summary)

    def generate_detailed_forecast_report(
        self, location: Location, forecast_data: Sequence[ForecastData]
    ) -> WeatherReport:
        """One row per forecast day for a single place."""
        title = f"Detailed Forecast - {location.display_name}"
        headers = ["Date", "Day", "Low", "High", "Conditions", "Humidity", "Wind", "Precip"]
        if not forecast_data:
            return self._report(title, headers, [])

        fmt = self.formatter
        rows = [
            [
                f"{day.date:%Y-%m-%d}",
                f"{day.date:%a}",
                self._temperature(day.temperature_min),
                self._temperature(day.temperature_max),
                day.description.capitalize(),
                fmt.format_humidity(day.humidity),
                fmt.format_wind_speed(day.wind_speed),
                f"{day.precipitation_chance}%" if day.precipitation_chance > 0 else "-",
            ]
            for day in forecast_data
        ]
        summary = f"{len(forecast_data)}-day forecast starting {forecast_data[0].date:%A %d %B %Y}"
        return self._report(title, headers, rows, summary, align="<<>><>>>")

    def generate_query_history_report(
        self, query_history: Sequence[WeatherQuery], limit: int = 50
    ) -> WeatherReport:
        """The most recent queries, newest first."""
        title = "Query History Report"
        headers = ["Date/Time", "Location", "Type", "Temperature", "Conditions"]
        if not query_history:
            return self._report(title, headers, [])

        recent = sorted(query_history, key=lambda q: q.query_time, reverse=True)[:limit]
        rows = []
        for query in recent:
            weather = query.weather_data
            rows.append(
                [
                    f"{query.query_time:%Y-%m-%d %H:%M}",
                    query.location.display_name,
                    query.query_type.capitalize(),
                    self._temperature(weather.temperature) if weather else "-",
                    weather.description.capitalize() if weather else "-",
                ]
            )
        total = _count(len(query_history), "query", "queries")
        summary = f"Showing the {len(rows)} most recent of {total}"
        return self._report(title, headers, rows, summary, align="<<<>")

    def generate_location_statistics_report(
        self, query_history: Sequence[WeatherQuery]
    ) -> WeatherReport:
        """How often each place was looked up, with its average observed temperature."""
        title = "Location Statistics Report"
        headers = ["Location", "Queries", "Last Query", "Avg Temp", "Temp Samples"]
        if not query_history:
            return self._report(title, headers, [])

        counts: dict[str, int] = {}
        last_seen: dict[str, datetime] = {}
        temperatures: dict[str, list[float]] = {}
        for query in query_history:
            name = query.location.display_name
            counts[name] = counts.get(name, 0) + 1
            last_seen[name] = max(last_seen.get(name, query.query_time), query.query_time)
            if query.weather_data:
                temperatures.setdefault(name, []).append(query.weather_data.temperature)

        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold()))
        rows = []
        for name, count in ranked:
            samples = temperatures.get(name, [])
            average = self._temperature(sum(samples) / len(samples)) if samples else "-"
            rows.append(
                [name, str(count), f"{last_seen[name]:%Y-%m-%d %H:%M}", average, str(len(samples))]
            )
        summary = (
            f"{_count(len(query_history), 'query', 'queries')} across "
            f"{_count(len(counts), 'place')} | "
            f"most looked up: {ranked[0][0]}"
        )
        return self._report(title, headers, rows, summary, align="<><>>")

    def generate_temperature_trend_report(
        self, location: Location, historical_data: Sequence[tuple[datetime, WeatherData]]
    ) -> WeatherReport:
        """Observed temperatures for one place over time, with the change between them."""
        title = f"Temperature Trends - {location.display_name}"
        headers = ["Date/Time", "Temperature", "Feels Like", "Conditions", "Change", "Trend"]
        if not historical_data:
            return self._report(title, headers, [])

        samples = sorted(historical_data, key=lambda sample: sample[0])
        rows = []
        previous: float | None = None
        for when, weather in samples:
            if previous is None:
                change, trend = "-", "-"
            else:
                delta = weather.temperature - previous
                change = self.formatter.format_temperature_delta(delta)
                trend = "→" if abs(delta) < STEADY_CHANGE else "↑" if delta > 0 else "↓"
            rows.append(
                [
                    f"{when:%Y-%m-%d %H:%M}",
                    self._temperature(weather.temperature),
                    self._temperature(weather.feels_like),
                    weather.description.capitalize(),
                    change,
                    trend,
                ]
            )
            previous = weather.temperature

        if len(samples) >= 2:
            overall = samples[-1][1].temperature - samples[0][1].temperature
            span = describe_span(samples[-1][0] - samples[0][0])
            summary = (
                f"Overall change: {self.formatter.format_temperature_delta(overall)} over {span}"
            )
        else:
            summary = "Look up this place again to see how its temperature changes."
        return self._report(title, headers, rows, summary, align="<>><>")
