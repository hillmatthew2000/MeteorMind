import pytest

from meteormind.units import (
    DistanceUnit,
    PressureUnit,
    TemperatureUnit,
    UnitConverter,
    UnitPreferences,
    WeatherFormatter,
    WindSpeedUnit,
    compass_point,
    create_imperial_preferences,
    create_metric_preferences,
)


class TestConversions:
    @pytest.mark.parametrize(
        ("celsius", "fahrenheit"), [(0, 32), (100, 212), (-40, -40), (37, 98.6)]
    )
    def test_celsius_fahrenheit(self, celsius: float, fahrenheit: float) -> None:
        assert UnitConverter.celsius_to_fahrenheit(celsius) == pytest.approx(fahrenheit)
        assert UnitConverter.fahrenheit_to_celsius(fahrenheit) == pytest.approx(celsius)

    def test_temperature_between_every_pair_round_trips(self) -> None:
        for source in TemperatureUnit:
            for target in TemperatureUnit:
                there = UnitConverter.convert_temperature(21.3, source, target)
                assert UnitConverter.convert_temperature(there, target, source) == pytest.approx(
                    21.3
                )

    def test_kelvin(self) -> None:
        assert UnitConverter.convert_temperature(
            0, TemperatureUnit.CELSIUS, TemperatureUnit.KELVIN
        ) == pytest.approx(273.15)

    def test_temperature_delta_has_no_offset(self) -> None:
        assert UnitConverter.convert_temperature_delta(5, TemperatureUnit.FAHRENHEIT) == 9
        assert UnitConverter.convert_temperature_delta(5, TemperatureUnit.KELVIN) == 5

    @pytest.mark.parametrize(
        ("unit", "expected"),
        [
            (WindSpeedUnit.KILOMETERS_PER_HOUR, 36.0),
            (WindSpeedUnit.MILES_PER_HOUR, 22.369363),
            (WindSpeedUnit.KNOTS, 19.438445),
        ],
    )
    def test_wind_speed_uses_exact_factors(self, unit: WindSpeedUnit, expected: float) -> None:
        converted = UnitConverter.convert_wind_speed(10, WindSpeedUnit.METERS_PER_SECOND, unit)
        assert converted == pytest.approx(expected, rel=1e-6)
        back = UnitConverter.convert_wind_speed(converted, unit, WindSpeedUnit.METERS_PER_SECOND)
        assert back == pytest.approx(10)

    def test_pressure(self) -> None:
        convert = UnitConverter.convert_pressure
        assert convert(1013.25, PressureUnit.HECTOPASCAL, PressureUnit.ATMOSPHERES) == 1
        assert convert(1013.25, PressureUnit.HECTOPASCAL, PressureUnit.INCHES_OF_MERCURY) == (
            pytest.approx(29.921, abs=1e-3)
        )
        assert convert(1000, PressureUnit.MILLIBARS, PressureUnit.HECTOPASCAL) == 1000

    def test_distance(self) -> None:
        convert = UnitConverter.convert_distance
        assert convert(1, DistanceUnit.MILES, DistanceUnit.KILOMETERS) == pytest.approx(1.609344)
        assert convert(1, DistanceUnit.FEET, DistanceUnit.METERS) == pytest.approx(0.3048)


class TestUnitEnums:
    def test_lookup_ignores_case(self) -> None:
        # The GUI offered "inhg" while the enum value is "inHg", which used to raise.
        assert PressureUnit("inhg") is PressureUnit.INCHES_OF_MERCURY
        assert TemperatureUnit("Celsius") is TemperatureUnit.CELSIUS

    def test_unknown_value_still_raises(self) -> None:
        with pytest.raises(ValueError):
            TemperatureUnit("rankine")

    def test_symbols(self) -> None:
        assert TemperatureUnit.FAHRENHEIT.symbol == "°F"
        assert WindSpeedUnit.KNOTS.symbol == "kn"


class TestUnitPreferences:
    def test_round_trip(self) -> None:
        prefs = create_imperial_preferences()
        assert UnitPreferences.from_dict(prefs.to_dict()) == prefs

    def test_invalid_values_fall_back_to_metric_defaults(self) -> None:
        prefs = UnitPreferences.from_dict({"temperature": "fahrenheit", "pressure": "bogus"})
        assert prefs.temperature is TemperatureUnit.FAHRENHEIT
        assert prefs.pressure is PressureUnit.HECTOPASCAL

    @pytest.mark.parametrize(
        ("setting", "expected"),
        [
            ("imperial", create_imperial_preferences()),
            ("metric", create_metric_preferences()),
            ({"wind_speed": "kmh"}, UnitPreferences(wind_speed=WindSpeedUnit.KILOMETERS_PER_HOUR)),
            (None, create_metric_preferences()),
        ],
    )
    def test_from_setting_accepts_legacy_preset_names(
        self, setting: object, expected: UnitPreferences
    ) -> None:
        assert UnitPreferences.from_setting(setting) == expected


class TestFormatter:
    metric = WeatherFormatter(create_metric_preferences())
    imperial = WeatherFormatter(create_imperial_preferences())

    def test_temperature(self) -> None:
        assert self.metric.format_temperature(15.24) == "15.2°C"
        assert self.imperial.format_temperature(15.24) == "59.4°F"
        assert self.metric.format_temperature(15.24, show_unit=False) == "15.2"
        assert self.metric.format_temperature(15.6, decimals=0) == "16°C"

    def test_never_shows_negative_zero(self) -> None:
        assert self.metric.format_temperature(-0.04) == "0.0°C"
        assert self.metric.format_temperature(-0.4, decimals=0) == "0°C"

    def test_temperature_delta(self) -> None:
        # A +0.5 °C change is +0.9 °F, not the absolute 32.9 °F it used to show.
        assert self.imperial.format_temperature_delta(0.5) == "+0.9°F"
        assert self.metric.format_temperature_delta(-2.0) == "-2.0°C"
        assert self.metric.format_temperature_delta(0.0, show_unit=False) == "0.0"

    def test_wind_pressure_distance(self) -> None:
        assert self.metric.format_wind_speed(4.16) == "4.2 m/s"
        assert self.imperial.format_wind_speed(10) == "22 mph"
        assert self.metric.format_pressure(1013.4) == "1013 hPa"
        assert self.imperial.format_pressure(1013.25) == "29.92 inHg"
        assert self.metric.format_visibility(10000) == "10.0 km"
        assert self.imperial.format_visibility(10000) == "6.2 mi"
        assert self.metric.format_visibility(None) == "—"

    @pytest.mark.parametrize(
        ("degrees", "expected"),
        [(0, "N"), (360, "N"), (11, "N"), (12, "NNE"), (225, "SW"), (350, "N"), (348, "NNW")],
    )
    def test_compass_point(self, degrees: int, expected: str) -> None:
        assert compass_point(degrees) == expected

    def test_wind_direction(self) -> None:
        assert self.metric.format_wind_direction(0) == "N (0°)"
        assert self.metric.format_wind_direction(-5) == "N/A"

    def test_humidity_and_preferences_display(self) -> None:
        assert self.metric.format_humidity(55) == "55%"
        assert "°F" in self.imperial.get_unit_preferences_display()
