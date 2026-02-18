"""Vista listado de Comunicaciones."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox
)
from PySide6.QtGui import QFont

from views.widgets.filterable_table import FilterableTable
from controllers.comunicacion_controller import ComunicacionController

COLUMNS = [
    ("id_comunicacion", "ID"),
    ("fecha", "Fecha"),
    ("canal", "Canal"),
    ("emisor", "Emisor"),
    ("receptor", "Receptor"),
    ("motivo", "Motivo"),
    ("resultado", "Resultado"),
]


class ComunicacionListView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Comunicaciones")
        title.setFont(QFont("Lato", 17, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        btn_new = QPushButton("+ Nueva Comunicacion")
        btn_new.clicked.connect(self._new_comunicacion)
        header.addWidget(btn_new)

        btn_edit = QPushButton("Editar")
        btn_edit.setProperty("variant", "secondary")
        btn_edit.clicked.connect(self._edit_comunicacion)
        header.addWidget(btn_edit)

        layout.addLayout(header)

        self._table = FilterableTable(COLUMNS)
        self._table.row_double_clicked.connect(self._on_double_click)
        layout.addWidget(self._table)

    def refresh(self):
        data = ComunicacionController.get_scoped(order_by="fecha DESC")
        self._table.set_data(data)

    def _new_comunicacion(self):
        from views.comunicaciones.comunicacion_form import ComunicacionFormDialog
        dlg = ComunicacionFormDialog(parent=self)
        if dlg.exec():
            self.refresh()

    def _edit_comunicacion(self):
        _id = self._table.get_selected_id()
        if not _id:
            QMessageBox.information(self, "Atencion", "Seleccione una comunicacion.")
            return
        from views.comunicaciones.comunicacion_form import ComunicacionFormDialog
        dlg = ComunicacionFormDialog(comunicacion_id=_id, parent=self)
        if dlg.exec():
            self.refresh()

    def _on_double_click(self, _id):
        from views.comunicaciones.comunicacion_form import ComunicacionFormDialog
        dlg = ComunicacionFormDialog(comunicacion_id=_id, parent=self)
        if dlg.exec():
            self.refresh()
