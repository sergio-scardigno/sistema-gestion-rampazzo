"""
Sistema Rampazzo - Punto de entrada.
"""
import os
import sys
import logging
from pathlib import Path

# Forzar UTF-8 globalmente (necesario en Windows para simbolos latinos)
os.environ.setdefault("PYTHONUTF8", "1")
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Inicializar logging lo mas temprano posible (antes de Qt)
from core.logging_setup import init_logging
init_logging()

logger = logging.getLogger(__name__)

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QFont, QIcon

from config import APP_NAME, APP_VERSION, BASE_DIR
from core.db_local import init_db, validate_version_compatibility, validate_remote_version_compatibility
from core.auth import ensure_admin_exists
from core.audit import init_audit_protection

FONTS_DIR = BASE_DIR / "resources" / "fonts"


def load_fonts():
    """Cargar fuente Lato desde resources/fonts/."""
    loaded = False
    if FONTS_DIR.exists():
        for ttf in FONTS_DIR.glob("*.ttf"):
            font_id = QFontDatabase.addApplicationFont(str(ttf))
            if font_id >= 0:
                loaded = True
    return loaded


def load_stylesheet(app: QApplication):
    qss_path = BASE_DIR / "resources" / "styles" / "theme.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))


def _apply_app_icon(app: QApplication):
    """Establece el icono de ventana global usando el logo principal si existe."""
    from controllers.config_controller import ConfigController
    logo_path = ConfigController.get_logo_principal()
    if logo_path:
        icon = QIcon(logo_path)
        if not icon.isNull():
            app.setWindowIcon(icon)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")

    # Cargar fuente Lato y establecer como default
    lato_loaded = load_fonts()
    default_font = QFont("Lato" if lato_loaded else "Segoe UI", 10)
    app.setFont(default_font)

    load_stylesheet(app)

    # Init local database
    init_db()
    init_audit_protection()
    ensure_admin_exists()

    # Validar compatibilidad de version con la BD local
    compatible, msg = validate_version_compatibility()
    if not compatible:
        QMessageBox.critical(
            None, "Version Incompatible",
            msg
        )
        sys.exit(1)

    # Validar version contra MongoDB remoto (si hay conexion)
    remote_ok, remote_msg = validate_remote_version_compatibility()
    if not remote_ok:
        QMessageBox.critical(
            None, "Version Incompatible",
            remote_msg
        )
        sys.exit(1)

    # Aplicar icono de ventana global si hay logo configurado
    _apply_app_icon(app)

    # Show login
    from views.login_view import LoginView
    login = LoginView()

    def on_login_success():
        login.close()
        from views.main_window import MainWindow
        window = MainWindow()
        window.show()

        # Start connection monitor
        from core.connection_monitor import ConnectionMonitor
        monitor = ConnectionMonitor(check_interval_ms=30000)
        monitor.status_changed.connect(
            lambda online: window.set_sync_status("online" if online else "offline")
        )
        monitor.check()
        window._connection_monitor = monitor  # prevent GC

        # Start scheduler con todas las automatizaciones
        try:
            from core.sync_engine import SyncEngine
            from core.scheduler import start_scheduler, setup_all_jobs
            sync = SyncEngine()
            start_scheduler()
            setup_all_jobs(sync_engine=sync)
            window._sync_engine = sync

            # Al terminar el sync, refrescar la vista activa y actualizar indicador
            def _on_sync_done(success, msg):
                window.set_sync_status("online" if success else "offline", msg)
                if success:
                    try:
                        current = window._stack.currentWidget()
                        if current and hasattr(current, "refresh"):
                            current.refresh()
                    except Exception:
                        pass

            sync.sync_finished.connect(_on_sync_done)
            sync.sync_progress.connect(
                lambda detail: window.set_sync_status("syncing", detail)
            )

            # Sync inicial inmediato en segundo plano (no bloquea la UI)
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1000, sync.force_sync)
        except Exception:
            logger.exception("Scheduler no iniciado")

    login.login_success.connect(on_login_success)
    login.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
