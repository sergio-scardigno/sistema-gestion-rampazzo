"""Vista de Configuracion con pestanas: Empleados + General (logos).

Solo superusuario ve la pestaña 'General' de branding.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from PySide6.QtCore import Signal

from core.auth import Session
from views.config.usuarios_view import UsuariosView
from views.config.config_general_view import ConfigGeneralView


class ConfigTabsView(QWidget):
    """Contenedor con tabs para el modulo Configuracion."""
    logo_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_superusuario = Session.get().rol == "superusuario"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: #f0f0f0;
            }
            QTabBar::tab {
                background: #e0e0e0;
                color: #4a4a4a;
                padding: 10px 24px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-family: "Lato", "Segoe UI", sans-serif;
                font-weight: bold;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background: #f0f0f0;
                color: #c9a84c;
            }
            QTabBar::tab:hover {
                background: #d5d5d5;
            }
        """)

        # Pestaña Empleados (siempre visible)
        self._usuarios_view = UsuariosView()
        self._tabs.addTab(self._usuarios_view, "Empleados")

        # Pestaña General / Logos (solo superusuario)
        if self._is_superusuario:
            self._config_general = ConfigGeneralView()
            self._config_general.logo_changed.connect(self._on_logo_changed)
            self._tabs.addTab(self._config_general, "General / Logos")
        else:
            self._config_general = None

        layout.addWidget(self._tabs)

    def _on_logo_changed(self):
        self.logo_changed.emit()

    def refresh(self):
        # Refrescar la pestaña activa
        idx = self._tabs.currentIndex()
        widget = self._tabs.widget(idx)
        if hasattr(widget, "refresh"):
            widget.refresh()
