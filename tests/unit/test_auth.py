"""Tests unitarios para core/auth.py (hash, session, login con mocks)."""
import pytest
from unittest.mock import patch, MagicMock

from core.auth import hash_password, check_password, Session, login


class TestHashPassword:
    def test_returns_string(self):
        result = hash_password("mi_password")
        assert isinstance(result, str)

    def test_starts_with_bcrypt_prefix(self):
        result = hash_password("test")
        assert result.startswith("$2")

    def test_different_each_call(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # salt diferente


class TestCheckPassword:
    def test_correct_password(self):
        hashed = hash_password("secret123")
        assert check_password("secret123", hashed) is True

    def test_wrong_password(self):
        hashed = hash_password("secret123")
        assert check_password("wrong", hashed) is False

    def test_empty_password(self):
        hashed = hash_password("")
        assert check_password("", hashed) is True
        assert check_password("something", hashed) is False


class TestSession:
    def test_singleton(self):
        s1 = Session.get()
        s2 = Session.get()
        assert s1 is s2

    def test_not_logged_in_by_default(self):
        session = Session.get()
        assert session.logged_in is False

    def test_username_empty_when_no_user(self):
        assert Session.get().username == ""

    def test_rol_empty_when_no_user(self):
        assert Session.get().rol == ""

    def test_nombre_empty_when_no_user(self):
        assert Session.get().nombre == ""

    def test_login_sets_user(self):
        session = Session.get()
        session.usuario = {"username": "admin", "rol": "superusuario", "nombre_completo": "Admin"}
        assert session.logged_in is True
        assert session.username == "admin"
        assert session.rol == "superusuario"
        assert session.nombre == "Admin"

    def test_logout_clears_user(self):
        session = Session.get()
        session.usuario = {"username": "admin", "rol": "superusuario", "nombre_completo": "Admin"}
        session.logout()
        assert session.logged_in is False
        assert session.username == ""


class TestLoginFunction:
    """Test login contra cache local (Mongo desconectado por defecto en fixtures)."""

    def test_login_exitoso_offline(self, seed_usuario):
        ok, msg = login("testuser", "test123")
        assert ok is True
        assert "offline" in msg.lower()

    def test_login_password_incorrecta(self, seed_usuario):
        ok, msg = login("testuser", "wrong")
        assert ok is False
        assert "incorrecta" in msg.lower()

    def test_login_usuario_inexistente(self):
        ok, msg = login("nadie", "test123")
        assert ok is False
        assert "no encontrado" in msg.lower()

    def test_login_usuario_desactivado(self, seed_usuario):
        from core import db_local
        db_local.update("usuarios", seed_usuario["_id"], {"activo": 0})
        ok, msg = login("testuser", "test123")
        assert ok is False
        assert "desactivado" in msg.lower()

    def test_login_usuario_eliminado(self, seed_usuario):
        from core import db_local
        db_local.update("usuarios", seed_usuario["_id"], {"eliminado": 1})
        ok, msg = login("testuser", "test123")
        assert ok is False
        assert "baja" in msg.lower()

    def test_login_sets_session(self, seed_usuario):
        login("testuser", "test123")
        session = Session.get()
        assert session.logged_in is True
        assert session.username == "testuser"
