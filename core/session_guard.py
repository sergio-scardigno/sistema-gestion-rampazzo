"""
SessionGuard – Verificacion periodica del estado del usuario activo.
Detecta si el usuario fue pausado/eliminado y fuerza el cierre de sesion.
"""
from PySide6.QtCore import QObject, QTimer, Signal

from core import db_local
from core.auth import Session


class SessionGuard(QObject):
    """Monitorea el estado del usuario logueado cada 30 segundos."""

    session_invalidated = Signal(str)  # Emite mensaje para mostrar al usuario

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(30_000)  # 30 segundos
        self._timer.timeout.connect(self._check)

    def start(self):
        """Iniciar el monitoreo."""
        self._timer.start()

    def stop(self):
        """Detener el monitoreo."""
        self._timer.stop()

    def _check(self):
        """Verifica si el usuario sigue activo y si hay signals pendientes."""
        session = Session.get()
        if not session.logged_in or not session.usuario:
            return

        user_id = session.usuario.get("_id", "")
        username = session.username

        # 1. Verificar campo activo en la BD
        user = db_local.find_by_id("usuarios", user_id)
        if not user:
            self.session_invalidated.emit(
                "Su cuenta ha sido eliminada del sistema."
            )
            return

        if not user.get("activo", 1):
            reason = "Su cuenta ha sido pausada por un administrador."
            if user.get("eliminado"):
                reason = "Su cuenta ha sido dada de baja por un administrador."
            self.session_invalidated.emit(reason)
            return

        # 2. Verificar signals de force_logout
        if username:
            from controllers.auth_controller import AuthController
            signals = AuthController.check_signals_for_user(username)
            for sig in signals:
                if sig.get("signal_type") == "force_logout":
                    AuthController.mark_signal_processed(sig["_id"])
                    self.session_invalidated.emit(
                        "Su sesion ha sido cerrada por un administrador."
                    )
                    return
