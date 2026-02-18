"""Formulario de Movimiento economico."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QDateEdit, QPushButton, QLabel, QComboBox, QMessageBox, QDoubleSpinBox,
    QScrollArea, QFrame, QWidget
)
from PySide6.QtCore import QDate
from PySide6.QtGui import QFont

from controllers.movimiento_controller import MovimientoController
from controllers.cliente_controller import ClienteController
from controllers.expediente_controller import ExpedienteController
from core.auth import Session


class MovimientoFormDialog(QDialog):
    def __init__(self, movimiento_id: str = None, expediente_id: str = None,
                 cliente_id: str = None, parent=None):
        super().__init__(parent)
        self._id = movimiento_id
        self._is_edit = movimiento_id is not None
        self._preset_expediente = expediente_id
        self._preset_cliente = cliente_id

        self.setWindowTitle("Editar Movimiento" if self._is_edit else "Nuevo Movimiento")
        self.setMinimumWidth(550)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("Movimiento Economico")
        title.setFont(QFont("Lato", 15, QFont.Weight.Bold))
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        form_container = QWidget()
        form = QFormLayout(form_container)
        form.setContentsMargins(4, 4, 4, 4)
        form.setSpacing(8)

        self._cmb_cliente = QComboBox()
        self._cmb_cliente.setEditable(True)
        self._cmb_cliente.addItem("-- Sin cliente --", "")
        if self._preset_cliente:
            # Solo cargar el cliente pre-seleccionado
            cli = ClienteController.get_by_id(self._preset_cliente)
            if cli:
                self._cmb_cliente.addItem(cli.get("nombre_completo", ""), cli["_id"])
            idx_pc = self._cmb_cliente.findData(self._preset_cliente)
            if idx_pc >= 0:
                self._cmb_cliente.setCurrentIndex(idx_pc)
        else:
            clientes = ClienteController.get_all(
                order_by="nombre_completo ASC", limit=100)
            for c in clientes:
                self._cmb_cliente.addItem(c.get("nombre_completo", ""), c["_id"])
        form.addRow("Cliente:", self._cmb_cliente)

        self._cmb_expediente = QComboBox()
        self._cmb_expediente.setEditable(True)
        self._cmb_expediente.addItem("-- Sin carpeta --", "")
        if self._preset_expediente:
            # Solo cargar la carpeta pre-seleccionada
            exp_data = ExpedienteController.get_by_id(self._preset_expediente)
            if exp_data:
                label = f'Carpeta #{exp_data.get("id_expediente","")} - {exp_data.get("tipo_tramite","")}'
                self._cmb_expediente.addItem(label, exp_data["_id"])
            idx_pe = self._cmb_expediente.findData(self._preset_expediente)
            if idx_pe >= 0:
                self._cmb_expediente.setCurrentIndex(idx_pe)
        else:
            exps = ExpedienteController.get_scoped(
                order_by="id_expediente DESC", limit=100)
            for e in exps:
                label = f'Carpeta #{e.get("id_expediente","")} - {e.get("tipo_tramite","")}'
                self._cmb_expediente.addItem(label, e["_id"])
        form.addRow("Carpeta:", self._cmb_expediente)

        self._cmb_tipo = QComboBox()
        for t in MovimientoController.TIPOS:
            self._cmb_tipo.addItem(t)
        form.addRow("Tipo *:", self._cmb_tipo)

        self._spn_monto = QDoubleSpinBox()
        self._spn_monto.setRange(0, 999999999)
        self._spn_monto.setDecimals(2)
        self._spn_monto.setPrefix("$ ")
        form.addRow("Monto *:", self._spn_monto)

        self._date = QDateEdit()
        self._date.setCalendarPopup(True)
        self._date.setDate(QDate.currentDate())
        self._date.setDisplayFormat("dd/MM/yyyy")
        form.addRow("Fecha:", self._date)

        self._cmb_forma_pago = QComboBox()
        for f in MovimientoController.FORMAS_PAGO:
            self._cmb_forma_pago.addItem(f)
        form.addRow("Forma pago:", self._cmb_forma_pago)

        self._cmb_estado = QComboBox()
        for e in MovimientoController.ESTADOS:
            self._cmb_estado.addItem(e)
        form.addRow("Estado:", self._cmb_estado)

        self._txt_comprobante = QLineEdit()
        form.addRow("Comprobante:", self._txt_comprobante)

        self._spn_saldo = QDoubleSpinBox()
        self._spn_saldo.setRange(0, 999999999)
        self._spn_saldo.setDecimals(2)
        self._spn_saldo.setPrefix("$ ")
        form.addRow("Saldo pendiente:", self._spn_saldo)

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
        data = MovimientoController.get_by_id(self._id)
        if not data:
            self.reject()
            return
        # Cliente (asegurar que este en el combo aunque no se haya cargado)
        id_cli = data.get("id_cliente", "")
        idx_c = self._cmb_cliente.findData(id_cli)
        if idx_c < 0 and id_cli:
            cli = ClienteController.get_by_id(id_cli)
            if cli:
                self._cmb_cliente.addItem(cli.get("nombre_completo", ""), cli["_id"])
                idx_c = self._cmb_cliente.findData(id_cli)
        if idx_c >= 0:
            self._cmb_cliente.setCurrentIndex(idx_c)
        # Carpeta (asegurar que este en el combo aunque no se haya cargado)
        id_exp = data.get("id_expediente", "")
        idx_e = self._cmb_expediente.findData(id_exp)
        if idx_e < 0 and id_exp:
            exp_data = ExpedienteController.get_by_id(id_exp)
            if exp_data:
                label = f'Carpeta #{exp_data.get("id_expediente","")} - {exp_data.get("tipo_tramite","")}'
                self._cmb_expediente.addItem(label, exp_data["_id"])
                idx_e = self._cmb_expediente.findData(id_exp)
        if idx_e >= 0:
            self._cmb_expediente.setCurrentIndex(idx_e)
        self._cmb_tipo.setCurrentText(data.get("tipo", ""))
        self._spn_monto.setValue(float(data.get("monto", 0) or 0))
        f = data.get("fecha", "")
        if f and len(f) >= 10:
            self._date.setDate(QDate.fromString(f[:10], "yyyy-MM-dd"))
        self._cmb_forma_pago.setCurrentText(data.get("forma_pago", ""))
        self._cmb_estado.setCurrentText(data.get("estado", "Pendiente"))
        self._txt_comprobante.setText(data.get("comprobante", ""))
        self._spn_saldo.setValue(float(data.get("saldo", 0) or 0))

    def _save(self):
        monto = self._spn_monto.value()
        if monto <= 0:
            QMessageBox.warning(self, "Atencion", "El monto debe ser mayor a 0.")
            return

        session = Session.get()
        data = {
            "id_cliente": self._cmb_cliente.currentData() or "",
            "id_expediente": self._cmb_expediente.currentData() or "",
            "tipo": self._cmb_tipo.currentText(),
            "monto": monto,
            "fecha": self._date.date().toString("yyyy-MM-dd"),
            "forma_pago": self._cmb_forma_pago.currentText(),
            "estado": self._cmb_estado.currentText(),
            "comprobante": self._txt_comprobante.text().strip(),
            "saldo": self._spn_saldo.value(),
            "responsable_username": session.username if session.logged_in else "",
        }
        if self._is_edit:
            MovimientoController.update(self._id, data)
        else:
            MovimientoController.create(data)
        self.accept()
