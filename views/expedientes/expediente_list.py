"""Vista listado de Carpetas."""
from datetime import date, datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox, QComboBox,
    QFrame, QGridLayout
)
from PySide6.QtGui import QFont

from views.widgets.filterable_table import FilterableTable
from controllers.expediente_controller import ExpedienteController

COLUMNS = [
    ("cli_nombre", "Cliente"),
    ("numero_carpeta_cliente", "N° Carpeta Cliente"),
    ("rama", "Rama"),
    ("modalidad", "Modalidad"),
    ("subtipo", "Subtipo"),
    ("tipo_tramite", "Tipo Tramite"),
    ("etapa_label", "Etapa"),
    ("estado", "Estado"),
    ("responsable", "Responsable"),
    ("prioridad", "Prioridad"),
    ("fecha_apertura", "Fecha Apertura"),
    ("dias_abierta", "Dias"),
    ("numero_expediente_anses", "Nro Tramite ANSES"),
]


class MetricStatusCard(QFrame):
    def __init__(self, titulo: str, etiqueta: str, color_etiqueta: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #0f213b;
                border: 1px solid #1f3658;
                border-radius: 10px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        self._lbl_titulo = QLabel(titulo)
        self._lbl_titulo.setStyleSheet("color: #dce8ff; font-size: 12px; font-weight: 600;")
        top.addWidget(self._lbl_titulo)
        top.addStretch()

        self._lbl_etiqueta = QLabel(etiqueta)
        self._lbl_etiqueta.setStyleSheet(
            f"background: {color_etiqueta}; color: #ffffff; border-radius: 8px; "
            "padding: 3px 8px; font-size: 10px; font-weight: 700;"
        )
        top.addWidget(self._lbl_etiqueta)
        layout.addLayout(top)

        self._lbl_valor = QLabel("0")
        self._lbl_valor.setFont(QFont("Lato", 18, QFont.Weight.Bold))
        self._lbl_valor.setStyleSheet("color: #ffffff;")
        layout.addWidget(self._lbl_valor)

    def set_valor(self, valor: int):
        self._lbl_valor.setText(str(valor))


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

        self._cmb_etapa = QComboBox()
        self._cmb_etapa.addItem("Todas las etapas", "")
        for etapa in ExpedienteController.ETAPAS:
            self._cmb_etapa.addItem(etapa["titulo"], etapa["codigo"])
        self._cmb_etapa.currentIndexChanged.connect(self.refresh)
        header.addWidget(self._cmb_etapa)

        # Filtro modalidad
        self._cmb_modalidad = QComboBox()
        self._cmb_modalidad.addItem("Todas las modalidades", "")
        for modalidad in ExpedienteController.MODALIDADES:
            self._cmb_modalidad.addItem(modalidad, modalidad)
        self._cmb_modalidad.currentIndexChanged.connect(self.refresh)
        header.addWidget(self._cmb_modalidad)

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

        # Tarjetas de métricas de carpetas
        metrics_layout = QGridLayout()
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setHorizontalSpacing(10)
        metrics_layout.setVerticalSpacing(10)
        self._metric_cards: dict[str, MetricStatusCard] = {}
        cards_cfg = [
            ("activos", "Carpetas activas", "Activos", "#0f6be5"),
            ("urgentes", "Con alerta de tarea", "Urgente", "#c93333"),
            ("semana", "Turnos de la semana", "Semana", "#2d8f4e"),
            ("pendientes", "Con tareas pendientes", "Pendiente", "#b8963c"),
        ]
        for idx, (key, titulo, etiqueta, color) in enumerate(cards_cfg):
            card = MetricStatusCard(titulo, etiqueta, color)
            self._metric_cards[key] = card
            metrics_layout.addWidget(card, 0, idx)
        layout.addLayout(metrics_layout)

        # Table (search_fields extra permiten buscar por nombre/DNI del cliente)
        self._table = FilterableTable(
            COLUMNS,
            search_fields=["cli_nombre", "cli_dni", "cli_cuil"],
            search_placeholder="Buscar por N\u00b0 carpeta, DNI/CUIL o nombre del cliente...",
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
        modalidad = self._cmb_modalidad.currentData()
        if modalidad:
            conditions.append("e.modalidad = ?")
            params += (modalidad,)
        etapa = self._cmb_etapa.currentData()
        if etapa:
            conditions.append("e.etapa_codigo = ?")
            params += (etapa,)
        where = " AND ".join(conditions)
        data = ExpedienteController.get_scoped_with_cliente(
            where=where, params=params, order_by="e.fecha_apertura DESC"
        )
        etapas_map = {x["codigo"]: x["titulo"] for x in ExpedienteController.ETAPAS}
        for row in data:
            row["etapa_label"] = etapas_map.get(row.get("etapa_codigo", ""), row.get("etapa_codigo", ""))
        self._calcular_dias(data)
        expediente_ids = [row.get("_id", "") for row in data if row.get("_id")]
        metricas_rel = ExpedienteController.get_metricas_relacionadas(expediente_ids)
        activos = sum(1 for row in data if row.get("estado", "") not in ExpedienteController.ESTADOS_CIERRE)
        self._metric_cards["activos"].set_valor(activos)
        self._metric_cards["urgentes"].set_valor(metricas_rel.get("urgentes", 0))
        self._metric_cards["semana"].set_valor(metricas_rel.get("semana", 0))
        self._metric_cards["pendientes"].set_valor(metricas_rel.get("pendientes", 0))
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
