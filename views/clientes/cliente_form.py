"""Formulario de alta/edicion de Cliente."""
import logging

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QTextEdit, QDateEdit, QPushButton, QLabel, QMessageBox, QFrame,
    QCompleter, QComboBox, QScrollArea
)
from PySide6.QtCore import Qt, QDate, QRegularExpression, QStringListModel
from PySide6.QtGui import QFont, QRegularExpressionValidator

logger = logging.getLogger(__name__)

from controllers.cliente_controller import ClienteController
from services import anses_oficinas_service
from core.lock_manager import LockManager
from utils.validators import format_cuil


class ClienteFormDialog(QDialog):
    def __init__(self, cliente_id: str = None, prefill_data: dict = None, parent=None):
        super().__init__(parent)
        self._id = cliente_id
        self._is_edit = cliente_id is not None
        self._locked = False
        self._prefill = prefill_data
        self.created_client = None  # almacena el cliente creado (para flujo de conversion)

        self.setWindowTitle("Editar Cliente" if self._is_edit else "Nuevo Cliente")
        self.setMinimumWidth(600)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 8, 12, 8)

        # Title
        title = QLabel("Editar Cliente" if self._is_edit else "Nuevo Cliente")
        title.setFont(QFont("Lato", 15, QFont.Weight.Bold))
        layout.addWidget(title)

        # Scroll area para el formulario
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        form_container = QWidget()

        # Form
        form = QFormLayout(form_container)
        form.setSpacing(8)
        form.setContentsMargins(4, 4, 4, 4)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._txt_numero_carpeta = QLineEdit()
        self._txt_numero_carpeta.setPlaceholderText("Numero de carpeta fisica (solo numeros)")
        self._txt_numero_carpeta.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"^\d*$"))
        )
        if self._is_edit:
            self._txt_numero_carpeta.setToolTip("Doble clic para ir a las carpetas de este cliente")
            self._txt_numero_carpeta.mouseDoubleClickEvent = self._on_numero_carpeta_dblclick
        form.addRow("N° de carpeta *:", self._txt_numero_carpeta)

        self._txt_nombre = QLineEdit()
        self._txt_nombre.setPlaceholderText("Nombre completo del cliente")
        form.addRow("Nombre completo *:", self._txt_nombre)

        self._txt_dni = QLineEdit()
        self._txt_dni.setPlaceholderText("Numero de DNI/LC (solo numeros)")
        self._txt_dni.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"^\d{0,8}$"))
        )
        form.addRow("DNI/LC:", self._txt_dni)

        self._txt_cuil = QLineEdit()
        self._txt_cuil.setPlaceholderText("XX-XXXXXXXX-X")
        self._txt_cuil.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"^[\d\-]*$"))
        )
        self._txt_cuil.editingFinished.connect(self._format_cuil)
        form.addRow("CUIL:", self._txt_cuil)

        self._date_nacimiento = QDateEdit()
        self._date_nacimiento.setCalendarPopup(True)
        self._date_nacimiento.setDisplayFormat("dd/MM/yyyy")
        self._date_nacimiento.setDate(QDate(1960, 1, 1))
        form.addRow("Fecha nacimiento:", self._date_nacimiento)

        self._txt_direccion = QLineEdit()
        self._txt_direccion.setPlaceholderText("Direccion completa")
        form.addRow("Direccion:", self._txt_direccion)

        # ── Localidad (con autocompletado desde CSV) ──
        self._txt_localidad = QLineEdit()
        self._txt_localidad.setPlaceholderText("Escriba para buscar localidad...")
        localidades_labels = anses_oficinas_service.get_todas_localidades_labels()
        self._localidades_model = QStringListModel(localidades_labels)
        completer = QCompleter()
        completer.setModel(self._localidades_model)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setMaxVisibleItems(15)
        self._txt_localidad.setCompleter(completer)
        form.addRow("Localidad:", self._txt_localidad)

        self._txt_telefonos = QLineEdit()
        self._txt_telefonos.setPlaceholderText("Separar con coma: 1155551234, 2241556789")
        form.addRow("Telefonos:", self._txt_telefonos)

        self._txt_email = QLineEdit()
        self._txt_email.setPlaceholderText("email@ejemplo.com")
        form.addRow("Email:", self._txt_email)

        self._txt_obra_social = QLineEdit()
        form.addRow("Obra social:", self._txt_obra_social)

        self._txt_actividad = QLineEdit()
        form.addRow("Actividad:", self._txt_actividad)

        self._combo_procedencia = QComboBox()
        self._combo_procedencia.addItems([
            "", "Instagram", "TikTok", "Facebook", "Referido",
            "Presencial", "Web", "Telefono", "Otro"
        ])
        form.addRow("Procedencia:", self._combo_procedencia)

        # Separator visual antes de claves
        sep_claves = QFrame()
        sep_claves.setFrameShape(QFrame.Shape.HLine)
        sep_claves.setStyleSheet("color: #e0e0e0; margin: 4px 0;")
        form.addRow(sep_claves)

        self._txt_clave_mi_anses = QLineEdit()
        self._txt_clave_mi_anses.setPlaceholderText("Clave de Mi ANSES")
        form.addRow("Clave Mi ANSES:", self._txt_clave_mi_anses)

        self._txt_clave_fiscal = QLineEdit()
        self._txt_clave_fiscal.setPlaceholderText("Clave fiscal AFIP")
        form.addRow("Clave Fiscal:", self._txt_clave_fiscal)

        self._txt_observaciones = QTextEdit()
        self._txt_observaciones.setMaximumHeight(80)
        form.addRow("Observaciones:", self._txt_observaciones)

        scroll.setWidget(form_container)
        layout.addWidget(scroll)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setProperty("variant", "secondary")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("Guardar")
        btn_save.clicked.connect(self._save)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

        # Load data if editing, o sugerir numero de carpeta si es nuevo
        if self._is_edit:
            self._load_data()
        else:
            # Sugerir siguiente numero de carpeta correlativo
            suggested = ClienteController.get_suggested_numero_carpeta()
            self._txt_numero_carpeta.setText(suggested)
            if self._prefill:
                self._apply_prefill()

    def _load_data(self):
        data = ClienteController.get_by_id(self._id)
        if not data:
            QMessageBox.warning(self, "Error", "Cliente no encontrado.")
            self.reject()
            return

        # Try to acquire lock
        ok, msg = LockManager.acquire_lock("clientes", self._id)
        if not ok:
            QMessageBox.information(self, "Registro bloqueado", msg)
            # Load as read-only
            self._set_readonly(True)
        else:
            self._locked = True

        self._txt_numero_carpeta.setText(str(data.get("numero_carpeta", "") or ""))
        self._txt_nombre.setText(data.get("nombre_completo", ""))
        self._txt_dni.setText(data.get("dni", ""))
        cuil_val = data.get("cuil", "") or ""
        self._txt_cuil.setText(format_cuil(cuil_val) if cuil_val else "")

        fn = data.get("fecha_nacimiento", "")
        if fn and len(fn) >= 10:
            try:
                self._date_nacimiento.setDate(QDate.fromString(fn[:10], "yyyy-MM-dd"))
            except Exception:
                logger.debug("No se pudo parsear fecha_nacimiento '%s'", fn, exc_info=True)

        self._txt_direccion.setText(data.get("direccion", ""))
        self._txt_localidad.setText(data.get("localidad", ""))
        tels = data.get("telefonos", "")
        if isinstance(tels, list):
            self._txt_telefonos.setText(", ".join(tels))
        else:
            self._txt_telefonos.setText(str(tels) if tels else "")
        self._txt_email.setText(data.get("email", ""))
        self._txt_obra_social.setText(data.get("obra_social", ""))
        self._txt_actividad.setText(data.get("actividad", ""))
        procedencia = data.get("procedencia_contacto", "") or ""
        idx = self._combo_procedencia.findText(procedencia)
        self._combo_procedencia.setCurrentIndex(idx if idx >= 0 else 0)
        self._txt_clave_mi_anses.setText(data.get("clave_mi_anses", "") or "")
        self._txt_clave_fiscal.setText(data.get("clave_fiscal", "") or "")
        self._txt_observaciones.setPlainText(data.get("observaciones", ""))

    def _apply_prefill(self):
        """Pre-cargar campos del formulario con datos de una consulta CRM."""
        p = self._prefill
        if p.get("nombre_completo"):
            self._txt_nombre.setText(p["nombre_completo"])
        if p.get("dni"):
            self._txt_dni.setText(p["dni"])
        if p.get("telefonos"):
            self._txt_telefonos.setText(p["telefonos"])
        if p.get("email"):
            self._txt_email.setText(p["email"])
        if p.get("direccion"):
            self._txt_direccion.setText(p["direccion"])
        if p.get("localidad"):
            self._txt_localidad.setText(p["localidad"])
        if p.get("observaciones"):
            self._txt_observaciones.setPlainText(p["observaciones"])

    def _set_readonly(self, readonly: bool):
        for w in [self._txt_numero_carpeta, self._txt_nombre, self._txt_dni, self._txt_cuil,
                   self._txt_direccion, self._txt_localidad, self._txt_telefonos, self._txt_email,
                   self._txt_obra_social, self._txt_actividad,
                   self._txt_clave_mi_anses, self._txt_clave_fiscal]:
            w.setReadOnly(readonly)
        self._txt_observaciones.setReadOnly(readonly)
        self._date_nacimiento.setEnabled(not readonly)
        self._combo_procedencia.setEnabled(not readonly)

    def _format_cuil(self):
        """Auto-formatear CUIL al salir del campo."""
        text = self._txt_cuil.text().strip()
        if text:
            formatted = format_cuil(text)
            self._txt_cuil.setText(formatted)

    def _save(self):
        numero_carpeta = self._txt_numero_carpeta.text().strip()
        if not numero_carpeta:
            QMessageBox.warning(self, "Atencion", "El numero de carpeta es obligatorio.")
            return
        if not numero_carpeta.isdigit():
            QMessageBox.warning(self, "Atencion", "El numero de carpeta debe contener solo numeros.")
            return

        nombre = self._txt_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Atencion", "El nombre es obligatorio.")
            return

        telefonos_text = self._txt_telefonos.text().strip()
        telefonos = [t.strip() for t in telefonos_text.split(",") if t.strip()] if telefonos_text else []

        data = {
            "numero_carpeta": numero_carpeta,
            "nombre_completo": nombre.upper(),
            "dni": self._txt_dni.text().strip(),
            "cuil": format_cuil(self._txt_cuil.text().strip()) if self._txt_cuil.text().strip() else "",
            "fecha_nacimiento": self._date_nacimiento.date().toString("yyyy-MM-dd"),
            "direccion": self._txt_direccion.text().strip(),
            "localidad": self._txt_localidad.text().strip(),
            "telefonos": telefonos,
            "email": self._txt_email.text().strip().lower(),
            "obra_social": self._txt_obra_social.text().strip(),
            "actividad": self._txt_actividad.text().strip(),
            "procedencia_contacto": self._combo_procedencia.currentText(),
            "clave_mi_anses": self._txt_clave_mi_anses.text().strip(),
            "clave_fiscal": self._txt_clave_fiscal.text().strip(),
            "observaciones": self._txt_observaciones.toPlainText().strip(),
        }

        try:
            if self._is_edit:
                ClienteController.update(self._id, data)
            else:
                self.created_client = ClienteController.create(data)
        except ValueError as e:
            QMessageBox.warning(self, "Error de validacion", str(e))
            return

        self.accept()

    def closeEvent(self, event):
        if self._locked and self._id:
            LockManager.release_lock("clientes", self._id)
        super().closeEvent(event)

    def reject(self):
        if self._locked and self._id:
            LockManager.release_lock("clientes", self._id)
        super().reject()

    def _on_numero_carpeta_dblclick(self, event):
        """Al hacer doble clic en N° de carpeta, abrir las carpetas del cliente."""
        if not self._is_edit or not self._id:
            return
        from controllers.expediente_controller import ExpedienteController
        expedientes = ExpedienteController.get_by_cliente(self._id)
        if not expedientes:
            QMessageBox.information(self, "Sin carpetas", "Este cliente no tiene carpetas asociadas.")
            return
        if len(expedientes) == 1:
            self._abrir_expediente(expedientes[0]["_id"])
        else:
            self._elegir_expediente(expedientes)

    def _abrir_expediente(self, expediente_id: str):
        """Abrir el formulario de edicion de una carpeta."""
        from views.expedientes.expediente_form import ExpedienteFormDialog
        dlg = ExpedienteFormDialog(expediente_id=expediente_id, parent=self)
        dlg.exec()

    def _elegir_expediente(self, expedientes: list[dict]):
        """Mostrar lista de carpetas para elegir cual abrir."""
        from PySide6.QtWidgets import QDialog, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
        dlg = QDialog(self)
        dlg.setWindowTitle("Seleccionar Carpeta")
        dlg.setMinimumSize(600, 300)
        lay = QVBoxLayout(dlg)

        lbl = QLabel(f"Este cliente tiene {len(expedientes)} carpetas. Seleccione una:")
        lbl.setFont(QFont("Lato", 11, QFont.Weight.Bold))
        lay.addWidget(lbl)

        table = QTableWidget()
        cols = [("id_expediente", "ID"), ("tipo_tramite", "Tipo"), ("estado", "Estado"),
                ("responsable", "Responsable"), ("fecha_apertura", "Apertura")]
        table.setColumnCount(len(cols))
        table.setHorizontalHeaderLabels([c[1] for c in cols])
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setRowCount(len(expedientes))

        for row, exp in enumerate(expedientes):
            for col, (field, _) in enumerate(cols):
                val = str(exp.get(field, ""))
                item = QTableWidgetItem(val)
                item.setData(Qt.ItemDataRole.UserRole, exp.get("_id", ""))
                table.setItem(row, col, item)

        def on_dblclick(index):
            item = table.item(index.row(), 0)
            if item:
                eid = item.data(Qt.ItemDataRole.UserRole)
                if eid:
                    dlg.close()
                    self._abrir_expediente(eid)

        table.doubleClicked.connect(on_dblclick)
        lay.addWidget(table)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setProperty("variant", "secondary")
        btn_cancel.clicked.connect(dlg.reject)
        btn_layout.addWidget(btn_cancel)
        btn_open = QPushButton("Abrir")
        btn_open.clicked.connect(lambda: (
            on_dblclick(table.currentIndex()) if table.currentIndex().isValid() else None
        ))
        btn_layout.addWidget(btn_open)
        lay.addLayout(btn_layout)

        dlg.exec()
