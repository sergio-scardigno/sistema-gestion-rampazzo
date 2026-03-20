"""Vista para Carpetas Iniciadas (Presencial / Virtual)."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget, QMessageBox, QFrame
)
from PySide6.QtGui import QFont

from controllers.expediente_controller import ExpedienteController
from views.widgets.filterable_table import FilterableTable


COLUMNS = [
    ("id_expediente", "ID"),
    ("numero_carpeta_cliente", "N° Carpeta Cliente"),
    ("subtipo", "Subtipo"),
    ("estado", "Estado"),
    ("responsable", "Responsable"),
    ("fecha_apertura", "Fecha Apertura"),
    ("numero_expediente_anses", "Nro Tramite ANSES"),
]


class _CountCard(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QFrame { background-color: #0f213b; border: 1px solid #1f3658; border-radius: 10px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: #dce8ff; font-size: 12px; font-weight: 600;")
        layout.addWidget(lbl_title)
        self._lbl_count = QLabel("0")
        self._lbl_count.setFont(QFont("Lato", 18, QFont.Weight.Bold))
        self._lbl_count.setStyleSheet("color: #ffffff;")
        layout.addWidget(self._lbl_count)

    def set_count(self, value: int):
        self._lbl_count.setText(str(value))


class CarpetasIniciadasView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Carpetas Iniciadas")
        title.setFont(QFont("Lato", 17, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        btn_new = QPushButton("+ Nueva Carpeta")
        btn_new.clicked.connect(self._new_expediente)
        header.addWidget(btn_new)

        btn_edit = QPushButton("Editar")
        btn_edit.setProperty("variant", "secondary")
        btn_edit.clicked.connect(self._edit_selected)
        header.addWidget(btn_edit)

        btn_delete = QPushButton("Eliminar")
        btn_delete.setProperty("variant", "danger")
        btn_delete.clicked.connect(self._delete_selected)
        header.addWidget(btn_delete)
        root.addLayout(header)

        cards = QHBoxLayout()
        cards.setSpacing(10)
        self._card_presencial = _CountCard("Iniciadas Presenciales")
        self._card_virtual = _CountCard("Iniciadas Virtuales")
        cards.addWidget(self._card_presencial)
        cards.addWidget(self._card_virtual)
        cards.addStretch()
        root.addLayout(cards)

        self._tabs = QTabWidget()

        self._table_presencial = FilterableTable(
            COLUMNS,
            search_fields=["cli_nombre", "cli_dni", "cli_cuil"],
            search_placeholder="Buscar por N° carpeta, DNI/CUIL o nombre...",
        )
        self._table_presencial.row_double_clicked.connect(self._open_detail)
        tab_presencial = QWidget()
        tab_pres_layout = QVBoxLayout(tab_presencial)
        tab_pres_layout.setContentsMargins(0, 0, 0, 0)
        tab_pres_layout.addWidget(self._table_presencial)
        self._tabs.addTab(tab_presencial, "Presenciales")

        self._table_virtual = FilterableTable(
            COLUMNS,
            search_fields=["cli_nombre", "cli_dni", "cli_cuil"],
            search_placeholder="Buscar por N° carpeta, DNI/CUIL o nombre...",
        )
        self._table_virtual.row_double_clicked.connect(self._open_detail)
        tab_virtual = QWidget()
        tab_virtual_layout = QVBoxLayout(tab_virtual)
        tab_virtual_layout.setContentsMargins(0, 0, 0, 0)
        tab_virtual_layout.addWidget(self._table_virtual)
        self._tabs.addTab(tab_virtual, "Virtuales")

        root.addWidget(self._tabs)

    def _where_for_modalidad(self, modalidad: str) -> tuple[str, tuple]:
        return "e.rama = ? AND e.modalidad = ?", ("Previsional", modalidad)

    def refresh(self):
        where_p, params_p = self._where_for_modalidad("Presencial")
        data_p = ExpedienteController.get_scoped_with_cliente(
            where=where_p, params=params_p, order_by="e.fecha_apertura DESC"
        )
        where_v, params_v = self._where_for_modalidad("Virtual")
        data_v = ExpedienteController.get_scoped_with_cliente(
            where=where_v, params=params_v, order_by="e.fecha_apertura DESC"
        )
        self._table_presencial.set_data(data_p)
        self._table_virtual.set_data(data_v)
        self._card_presencial.set_count(len(data_p))
        self._card_virtual.set_count(len(data_v))

    def _active_table(self) -> FilterableTable:
        if self._tabs.currentIndex() == 1:
            return self._table_virtual
        return self._table_presencial

    def _new_expediente(self):
        from views.expedientes.expediente_form import ExpedienteFormDialog
        dlg = ExpedienteFormDialog(parent=self)
        if dlg.exec():
            self.refresh()

    def _edit_selected(self):
        table = self._active_table()
        _id = table.get_selected_id()
        if not _id:
            QMessageBox.information(self, "Atencion", "Seleccione una carpeta.")
            return
        from views.expedientes.expediente_form import ExpedienteFormDialog
        dlg = ExpedienteFormDialog(expediente_id=_id, parent=self)
        if dlg.exec():
            self.refresh()

    def _delete_selected(self):
        table = self._active_table()
        _id = table.get_selected_id()
        if not _id:
            QMessageBox.information(self, "Atencion", "Seleccione una carpeta.")
            return
        reply = QMessageBox.question(
            self,
            "Confirmar",
            "Eliminar esta carpeta?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            ExpedienteController.delete(_id)
            self.refresh()

    def _open_detail(self, _id: str):
        from views.expedientes.expediente_form import ExpedienteFormDialog
        dlg = ExpedienteFormDialog(expediente_id=_id, parent=self)
        if dlg.exec():
            self.refresh()
