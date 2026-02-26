"""Selector de modelos y gestor ABM de modelos de escritos."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from controllers.escrito_controller import EscritoController, ModeloEscritoController
from views.escritos.escrito_editor import EscritoEditorDialog, ModeloEditorDialog
from views.widgets.filterable_table import FilterableTable

class ModelosManagerDialog(QDialog):
    def __init__(self, rama: str = "", parent=None):
        super().__init__(parent)
        self._rama = rama or ""
        self.setWindowTitle("Gestion de modelos de escritos")
        self.setMinimumSize(800, 500)

        layout = QVBoxLayout(self)
        title = QLabel("Modelos de escritos")
        layout.addWidget(title)

        self._table = FilterableTable([
            ("nombre", "Nombre"),
            ("rama", "Rama"),
            ("descripcion", "Descripcion"),
        ])
        self._table.row_double_clicked.connect(self._editar_modelo)
        layout.addWidget(self._table)

        buttons = QHBoxLayout()
        btn_new = QPushButton("+ Nuevo modelo")
        btn_new.clicked.connect(self._nuevo_modelo)
        buttons.addWidget(btn_new)

        btn_edit = QPushButton("Editar")
        btn_edit.setProperty("variant", "secondary")
        btn_edit.clicked.connect(self._editar_selected)
        buttons.addWidget(btn_edit)

        btn_disable = QPushButton("Desactivar")
        btn_disable.setProperty("variant", "secondary")
        btn_disable.clicked.connect(self._desactivar_selected)
        buttons.addWidget(btn_disable)

        buttons.addStretch()
        btn_close = QPushButton("Cerrar")
        btn_close.setProperty("variant", "secondary")
        btn_close.clicked.connect(self.accept)
        buttons.addWidget(btn_close)
        layout.addLayout(buttons)

        self.refresh()

    def refresh(self):
        data = ModeloEscritoController.get_activos(self._rama)
        self._table.set_data(data)

    def _nuevo_modelo(self):
        dlg = ModeloEditorDialog(parent=self)
        if dlg.exec():
            self.refresh()

    def _editar_selected(self):
        model_id = self._table.get_selected_id()
        if not model_id:
            QMessageBox.information(self, "Atencion", "Seleccione un modelo.")
            return
        self._editar_modelo(model_id)

    def _editar_modelo(self, model_id: str):
        dlg = ModeloEditorDialog(modelo_id=model_id, parent=self)
        if dlg.exec():
            self.refresh()

    def _desactivar_selected(self):
        model_id = self._table.get_selected_id()
        if not model_id:
            QMessageBox.information(self, "Atencion", "Seleccione un modelo.")
            return
        ModeloEscritoController.update(model_id, {"activo": 0})
        self.refresh()


class ModeloSelectorDialog(QDialog):
    def __init__(self, id_expediente: str, rama: str = "", parent=None):
        super().__init__(parent)
        self._id_expediente = id_expediente
        self._rama = rama or ""
        self.created_escrito_id = ""

        self.setWindowTitle("Seleccionar modelo de escrito")
        self.setMinimumSize(800, 500)

        ModeloEscritoController.seed_defaults()

        root = QVBoxLayout(self)
        label = QLabel(
            "Seleccione un modelo para crear un escrito autocompletado "
            f"(rama actual: {self._rama or 'Todas'})."
        )
        label.setWordWrap(True)
        root.addWidget(label)

        self._table = FilterableTable([
            ("nombre", "Modelo"),
            ("rama", "Rama"),
            ("descripcion", "Descripcion"),
        ])
        self._table.row_double_clicked.connect(self._usar_modelo)
        root.addWidget(self._table)

        actions = QHBoxLayout()
        btn_manage = QPushButton("Gestionar modelos")
        btn_manage.setProperty("variant", "secondary")
        btn_manage.clicked.connect(self._gestionar_modelos)
        actions.addWidget(btn_manage)

        actions.addStretch()

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setProperty("variant", "secondary")
        btn_cancel.clicked.connect(self.reject)
        actions.addWidget(btn_cancel)

        btn_use = QPushButton("Usar modelo")
        btn_use.clicked.connect(self._usar_selected)
        actions.addWidget(btn_use)
        root.addLayout(actions)

        self.refresh()

    def refresh(self):
        rows = ModeloEscritoController.get_activos(self._rama)
        self._table.set_data(rows)

    def _usar_selected(self):
        model_id = self._table.get_selected_id()
        if not model_id:
            QMessageBox.information(self, "Atencion", "Seleccione un modelo.")
            return
        self._usar_modelo(model_id)

    def _usar_modelo(self, model_id: str):
        escrito = EscritoController.crear_desde_modelo(self._id_expediente, model_id)
        if not escrito:
            QMessageBox.warning(self, "Error", "No se pudo crear el escrito.")
            return

        self.created_escrito_id = escrito.get("_id", "")
        editor = EscritoEditorDialog(self.created_escrito_id, parent=self)
        if editor.exec():
            self.accept()

    def _gestionar_modelos(self):
        dlg = ModelosManagerDialog(rama=self._rama, parent=self)
        if dlg.exec():
            self.refresh()

