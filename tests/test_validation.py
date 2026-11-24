import pytest

from meteormind.validation import InputValidator


class TestCityName:
    @pytest.mark.parametrize(
        "name",
        ["London", "New York", "São Paulo", "St. John's", "Aix-en-Provence", "東京", "Αθήνα"],
    )
    def test_accepts_real_place_names(self, name: str) -> None:
        result = InputValidator.validate_city_name(name)
        assert result.is_valid, result.error_message
        assert result.value == name

    def test_normalises_whitespace_but_keeps_capitalisation(self) -> None:
        assert InputValidator.validate_city_name("  McAllen   ").value == "McAllen"
        assert InputValidator.validate_city_name("new   york").value == "new york"

    @pytest.mark.parametrize(
        ("name", "message"),
        [
            ("", "empty"),
            ("   ", "empty"),
            ("123", "letters"),
            ("Lond0n", "invalid characters"),
            ("Paris; DROP", "invalid characters"),
            ("x", "too short"),
            ("a" * 101, "too long"),
        ],
    )
    def test_rejects_bad_input(self, name: str, message: str) -> None:
        result = InputValidator.validate_city_name(name)
        assert not result.is_valid
        assert message in result.error_message

    def test_rejects_non_strings(self) -> None:
        assert not InputValidator.validate_city_name(None).is_valid


class TestCountryCode:
    def test_optional(self) -> None:
        for value in (None, "", "  "):
            result = InputValidator.validate_country_code(value)
            assert result.is_valid and result.value is None

    def test_upper_cases(self) -> None:
        assert InputValidator.validate_country_code(" gb ").value == "GB"

    @pytest.mark.parametrize("code", ["USA", "1A", "U"])
    def test_rejects_invalid(self, code: str) -> None:
        assert not InputValidator.validate_country_code(code).is_valid


class TestLocationQuery:
    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("London", ("London", None)),
            ("London, gb", ("London", "GB")),
            ("London,GB", ("London", "GB")),
            ("Paris, Texas", ("Paris Texas", None)),
        ],
    )
    def test_parses_optional_country_suffix(
        self, query: str, expected: tuple[str, str | None]
    ) -> None:
        result = InputValidator.parse_location_query(query)
        assert result.is_valid, result.error_message
        assert result.value == expected

    def test_invalid_city_is_reported(self) -> None:
        assert not InputValidator.parse_location_query("42, GB").is_valid


class TestNumericInput:
    def test_bounds_and_whole_numbers(self) -> None:
        validate = InputValidator.validate_numeric_input
        assert validate("3", 1, 5, decimal_places=0).value == 3
        assert validate("3.0", 1, 5, decimal_places=0).is_valid
        assert not validate("3.5", 1, 5, decimal_places=0).is_valid
        assert not validate("0", 1, 5).is_valid
        assert not validate("6", 1, 5).is_valid
        assert not validate("-1", allow_negative=False).is_valid
        assert not validate("abc").is_valid
        assert not validate("").is_valid
