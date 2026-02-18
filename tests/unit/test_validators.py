"""Tests unitarios para utils/validators.py"""
import pytest
from utils.validators import (
    validate_cuil, validate_dni, validate_email, validate_phone, format_cuil,
)


# =====================================================================
# validate_cuil
# =====================================================================

class TestValidateCuil:
    def test_empty_is_optional(self):
        ok, msg = validate_cuil("")
        assert ok is True
        assert msg == ""

    @pytest.mark.parametrize("cuil", [
        "20-12345678-9",
        "23-12345678-9",
        "24-12345678-9",
        "27-12345678-9",
        "20123456789",       # sin guiones
    ])
    def test_valid_cuils(self, cuil):
        ok, msg = validate_cuil(cuil)
        assert ok is True

    def test_wrong_length(self):
        ok, msg = validate_cuil("20-1234567-9")  # 10 digitos
        assert ok is False
        assert "11 digitos" in msg

    def test_too_many_digits(self):
        ok, msg = validate_cuil("20-123456789-9")  # 12 digitos
        assert ok is False

    @pytest.mark.parametrize("prefix", ["10", "99", "00"])
    def test_invalid_prefix(self, prefix):
        ok, msg = validate_cuil(f"{prefix}-12345678-9")
        assert ok is False
        assert "prefijo" in msg.lower()

    @pytest.mark.parametrize("prefix", ["30", "33", "34"])
    def test_valid_cuit_prefix(self, prefix):
        """Prefijos 30, 33 y 34 son CUIT de persona juridica, validos."""
        ok, msg = validate_cuil(f"{prefix}-12345678-9")
        assert ok is True


# =====================================================================
# validate_dni
# =====================================================================

class TestValidateDni:
    def test_empty_is_optional(self):
        ok, msg = validate_dni("")
        assert ok is True

    @pytest.mark.parametrize("dni", ["1234567", "12345678", "12.345.678"])
    def test_valid_dnis(self, dni):
        ok, msg = validate_dni(dni)
        assert ok is True

    def test_too_short(self):
        ok, msg = validate_dni("123456")
        assert ok is False
        assert "7 u 8" in msg

    def test_too_long(self):
        ok, msg = validate_dni("123456789")
        assert ok is False


# =====================================================================
# validate_email
# =====================================================================

class TestValidateEmail:
    def test_empty_is_optional(self):
        ok, msg = validate_email("")
        assert ok is True

    @pytest.mark.parametrize("email", [
        "user@example.com",
        "user.name@domain.co.ar",
        "user+tag@test.org",
    ])
    def test_valid_emails(self, email):
        ok, msg = validate_email(email)
        assert ok is True

    @pytest.mark.parametrize("email", [
        "sin-arroba",
        "@sin-usuario.com",
        "user@",
        "user@.com",
        "user@domain",
    ])
    def test_invalid_emails(self, email):
        ok, msg = validate_email(email)
        assert ok is False
        assert "email" in msg.lower()


# =====================================================================
# validate_phone
# =====================================================================

class TestValidatePhone:
    def test_empty_is_optional(self):
        ok, msg = validate_phone("")
        assert ok is True

    @pytest.mark.parametrize("phone", [
        "3624001234",       # 10 digitos
        "1234567",          # 7 digitos (minimo)
        "+5493624001234",   # con prefijo internacional -> 13 digitos
    ])
    def test_valid_phones(self, phone):
        ok, msg = validate_phone(phone)
        assert ok is True

    def test_too_short(self):
        ok, msg = validate_phone("123456")
        assert ok is False

    def test_too_long(self):
        ok, msg = validate_phone("12345678901234")  # 14 digitos
        assert ok is False


# =====================================================================
# format_cuil
# =====================================================================

class TestFormatCuil:
    def test_format_11_digits(self):
        assert format_cuil("20123456789") == "20-12345678-9"

    def test_already_formatted(self):
        assert format_cuil("20-12345678-9") == "20-12345678-9"

    def test_short_returns_as_is(self):
        assert format_cuil("2012345") == "2012345"

    def test_empty(self):
        assert format_cuil("") == ""
