"""Regenerate the sample reports in ``examples/reports``.

Every report MeteorMind can build, made from the offline demo data with a
fixed date and clock, so the output is identical on every run::

    python examples/sample_reports.py            # rewrite examples/reports
    python examples/sample_reports.py OUT_DIR    # write somewhere else

The test suite checks that the committed files match this script's output.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    import meteormind  # noqa: F401
except ImportError:  # running from a checkout without installing
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from meteormind.demo import DemoWeatherClient
from meteormind.models import WeatherQuery
from meteormind.reporting import WeatherReport, WeatherReportGenerator, write_report
from meteormind.units import WeatherFormatter, create_imperial_preferences

TODAY = date(2026, 1, 15)
GENERATED = datetime(2026, 1, 15, 9, 30)
OUTPUT = Path(__file__).resolve().parent / "reports"

# Which reports are also written as CSV and JSON (every report gets a .txt).
EXTRA_FORMATS = {"compare": ("csv", "json"), "forecast-compare": ("csv",)}


def sample_history(client: DemoWeatherClient) -> list[WeatherQuery]:
    """A week of lookups: London every morning, Paris every other day, Tokyo forecasts."""
    london, paris, tokyo = (client.get_location_by_name(n) for n in ("London", "Paris", "Tokyo"))
    queries = []
    for days_ago in range(6, -1, -1):
        day = TODAY - timedelta(days=days_ago)
        that_day = DemoWeatherClient(today=day)
        start = datetime.combine(day, datetime.min.time())
        queries.append(
            WeatherQuery(london, start + timedelta(hours=8), that_day.get_current_weather(london))
        )
        if days_ago % 2 == 0:
            queries.append(
                WeatherQuery(
                    paris,
                    start + timedelta(hours=12, minutes=30),
                    that_day.get_current_weather(paris),
                )
            )
        if days_ago % 3 == 0:
            queries.append(WeatherQuery(tokyo, start + timedelta(hours=18), None, "forecast"))
    return queries


def build_reports() -> dict[str, WeatherReport]:
    """One report of each kind, keyed by the name used on the command line."""
    client = DemoWeatherClient(today=TODAY)
    metric = WeatherReportGenerator(WeatherFormatter(), clock=lambda: GENERATED)
    imperial = WeatherReportGenerator(
        WeatherFormatter(create_imperial_preferences()), clock=lambda: GENERATED
    )
    places = [
        client.get_location_by_name(name)
        for name in ("London", "Paris", "Tokyo", "New York", "Sydney")
    ]
    history = sample_history(client)
    london = places[0]
    london_samples = [
        (q.query_time, q.weather_data)
        for q in history
        if q.location.key == london.key and q.weather_data is not None
    ]
    return {
        "compare": metric.generate_current_weather_report(
            [(place, client.get_current_weather(place)) for place in places]
        ),
        "forecast": imperial.generate_detailed_forecast_report(
            london, client.get_forecast(london, 5)
        ),
        "forecast-compare": metric.generate_forecast_comparison_report(
            [(place, client.get_forecast(place, 3)) for place in places[:3]]
        ),
        "trends": metric.generate_temperature_trend_report(london, london_samples),
        "locations": metric.generate_location_statistics_report(history),
        "history": metric.generate_query_history_report(history),
    }


def write_samples(directory: Path) -> list[Path]:
    """Write every sample report into ``directory``; returns the files written."""
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name, report in build_reports().items():
        for fmt in ("txt", *EXTRA_FORMATS.get(name, ())):
            written.append(write_report(report, directory / f"{name}.{fmt}"))
    return written


def main(argv: list[str]) -> int:
    directory = Path(argv[0]) if argv else OUTPUT
    for path in write_samples(directory):
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
