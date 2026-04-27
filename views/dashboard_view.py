"""Dashboard principal con KPIs y tareas pendientes."""
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QPushButton, QMessageBox, QSplitter, QSizePolicy, QComboBox,
    QCalendarWidget, QDialog, QAbstractItemView,
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont, QColor, QBrush

logger = logging.getLogger(__name__)

from controllers.reporte_controller import ReporteController
from controllers.tarea_controller import TareaController
from controllers.turno_controller import TurnoController
from controllers.audit_controller import AuditController
from controllers.cliente_controller import ClienteController
from controllers.expediente_controller import ExpedienteController
from controllers.notificacion_controller import NotificacionController
from core.auth import Session
from core.permissions import tiene_permiso
from core.scheduler import (
    get_alertas_pendientes,
    get_recordatorios_turnos,
    get_alertas_sin_tarea,
    check_recordatorios_expedientes,
)


class KPICard(QFrame):
    def __init__(self, title: str, value: str, color: str = "#c9a84c", parent=None):
        super().__init__(parent)
        self.setFixedHeight(44)
        self.setMinimumWidth(120)
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f8f8f8);
                border: 1px solid #e2e2e2;
                border-radius: 6px;
                border-left: 3px solid {color};
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(8, 2, 8, 2)

        left = QVBoxLayout()
        left.setSpacing(0)
        left.setContentsMargins(0, 0, 0, 0)
        self._lbl_title = QLabel(title)
        self._lbl_title.setStyleSheet("color: #777; font-size: 9px; font-weight: 600; border: none;")
        left.addWidget(self._lbl_title)
        layout.addLayout(left, 1)

        self._lbl_value = QLabel(str(value))
        self._lbl_value.setFont(QFont("Lato", 15, QFont.Weight.Bold))
        self._lbl_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._lbl_value.setStyleSheet(f"color: {color}; border: none;")
        layout.addWidget(self._lbl_value)

    def update_value(self, value: str):
        self._lbl_value.setText(str(value))


