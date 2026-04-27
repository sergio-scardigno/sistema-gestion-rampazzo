"""Vista listado de Citas del estudio."""
import logging
from datetime import datetime, date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QMessageBox, QComboBox, QHeaderView,
)
from PySide6.QtGui import QFont, QColor, QBrush
from PySide6.QtCore import QDate, Qt

from views.widgets.filterable_table import FilterableTable
from views.widgets.no_wheel_datetime import NoWheelDateEdit
from controllers.cita_controller import CitaController
from core.auth import Session
from core.permissions import tiene_permiso

logger = logging.getLogger(__name__)

COLUMNS = [
    ("hora_cita", "Hora"),
    ("_nombre_cliente", "Cliente"),
    ("_numero_carpeta", "N\u00b0 Carpeta"),
    ("_tipo_tramite", "Tramite"),
    ("motivo", "Motivo"),
    ("estado", "Estado"),
    ("citado_por", "Citado por"),
]


class CitaListView(QWidget):

    BG_GREEN = "#d8efe3"
    BG_YELLOW = "#fef3cd"
    BG_RED = "#f5d3d8"
    FG_GREEN = "#1f4d3a"
    FG_YELLOW = "#856404"
    FG_RED = "#4a1a22"

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        # -- Header --
        header = QHBoxLayout()
        title = QLabel("Citas")
        title.setFont(QFont("Lato", 17, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        # Selector de fecha
        lbl_fecha = QLabel("Fecha:")
        lbl_fecha.setStyleSheet("font-size: 13px;")
        header.addWidget(lbl_fecha)

        self._date_selector = NoWheelDateEdit()
        self._date_selector.setCalendarPopup(True)
        self._date_selector.setDate(QDate.currentDate())
        self._date_selector.setDisplayFormat("dd/MM/yyyy")
        self._date_selector.dateChanged.connect(self._on_date_changed)
        header.addWidget(self._date_selector)

        btn_hoy = QPushButton("Hoy")
        btn_hoy.setProperty("variant", "secondary")
        btn_hoy.setFixedWidth(60)
        btn_hoy.clicked.connect(self._go_today)
        header.addWidget(btn_hoy)

        btn_prev = QPushButton("\u25C0")
        btn_prev.setFixedWidth(32)
        btn_prev.setToolTip("Dia anterior")
        btn_prev.clicked.connect(self._prev_day)
        header.addWidget(btn_prev)

        btn_next = QPushButton("\u25B6")
        btn_next.setFixedWidth(32)
        btn_next.setToolTip("Dia siguiente")
        btn_next.clicked.connect(self._next_day)
        header.addWidget(btn_next)

        # Filtro estado
        self._cmb_estado = QComboBox()
        self._cmb_estado.addItem("Todos los estados", "")
        for e in CitaController.ESTADOS:
            self._cmb_estado.addItem(e, e)
        self._cmb_estado.currentIndexChanged.connect(lambda: self.refresh())
        header.addWidget(self._cmb_estado)

        # Boton nueva cita (se oculta si no tiene permiso)
        self._btn_new = QPushButton("+ Nueva Cita")
        self._btn_new.clicked.connect(self._new_cita)
        header.addWidget(self._btn_new)

        btn_edit = QPushButton("Editar")
        btn_edit.setProperty("variant", "secondary")
        btn_edit.clicked.connect(self._edit_cita)
        header.addWidget(btn_edit)

        layout.addLayout(header)

        # -- Tabla --
        self._table = FilterableTable(
            COLUMNS,
            search_fields=[
                "_dni_cliente",
                "_numero_carpeta",
                "_carpeta_sistema",
                "_tipo_tramite",
                "motivo",
                "citado_por",
            ],
            search_placeholder=(
                "Buscar por cliente, DNI, N\u00b0 carpeta, carpeta sistema, tr\u00e1mite o motivo..."
            ),
            row_style_provider=self._style_row,
        )
        self._table.row_double_clicked.connect(self._on_double_click)

        table_widget = self._table._table
        table_widget.verticalHeader().setDefaultSectionSize(36)
        table_widget.setStyleSheet("QTableWidget::item { padding: 8px 10px; }")
        table_widget.horizontalHeader().setStretchLastSection(False)
        table_widget.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents)  # Hora
        table_widget.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)           # Cliente
        table_widget.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents)  # Carpeta
        table_widget.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents)  # Tramite
        table_widget.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch)           # Motivo
        table_widget.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.ResizeToContents)  # Estado
        table_widget.horizontalHeader().setSectionResizeMode(
            6, QHeaderView.ResizeMode.ResizeToContents)  # Citado por

        layout.addWidget(self._table)

        # -- Info inferior --
        self._lbl_info = QLabel()
        self._lbl_info.setStyleSheet("font-size: 13px; color: #6b6b6b; padding: 4px;")
        layout.addWidget(self._lbl_info)

    def _check_permisos(self):
        session = Session.get()
        can_create = tiene_permiso(session.rol, "citas.create")
        self._btn_new.setVisible(can_create)

    # -- Navegacion de fecha --

    def _on_date_changed(self):
        self.refresh()

    def _go_today(self):
        self._date_selector.setDate(QDate.currentDate())

    def _prev_day(self):
        self._date_selector.setDate(self._date_selector.date().addDays(-1))

    def _next_day(self):
        self._date_selector.setDate(self._date_selector.date().addDays(1))

    # -- Refresh --

    def refresh(self):
        self._check_permisos()
        fecha = self._date_selector.date().toString("yyyy-MM-dd")

        conditions = ["fecha_cita = ?"]
        params: list[str] = [fecha]

        estado = self._cmb_estado.currentData()
        if estado:
            conditions.append("estado = ?")
            params.append(estado)

        where = " AND ".join(conditions)
        data = CitaController.get_scoped(
            where=where, params=tuple(params),
            order_by="hora_cita ASC",
        )

        from controllers.cliente_controller import ClienteController
        from controllers.expediente_controller import ExpedienteController

        clientes_cache: dict[str, dict] = {}
        expedientes_cache: dict[str, dict] = {}

        for d in data:
            cid = d.get("id_cliente", "")
            if cid and cid not in clientes_cache:
                cli = ClienteController.get_by_id(cid)
                clientes_cache[cid] = cli or {}
            cliente = clientes_cache.get(cid, {})
            d["_nombre_cliente"] = cliente.get("nombre_completo", "")
            d["_dni_cliente"] = cliente.get("dni", "")

            eid = d.get("id_expediente", "")
            if eid and eid not in expedientes_cache:
                exp = ExpedienteController.get_by_id(eid)
                expedientes_cache[eid] = exp or {}
            expediente = expedientes_cache.get(eid, {})
            num_carpeta = cliente.get("numero_carpeta", "")
            id_exp = expediente.get("id_expediente", "")
            d["_numero_carpeta"] = num_carpeta or (f"#{id_exp}" if id_exp else "")
            d["_tipo_tramite"] = expediente.get("tipo_tramite", "")
            d["_carpeta_sistema"] = (
                str(id_exp) if id_exp != "" and id_exp is not None else ""
            )

        self._table.set_data(data)

        # Info
        fecha_display = self._date_selector.date().toString("dd/MM/yyyy")
        self._lbl_info.setText(
            f"Citas para el {fecha_display}: {len(data)}"
        )

    # -- Estilo de filas --

    def _style_row(self, row_data: dict, field: str, item):
        if field != "estado":
            return
        estado = str(row_data.get("estado", "") or "").strip()
        if estado == "Asistio":
            item.setForeground(QBrush(QColor(self.FG_GREEN)))
            item.setBackground(QBrush(QColor(self.BG_GREEN)))
        elif estado in ("No asistio", "Cancelada"):
            item.setForeground(QBrush(QColor(self.FG_RED)))
            item.setBackground(QBrush(QColor(self.BG_RED)))
        elif estado == "Confirmada":
            item.setForeground(QBrush(QColor(self.FG_GREEN)))
            item.setBackground(QBrush(QColor(self.BG_GREEN)))
        elif estado == "Pendiente":
            item.setForeground(QBrush(QColor(self.FG_YELLOW)))
            item.setBackground(QBrush(QColor(self.BG_YELLOW)))

        f = item.font()
        f.setWeight(QFont.Weight.Bold)
        item.setFont(f)

    # -- CRUD --

    def _new_cita(self):
        fecha_sel = self._date_selector.date().toString("yyyy-MM-dd")
        from views.citas.cita_form import CitaFormDialog
        dlg = CitaFormDialog(fecha_default=fecha_sel, parent=self)
        if dlg.exec():
            self.refresh()

    def _edit_cita(self):
        _id = self._table.get_selected_id()
        if not _id:
            QMessageBox.information(self, "Atencion", "Seleccione una cita.")
            return
        from views.citas.cita_form import CitaFormDialog
        dlg = CitaFormDialog(cita_id=_id, parent=self)
        if dlg.exec():
            self.refresh()

    def _on_double_click(self, _id):
        from views.citas.cita_form import CitaFormDialog
        dlg = CitaFormDialog(cita_id=_id, parent=self)
        if dlg.exec():
            self.refresh()
