"""Validation of user input: city names, country codes and menu choices.

Validators return a :class:`ValidationResult` rather than raising, so the
interfaces can show the message and any suggestions next to the input.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, ClassVar

MAX_CITY_NAME_LENGTH = 100

# Punctuation that legitimately appears in place names ("St. John's", "Aix-en-Provence").
_CITY_PUNCTUATION = frozenset(" -.'’")


@dataclass
class ValidationResult:
    """Outcome of validating one input value."""

    is_valid: bool
    value: Any = None
    error_message: str = ""
    suggestions: list[str] = field(default_factory=list)


def _is_letter(char: str) -> bool:
    # Letters (L*) and combining marks (M*) in any script.
    return unicodedata.category(char)[0] in "LM"


class InputValidator:
    """Validators for the values users type into the CLI and GUI."""

    COUNTRY_CODE_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^[A-Z]{2}$")

    COMMON_COUNTRIES: ClassVar[dict[str, str]] = {
        "US": "United States",
        "GB": "United Kingdom",
        "CA": "Canada",
        "AU": "Australia",
        "DE": "Germany",
        "FR": "France",
        "IT": "Italy",
        "ES": "Spain",
        "JP": "Japan",
        "CN": "China",
        "IN": "India",
        "BR": "Brazil",
        "MX": "Mexico",
        "ZA": "South Africa",
        "NZ": "New Zealand",
        "NL": "Netherlands",
        "SE": "Sweden",
        "NO": "Norway",
        "DK": "Denmark",
    }

    @classmethod
    def validate_city_name(cls, city_name: object) -> ValidationResult:
        """Accept place names in any script; reject digits and stray symbols.

        The returned value has surrounding and repeated whitespace removed but
        keeps the user's capitalisation (``.title()`` would mangle names such
        as "McAllen").
        """
        if not isinstance(city_name, str):
            return ValidationResult(False, error_message="City name must be text")

        name = " ".join(city_name.split())
        examples = ["Try a city name such as 'Paris', 'São Paulo' or 'New York'"]
        if not name:
            return ValidationResult(
                False, error_message="City name cannot be empty", suggestions=examples
            )
        if len(name) > MAX_CITY_NAME_LENGTH:
            return ValidationResult(
                False,
                error_message=f"City name is too long (max {MAX_CITY_NAME_LENGTH} characters)",
            )
        if not any(_is_letter(ch) for ch in name):
            return ValidationResult(
                False, error_message="City name must contain letters", suggestions=examples
            )
        if any(not (_is_letter(ch) or ch in _CITY_PUNCTUATION) for ch in name):
            return ValidationResult(
                False,
                error_message="City name contains invalid characters",
                suggestions=[
                    "Use letters, spaces, hyphens, periods and apostrophes only",
                    "Add the country separately, or after a comma: 'Paris, FR'",
                ],
            )
        if len(name) < 2:
            return ValidationResult(False, error_message="City name is too short")
        return ValidationResult(True, value=name)

    @classmethod
    def validate_country_code(cls, country_code: str | None) -> ValidationResult:
        """Validate an optional ISO 3166-1 alpha-2 code; returns it upper-cased."""
        if country_code is None or not country_code.strip():
            return ValidationResult(True, value=None)
        code = country_code.strip().upper()
        if not cls.COUNTRY_CODE_PATTERN.match(code):
            common = ", ".join(list(cls.COMMON_COUNTRIES)[:10])
            return ValidationResult(
                False,
                error_message="Country code must be exactly 2 letters (ISO 3166-1)",
                suggestions=[f"Common codes: {common}"],
            )
        return ValidationResult(True, value=code)

    @classmethod
    def parse_location_query(cls, query: str) -> ValidationResult:
        """Parse ``"City"`` or ``"City, CC"`` into a validated ``(city, country)`` pair.

        Only a trailing two-letter part is treated as a country code, so
        "Paris, Texas" is searched as a whole rather than rejected.
        """
        city, _, country = query.rpartition(",")
        if not city or len(country.strip()) != 2:
            city, country = query, ""
        city_result = cls.validate_city_name(city.replace(",", " "))
        if not city_result.is_valid:
            return city_result
        country_result = cls.validate_country_code(country)
        if not country_result.is_valid:
            return country_result
        return ValidationResult(True, value=(city_result.value, country_result.value))

    @classmethod
    def validate_numeric_input(
        cls,
        value: str,
        min_value: float | None = None,
        max_value: float | None = None,
        allow_negative: bool = True,
        decimal_places: int | None = None,
    ) -> ValidationResult:
        """Parse a number and check it against optional bounds."""
        if not isinstance(value, str) or not value.strip():
            return ValidationResult(False, error_message="Value cannot be empty")
        text = value.strip()
        try:
            number = float(text)
        except ValueError:
            return ValidationResult(False, error_message=f"'{text}' is not a number")
        if not allow_negative and number < 0:
            return ValidationResult(False, error_message="Negative values are not allowed")
        if min_value is not None and number < min_value:
            return ValidationResult(False, error_message=f"Value must be at least {min_value:g}")
        if max_value is not None and number > max_value:
            return ValidationResult(False, error_message=f"Value must be at most {max_value:g}")
        if decimal_places is not None:
            _, _, fraction = text.partition(".")
            if len(fraction.rstrip("0")) > decimal_places:
                if decimal_places == 0:
                    return ValidationResult(False, error_message="Enter a whole number")
                return ValidationResult(
                    False, error_message=f"Use at most {decimal_places} decimal places"
                )
        return ValidationResult(True, value=number)
