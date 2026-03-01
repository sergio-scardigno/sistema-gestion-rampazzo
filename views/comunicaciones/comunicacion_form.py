"""Formulario de Comunicacion."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QTextEdit, QDateEdit, QPushButton, QLabel, QComboBox, QMessageBox,
    QScrollArea, QFrame, QWidget
)
from PySide6.QtCore import QDate
from PySide6.QtGui import QFont

from controllers.comunicacion_controller import ComunicacionController
from controllers.expediente_controller import ExpedienteController
from core.auth import Session
from views.widgets.no_wheel_datetime import NoWheelDateEdit


class ComunicacionFormDialog(QDialog):
    def __init__(self, comunicacion_id: str = None, expediente_id: str = None, parent=None):
        super().__init__(parent)
        self._id = comunicacion_id
        self._is_edit = comunicacion_id is not None

        self.setWindowTitle("Editar Comunicacion" if self._is_edit else "Nueva Comunicacion")
        self.setMinimumWidth(550)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("Registrar Comunicacion")
        title.setFont(QFont("Lato", 15, QFont.Weight.Bold))
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        form_container = QWidget()
        form = QFormLayout(form_container)
        form.setContentsMargins(4, 4, 4, 4)
        form.setSpacing(8)

        self._cmb_expediente = QComboBox()
        self._cmb_expediente.setEditable(True)
        self._cmb_expediente.addItem("-- Sin carpeta --", "")
        if expediente_id:
            # Caso optimizado: solo cargar la carpeta pre-seleccionada
            exp_data = ExpedienteController.get_by_id(expediente_id)
            if exp_data:
                label = f'Carpeta #{exp_data.get("id_expediente","")} - {exp_data.get("tipo_tramite","")}'
                self._cmb_expediente.addItem(label, exp_data["_id"])
            idx = self._cmb_expediente.findData(expediente_id)
            if idx >= 0:
                self._cmb_expediente.setCurrentIndex(idx)
        else:
            exps = ExpedienteController.get_scoped(
                order_by="id_expediente DESC", limit=100)
            for e in exps:
                label = f'Carpeta #{e.get("id_expediente","")} - {e.get("tipo_tramite","")}'
                self._cmb_expediente.addItem(label, e["_id"])
        form.addRow("Carpeta:", self._cmb_expediente)

        self._date = NoWheelDateEdit()
        self._date.setCalendarPopup(True)
        self._date.setDate(QDate.currentDate())
        self._date.setDisplayFormat("dd/MM/yyyy")
        form.addRow("Fecha:", self._date)

        self._cmb_canal = QComboBox()
        for c in ComunicacionController.CANALES:
            self._cmb_canal.addItem(c)
        form.addRow("Canal:", self._cmb_canal)

        self._txt_emisor = QLineEdit()
        form.addRow("Emisor:", self._txt_emisor)

        self._txt_receptor = QLineEdit()
        form.addRow("Receptor:", self._txt_receptor)

        self._txt_motivo = QLineEdit()
        form.addRow("Motivo:", self._txt_motivo)

        self._txt_mensaje = QTextEdit()
        self._txt_mensaje.setMaximumHeight(80)
        form.addRow("Mensaje:", self._txt_mensaje)

        self._txt_resultado = QLineEdit()
        form.addRow("Resultado:", self._txt_resultado)

        scroll.setWidget(form_container)
        layout.addWidget(scroll)

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

        if self._is_edit:
            self._load_data()

    def _load_data(self):
        data = ComunicacionController.get_by_id(self._id)
        if not data:
            self.reject()
            return
        # Asegurar que la carpeta este en el combo aunque no se haya cargado
        id_exp = data.get("id_expediente", "")
        idx = self._cmb_expediente.findData(id_exp)
        if idx < 0 and id_exp:
            exp_data = ExpedienteController.get_by_id(id_exp)
            if exp_data:
                label = f'Carpeta #{exp_data.get("id_expediente","")} - {exp_data.get("tipo_tramite","")}'
                self._cmb_expediente.addItem(label, exp_data["_id"])
                idx = self._cmb_expediente.findData(id_exp)
        if idx >= 0:
            self._cmb_expediente.setCurrentIndex(idx)
        f = data.get("fecha", "")
        if f and len(f) >= 10:
            self._date.setDate(QDate.fromString(f[:10], "yyyy-MM-dd"))
        self._cmb_canal.setCurrentText(data.get("canal", ""))
        self._txt_emisor.setText(data.get("emisor", ""))
        self._txt_receptor.setText(data.get("receptor", ""))
        self._txt_motivo.setText(data.get("motivo", ""))
        self._txt_mensaje.setPlainText(data.get("mensaje", ""))
        self._txt_resultado.setText(data.get("resultado", ""))

    def _save(self):
        session = Session.get()
        data = {
            "id_expediente": self._cmb_expediente.currentData() or "",
            "fecha": self._date.date().toString("yyyy-MM-dd"),
            "canal": self._cmb_canal.currentText(),
            "emisor": self._txt_emisor.text().strip(),
            "receptor": self._txt_receptor.text().strip(),
            "responsable_username": session.username if session.logged_in else "",
            "motivo": self._txt_motivo.text().strip(),
            "mensaje": self._txt_mensaje.toPlainText().strip(),
            "resultado": self._txt_resultado.text().strip(),
        }
        if self._is_edit:
            ComunicacionController.update(self._id, data)
        else:
            ComunicacionController.create(data)
        self.accept()
