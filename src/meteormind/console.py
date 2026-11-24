"""Plain-text output helpers for the command-line interface.

Columns are aligned by *display* width, so place names in scripts with
double-width characters (東京, 서울) still line up.
"""

from __future__ import annotations

import io
import unicodedata
from collections.abc import Sequence
from typing import TextIO

from .models import ForecastData, Location, WeatherData, WeatherQuery
from .units import WeatherFormatter


def configure_stream(stream: TextIO) -> None:
    """Never fail on characters the stream's encoding cannot represent.

    Output piped to a file on Windows uses the legacy code page, which has no
    room for many place names; such characters are written as ``?`` instead
    of raising :class:`UnicodeEncodeError`.
    """
    if isinstance(stream, io.TextIOWrapper) and not _is_utf(stream.encoding):
        stream.reconfigure(errors="replace")


def _is_utf(encoding: str) -> bool:
    return encoding.lower().replace("-", "").replace("_", "").startswith("utf")


def display_width(text: str) -> int:
    """Number of terminal columns ``text`` occupies."""
    width = 0
    for char in text:
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in "WF" else 1
    return width


def pad(text: str, width: int, align: str = "<") -> str:
    gap = " " * max(width - display_width(text), 0)
    return gap + text if align == ">" else text + gap


def format_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    align: str = "",
    indent: str = "",
) -> str:
    """Render rows as aligned columns separated by two spaces.

    ``align`` gives one character per column, ``<`` or ``>``; columns without
    one are left-aligned. Cells may contain line breaks.
    """
    split_rows = [[str(cell).splitlines() or [""] for cell in row] for row in rows]
    widths = [display_width(h) for h in headers]
    for row in split_rows:
        for i, lines in enumerate(row):
            widths[i] = max(widths[i], *(display_width(line) for line in lines))
    aligns = [align[i] if i < len(align) else "<" for i in range(len(headers))]

    def render(cells: Sequence[str]) -> str:
        parts = [pad(cell, widths[i], aligns[i]) for i, cell in enumerate(cells)]
        return (indent + "  ".join(parts)).rstrip()

    lines = [render(headers), indent + "  ".join("-" * w for w in widths)]
    for row in split_rows:
        height = max(len(cell) for cell in row)
        for n in range(height):
            lines.append(render([cell[n] if n < len(cell) else "" for cell in row]))
    return "\n".join(lines)


def format_pairs(pairs: Sequence[tuple[str, str]], indent: str = "  ") -> str:
    """Render ``label  value`` lines with the values aligned."""
    width = max((display_width(label) for label, _ in pairs), default=0)
    return "\n".join(f"{indent}{pad(label, width)}  {value}" for label, value in pairs)


def describe_weather(weather: WeatherData, location: Location, fmt: WeatherFormatter) -> str:
    """A short multi-line description of current conditions."""
    temperature = fmt.format_temperature(weather.temperature)
    if weather.temp_min is not None and weather.temp_max is not None:
        low = fmt.format_temperature(weather.temp_min)
        high = fmt.format_temperature(weather.temp_max)
        temperature += f" (low {low}, high {high})"
    wind = fmt.format_wind_speed(weather.wind_speed)
    if weather.wind_speed > 0:
        wind += f" from {fmt.format_wind_direction(weather.wind_direction)}"
    pairs = [
        ("Conditions", weather.description),
        ("Temperature", temperature),
        ("Feels like", fmt.format_temperature(weather.feels_like)),
        ("Humidity", fmt.format_humidity(weather.humidity)),
        ("Pressure", fmt.format_pressure(weather.pressure)),
        ("Wind", wind),
    ]
    if weather.visibility is not None:
        pairs.append(("Visibility", fmt.format_visibility(weather.visibility)))
    pairs.append(("Observed", f"{weather.timestamp:%Y-%m-%d %H:%M}"))
    return f"{location.display_name}\n{format_pairs(pairs)}"


def describe_forecast(forecast: Sequence[ForecastData], fmt: WeatherFormatter) -> str:
    rows = [
        [
            f"{day.date:%a %d %b}",
            fmt.format_temperature(day.temperature_max),
            fmt.format_temperature(day.temperature_min),
            f"{day.precipitation_chance}%",
            fmt.format_humidity(day.humidity),
            fmt.format_wind_speed(day.wind_speed),
            day.description,
        ]
        for day in forecast
    ]
    headers = ["Day", "High", "Low", "Precip", "Humidity", "Wind", "Conditions"]
    return format_table(headers, rows, align="<>>>>><", indent="  ")


def describe_error(error: Exception) -> str:
    """``Error: message`` followed by any suggestions the error carries."""
    suggestions: Sequence[str] = getattr(error, "suggestions", None) or ()
    return "\n".join([f"Error: {error}", *(f"  - {tip}" for tip in suggestions)])


def favorites_table(favorites: Sequence[Location]) -> str:
    rows = [
        [
            str(n),
            loc.display_name,
            f"{loc.latitude:.2f}, {loc.longitude:.2f}",
            f"{loc.added_date:%Y-%m-%d}",
        ]
        for n, loc in enumerate(favorites, 1)
    ]
    return format_table(["#", "Place", "Coordinates", "Added"], rows, align=">")


def history_table(queries: Sequence[WeatherQuery], fmt: WeatherFormatter) -> str:
    rows = []
    for query in queries:
        weather = query.weather_data
        rows.append(
            [
                f"{query.query_time:%Y-%m-%d %H:%M}",
                query.location.display_name,
                query.query_type,
                fmt.format_temperature(weather.temperature) if weather else "",
                weather.description if weather else "",
            ]
        )
    return format_table(["When", "Place", "Type", "Temp", "Conditions"], rows, align="<<<>")
