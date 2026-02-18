"""Tests unitarios para utils/formatters.py"""
import pytest
from utils.formatters import format_date, format_currency, format_cuil_display


class TestFormatDate:
    @pytest.mark.parametrize("iso,expected", [
        ("2025-03-15", "15/03/2025"),
        ("2025-03-15T10:30:00", "15/03/2025"),
        ("2025-12-01T00:00:00+00:00", "01/12/2025"),
    ])
    def test_valid_dates(self, iso, expected):
        assert format_date(iso) == expected

    def test_empty_returns_empty(self):
        assert format_date("") == ""

    def test_none_returns_empty(self):
        assert format_date(None) == ""

    def test_short_string_returned_as_is(self):
        assert format_date("abc") == "abc"

    def test_invalid_date_returned_as_is(self):
        result = format_date("9999-99-99")
        assert isinstance(result, str)


class TestFormatCurrency:
    def test_integer(self):
        assert format_currency(1000) == "$1,000.00"

    def test_float(self):
        assert format_currency(1234.5) == "$1,234.50"

    def test_zero(self):
        assert format_currency(0) == "$0.00"

    def test_string_number(self):
        assert format_currency("500") == "$500.00"

    def test_none_returns_zero(self):
        assert format_currency(None) == "$0.00"

    def test_invalid_returns_zero(self):
        assert format_currency("abc") == "$0.00"


class TestFormatCuilDisplay:
    def test_eleven_digits(self):
        assert format_cuil_display("20123456789") == "20-12345678-9"

    def test_already_formatted(self):
        assert format_cuil_display("20-12345678-9") == "20-12345678-9"

    def test_empty(self):
        assert format_cuil_display("") == ""

    def test_none(self):
        assert format_cuil_display(None) == ""

    def test_wrong_length(self):
        assert format_cuil_display("12345") == "12345"
