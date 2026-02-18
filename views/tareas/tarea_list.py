"""Vista listado de Tareas / Seguimiento."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox, QComboBox
)
from PySide6.QtGui import QFont

from views.widgets.filterable_table import FilterableTable
from controllers.tarea_controller import TareaController

COLUMNS = [
    ("id_tarea", "ID"),
    ("descripcion", "Descripcion"),
    ("tipo_accion", "Tipo"),
    ("responsable", "Responsable"),
    ("fecha_inicio", "Inicio"),
    ("fecha_vencimiento", "Vencimiento"),
    ("estado", "Estado"),
]


class TareaListView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Tareas y Seguimiento")
        title.setFont(QFont("Lato", 17, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        self._cmb_estado = QComboBox()
        self._cmb_estado.addItem("Todos", "")
        for e in TareaController.ESTADOS:
            self._cmb_estado.addItem(e, e)
        self._cmb_estado.currentIndexChanged.connect(self.refresh)
        header.addWidget(self._cmb_estado)

        btn_new = QPushButton("+ Nueva Tarea")
        btn_new.clicked.connect(self._new_tarea)
        header.addWidget(btn_new)

        btn_edit = QPushButton("Editar")
        btn_edit.setProperty("variant", "secondary")
        btn_edit.clicked.connect(self._edit_tarea)
        header.addWidget(btn_edit)

        btn_delete = QPushButton("Eliminar")
        btn_delete.setProperty("variant", "danger")
        btn_delete.clicked.connect(self._delete_tarea)
        header.addWidget(btn_delete)

        layout.addLayout(header)

        self._table = FilterableTable(COLUMNS)
        self._table.row_double_clicked.connect(self._on_double_click)
        layout.addWidget(self._table)

    def refresh(self):
        estado = self._cmb_estado.currentData()
        if estado:
            data = TareaController.get_scoped(
                where="estado = ?", params=(estado,), order_by="fecha_vencimiento ASC"
            )
        else:
            data = TareaController.get_scoped(order_by="fecha_vencimiento ASC")
        self._table.set_data(data)

    def _new_tarea(self):
        from views.tareas.tarea_form import TareaFormDialog
        dlg = TareaFormDialog(parent=self)
        if dlg.exec():
            self.refresh()

    def _edit_tarea(self):
        _id = self._table.get_selected_id()
        if not _id:
            QMessageBox.information(self, "Atencion", "Seleccione una tarea.")
            return
        from views.tareas.tarea_form import TareaFormDialog
        dlg = TareaFormDialog(tarea_id=_id, parent=self)
        if dlg.exec():
            self.refresh()

    def _on_double_click(self, _id):
        from views.tareas.tarea_form import TareaFormDialog
        dlg = TareaFormDialog(tarea_id=_id, parent=self)
        if dlg.exec():
            self.refresh()

    def _delete_tarea(self):
        _id = self._table.get_selected_id()
        if not _id:
            QMessageBox.information(self, "Atencion", "Seleccione una tarea.")
            return
        reply = QMessageBox.question(
            self, "Confirmar", "Eliminar esta tarea?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            TareaController.delete(_id)
            self.refresh()
