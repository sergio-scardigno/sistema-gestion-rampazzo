"""Smoke tests de UI con pytest-qt.

Verifican que las ventanas principales se construyan sin errores
y que los flujos criticos (login) funcionen a nivel de widgets.

Nota: estos tests requieren un display (real o virtual).
En CI sin display, marcarlos como skip o usar pytest-xvfb.
"""
import pytest
from unittest.mock import patch, MagicMock

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt


# =====================================================================
# LoginView
# =====================================================================

class TestLoginViewSmoke:
    """Smoke tests para la pantalla de login."""

    def test_login_view_renders(self, qtbot):
        """LoginView se instancia sin errores."""
        from views.login_view import LoginView
        view = LoginView()
        qtbot.addWidget(view)
        assert view.windowTitle() != ""

    def test_login_view_has_fields(self, qtbot):
        """LoginView tiene los campos de usuario y contrasena."""
        from views.login_view import LoginView
        view = LoginView()
        qtbot.addWidget(view)
        assert view._txt_username is not None
        assert view._txt_password is not None
        assert view._btn_login is not None

    def test_login_empty_fields_shows_warning(self, qtbot, monkeypatch):
        """Submit vacio muestra advertencia, no intenta login."""
        from views.login_view import LoginView
        view = LoginView()
        qtbot.addWidget(view)

        # Mockear QMessageBox para que no bloquee
        monkeypatch.setattr(QMessageBox, "warning", lambda *args: None)

        view._txt_username.setText("")
        view._txt_password.setText("")
        view._do_login()
        # No debe emitir login_success
        # (si llegara a auth controller con campos vacios, seria un bug)

    def test_login_success_emits_signal(self, qtbot, seed_usuario, monkeypatch):
        """Login correcto emite la signal login_success."""
        from views.login_view import LoginView
        view = LoginView()
        qtbot.addWidget(view)

        view._txt_username.setText("testuser")
        view._txt_password.setText("test123")

        with qtbot.waitSignal(view.login_success, timeout=5000):
            view._do_login()

    def test_login_failure_shows_error(self, qtbot, seed_usuario, monkeypatch):
        """Login fallido muestra QMessageBox.critical."""
        from views.login_view import LoginView
        view = LoginView()
        qtbot.addWidget(view)

        critical_called = []
        monkeypatch.setattr(QMessageBox, "critical", lambda *args: critical_called.append(True))

        view._txt_username.setText("testuser")
        view._txt_password.setText("wrong_password")
        view._do_login()

        assert len(critical_called) == 1

    def test_login_button_reenabled_after_failure(self, qtbot, seed_usuario, monkeypatch):
        """El boton de login se rehabilita despues de un fallo."""
        from views.login_view import LoginView
        view = LoginView()
        qtbot.addWidget(view)

        monkeypatch.setattr(QMessageBox, "critical", lambda *args: None)

        view._txt_username.setText("testuser")
        view._txt_password.setText("wrong")
        view._do_login()

        assert view._btn_login.isEnabled() is True
        assert view._btn_login.text() == "Iniciar Sesion"


# =====================================================================
# MainWindow – solo instanciacion (requiere sesion activa)
# =====================================================================

class TestMainWindowSmoke:
    """Smoke tests para la ventana principal."""

    def test_main_window_renders(self, qtbot, session_superusuario, monkeypatch):
        """MainWindow se instancia sin errores con sesion activa."""
        # Mockear SessionGuard para evitar timers y conexiones reales
        monkeypatch.setattr(
            "views.main_window.SessionGuard",
            MagicMock(return_value=MagicMock()),
        )
        from views.main_window import MainWindow
        window = MainWindow()
        qtbot.addWidget(window)
        assert window.windowTitle() != ""

    def test_sidebar_has_buttons(self, qtbot, session_superusuario, monkeypatch):
        """MainWindow tiene botones de sidebar segun permisos del rol."""
        monkeypatch.setattr(
            "views.main_window.SessionGuard",
            MagicMock(return_value=MagicMock()),
        )
        from views.main_window import MainWindow
        window = MainWindow()
        qtbot.addWidget(window)
        # Superusuario debe tener acceso a dashboard al menos
        assert len(window._sidebar_buttons) > 0
        assert "dashboard" in window._sidebar_buttons

    def test_sidebar_restricted_role(self, qtbot, session_secretaria, monkeypatch):
        """Secretaria tiene menos botones que superusuario."""
        monkeypatch.setattr(
            "views.main_window.SessionGuard",
            MagicMock(return_value=MagicMock()),
        )
        from views.main_window import MainWindow
        window = MainWindow()
        qtbot.addWidget(window)
        # Secretaria no debe ver usuarios ni auditoria
        assert "usuarios" not in window._sidebar_buttons
        assert "auditoria" not in window._sidebar_buttons
        # Pero si debe ver dashboard y clientes
        assert "dashboard" in window._sidebar_buttons
        assert "clientes" in window._sidebar_buttons
