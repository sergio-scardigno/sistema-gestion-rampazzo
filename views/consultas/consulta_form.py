"""Formulario de alta/edicion de Consulta (CRM)."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QTextEdit, QDateEdit, QPushButton, QLabel, QComboBox, QMessageBox,
    QSpinBox, QCompleter, QScrollArea, QFrame, QWidget
)
from PySide6.QtCore import Qt, QDate, QStringListModel
from PySide6.QtGui import QFont

from controllers.consulta_controller import ConsultaController
from services import anses_oficinas_service
from core.auth import Session

# Mapeo de valores internos de estado a labels visibles en UI
_ESTADO_LABELS = {
    "Convertido en expediente": "Convertido en carpeta",
}


class ConsultaFormDialog(QDialog):
    def __init__(self, consulta_id: str = None, parent=None):
        super().__init__(parent)
        self._id = consulta_id
        self._is_edit = consulta_id is not None

        self.setWindowTitle("Editar Consulta" if self._is_edit else "Nueva Consulta")
        self.setMinimumWidth(550)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("Editar Consulta" if self._is_edit else "Nueva Consulta")
        title.setFont(QFont("Lato", 15, QFont.Weight.Bold))
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        form_container = QWidget()
        form = QFormLayout(form_container)
        form.setContentsMargins(4, 4, 4, 4)
        form.setSpacing(8)

        self._date_ingreso = QDateEdit()
        self._date_ingreso.setCalendarPopup(True)
        self._date_ingreso.setDate(QDate.currentDate())
        self._date_ingreso.setDisplayFormat("dd/MM/yyyy")
        form.addRow("Fecha ingreso:", self._date_ingreso)

        self._cmb_canal = QComboBox()
        for c in ConsultaController.CANALES:
            self._cmb_canal.addItem(c)
        form.addRow("Canal:", self._cmb_canal)

        self._txt_nombre = QLineEdit()
        self._txt_nombre.setPlaceholderText("Nombre del consultante")
        form.addRow("Nombre *:", self._txt_nombre)

        self._txt_dni = QLineEdit()
        form.addRow("DNI:", self._txt_dni)

        self._spn_edad = QSpinBox()
        self._spn_edad.setRange(0, 120)
        self._spn_edad.setValue(0)
        form.addRow("Edad:", self._spn_edad)

        self._txt_telefono = QLineEdit()
        form.addRow("Telefono:", self._txt_telefono)

        self._txt_email = QLineEdit()
        form.addRow("Email:", self._txt_email)

        self._txt_localidad = QLineEdit()
        self._txt_localidad.setPlaceholderText("Escriba para buscar localidad...")
        # Autocompletado de localidades argentinas
        localidades_labels = anses_oficinas_service.get_todas_localidades_labels()
        self._localidades_model = QStringListModel(localidades_labels)
        completer = QCompleter()
        completer.setModel(self._localidades_model)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setMaxVisibleItems(15)
        self._txt_localidad.setCompleter(completer)
        form.addRow("Localidad:", self._txt_localidad)

        self._txt_motivo = QTextEdit()
        self._txt_motivo.setMaximumHeight(70)
        form.addRow("Motivo *:", self._txt_motivo)

        self._cmb_estado = QComboBox()
        for e in ConsultaController.ESTADOS:
            label = _ESTADO_LABELS.get(e, e)
            self._cmb_estado.addItem(label, e)
        form.addRow("Estado:", self._cmb_estado)

        self._txt_operador = QLineEdit()
        self._txt_operador.setText(Session.get().nombre)
        form.addRow("Operador:", self._txt_operador)

        self._txt_obs = QTextEdit()
        self._txt_obs.setMaximumHeight(60)
        form.addRow("Observaciones:", self._txt_obs)

        scroll.setWidget(form_container)
        layout.addWidget(scroll)

        btn_layout = QHBoxLayout()

        # Boton convertir en cliente (solo en modo edicion)
        if self._is_edit:
            btn_convert = QPushButton("Convertir en Cliente")
            btn_convert.setStyleSheet(
                "background-color: #2d8f4e; color: #ffffff; font-weight: 600;"
                "border-radius: 6px; padding: 9px 18px;"
            )
            btn_convert.clicked.connect(self._convert_to_client)
            btn_layout.addWidget(btn_convert)

        btn_layout.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setProperty("variant", "secondary")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        btn_save = QPushButton("Guardar")
        btn_save.clicked.connect(self._save)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

        if self._is_edit:
            self._load_data()

    def _load_data(self):
        data = ConsultaController.get_by_id(self._id)
        if not data:
            self.reject()
            return
        fi = data.get("fecha_ingreso", "")
        if fi and len(fi) >= 10:
            self._date_ingreso.setDate(QDate.fromString(fi[:10], "yyyy-MM-dd"))
        self._cmb_canal.setCurrentText(data.get("canal", ""))
        self._txt_nombre.setText(data.get("nombre", ""))
        self._txt_dni.setText(data.get("dni", ""))
        self._spn_edad.setValue(int(data.get("edad", 0) or 0))
        self._txt_telefono.setText(data.get("telefono", ""))
        self._txt_email.setText(data.get("email", ""))
        self._txt_localidad.setText(data.get("localidad", ""))
        self._txt_motivo.setPlainText(data.get("motivo", ""))
        idx_estado = self._cmb_estado.findData(data.get("estado", "Nuevo"))
        if idx_estado >= 0:
            self._cmb_estado.setCurrentIndex(idx_estado)
        self._txt_operador.setText(data.get("operador", ""))
        self._txt_obs.setPlainText(data.get("observaciones", ""))

    def _save(self):
        nombre = self._txt_nombre.text().strip()
        motivo = self._txt_motivo.toPlainText().strip()
        if not nombre:
            QMessageBox.warning(self, "Atencion", "El nombre es obligatorio.")
            return
        if not motivo:
            QMessageBox.warning(self, "Atencion", "El motivo es obligatorio.")
            return

        data = {
            "fecha_ingreso": self._date_ingreso.date().toString("yyyy-MM-dd"),
            "canal": self._cmb_canal.currentText(),
            "nombre": nombre.upper(),
            "dni": self._txt_dni.text().strip(),
            "edad": self._spn_edad.value(),
            "telefono": self._txt_telefono.text().strip(),
            "email": self._txt_email.text().strip().lower(),
            "localidad": self._txt_localidad.text().strip(),
            "motivo": motivo,
            "estado": self._cmb_estado.currentData() or self._cmb_estado.currentText(),
            "operador": self._txt_operador.text().strip(),
            "observaciones": self._txt_obs.toPlainText().strip(),
        }

        if self._is_edit:
            ConsultaController.update(self._id, data)
        else:
            ConsultaController.create(data)
        self.accept()

    def _convert_to_client(self):
        """Abre el formulario de cliente con datos pre-cargados desde la consulta."""
        from controllers.cliente_controller import ClienteController

        # Verificar estado actual de la consulta
        consulta = ConsultaController.get_by_id(self._id)
        if not consulta:
            return

        if consulta.get("estado") == "Convertido en expediente":
            QMessageBox.information(
                self, "Info", "Esta consulta ya fue convertida en carpeta."
            )
            return

        # Si ya tiene cliente asociado, informar
        id_cliente_existente = consulta.get("id_cliente", "")
        if id_cliente_existente:
            cliente_existente = ClienteController.get_by_id(id_cliente_existente)
            if cliente_existente:
                QMessageBox.information(
                    self, "Info",
                    f"Esta consulta ya esta asociada al cliente:\n"
                    f"{cliente_existente.get('nombre_completo', '')} "
                    f"(Carpeta N° {cliente_existente.get('numero_carpeta', '-')})."
                )
                return

        # Construir datos pre-carga desde los campos del formulario
        dni_consulta = self._txt_dni.text().strip()
        obs_parts = []
        id_consulta = consulta.get("id_consulta", "")
        if id_consulta:
            obs_parts.append(f"Desde consulta #{id_consulta}")
        obs_text = self._txt_obs.toPlainText().strip()
        if obs_text:
            obs_parts.append(obs_text)

        prefill = {
            "nombre_completo": self._txt_nombre.text().strip().upper(),
            "dni": dni_consulta,
            "telefonos": self._txt_telefono.text().strip(),
            "email": self._txt_email.text().strip(),
            "localidad": self._txt_localidad.text().strip(),
            "observaciones": ". ".join(obs_parts) if obs_parts else "",
        }

        from views.clientes.cliente_form import ClienteFormDialog
        dlg = ClienteFormDialog(prefill_data=prefill, parent=self)
        dlg.setWindowTitle("Convertir Consulta en Cliente")
        if not dlg.exec():
            return

        cliente = dlg.created_client
        if not cliente:
            return

        # Crear carpeta asociada al nuevo cliente
        from controllers.expediente_controller import ExpedienteController
        ExpedienteController.create({
            "id_cliente": cliente["_id"],
            "tipo_tramite": "Otro",
            "responsable": self._txt_operador.text().strip(),
            "observaciones": self._txt_motivo.toPlainText().strip(),
        })

        # Vincular consulta al nuevo cliente y actualizar estado
        ConsultaController.update(self._id, {
            "estado": "Convertido en expediente",
            "id_cliente": cliente["_id"],
        })

        # Reflejar el nuevo estado en el combo del formulario
        idx_conv = self._cmb_estado.findData("Convertido en expediente")
        if idx_conv >= 0:
            self._cmb_estado.setCurrentIndex(idx_conv)

        QMessageBox.information(
            self, "Exito",
            f"Cliente y carpeta creados exitosamente "
            f"(Carpeta del cliente N° {cliente.get('numero_carpeta', '')}).\n"
            f"La consulta quedo asociada al nuevo cliente."
        )
