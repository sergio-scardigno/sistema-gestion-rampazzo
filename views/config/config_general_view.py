"""Vista de configuracion general – Branding / Logos / Admin avanzada.

Solo visible/editable para superusuario. Otros roles no ven los controles.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QMessageBox, QFrame, QTabWidget, QSizePolicy,
    QDialog, QLineEdit, QApplication,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap

from controllers.config_controller import ConfigController
from core.auth import Session


class LogoSelector(QFrame):
    """Widget reutilizable para seleccionar, previsualizar y eliminar un logo."""
    logo_changed = Signal()  # emitido cuando se guarda o elimina

    def __init__(self, title: str, getter, setter, remover, parent=None):
        super().__init__(parent)
        self._getter = getter
        self._setter = setter
        self._remover = remover

        self.setStyleSheet("""
            LogoSelector {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 10px;
                border-left: 4px solid #c9a84c;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Titulo
        lbl_title = QLabel(title)
        lbl_title.setFont(QFont("Lato", 14, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #1a1a1a; border: none;")
        layout.addWidget(lbl_title)

        # Preview
        self._lbl_preview = QLabel()
        self._lbl_preview.setFixedSize(200, 80)
        self._lbl_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_preview.setStyleSheet(
            "background-color: #f5f5f5; border: 1px dashed #cccccc; border-radius: 6px;"
        )
        layout.addWidget(self._lbl_preview)

        # Botones
        btn_layout = QHBoxLayout()

        self._btn_select = QPushButton("Seleccionar Imagen")
        self._btn_select.setStyleSheet("""
            QPushButton {
                background-color: #c9a84c;
                color: #111111;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #d4b85c; }
        """)
        self._btn_select.clicked.connect(self._select_file)
        btn_layout.addWidget(self._btn_select)

        self._btn_remove = QPushButton("Eliminar Logo")
        self._btn_remove.setStyleSheet("""
            QPushButton {
                background-color: #cc3333;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #aa2222; }
        """)
        self._btn_remove.clicked.connect(self._remove_logo)
        btn_layout.addWidget(self._btn_remove)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Info
        self._lbl_info = QLabel("")
        self._lbl_info.setStyleSheet("color: #6b6b6b; font-size: 11px; font-style: italic; border: none;")
        layout.addWidget(self._lbl_info)

        self._refresh_preview()

    def _refresh_preview(self):
        """Actualiza la vista previa del logo actual."""
        path = self._getter()
        if path:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self._lbl_preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._lbl_preview.setPixmap(scaled)
                self._lbl_info.setText(f"Archivo: {path}")
                self._btn_remove.setEnabled(True)
                return
        # Sin logo
        self._lbl_preview.clear()
        self._lbl_preview.setText("Sin logo configurado")
        self._lbl_preview.setStyleSheet(
            "background-color: #f5f5f5; border: 1px dashed #cccccc; "
            "border-radius: 6px; color: #aaaaaa; font-size: 12px;"
        )
        self._lbl_info.setText("")
        self._btn_remove.setEnabled(False)

    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar imagen",
            "",
            "Imagenes (*.png *.jpg *.jpeg *.bmp *.ico);;Todos (*)",
        )
        if not path:
            return

        ok, msg = self._setter(path)
        if ok:
            self._refresh_preview()
            self.logo_changed.emit()
            QMessageBox.information(self, "Logo Actualizado", msg)
        else:
            QMessageBox.warning(self, "Error", msg)

    def _remove_logo(self):
        reply = QMessageBox.question(
            self, "Eliminar Logo",
            "Esta seguro que desea eliminar este logo?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        ok, msg = self._remover()
        if ok:
            self._refresh_preview()
            self.logo_changed.emit()

    def refresh(self):
        self._refresh_preview()


class ConfigGeneralView(QWidget):
    """Pestaña de configuracion general con logos."""
    logo_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_superusuario = Session.get().rol == "superusuario"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        # Header
        title = QLabel("Configuracion General")
        title.setFont(QFont("Lato", 17, QFont.Weight.Bold))
        title.setStyleSheet("color: #1a1a1a;")
        layout.addWidget(title)

        if not self._is_superusuario:
            lbl = QLabel("Solo el superusuario puede modificar esta configuracion.")
            lbl.setStyleSheet("color: #8a8a8a; font-size: 14px; font-style: italic;")
            layout.addWidget(lbl)
            layout.addStretch()
            return

        # Seccion Branding
        lbl_section = QLabel("Branding / Logos")
        lbl_section.setFont(QFont("Lato", 16, QFont.Weight.Bold))
        lbl_section.setStyleSheet("color: #c9a84c;")
        layout.addWidget(lbl_section)

        info = QLabel(
            "Configure los logos del sistema. El logo principal se muestra en el Login, "
            "Dashboard y cabecera del sidebar. El logo de Carpetas se usa como icono "
            "del modulo Carpetas en el sidebar."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #6b6b6b; font-size: 12px; margin-bottom: 8px;")
        layout.addWidget(info)

        # Logo principal
        self._logo_principal = LogoSelector(
            "Logo Principal (Login / Dashboard / Sidebar)",
            ConfigController.get_logo_principal,
            ConfigController.set_logo_principal,
            ConfigController.remove_logo_principal,
        )
        self._logo_principal.logo_changed.connect(self._on_logo_changed)
        layout.addWidget(self._logo_principal)

        # Logo expedientes
        self._logo_expedientes = LogoSelector(
            "Logo Carpetas (Icono del modulo)",
            ConfigController.get_logo_expedientes,
            ConfigController.set_logo_expedientes,
            ConfigController.remove_logo_expedientes,
        )
        self._logo_expedientes.logo_changed.connect(self._on_logo_changed)
        layout.addWidget(self._logo_expedientes)

        # -----------------------------------------------------------
        # Seccion Administracion Avanzada
        # -----------------------------------------------------------
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("color: #e0e0e0; margin-top: 16px; margin-bottom: 8px;")
        layout.addWidget(separator)

        lbl_admin = QLabel("Administracion Avanzada")
        lbl_admin.setFont(QFont("Lato", 16, QFont.Weight.Bold))
        lbl_admin.setStyleSheet("color: #cc3333;")
        layout.addWidget(lbl_admin)

        lbl_warn = QLabel(
            "Estas acciones son irreversibles y afectan tanto la base de datos "
            "local como la remota (MongoDB Atlas). Asegurese de saber lo que hace."
        )
        lbl_warn.setWordWrap(True)
        lbl_warn.setStyleSheet("color: #6b6b6b; font-size: 12px; margin-bottom: 8px;")
        layout.addWidget(lbl_warn)

        # Contenedor del boton de reset
        reset_frame = QFrame()
        reset_frame.setStyleSheet("""
            QFrame {
                background-color: #fff5f5;
                border: 1px solid #e0c0c0;
                border-radius: 10px;
                border-left: 4px solid #cc3333;
            }
        """)
        reset_layout = QVBoxLayout(reset_frame)
        reset_layout.setContentsMargins(20, 16, 20, 16)
        reset_layout.setSpacing(10)

        lbl_reset_title = QLabel("Borrar toda la base de datos")
        lbl_reset_title.setFont(QFont("Lato", 14, QFont.Weight.Bold))
        lbl_reset_title.setStyleSheet("color: #cc3333; border: none;")
        reset_layout.addWidget(lbl_reset_title)

        lbl_reset_desc = QLabel(
            "Elimina TODOS los datos (clientes, carpetas, tareas, turnos, movimientos, "
            "documentos, auditorias, etc.) de la base local y remota. "
            "Solo se conservan los 5 usuarios originales del sistema.\n\n"
            "Se creara un backup automatico antes de proceder."
        )
        lbl_reset_desc.setWordWrap(True)
        lbl_reset_desc.setStyleSheet("color: #6b6b6b; font-size: 12px; border: none;")
        reset_layout.addWidget(lbl_reset_desc)

        btn_row = QHBoxLayout()
        self._btn_reset_db = QPushButton("Borrar base de datos (reset total)")
        self._btn_reset_db.setStyleSheet("""
            QPushButton {
                background-color: #cc3333;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 10px 22px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #aa2222; }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #888888;
            }
        """)
        self._btn_reset_db.clicked.connect(self._on_reset_database)
        btn_row.addWidget(self._btn_reset_db)
        btn_row.addStretch()
        reset_layout.addLayout(btn_row)

        self._lbl_reset_status = QLabel("")
        self._lbl_reset_status.setStyleSheet(
            "color: #888888; font-size: 11px; font-style: italic; border: none;"
        )
        reset_layout.addWidget(self._lbl_reset_status)

        layout.addWidget(reset_frame)

        # Verificar conexion para habilitar/deshabilitar boton
        self._update_reset_button_state()

        layout.addStretch()

    # ---- Helpers internos ----

    def _update_reset_button_state(self):
        """Habilita o deshabilita el boton de reset segun la conexion a Atlas."""
        from core.db_remote import is_connected
        if is_connected():
            self._btn_reset_db.setEnabled(True)
            self._lbl_reset_status.setText("")
        else:
            self._btn_reset_db.setEnabled(False)
            self._lbl_reset_status.setText(
                "Requiere conexion a MongoDB Atlas. Verifique su conexion a internet."
            )

    def _on_reset_database(self):
        """Muestra dialogo de confirmacion y ejecuta el reset."""
        self._update_reset_button_state()
        if not self._btn_reset_db.isEnabled():
            return

        dlg = ResetDatabaseDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        # Ejecutar reset
        self._btn_reset_db.setEnabled(False)
        self._lbl_reset_status.setText("Ejecutando reset... por favor espere.")
        QApplication.processEvents()

        from core.reset_service import reset_all_data_keep_seed_users
        ok, msg = reset_all_data_keep_seed_users()

        if ok:
            QMessageBox.information(
                self,
                "Reset Completado",
                f"{msg}\n\nLa aplicacion se cerrara. "
                "Vuelva a abrirla para iniciar sesion con los usuarios por defecto.",
            )
            QApplication.quit()
        else:
            self._btn_reset_db.setEnabled(True)
            self._lbl_reset_status.setText("")
            QMessageBox.critical(self, "Error en Reset", msg)

    def _on_logo_changed(self):
        self.logo_changed.emit()

    def refresh(self):
        if self._is_superusuario:
            self._logo_principal.refresh()
            self._logo_expedientes.refresh()
            self._update_reset_button_state()


class ResetDatabaseDialog(QDialog):
    """Dialogo de confirmacion para el reset total de la base de datos.

    El usuario debe escribir la frase 'BORRAR TODO' para habilitar
    el boton de confirmacion.
    """

    CONFIRMATION_PHRASE = "BORRAR TODO"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirmar Reset de Base de Datos")
        self.setFixedWidth(480)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        # Icono + titulo
        lbl_title = QLabel("ATENCION: Accion Irreversible")
        lbl_title.setFont(QFont("Lato", 16, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #cc3333;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_title)

        # Advertencia detallada
        lbl_warning = QLabel(
            "Esta a punto de BORRAR TODOS los datos del sistema, "
            "incluyendo:\n\n"
            "  - Clientes y carpetas/expedientes\n"
            "  - Tareas, turnos y comunicaciones\n"
            "  - Movimientos economicos\n"
            "  - Documentos y auditorias\n"
            "  - Notificaciones y configuraciones\n\n"
            "Se borran tanto los datos LOCALES como los REMOTOS "
            "(MongoDB Atlas).\n\n"
            "Solo se conservaran los 5 usuarios originales del sistema "
            "(secretaria, agente, abogado, admin, super) con sus "
            "contrasenas por defecto.\n\n"
            "Se creara un backup automatico antes de proceder."
        )
        lbl_warning.setWordWrap(True)
        lbl_warning.setStyleSheet(
            "color: #333333; font-size: 12px; "
            "background-color: #fff5f5; border: 1px solid #e0c0c0; "
            "border-radius: 6px; padding: 12px;"
        )
        layout.addWidget(lbl_warning)

        # Instruccion
        lbl_instruction = QLabel(
            f'Escriba <b>{self.CONFIRMATION_PHRASE}</b> para confirmar:'
        )
        lbl_instruction.setStyleSheet("color: #333333; font-size: 13px;")
        layout.addWidget(lbl_instruction)

        # Input de confirmacion
        self._input = QLineEdit()
        self._input.setPlaceholderText(self.CONFIRMATION_PHRASE)
        self._input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
                font-weight: bold;
            }
            QLineEdit:focus {
                border-color: #cc3333;
            }
        """)
        self._input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._input)

        # Botones
        btn_layout = QHBoxLayout()

        self._btn_cancel = QPushButton("Cancelar")
        self._btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #e0e0e0;
                color: #333333;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #cccccc; }
        """)
        self._btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self._btn_cancel)

        btn_layout.addStretch()

        self._btn_confirm = QPushButton("Confirmar Reset")
        self._btn_confirm.setEnabled(False)
        self._btn_confirm.setStyleSheet("""
            QPushButton {
                background-color: #cc3333;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #aa2222; }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #888888;
            }
        """)
        self._btn_confirm.clicked.connect(self.accept)
        btn_layout.addWidget(self._btn_confirm)

        layout.addLayout(btn_layout)

    def _on_text_changed(self, text: str):
        self._btn_confirm.setEnabled(text.strip() == self.CONFIRMATION_PHRASE)