class DashboardView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._kpi_cards: dict[str, KPICard] = {}
        self._session = Session.get()
        self._can_view_clientes = tiene_permiso(self._session.rol, "clientes.read")
        self._can_view_expedientes = tiene_permiso(self._session.rol, "expedientes.read")
        self._can_view_tareas = tiene_permiso(self._session.rol, "tareas.read")
        self._can_view_turnos = tiene_permiso(self._session.rol, "turnos.read")
        self._show_audit_kpi = tiene_permiso(self._session.rol, "auditoria.*")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(12, 8, 12, 12)
        self._layout.setSpacing(8)

        # ── Busqueda rapida por N° de carpeta, DNI o nombre ──
        search_frame = QFrame()
        search_frame.setObjectName("search_frame")
        search_frame.setStyleSheet("""
            #search_frame {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                border-left: 4px solid #c9a84c;
                padding: 6px 8px;
            }
        """)
        search_layout = QHBoxLayout(search_frame)
        search_layout.setSpacing(8)
        search_layout.setContentsMargins(4, 2, 4, 2)

        lbl_search = QLabel("Buscar cliente:")
        lbl_search.setFont(QFont("Lato", 11, QFont.Weight.Bold))
        lbl_search.setStyleSheet("color: #c9a84c; border: none;")
        search_layout.addWidget(lbl_search)

        self._txt_buscar_carpeta = QLineEdit()
        self._txt_buscar_carpeta.setPlaceholderText("N° carpeta, DNI o nombre...")
        self._txt_buscar_carpeta.setMaximumWidth(350)
        self._txt_buscar_carpeta.setStyleSheet("""
            QLineEdit {
                border: 1px solid #c9a84c;
                border-radius: 5px;
                padding: 6px 10px;
                font-size: 13px;
                font-weight: bold;
                background: #fafafa;
            }
            QLineEdit:focus {
                border: 2px solid #c9a84c;
                background: #ffffff;
            }
        """)
        self._txt_buscar_carpeta.returnPressed.connect(self._buscar_por_carpeta)
        search_layout.addWidget(self._txt_buscar_carpeta)

        btn_buscar = QPushButton("Buscar")
        btn_buscar.setStyleSheet("""
            QPushButton {
                background-color: #c9a84c;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 6px 16px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #b8963c;
            }
        """)
        btn_buscar.clicked.connect(self._buscar_por_carpeta)
        search_layout.addWidget(btn_buscar)

        btn_limpiar = QPushButton("Limpiar")
        btn_limpiar.setStyleSheet("""
            QPushButton {
                background-color: #6b6b6b;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
        """)
        btn_limpiar.clicked.connect(self._limpiar_busqueda)
        search_layout.addWidget(btn_limpiar)

        search_layout.addStretch()
        self._layout.addWidget(search_frame)

        # Panel de resultado de busqueda (oculto por defecto)
        self._resultado_frame = QFrame()
        self._resultado_frame.setObjectName("resultado_frame")
        self._resultado_frame.setStyleSheet("""
            #resultado_frame {
                background-color: #fffdf5;
                border: 2px solid #c9a84c;
                border-radius: 10px;
                padding: 16px;
            }
        """)
        self._resultado_layout = QVBoxLayout(self._resultado_frame)
        self._resultado_layout.setSpacing(10)
        self._resultado_frame.setVisible(False)
        self._layout.addWidget(self._resultado_frame)

        # Filtro rápido por etapa y asignaciones para mí
        stage_frame = QFrame()
        stage_frame.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
        """)
        stage_layout = QVBoxLayout(stage_frame)
        stage_layout.setContentsMargins(8, 6, 8, 6)
        stage_layout.setSpacing(4)
        stage_header = QHBoxLayout()
        stage_header.addWidget(QLabel("Asignado a mí por etapa"))
        stage_header.addStretch()
        self._cmb_etapa_dashboard = QComboBox()
        self._cmb_etapa_dashboard.addItem("Todas las etapas", "")
        for etapa in ExpedienteController.ETAPAS:
            self._cmb_etapa_dashboard.addItem(etapa["titulo"], etapa["codigo"])
        ExpedienteController.aplicar_colores_items_combo_etapas(self._cmb_etapa_dashboard)
        self._cmb_etapa_dashboard.currentIndexChanged.connect(self._refresh_asignado_por_etapa)
        stage_header.addWidget(QLabel("Etapa:"))
        stage_header.addWidget(self._cmb_etapa_dashboard)
        stage_layout.addLayout(stage_header)
        self._table_asignado_etapa = QTableWidget()
        self._table_asignado_etapa.setColumnCount(4)
        self._table_asignado_etapa.setHorizontalHeaderLabels(["Carpeta", "Cliente", "Etapa", "Que hacer"])
        self._table_asignado_etapa.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table_asignado_etapa.horizontalHeader().setMinimumHeight(26)
        self._table_asignado_etapa.verticalHeader().setVisible(False)
        self._table_asignado_etapa.verticalHeader().setDefaultSectionSize(34)
        self._table_asignado_etapa.setMinimumHeight(160)
        self._table_asignado_etapa.setMaximumHeight(250)
        self._table_asignado_etapa.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                color: #1a1a1a;
                gridline-color: #eeeeee;
            }
            QTableWidget::item {
                padding: 4px 4px;
                border-bottom: 1px solid #f0f0f0;
                color: #1a1a1a;
            }
            QHeaderView::section {
                background-color: #fafafa;
                color: #4a4a4a;
                font-weight: 600;
                border: none;
                border-bottom: 2px solid #c9a84c;
                padding: 4px 4px;
            }
        """)
        self._table_asignado_etapa.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table_asignado_etapa.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table_asignado_etapa.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table_asignado_etapa.cellClicked.connect(self._on_asignado_etapa_clicked)
        stage_layout.addWidget(self._table_asignado_etapa)
        if self._can_view_expedientes:
            self._layout.addWidget(stage_frame)

        # KPI Grid - todas las cards visibles fluyen sin huecos
        _COLS = 5
        kpi_grid = QGridLayout()
        kpi_grid.setHorizontalSpacing(4)
        kpi_grid.setVerticalSpacing(4)

        all_kpi_defs: list[tuple[str, str, str, str]] = []

        if self._can_view_expedientes:
            all_kpi_defs.append(("exp_activos", "Carpetas Activas", "0", "#c9a84c"))
            all_kpi_defs.append(("exp_cerrados", "Carpetas Cerradas", "0", "#2d8f4e"))
        if self._can_view_tareas:
            all_kpi_defs.append(("tareas_pend", "Tareas Pendientes", "0", "#b8963c"))
            all_kpi_defs.append(("tareas_venc", "Tareas Vencidas", "0", "#cc3333"))
        if self._can_view_clientes:
            all_kpi_defs.append(("total_clientes", "Total Clientes", "0", "#4a4a4a"))
        if self._can_view_expedientes:
            all_kpi_defs.append(("tiempo_prom", "Tiempo Prom. Resolucion", "-", "#4a90d9"))
        if self._can_view_turnos:
            all_kpi_defs.append(("turnos_prox", "Turnos Prox. 7 dias", "0", "#c9a84c"))
            all_kpi_defs.append(("turnos_hoy", "Turnos Hoy", "0", "#b8963c"))
            all_kpi_defs.append(("turnos_sin_doc", "Sin Documentacion", "0", "#cc3333"))
            all_kpi_defs.append(("turnos_pend_res", "Pend. Resultado", "0", "#a07c30"))
        if self._can_view_expedientes:
            all_kpi_defs.append(("plazos_crit", "Plazos criticos vencidos", "0", "#c62828"))
            all_kpi_defs.append(("plazos_7", "Plazos prox. 7 dias", "0", "#e65100"))
            all_kpi_defs.append(("plazos_hoy", "Plazos hoy", "0", "#f9a825"))
        if self._show_audit_kpi:
            all_kpi_defs.append(("acciones_hoy", "Acciones Hoy", "0", "#4a4a4a"))

        for idx, (key, title_text, default, color) in enumerate(all_kpi_defs):
            card = KPICard(title_text, default, color)
            self._kpi_cards[key] = card
            kpi_grid.addWidget(card, idx // _COLS, idx % _COLS)

        self._layout.addLayout(kpi_grid)

        # Plazos de expedientes (tabla + calendario)
        plazos_frame = QFrame()
        plazos_frame.setStyleSheet("""
            QFrame { background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; }
        """)
        plazos_outer = QVBoxLayout(plazos_frame)
        plazos_outer.setContentsMargins(8, 6, 8, 6)
        lbl_pl = QLabel("Plazos de carpetas (pendientes de aviso)")
        lbl_pl.setFont(QFont("Lato", 13, QFont.Weight.Bold))
        lbl_pl.setStyleSheet("color: #7e57c2; border: none;")
        plazos_outer.addWidget(lbl_pl)
        plazos_split = QSplitter(Qt.Orientation.Horizontal)
        plazos_split.setChildrenCollapsible(False)
        self._table_plazos = QTableWidget()
        self._table_plazos.setColumnCount(7)
        self._table_plazos.setHorizontalHeaderLabels([
            "Fecha", "Carpeta", "Cliente", "Etapa", "Titulo", "Crit.", "Vence"
        ])
        self._table_plazos.horizontalHeader().setStretchLastSection(True)
        self._table_plazos.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table_plazos.verticalHeader().setVisible(False)
        self._table_plazos.setMinimumHeight(160)
        self._calendar_plazos = QCalendarWidget()
        self._calendar_plazos.setMaximumWidth(320)
        self._calendar_plazos.setGridVisible(True)
        self._calendar_plazos.setSelectedDate(QDate.currentDate())
        self._calendar_plazos.clicked.connect(self._on_plazo_calendar_clicked)
        plazos_split.addWidget(self._table_plazos)
        plazos_split.addWidget(self._calendar_plazos)
        plazos_split.setStretchFactor(0, 3)
        plazos_split.setStretchFactor(1, 1)
        plazos_outer.addWidget(plazos_split)
        if self._can_view_expedientes:
            self._layout.addWidget(plazos_frame)
        self._plazos_cache: list[dict] = []

        # ── Layout de 2 columnas: Turnos (izq) + Alertas/Vencidas (der) ──
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        bottom_splitter.setHandleWidth(6)
        bottom_splitter.setChildrenCollapsible(False)

        # --- Columna izquierda: Turnos de Hoy ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 4, 0)
        left_layout.setSpacing(4)

        lbl_turnos_hoy = QLabel("Turnos de Hoy")
        lbl_turnos_hoy.setFont(QFont("Lato", 13, QFont.Weight.Bold))
        lbl_turnos_hoy.setStyleSheet("color: #c9a84c;")
        left_layout.addWidget(lbl_turnos_hoy)

        self._table_turnos_hoy = QTableWidget()
        self._table_turnos_hoy.setColumnCount(6)
        self._table_turnos_hoy.setHorizontalHeaderLabels([
            "Hora", "Cliente", "Tramite", "Oficina", "Responsable", "Doc."
        ])
        self._table_turnos_hoy.horizontalHeader().setStretchLastSection(True)
        self._table_turnos_hoy.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table_turnos_hoy.horizontalHeader().setMinimumHeight(24)
        self._table_turnos_hoy.verticalHeader().setVisible(False)
        self._table_turnos_hoy.verticalHeader().setDefaultSectionSize(28)
        self._table_turnos_hoy.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._table_turnos_hoy.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                color: #1a1a1a;
                gridline-color: #eeeeee;
            }
            QTableWidget::item {
                padding: 4px;
                border-bottom: 1px solid #f0f0f0;
                color: #1a1a1a;
            }
            QHeaderView::section {
                background-color: #fafafa;
                color: #4a4a4a;
                font-weight: 600;
                border: none;
                border-bottom: 2px solid #c9a84c;
                padding: 4px;
            }
        """)
        self._table_turnos_hoy.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table_turnos_hoy.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table_turnos_hoy.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table_turnos_hoy.cellClicked.connect(self._on_turnos_hoy_clicked)
        left_layout.addWidget(self._table_turnos_hoy)

        if self._can_view_turnos:
            bottom_splitter.addWidget(left_panel)

        # --- Columna derecha: Alertas + Tareas Vencidas ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(8)

        lbl_alertas = QLabel("Alertas y Recordatorios")
        lbl_alertas.setFont(QFont("Lato", 13, QFont.Weight.Bold))
        lbl_alertas.setStyleSheet("color: #cc3333;")
        right_layout.addWidget(lbl_alertas)

        self._alertas_scroll = QScrollArea()
        self._alertas_scroll.setWidgetResizable(True)
        self._alertas_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._alertas_scroll.setMinimumHeight(160)
        self._alertas_scroll.setMaximumHeight(240)
        alertas_widget = QWidget()
        self._alertas_container = QVBoxLayout(alertas_widget)
        self._alertas_container.setContentsMargins(0, 4, 0, 4)
        self._alertas_container.setSpacing(4)
        self._alertas_scroll.setWidget(alertas_widget)

        self._lbl_no_alertas = QLabel("Sin alertas pendientes")
        self._lbl_no_alertas.setStyleSheet("color: #6b6b6b; font-style: italic; padding: 6px;")
        self._alertas_container.addWidget(self._lbl_no_alertas)

        right_layout.addWidget(self._alertas_scroll)

        lbl_vencidas = QLabel("Tareas Vencidas / Proximas a Vencer")
        lbl_vencidas.setFont(QFont("Lato", 13, QFont.Weight.Bold))
        lbl_vencidas.setStyleSheet("color: #1a1a1a;")
        right_layout.addWidget(lbl_vencidas)

        self._table_vencidas = QTableWidget()
        self._table_vencidas.setColumnCount(5)
        self._table_vencidas.setHorizontalHeaderLabels([
            "Tarea", "Cliente", "Responsable", "Vencimiento", "Estado"
        ])
        self._table_vencidas.horizontalHeader().setStretchLastSection(True)
        self._table_vencidas.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table_vencidas.horizontalHeader().setMinimumHeight(26)
        self._table_vencidas.verticalHeader().setVisible(False)
        self._table_vencidas.verticalHeader().setDefaultSectionSize(34)
        self._table_vencidas.setMinimumHeight(160)
        self._table_vencidas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._table_vencidas.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                color: #1a1a1a;
                gridline-color: #eeeeee;
            }
            QTableWidget::item {
                padding: 4px 4px;
                border-bottom: 1px solid #f0f0f0;
                color: #1a1a1a;
            }
            QHeaderView::section {
                background-color: #fafafa;
                color: #4a4a4a;
                font-weight: 600;
                border: none;
                border-bottom: 2px solid #c9a84c;
                padding: 4px 4px;
            }
        """)
        self._table_vencidas.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table_vencidas.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table_vencidas.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table_vencidas.cellClicked.connect(self._on_vencidas_clicked)
        right_layout.addWidget(self._table_vencidas)

        if not self._can_view_tareas:
            lbl_vencidas.setVisible(False)
            self._table_vencidas.setVisible(False)

        if self._can_view_tareas or self._can_view_turnos or self._can_view_expedientes:
            bottom_splitter.addWidget(right_panel)

        # Proporciones iniciales: 60% turnos, 40% alertas/vencidas
        if bottom_splitter.count() > 0:
            if bottom_splitter.count() == 2:
                bottom_splitter.setStretchFactor(0, 6)
                bottom_splitter.setStretchFactor(1, 4)
            self._layout.addWidget(bottom_splitter, 1)

        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def refresh(self):
        try:
            check_recordatorios_expedientes()
        except Exception:
            logger.exception("Error al verificar recordatorios de expedientes")
        from datetime import datetime, timedelta
        today = datetime.now().strftime("%Y-%m-%d")  # Fecha LOCAL (no UTC)

        # KPIs operativos (con scope + permiso)
        if self._can_view_expedientes:
            exp_activos = len(ExpedienteController.get_scoped(
                where="e.estado NOT IN ('Cerrado','Archivado')"))
            exp_cerrados = len(ExpedienteController.get_scoped(
                where="e.estado IN ('Cerrado','Archivado')"))
            self._kpi_cards["exp_activos"].update_value(str(exp_activos))
            self._kpi_cards["exp_cerrados"].update_value(str(exp_cerrados))

            tiempo_data = ReporteController.tiempo_promedio_resolucion()
            prom = tiempo_data.get("promedio_dias", 0)
            total_cerr = tiempo_data.get("total_cerrados", 0)
            self._kpi_cards["tiempo_prom"].update_value(f"{prom:.0f} dias" if total_cerr > 0 else "-")

        if self._can_view_tareas:
            tareas_pend = len(TareaController.get_scoped(
                where="estado IN ('Pendiente','En curso','En espera')"))
            tareas_venc = len(TareaController.get_scoped(
                where="estado IN ('Pendiente','En curso') AND fecha_vencimiento < ?",
                params=(today,)))
            self._kpi_cards["tareas_pend"].update_value(str(tareas_pend))
            self._kpi_cards["tareas_venc"].update_value(str(tareas_venc))

        if self._can_view_clientes:
            total_clientes = ClienteController.count_all()
            self._kpi_cards["total_clientes"].update_value(str(total_clientes))

        turnos_hoy: list[dict] = []
        if self._can_view_turnos:
            limit_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            turnos_prox = TurnoController.get_scoped(
                where="fecha_turno >= ? AND fecha_turno <= ? AND estado IN ('Pendiente','Confirmado')",
                params=(today, limit_date))
            turnos_hoy = TurnoController.get_scoped(
                where="fecha_turno = ?", params=(today,), order_by="hora_turno ASC")
            turnos_sin_doc = TurnoController.get_scoped(
                where="documentacion_lista = 0 AND estado IN ('Pendiente','Confirmado') AND fecha_turno >= ?",
                params=(today,))
            turnos_pend_res = TurnoController.get_scoped(
                where="estado = 'Asistido' AND (resultado IS NULL OR resultado = '')")

            self._kpi_cards["turnos_prox"].update_value(str(len(turnos_prox)))
            self._kpi_cards["turnos_hoy"].update_value(str(len(turnos_hoy)))
            self._kpi_cards["turnos_sin_doc"].update_value(str(len(turnos_sin_doc)))
            self._kpi_cards["turnos_pend_res"].update_value(str(len(turnos_pend_res)))

            # Tabla turnos de hoy (con cache de clientes para evitar queries repetidas)
            clientes_cache: dict[str, dict | None] = {}
            self._table_turnos_hoy.setRowCount(len(turnos_hoy))
            for i, t in enumerate(turnos_hoy):
                it_hora = QTableWidgetItem(t.get("hora_turno", ""))
                it_hora.setData(Qt.ItemDataRole.UserRole, (t.get("_id") or "").strip())
                self._table_turnos_hoy.setItem(i, 0, it_hora)
                cid = t.get("id_cliente", "")
                if cid and cid not in clientes_cache:
                    clientes_cache[cid] = ClienteController.get_by_id(cid)
                cli = clientes_cache.get(cid)
                nombre = cli.get("nombre_completo", "") if cli else ""
                self._table_turnos_hoy.setItem(i, 1, QTableWidgetItem(nombre))
                self._table_turnos_hoy.setItem(i, 2, QTableWidgetItem(t.get("tipo_tramite", "")))
                self._table_turnos_hoy.setItem(i, 3, QTableWidgetItem(t.get("oficina_anses", "")))
                self._table_turnos_hoy.setItem(i, 4, QTableWidgetItem(t.get("responsable", "")))
                doc = "Si" if t.get("documentacion_lista") else "No"
                self._table_turnos_hoy.setItem(i, 5, QTableWidgetItem(doc))
        else:
            self._table_turnos_hoy.setRowCount(0)

        if self._can_view_expedientes:
            plz = ExpedienteController.count_plazos_por_estado_scoped()
            self._kpi_cards["plazos_crit"].update_value(str(plz.get("criticos_vencidos", 0)))
            self._kpi_cards["plazos_7"].update_value(str(plz.get("proximos_7", 0)))
            self._kpi_cards["plazos_hoy"].update_value(str(plz.get("hoy", 0)))

        # KPI Auditoria
        if self._show_audit_kpi:
            acciones_hoy = AuditController.get_acciones_hoy()
            self._kpi_cards["acciones_hoy"].update_value(str(acciones_hoy))

        # Alertas del scheduler
        if self._can_view_tareas or self._can_view_turnos or self._can_view_expedientes:
            self._refresh_alertas()
        else:
            self._table_vencidas.setRowCount(0)

        if self._can_view_expedientes:
            self._refresh_asignado_por_etapa()
            self._refresh_plazos_dashboard()
        else:
            self._table_asignado_etapa.setRowCount(0)
            self._table_plazos.setRowCount(0)

        # Tareas vencidas (con scope)
        if self._can_view_tareas:
            vencidas = TareaController.get_scoped(
                where="estado IN ('Pendiente','En curso') AND fecha_vencimiento < ?",
                params=(today,), order_by="fecha_vencimiento ASC")
            expediente_cache: dict[str, dict | None] = {}
            cliente_cache_vencidas: dict[str, dict | None] = {}
            self._table_vencidas.setRowCount(len(vencidas[:20]))
            for i, t in enumerate(vencidas[:20]):
                it0 = QTableWidgetItem(t.get("descripcion", ""))
                it0.setData(Qt.ItemDataRole.UserRole, (t.get("_id") or "").strip())
                it0.setToolTip(t.get("descripcion", ""))
                self._table_vencidas.setItem(i, 0, it0)
                expediente_oid = t.get("id_expediente", "") or ""
                nombre_cliente = ""
                if expediente_oid:
                    if expediente_oid not in expediente_cache:
                        expediente_cache[expediente_oid] = ExpedienteController.get_by_id(expediente_oid)
                    exp = expediente_cache.get(expediente_oid)
                    cliente_oid = exp.get("id_cliente", "") if exp else ""
                    if cliente_oid:
                        if cliente_oid not in cliente_cache_vencidas:
                            cliente_cache_vencidas[cliente_oid] = ClienteController.get_by_id(cliente_oid)
                        cli = cliente_cache_vencidas.get(cliente_oid)
                        nombre_cliente = cli.get("nombre_completo", "") if cli else ""
                self._table_vencidas.setItem(i, 1, QTableWidgetItem(nombre_cliente))
                self._table_vencidas.setItem(i, 2, QTableWidgetItem(t.get("responsable", "")))
                self._table_vencidas.setItem(i, 3, QTableWidgetItem(t.get("fecha_vencimiento", "")))
                self._table_vencidas.setItem(i, 4, QTableWidgetItem(t.get("estado", "")))
        else:
            self._table_vencidas.setRowCount(0)

    def _on_plazo_calendar_clicked(self, _qd: QDate):
        self._fill_plazos_table_filtered()

    def _refresh_plazos_dashboard(self):
        if not self._can_view_expedientes:
            self._plazos_cache = []
            self._table_plazos.setRowCount(0)
            return
        try:
            from datetime import datetime, timedelta
            today = datetime.now().date()
            desde = (today - timedelta(days=60)).strftime("%Y-%m-%d")
            hasta = (today + timedelta(days=120)).strftime("%Y-%m-%d")
            self._plazos_cache = ExpedienteController.list_recordatorios_agenda_scoped(
                desde, hasta, solo_pendientes_disparo=True, limit=200,
            )
            self._fill_plazos_table_filtered()
        except Exception:
            logger.exception("Error al cargar plazos en dashboard")
            self._plazos_cache = []
            self._table_plazos.setRowCount(0)

    def _fill_plazos_table_filtered(self):
        from datetime import datetime
        picked = self._calendar_plazos.selectedDate().toString("yyyy-MM-dd")
        today_s = datetime.now().strftime("%Y-%m-%d")
        etapas_map = {x["codigo"]: x["titulo"] for x in ExpedienteController.ETAPAS}
        rows = [
            r for r in self._plazos_cache
            if (r.get("fecha_disparo") or "")[:10] == picked
        ]
        self._table_plazos.setRowCount(len(rows))
        for i, r in enumerate(rows):
            fd = (r.get("fecha_disparo") or "")[:10]
            crit = bool(int(r.get("es_critico", 0) or 0))
            if fd < today_s:
                vence = "Vencido"
            elif fd == today_s:
                vence = "Hoy"
            else:
                vence = "Proximo"
            ec = (r.get("etapa_codigo") or "").strip()
            etapa = etapas_map.get(ec, ec or "-")
            vals = [
                fd,
                str(r.get("exp_id_expediente", "")),
                r.get("cli_nombre", "") or "",
                etapa,
                r.get("titulo", "") or "",
                "Si" if crit else "",
                vence,
            ]
            for j, text in enumerate(vals):
                it = QTableWidgetItem(text)
                if fd < today_s:
                    it.setBackground(QBrush(QColor("#ffebee")))
                elif fd == today_s:
                    it.setBackground(QBrush(QColor("#fff3e0")))
                elif crit:
                    it.setBackground(QBrush(QColor("#f3e5f5")))
                self._table_plazos.setItem(i, j, it)

    def _refresh_alertas(self):
        """Actualiza la seccion de alertas y recordatorios."""
        # Limpiar alertas previas
        while self._alertas_container.count():
            item = self._alertas_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        alertas = []
        try:
            alertas.extend(get_alertas_pendientes()[:5])
            alertas.extend(get_recordatorios_turnos()[:5])
            alertas.extend(get_alertas_sin_tarea()[:5])
        except Exception:
            logger.exception("Error al cargar alertas del scheduler en dashboard")

        # Notificaciones persistentes del usuario logueado
        try:
            session = Session.get()
            if session.logged_in:
                notifs = NotificacionController.get_active_for_user(session.username, limit=10)
                for n in notifs:
                    alertas.append({
                        "tipo": n.get("tipo", "tarea_asignada"),
                        "mensaje": n.get("mensaje", ""),
                        "id": n.get("id_referencia", n.get("_id", "")),
                    })
        except Exception:
            logger.exception("Error al cargar notificaciones en dashboard")

        alertas_visibles = [a for a in alertas if self._can_show_alerta(a)]
        if not alertas_visibles:
            lbl = QLabel("Sin alertas pendientes")
            lbl.setStyleSheet("color: #6b6b6b; font-style: italic; padding: 12px 8px;")
            self._alertas_container.addWidget(lbl)
            return

        for alerta in alertas_visibles[:20]:
            tipo = alerta.get("tipo", "")
            if tipo == "tarea_vencida":
                icon = "\u26A0"
                color = "#cc3333"
            elif tipo == "turno_proximo":
                icon = "\u23F0"
                color = "#c9a84c"
            elif tipo == "expediente_sin_tarea":
                icon = "\u2757"
                color = "#a07c30"
            elif tipo == "tarea_asignada":
                icon = "\U0001F4CB"
                color = "#2d6bcf"
            elif tipo == "tarea_proxima_vencer":
                icon = "\u23F3"
                color = "#a07c30"
            elif tipo == "turno_asignado":
                icon = "\u23F0"
                color = "#c9a84c"
            elif tipo == "expediente_etapa_encargado":
                icon = "\U0001F4C1"
                color = "#2d6bcf"
            elif tipo == "recordatorio_expediente":
                icon = "\U0001F514"
                color = "#7e57c2"
            else:
                icon = "\u2139"
                color = "#4a4a4a"

            btn = QPushButton(f"{icon}  {alerta.get('mensaje', '')}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    text-align: left;
                    color: {color};
                    background: #fafafa;
                    border: 1px solid #e0e0e0;
                    border-left: 3px solid {color};
                    border-radius: 4px;
                    padding: 6px 8px;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background: #f1f1f1;
                }}
            """)
            btn.clicked.connect(lambda _checked=False, a=alerta: self._open_alerta(a))
            self._alertas_container.addWidget(btn)

    def _refresh_asignado_por_etapa(self):
        if not self._can_view_expedientes:
            self._table_asignado_etapa.setRowCount(0)
            return
        session = Session.get()
        if not session.logged_in:
            self._table_asignado_etapa.setRowCount(0)
            return
        etapa = self._cmb_etapa_dashboard.currentData() if hasattr(self, "_cmb_etapa_dashboard") else ""
        rows = ExpedienteController.get_pendientes_etapa_para_usuario(
            username=session.username,
            etapa_codigo=etapa or "",
            limit=30,
        )
        etapas_map = {x["codigo"]: x for x in ExpedienteController.ETAPAS}
        self._table_asignado_etapa.setRowCount(len(rows))
        for i, row in enumerate(rows):
            etapa_meta = etapas_map.get(row.get("etapa_codigo", ""), {})
            it0 = QTableWidgetItem(str(row.get("id_expediente", "")))
            it0.setData(Qt.ItemDataRole.UserRole, (row.get("_id") or "").strip())
            self._table_asignado_etapa.setItem(i, 0, it0)
            self._table_asignado_etapa.setItem(i, 1, QTableWidgetItem(row.get("cli_nombre", "")))
            self._table_asignado_etapa.setItem(i, 2, QTableWidgetItem(etapa_meta.get("titulo", row.get("etapa_codigo", ""))))
            self._table_asignado_etapa.setItem(i, 3, QTableWidgetItem(etapa_meta.get("instruccion_corta", "")))

    def _can_show_alerta(self, alerta: dict) -> bool:
        tipo = alerta.get("tipo", "")
        if tipo.startswith("tarea_"):
            return self._can_view_tareas
        if tipo.startswith("turno_"):
            return self._can_view_turnos
        if tipo.startswith("expediente_") or tipo == "recordatorio_expediente":
            return self._can_view_expedientes
        return self._can_view_tareas or self._can_view_turnos or self._can_view_expedientes

    def _open_alerta(self, alerta: dict):
        tipo = alerta.get("tipo", "")
        ref_id = (alerta.get("id") or "").strip()
        if not ref_id:
            return
        if tipo.startswith("tarea_"):
            self._open_tarea(ref_id)
        elif tipo.startswith("turno_"):
            self._open_turno(ref_id)
        elif tipo.startswith("expediente_") or tipo == "recordatorio_expediente":
            self._open_expediente(ref_id)

    def _open_tarea(self, tarea_id: str):
        from views.tareas.tarea_form import TareaFormDialog
        dlg = TareaFormDialog(tarea_id=tarea_id, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _open_turno(self, turno_id: str):
        from views.turnos.turno_form import TurnoFormDialog
        dlg = TurnoFormDialog(turno_id=turno_id, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _open_expediente(self, expediente_id: str):
        from views.expedientes.expediente_form import ExpedienteFormDialog
        dlg = ExpedienteFormDialog(expediente_id=expediente_id, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_asignado_etapa_clicked(self, row: int, _col: int):
        """Abre la carpeta al hacer click en una fila."""
        it = self._table_asignado_etapa.item(row, 0)
        if not it:
            return
        eid = (it.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not eid:
            return
        from views.expedientes.expediente_form import ExpedienteFormDialog
        dlg = ExpedienteFormDialog(expediente_id=eid, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_vencidas_clicked(self, row: int, _col: int):
        """Abre la tarea al hacer click en una fila."""
        it = self._table_vencidas.item(row, 0)
        if not it:
            return
        tid = (it.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not tid:
            return
        self._open_tarea(tid)

    def _on_turnos_hoy_clicked(self, row: int, _col: int):
        """Abre el turno al hacer click en una fila."""
        it = self._table_turnos_hoy.item(row, 0)
        if not it:
            return
        turno_id = (it.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not turno_id:
            return
        self._open_turno(turno_id)

    # ------------------------------------------------------------------
    # Busqueda rapida por N° de carpeta, DNI o nombre
    # ------------------------------------------------------------------

    def _buscar_por_carpeta(self):
        """Buscar cliente por N° de carpeta, DNI o nombre y mostrar panel."""
        import re
        query = self._txt_buscar_carpeta.text().strip()
        if not query:
            return

        digits_only = re.sub(r'[^\d]', '', query)
        is_numeric = query.replace('.', '').replace('-', '').replace(' ', '').isdigit() and len(digits_only) > 0

        if is_numeric:
            self._buscar_numerico(query, digits_only)
        else:
            self._buscar_por_nombre(query)

    def _buscar_numerico(self, query: str, digits: str):
        """Busqueda cuando la entrada es numerica (N° carpeta o DNI)."""
        is_dni_length = len(digits) in (7, 8)

        if is_dni_length:
            resultados = ClienteController.search_by_dni(digits)
            if len(resultados) == 1:
                self._mostrar_resultado_cliente(resultados[0])
                return
            if len(resultados) > 1:
                self._seleccionar_cliente(resultados)
                return
            cliente = ClienteController.get_by_numero_carpeta(digits)
            if cliente:
                self._mostrar_resultado_cliente(cliente)
                return
            self._mostrar_resultado_vacio(query)
        else:
            cliente = ClienteController.get_by_numero_carpeta(digits)
            if cliente:
                self._mostrar_resultado_cliente(cliente)
                return
            resultados = ClienteController.search_by_dni(digits)
            if len(resultados) == 1:
                self._mostrar_resultado_cliente(resultados[0])
                return
            if len(resultados) > 1:
                self._seleccionar_cliente(resultados)
                return
            self._mostrar_resultado_vacio(query)

    def _buscar_por_nombre(self, query: str):
        """Busqueda por nombre (texto no numerico)."""
        resultados = ClienteController.search_clientes(query)
        if len(resultados) == 0:
            self._mostrar_resultado_vacio(query)
        elif len(resultados) == 1:
            self._mostrar_resultado_cliente(resultados[0])
        else:
            self._seleccionar_cliente(resultados)

    def _seleccionar_cliente(self, clientes: list[dict]):
        """Abrir dialogo para elegir un cliente entre varios resultados."""
        from views.widgets.cliente_picker_dialog import ClientePickerDialog
        dlg = ClientePickerDialog(clientes, parent=self)
        if dlg.exec():
            cliente = ClienteController.get_by_id(dlg.selected_id)
            if cliente:
                self._mostrar_resultado_cliente(cliente)

    def _limpiar_busqueda(self):
        """Limpiar campo de busqueda y ocultar resultado."""
        self._txt_buscar_carpeta.clear()
        self._resultado_frame.setVisible(False)

    def _mostrar_resultado_vacio(self, query: str):
        """Mostrar que no se encontro ningun cliente."""
        self._limpiar_resultado_layout()
        lbl = QLabel(f'No se encontro ningun cliente para "{query}"')
        lbl.setStyleSheet("color: #cc3333; font-size: 14px; font-weight: bold; border: none;")
        self._resultado_layout.addWidget(lbl)
        self._resultado_frame.setVisible(True)

    def _limpiar_resultado_layout(self):
        """Limpiar contenido del panel de resultado."""
        while self._resultado_layout.count():
            item = self._resultado_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

    def _mostrar_resultado_cliente(self, cliente: dict):
        """Mostrar datos del cliente y sus carpetas en el panel."""
        self._limpiar_resultado_layout()

        # Header del resultado
        header_layout = QHBoxLayout()
        nc = cliente.get("numero_carpeta", "")
        lbl_title = QLabel(f"Carpeta N° {nc}")
        lbl_title.setFont(QFont("Lato", 16, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #c9a84c; border: none;")
        header_layout.addWidget(lbl_title)
        header_layout.addStretch()

        btn_abrir_cli = QPushButton("Abrir Cliente")
        btn_abrir_cli.setStyleSheet("""
            QPushButton {
                background-color: #c9a84c; color: white; border: none;
                border-radius: 6px; padding: 6px 16px; font-weight: bold;
            }
            QPushButton:hover { background-color: #b8963c; }
        """)
        cliente_id = cliente["_id"]
        btn_abrir_cli.clicked.connect(lambda checked, cid=cliente_id: self._abrir_cliente(cid))
        header_layout.addWidget(btn_abrir_cli)
        self._resultado_layout.addLayout(header_layout)

        # Datos del cliente
        nombre = cliente.get("nombre_completo", "")
        dni = cliente.get("dni", "")
        cuil = cliente.get("cuil", "")
        tels = cliente.get("telefonos", "")
        if isinstance(tels, list):
            tels = ", ".join(tels)
        email = cliente.get("email", "")
        direccion = cliente.get("direccion", "")

        info_lines = []
        if nombre:
            info_lines.append(f"<b>Nombre:</b> {nombre}")
        if dni:
            info_lines.append(f"<b>DNI:</b> {dni}")
        if cuil:
            info_lines.append(f"<b>CUIL:</b> {cuil}")
        if tels:
            info_lines.append(f"<b>Telefonos:</b> {tels}")
        if email:
            info_lines.append(f"<b>Email:</b> {email}")
        if direccion:
            info_lines.append(f"<b>Direccion:</b> {direccion}")

        lbl_info = QLabel(" &nbsp;|&nbsp; ".join(info_lines))
        lbl_info.setStyleSheet("color: #333333; font-size: 12px; padding: 4px 0; border: none;")
        lbl_info.setTextFormat(Qt.TextFormat.RichText)
        lbl_info.setWordWrap(True)
        self._resultado_layout.addWidget(lbl_info)

        # Carpetas del cliente (carga limitada para rapidez)
        _DASHBOARD_EXP_LIMIT = 50
        total_exp = ExpedienteController.count_by_cliente(cliente_id)
        expedientes = ExpedienteController.get_by_cliente(cliente_id, limit=_DASHBOARD_EXP_LIMIT)

        if expedientes:
            if total_exp > _DASHBOARD_EXP_LIMIT:
                lbl_exp = QLabel(f"Carpetas (mostrando {len(expedientes)} de {total_exp}):")
            else:
                lbl_exp = QLabel(f"Carpetas ({total_exp}):")
            lbl_exp.setFont(QFont("Lato", 12, QFont.Weight.Bold))
            lbl_exp.setStyleSheet("color: #1a1a1a; margin-top: 8px; border: none;")
            self._resultado_layout.addWidget(lbl_exp)

            table = QTableWidget()
            table.setColumnCount(6)
            table.setHorizontalHeaderLabels([
                "Cliente", "Tipo Tramite", "Estado", "Responsable", "Nro ANSES", ""
            ])
            table.horizontalHeader().setStretchLastSection(True)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.horizontalHeader().setMinimumHeight(36)
            table.verticalHeader().setVisible(False)
            table.verticalHeader().setDefaultSectionSize(40)
            table.setRowCount(len(expedientes))
            table.setMaximumHeight(min(50 + len(expedientes) * 42, 300))
            table.setStyleSheet("""
                QTableWidget {
                    background-color: #ffffff;
                    border: 1px solid #e0e0e0;
                    border-radius: 6px;
                    color: #1a1a1a;
                    gridline-color: #eeeeee;
                }
                QTableWidget::item {
                    padding: 8px;
                    border-bottom: 1px solid #f0f0f0;
                    color: #1a1a1a;
                }
                QHeaderView::section {
                    background-color: #fafafa;
                    color: #4a4a4a;
                    font-weight: 600;
                    border: none;
                    border-bottom: 2px solid #c9a84c;
                    padding: 6px;
                }
            """)

            for i, exp in enumerate(expedientes):
                table.setItem(i, 0, QTableWidgetItem(cliente.get("nombre_completo", "")))
                table.setItem(i, 1, QTableWidgetItem(exp.get("tipo_tramite", "")))
                table.setItem(i, 2, QTableWidgetItem(exp.get("estado", "")))
                table.setItem(i, 3, QTableWidgetItem(exp.get("responsable", "")))
                table.setItem(i, 4, QTableWidgetItem(exp.get("numero_expediente_anses", "")))
                btn = QPushButton("Abrir")
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #4a4a4a; color: white; border: none;
                        border-radius: 4px; padding: 4px 12px; font-size: 11px;
                    }
                    QPushButton:hover { background-color: #333333; }
                """)
                exp_id = exp["_id"]
                btn.clicked.connect(lambda checked, eid=exp_id: self._abrir_expediente(eid))
                table.setCellWidget(i, 5, btn)

            self._resultado_layout.addWidget(table)

            # Boton "Ver todas" si hay mas carpetas de las mostradas
            if total_exp > _DASHBOARD_EXP_LIMIT:
                btn_ver_todas = QPushButton(f"Ver todas las carpetas ({total_exp})")
                btn_ver_todas.setStyleSheet("""
                    QPushButton {
                        background-color: #c9a84c; color: white; border: none;
                        border-radius: 6px; padding: 8px 20px; font-weight: bold;
                        font-size: 12px;
                    }
                    QPushButton:hover { background-color: #b8963c; }
                """)
                btn_ver_todas.clicked.connect(
                    lambda checked, cid=cliente_id: self._ver_todas_carpetas(cid)
                )
                self._resultado_layout.addWidget(btn_ver_todas)
        else:
            lbl_no_exp = QLabel("Este cliente no tiene carpetas.")
            lbl_no_exp.setStyleSheet("color: #6b6b6b; font-style: italic; border: none;")
            self._resultado_layout.addWidget(lbl_no_exp)

        self._resultado_frame.setVisible(True)

    def _abrir_cliente(self, cliente_id: str):
        """Abrir el formulario de edicion del cliente."""
        from views.clientes.cliente_form import ClienteFormDialog
        dlg = ClienteFormDialog(cliente_id=cliente_id, parent=self)
        dlg.exec()

    def _abrir_expediente(self, expediente_id: str):
        """Abrir el formulario de edicion de la carpeta."""
        from views.expedientes.expediente_form import ExpedienteFormDialog
        dlg = ExpedienteFormDialog(expediente_id=expediente_id, parent=self)
        dlg.exec()

    def _ver_todas_carpetas(self, cliente_id: str):
        """Cargar todas las carpetas del cliente sin limite en el panel."""
        expedientes = ExpedienteController.get_by_cliente(cliente_id)
        cliente = ClienteController.get_by_id(cliente_id)
        if cliente:
            self._mostrar_resultado_cliente_full(cliente, expedientes)

    def _mostrar_resultado_cliente_full(self, cliente: dict, expedientes: list[dict]):
        """Mostrar todas las carpetas del cliente (sin limite)."""
        self._limpiar_resultado_layout()

        header_layout = QHBoxLayout()
        nc = cliente.get("numero_carpeta", "")
        lbl_title = QLabel(f"Carpeta N\u00b0 {nc} \u2014 Todas las carpetas ({len(expedientes)})")
        lbl_title.setFont(QFont("Lato", 16, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #c9a84c; border: none;")
        header_layout.addWidget(lbl_title)
        header_layout.addStretch()
        self._resultado_layout.addLayout(header_layout)

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            "Cliente", "Tipo Tramite", "Estado", "Responsable", "Nro ANSES", ""
        ])
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setMinimumHeight(36)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(40)
        table.setRowCount(len(expedientes))
        table.setMaximumHeight(min(50 + len(expedientes) * 42, 500))
        table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff; border: 1px solid #e0e0e0;
                border-radius: 6px; color: #1a1a1a; gridline-color: #eeeeee;
            }
            QTableWidget::item { padding: 8px; border-bottom: 1px solid #f0f0f0; color: #1a1a1a; }
            QHeaderView::section {
                background-color: #fafafa; color: #4a4a4a; font-weight: 600;
                border: none; border-bottom: 2px solid #c9a84c; padding: 6px;
            }
        """)

        for i, exp in enumerate(expedientes):
            table.setItem(i, 0, QTableWidgetItem(cliente.get("nombre_completo", "")))
            table.setItem(i, 1, QTableWidgetItem(exp.get("tipo_tramite", "")))
            table.setItem(i, 2, QTableWidgetItem(exp.get("estado", "")))
            table.setItem(i, 3, QTableWidgetItem(exp.get("responsable", "")))
            table.setItem(i, 4, QTableWidgetItem(exp.get("numero_expediente_anses", "")))
            btn = QPushButton("Abrir")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #4a4a4a; color: white; border: none;
                    border-radius: 4px; padding: 4px 12px; font-size: 11px;
                }
                QPushButton:hover { background-color: #333333; }
            """)
            exp_id = exp["_id"]
            btn.clicked.connect(lambda checked, eid=exp_id: self._abrir_expediente(eid))
            table.setCellWidget(i, 5, btn)

        self._resultado_layout.addWidget(table)
        self._resultado_frame.setVisible(True)
