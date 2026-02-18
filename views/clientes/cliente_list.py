"""Vista listado de Clientes con ABM."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox
)
from PySide6.QtGui import QFont

from views.widgets.filterable_table import FilterableTable
from controllers.cliente_controller import ClienteController


COLUMNS = [
    ("id_cliente", "ID"),
    ("numero_carpeta", "N° Carpeta"),
    ("nombre_completo", "Nombre Completo"),
    ("dni", "DNI"),
    ("cuil", "CUIL"),
    ("telefonos", "Telefonos"),
    ("email", "Email"),
    ("localidad", "Localidad"),
    ("direccion", "Direccion"),
]


class ClienteListView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("Clientes")
        title.setFont(QFont("Lato", 17, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        btn_new = QPushButton("+ Nuevo Cliente")
        btn_new.clicked.connect(self._new_cliente)
        header.addWidget(btn_new)

        btn_edit = QPushButton("Editar")
        btn_edit.setProperty("variant", "secondary")
        btn_edit.clicked.connect(self._edit_cliente)
        header.addWidget(btn_edit)

        btn_delete = QPushButton("Eliminar")
        btn_delete.setProperty("variant", "danger")
        btn_delete.clicked.connect(self._delete_cliente)
        header.addWidget(btn_delete)

        layout.addLayout(header)

        # Table
        self._table = FilterableTable(COLUMNS)
        self._table.row_double_clicked.connect(self._open_detail)
        layout.addWidget(self._table)

    def refresh(self):
        data = ClienteController.get_all(order_by="nombre_completo ASC")
        self._table.set_data(data)

    def _new_cliente(self):
        from views.clientes.cliente_form import ClienteFormDialog
        dlg = ClienteFormDialog(parent=self)
        if dlg.exec():
            self.refresh()

    def _edit_cliente(self):
        _id = self._table.get_selected_id()
        if not _id:
            QMessageBox.information(self, "Atencion", "Seleccione un cliente para editar.")
            return
        from views.clientes.cliente_form import ClienteFormDialog
        dlg = ClienteFormDialog(cliente_id=_id, parent=self)
        if dlg.exec():
            self.refresh()

    def _delete_cliente(self):
        _id = self._table.get_selected_id()
        if not _id:
            QMessageBox.information(self, "Atencion", "Seleccione un cliente para eliminar.")
            return
        reply = QMessageBox.question(
            self, "Confirmar", "Eliminar este cliente? Esta accion no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            ClienteController.delete(_id)
            self.refresh()

    def _open_detail(self, _id: str):
        from views.clientes.cliente_form import ClienteFormDialog
        dlg = ClienteFormDialog(cliente_id=_id, parent=self)
        if dlg.exec():
            self.refresh()
