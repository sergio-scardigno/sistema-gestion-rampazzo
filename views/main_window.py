"""
Ventana principal con sidebar dinamico segun rol + area de contenido + barra superior.
"""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QStackedWidget, QFrame, QMessageBox, QSizePolicy
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QIcon, QPixmap

from controllers.auth_controller import AuthController
from controllers.config_controller import ConfigController
from core.auth import Session
from core.permissions import modulos_permitidos
from core.session_guard import SessionGuard
from views.widgets.sync_indicator import SyncIndicator
from views.widgets.notification_bell import NotificationBell
from config import APP_NAME, APP_VERSION, APP_FULL_VERSION


# Mapeo de modulos a iconos (unicode simples)
MODULO_CONFIG = {
    "dashboard":      {"label": "  Dashboard",       "icon": "\u2302"},
    "clientes":       {"label": "  Clientes",        "icon": "\u263A"},
    "expedientes":    {"label": "  Carpetas",        "icon": "\u2630"},
    "tareas":         {"label": "  Tareas",          "icon": "\u2611"},
    "turnos":         {"label": "  Turnos ANSES",    "icon": "\u23F0"},
    "comunicaciones": {"label": "  Comunicaciones",  "icon": "\u2709"},
    "documentos":     {"label": "  Documentos",      "icon": "\u2637"},
    "administracion": {"label": "  Administracion",  "icon": "\u0024"},
    "reportes":       {"label": "  Reportes",        "icon": "\u2637"},
    "auditoria":      {"label": "  Auditoria",       "icon": "\u2318"},
    "usuarios":       {"label": "  Empleados",       "icon": "\u2603"},
    "configuracion":  {"label": "  Configuracion",   "icon": "\u2699"},
    "migracion":      {"label": "  Migracion Excel/CSV", "icon": "\u21C5"},
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_FULL_VERSION}")
        self.setMinimumSize(1100, 700)
        self.showMaximized()

        self._sidebar_buttons: dict[str, QPushButton] = {}
        self._views: dict[str, QWidget] = {}
        self._current_module = ""

        self._build_ui()
        self._load_views()
        self._navigate("dashboard")

        # SessionGuard: verifica periodicamente si el usuario sigue activo
        self._session_guard = SessionGuard(self)
        self._session_guard.session_invalidated.connect(self._on_session_invalidated)
        self._session_guard.start()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ---- Sidebar ----
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # Header (logo principal + texto)
        header_widget = QWidget()
        header_widget.setObjectName("sidebar_header")
        header_widget.setMinimumHeight(60)
        header_h_layout = QHBoxLayout(header_widget)
        header_h_layout.setContentsMargins(12, 8, 12, 8)
        header_h_layout.setSpacing(8)

        self._sidebar_logo_label = QLabel()
        self._sidebar_logo_label.setFixedSize(40, 40)
        self._sidebar_logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sidebar_logo_label.setStyleSheet("border: none; background: transparent;")
        header_h_layout.addWidget(self._sidebar_logo_label)

        self._sidebar_title_label = QLabel(APP_NAME)
        self._sidebar_title_label.setObjectName("sidebar_header_text")
        self._sidebar_title_label.setStyleSheet(
            "color: #c9a84c; font-size: 16px; font-weight: bold; "
            "font-family: 'Lato', 'Segoe UI', sans-serif; border: none; background: transparent;"
        )
        header_h_layout.addWidget(self._sidebar_title_label)
        header_h_layout.addStretch()

        sidebar_layout.addWidget(header_widget)
        self._apply_sidebar_logo()

        # Module buttons
        session = Session.get()
        allowed = modulos_permitidos(session.rol)

        for mod_key, cfg in MODULO_CONFIG.items():
            if mod_key in allowed:
                btn = QPushButton(f'{cfg["icon"]}  {cfg["label"]}')
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setProperty("active", "false")
                btn.clicked.connect(lambda checked=False, m=mod_key: self._navigate(m))
                sidebar_layout.addWidget(btn)
                self._sidebar_buttons[mod_key] = btn

        # Aplicar logo de carpetas si existe
        self._apply_expedientes_logo()

        sidebar_layout.addStretch()

        # Version label en sidebar
        version_sidebar = QLabel(f"v{APP_FULL_VERSION}")
        version_sidebar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_sidebar.setStyleSheet(
            "color: #555555; font-size: 10px; padding: 4px; "
            "border: none; background: transparent;"
        )
        sidebar_layout.addWidget(version_sidebar)

        # Logout button
        btn_logout = QPushButton("  Cerrar Sesion")
        btn_logout.setStyleSheet("""
            QPushButton {
                color: #cc3333;
                background: transparent;
                border: none;
                text-align: left;
                padding: 11px 18px;
                font-family: "Lato", "Segoe UI", sans-serif;
            }
            QPushButton:hover { background-color: #1e1e1e; }
        """)
        btn_logout.clicked.connect(self._logout)
        sidebar_layout.addWidget(btn_logout)

        root_layout.addWidget(sidebar)

        # ---- Right panel ----
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Top bar
        topbar = QFrame()
        topbar.setObjectName("topbar")
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(20, 0, 20, 0)

        self._topbar_title = QLabel("Dashboard")
        self._topbar_title.setObjectName("topbar_title")
        topbar_layout.addWidget(self._topbar_title)

        topbar_layout.addStretch()

        # Notification bell
        self._notification_bell = NotificationBell()
        self._notification_bell.notification_clicked.connect(self._on_notification_clicked)
        topbar_layout.addWidget(self._notification_bell)

        # Sync indicator
        self._sync_indicator = SyncIndicator()
        topbar_layout.addWidget(self._sync_indicator)

        # User info
        user_info = QLabel(f"{session.nombre}  ({session.rol.capitalize()})")
        user_info.setStyleSheet("color: #6b6b6b; font-size: 12px; margin-left: 16px;")
        topbar_layout.addWidget(user_info)

        # Version en topbar
        version_topbar = QLabel(f"v{APP_FULL_VERSION}")
        version_topbar.setStyleSheet("color: #aaaaaa; font-size: 10px; margin-left: 12px;")
        topbar_layout.addWidget(version_topbar)

        right_layout.addWidget(topbar)

        # Content area
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background-color: #f0f0f0;")
        right_layout.addWidget(self._stack)

        root_layout.addWidget(right)

    def _load_views(self):
        """Carga lazy de vistas."""
        from views.dashboard_view import DashboardView
        self._register_view("dashboard", DashboardView())

    def _register_view(self, key: str, widget: QWidget):
        self._views[key] = widget
        self._stack.addWidget(widget)

    def _ensure_view(self, key: str):
        """Carga la vista solo cuando se necesita (lazy loading)."""
        if key in self._views:
            return
        if key == "clientes":
            from views.clientes.cliente_list import ClienteListView
            self._register_view(key, ClienteListView())
        elif key == "expedientes":
            from views.expedientes.expediente_list import ExpedienteListView
            self._register_view(key, ExpedienteListView())
        elif key == "tareas":
            from views.tareas.tarea_list import TareaListView
            self._register_view(key, TareaListView())
        elif key == "turnos":
            from views.turnos.turno_list import TurnoListView
            self._register_view(key, TurnoListView())
        elif key == "comunicaciones":
            from views.comunicaciones.comunicacion_list import ComunicacionListView
            self._register_view(key, ComunicacionListView())
        elif key == "documentos":
            from views.documentos.documento_list import DocumentoListView
            self._register_view(key, DocumentoListView())
        elif key == "administracion":
            from views.administracion.movimiento_list import MovimientoListView
            self._register_view(key, MovimientoListView())
        elif key == "reportes":
            from views.reportes.reportes_view import ReportesView
            self._register_view(key, ReportesView())
        elif key == "auditoria":
            from views.auditoria.audit_list import AuditListView
            self._register_view(key, AuditListView())
        elif key == "usuarios":
            from views.config.usuarios_view import UsuariosView
            self._register_view(key, UsuariosView())
        elif key == "configuracion":
            from views.config.config_tabs_view import ConfigTabsView
            view = ConfigTabsView()
            view.logo_changed.connect(self._on_logos_changed)
            self._register_view(key, view)
        elif key == "migracion":
            from views.migration.migration_wizard import MigrationWizardLauncher
            self._register_view(key, MigrationWizardLauncher())
        else:
            placeholder = QLabel(f"Modulo '{key}' en construccion")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("font-size: 18px; color: #8a8a8a;")
            self._register_view(key, placeholder)

    def _navigate(self, module: str):
        self._ensure_view(module)
        self._current_module = module

        # Update sidebar active state
        for k, btn in self._sidebar_buttons.items():
            btn.setProperty("active", "true" if k == module else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        # Update topbar title
        cfg = MODULO_CONFIG.get(module, {})
        self._topbar_title.setText(cfg.get("label", module).strip())

        # Show view
        self._stack.setCurrentWidget(self._views[module])

        # Refresh view if it has a refresh method
        view = self._views[module]
        if hasattr(view, "refresh"):
            view.refresh()

    def _logout(self):
        reply = QMessageBox.question(
            self, "Cerrar Sesion",
            "Esta seguro que desea cerrar sesion?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._session_guard.stop()
            AuthController.logout()
            self.close()

    def _on_session_invalidated(self, message: str):
        """Forzar cierre de sesion por decision de un administrador."""
        self._session_guard.stop()
        QMessageBox.critical(
            self, "Sesion Cerrada",
            f"{message}\n\nDebe iniciar sesion nuevamente."
        )
        AuthController.logout()
        self.close()

    # ── Notification click handler ──

    def _on_notification_clicked(self, tipo: str, id_referencia: str):
        """Navegar al detalle de la entidad referenciada por la notificacion."""
        if not id_referencia:
            return

        if tipo == "tarea_asignada":
            from controllers.tarea_controller import TareaController
            tarea = TareaController.get_by_id(id_referencia)
            if not tarea:
                QMessageBox.information(
                    self, "Notificacion",
                    "La tarea ya no existe o fue eliminada."
                )
                return
            self._navigate("tareas")
            from views.tareas.tarea_form import TareaFormDialog
            dlg = TareaFormDialog(tarea_id=id_referencia, parent=self)
            dlg.exec()
            # Refrescar la vista de tareas tras cerrar el dialog
            view = self._views.get("tareas")
            if view and hasattr(view, "refresh"):
                view.refresh()

        elif tipo == "turno_asignado":
            from controllers.turno_controller import TurnoController
            turno = TurnoController.get_by_id(id_referencia)
            if not turno:
                QMessageBox.information(
                    self, "Notificacion",
                    "El turno ya no existe o fue eliminado."
                )
                return
            self._navigate("turnos")
            from views.turnos.turno_form import TurnoFormDialog
            dlg = TurnoFormDialog(turno_id=id_referencia, parent=self)
            dlg.exec()
            # Refrescar la vista de turnos tras cerrar el dialog
            view = self._views.get("turnos")
            if view and hasattr(view, "refresh"):
                view.refresh()

    def set_sync_status(self, status: str, detail: str = ""):
        self._sync_indicator.set_status(status, detail)

    # ── Logo helpers ──

    def _apply_sidebar_logo(self):
        """Aplica el logo principal en el header del sidebar."""
        logo_path = ConfigController.get_logo_principal()
        if logo_path:
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self._sidebar_logo_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._sidebar_logo_label.setPixmap(scaled)
                self._sidebar_logo_label.setVisible(True)
                return
        # Fallback: ocultar el label del logo
        self._sidebar_logo_label.clear()
        self._sidebar_logo_label.setVisible(False)

    def _apply_expedientes_logo(self):
        """Aplica el logo de carpetas al boton correspondiente."""
        btn = self._sidebar_buttons.get("expedientes")
        if not btn:
            return
        logo_path = ConfigController.get_logo_expedientes()
        if logo_path:
            icon = QIcon(logo_path)
            if not icon.isNull():
                btn.setIcon(icon)
                btn.setIconSize(QSize(20, 20))
                # Quitar el icono unicode del texto
                cfg = MODULO_CONFIG.get("expedientes", {})
                btn.setText(cfg.get("label", "  Carpetas"))
                return
        # Fallback: icono unicode original
        cfg = MODULO_CONFIG.get("expedientes", {})
        btn.setIcon(QIcon())  # limpiar icono
        btn.setText(f'{cfg["icon"]}  {cfg["label"]}')

    def _on_logos_changed(self):
        """Callback cuando se cambian logos desde Configuracion. Refresco inmediato."""
        self._apply_sidebar_logo()
        self._apply_expedientes_logo()
        self._apply_window_icon()

    def _apply_window_icon(self):
        """Actualiza el icono de la barra de titulo de la ventana (y de toda la app)."""
        from PySide6.QtWidgets import QApplication
        logo_path = ConfigController.get_logo_principal()
        if logo_path:
            icon = QIcon(logo_path)
            if not icon.isNull():
                self.setWindowIcon(icon)
                app = QApplication.instance()
                if app:
                    app.setWindowIcon(icon)
                return
        # Fallback: limpiar icono personalizado (vuelve al default del SO)
        self.setWindowIcon(QIcon())
        app = QApplication.instance()
        if app:
            app.setWindowIcon(QIcon())
