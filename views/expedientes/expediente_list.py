"""Vista listado de Carpetas."""
from datetime import date, datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox, QComboBox
)
from PySide6.QtGui import QFont

from views.widgets.filterable_table import FilterableTable
from controllers.expediente_controller import ExpedienteController

COLUMNS = [
    ("id_expediente", "ID"),
    ("numero_carpeta_cliente", "N° Carpeta Cliente"),
    ("rama", "Rama"),
    ("subtipo", "Subtipo"),
    ("tipo_tramite", "Tipo Tramite"),
    ("estado", "Estado"),
    ("responsable", "Responsable"),
    ("prioridad", "Prioridad"),
    ("fecha_apertura", "Fecha Apertura"),
    ("dias_abierta", "Dias"),
    ("numero_expediente_anses", "Nro Tramite ANSES"),
]


class ExpedienteListView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("Carpetas")
        title.setFont(QFont("Lato", 17, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        # Filtro rama
        self._cmb_rama = QComboBox()
        self._cmb_rama.addItem("Todas las ramas", "")
        for r in ExpedienteController.RAMAS:
            self._cmb_rama.addItem(r, r)
        self._cmb_rama.currentIndexChanged.connect(self.refresh)
        header.addWidget(self._cmb_rama)

        # Filtro estado
        self._cmb_estado = QComboBox()
        self._cmb_estado.addItem("Todos los estados", "")
        for e in ExpedienteController.ESTADOS:
            self._cmb_estado.addItem(e, e)
        self._cmb_estado.currentIndexChanged.connect(self.refresh)
        header.addWidget(self._cmb_estado)

        btn_new = QPushButton("+ Nueva Carpeta")
        btn_new.clicked.connect(self._new_expediente)
        header.addWidget(btn_new)

        btn_edit = QPushButton("Editar")
        btn_edit.setProperty("variant", "secondary")
        btn_edit.clicked.connect(self._edit_expediente)
        header.addWidget(btn_edit)

        btn_delete = QPushButton("Eliminar")
        btn_delete.setProperty("variant", "danger")
        btn_delete.clicked.connect(self._delete_expediente)
        header.addWidget(btn_delete)

        layout.addLayout(header)

        # Table (search_fields extra permiten buscar por nombre/DNI del cliente)
        self._table = FilterableTable(
            COLUMNS,
            search_fields=["cli_nombre", "cli_dni"],
            search_placeholder="Buscar por N\u00b0 carpeta, DNI o nombre del cliente...",
        )
        self._table.row_double_clicked.connect(self._open_detail)
        layout.addWidget(self._table)

    def refresh(self):
        estado = self._cmb_estado.currentData()
        rama = self._cmb_rama.currentData()
        conditions: list[str] = []
        params: tuple = ()
        if estado:
            conditions.append("e.estado = ?")
            params += (estado,)
        if rama:
            conditions.append("e.rama = ?")
            params += (rama,)
        where = " AND ".join(conditions)
        data = ExpedienteController.get_scoped_with_cliente(
            where=where, params=params, order_by="e.fecha_apertura DESC"
        )
        self._calcular_dias(data)
        self._table.set_data(data)

    @staticmethod
    def _calcular_dias(data: list[dict]):
        """Calcula dias_abierta para cada carpeta."""
        hoy = date.today()
        for row in data:
            fa = row.get("fecha_apertura", "")
            fc = row.get("fecha_cierre", "")
            estado = row.get("estado", "")
            try:
                fecha_inicio = datetime.strptime(fa[:10], "%Y-%m-%d").date() if fa else None
            except (ValueError, TypeError):
                fecha_inicio = None
            if not fecha_inicio:
                row["dias_abierta"] = ""
                continue
            if estado in ("Cerrado", "Archivado") and fc:
                try:
                    fecha_fin = datetime.strptime(fc[:10], "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    fecha_fin = hoy
            else:
                fecha_fin = hoy
            dias = (fecha_fin - fecha_inicio).days
            row["dias_abierta"] = str(max(dias, 0))

    def _new_expediente(self):
        from views.expedientes.expediente_form import ExpedienteFormDialog
        dlg = ExpedienteFormDialog(parent=self)
        if dlg.exec():
            self.refresh()

    def _edit_expediente(self):
        _id = self._table.get_selected_id()
        if not _id:
            QMessageBox.information(self, "Atencion", "Seleccione una carpeta.")
            return
        from views.expedientes.expediente_form import ExpedienteFormDialog
        dlg = ExpedienteFormDialog(expediente_id=_id, parent=self)
        if dlg.exec():
            self.refresh()

    def _delete_expediente(self):
        _id = self._table.get_selected_id()
        if not _id:
            QMessageBox.information(self, "Atencion", "Seleccione una carpeta.")
            return
        reply = QMessageBox.question(
            self, "Confirmar", "Eliminar esta carpeta?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            ExpedienteController.delete(_id)
            self.refresh()

    def _open_detail(self, _id: str):
        from views.expedientes.expediente_form import ExpedienteFormDialog
        dlg = ExpedienteFormDialog(expediente_id=_id, parent=self)
        if dlg.exec():
            self.refresh()
