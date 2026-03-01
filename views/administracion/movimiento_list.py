"""Vista listado de Movimientos economicos."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox, QComboBox
)
from PySide6.QtGui import QFont

from views.widgets.filterable_table import FilterableTable
from controllers.movimiento_controller import MovimientoController
from core.auth import Session
from core.permissions import tiene_permiso

COLUMNS = [
    ("id_movimiento", "ID"),
    ("fecha", "Fecha"),
    ("tipo", "Tipo"),
    ("monto", "Monto"),
    ("forma_pago", "Forma Pago"),
    ("estado", "Estado"),
    ("saldo", "Saldo"),
]


class MovimientoListView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)
        session = Session.get()
        self._can_write = tiene_permiso(session.rol, "movimientos.create")

        header = QHBoxLayout()
        title = QLabel("Administracion - Movimientos")
        title.setFont(QFont("Lato", 17, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        self._cmb_tipo = QComboBox()
        self._cmb_tipo.addItem("Todos", "")
        for t in MovimientoController.TIPOS:
            self._cmb_tipo.addItem(t, t)
        self._cmb_tipo.currentIndexChanged.connect(self.refresh)
        header.addWidget(self._cmb_tipo)

        self._cmb_estado = QComboBox()
        self._cmb_estado.addItem("Todos los estados", "")
        for e in MovimientoController.ESTADOS:
            self._cmb_estado.addItem(e, e)
        self._cmb_estado.currentIndexChanged.connect(self.refresh)
        header.addWidget(self._cmb_estado)

        self._btn_new = QPushButton("+ Nuevo Movimiento")
        self._btn_new.clicked.connect(self._new_movimiento)
        self._btn_new.setVisible(self._can_write)
        header.addWidget(self._btn_new)

        self._btn_edit = QPushButton("Editar")
        self._btn_edit.setProperty("variant", "secondary")
        self._btn_edit.clicked.connect(self._edit_movimiento)
        self._btn_edit.setVisible(self._can_write)
        header.addWidget(self._btn_edit)

        layout.addLayout(header)

        self._table = FilterableTable(COLUMNS)
        self._table.row_double_clicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        # Totales
        self._lbl_totales = QLabel()
        self._lbl_totales.setStyleSheet("font-size: 14px; color: #1a1a1a; font-weight: 600; padding: 8px;")
        layout.addWidget(self._lbl_totales)

    def refresh(self):
        conditions = []
        params = []

        tipo = self._cmb_tipo.currentData()
        if tipo:
            conditions.append("tipo = ?")
            params.append(tipo)

        estado = self._cmb_estado.currentData()
        if estado:
            conditions.append("estado = ?")
            params.append(estado)

        where = " AND ".join(conditions)
        data = MovimientoController.get_scoped(
            where=where, params=tuple(params), order_by="fecha DESC"
        )
        self._table.set_data(data)

        # Calculate totals
        total_monto = sum(float(d.get("monto", 0) or 0) for d in data)
        total_saldo = sum(float(d.get("saldo", 0) or 0) for d in data)
        self._lbl_totales.setText(
            f"Total monto: ${total_monto:,.2f}  |  Total saldo pendiente: ${total_saldo:,.2f}  |  "
            f"Registros: {len(data)}"
        )

    def _new_movimiento(self):
        if not self._can_write:
            QMessageBox.information(self, "Solo lectura", "No tiene permisos para crear movimientos.")
            return
        from views.administracion.movimiento_form import MovimientoFormDialog
        dlg = MovimientoFormDialog(parent=self)
        if dlg.exec():
            self.refresh()

    def _edit_movimiento(self):
        _id = self._table.get_selected_id()
        if not _id:
            QMessageBox.information(self, "Atencion", "Seleccione un movimiento.")
            return
        from views.administracion.movimiento_form import MovimientoFormDialog
        dlg = MovimientoFormDialog(movimiento_id=_id, read_only=not self._can_write, parent=self)
        if dlg.exec():
            self.refresh()

    def _on_double_click(self, _id):
        from views.administracion.movimiento_form import MovimientoFormDialog
        dlg = MovimientoFormDialog(movimiento_id=_id, read_only=not self._can_write, parent=self)
        if dlg.exec():
            self.refresh()
