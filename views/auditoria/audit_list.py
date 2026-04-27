"""Vista principal de Auditoria con log de actividad y estadisticas por empleado."""
import io
import logging
from datetime import datetime, timedelta

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QTabWidget, QComboBox, QDateEdit, QPushButton, QGridLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont, QColor

logger = logging.getLogger(__name__)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from controllers.audit_controller import (
    AuditController, COLECCION_LABELS, ACCION_LABELS
)
from views.auditoria.audit_detail import AuditDetailDialog
from views.widgets.no_wheel_datetime import NoWheelDateEdit


class AuditListView(QWidget):
    """Modulo de auditoria y trazabilidad."""

    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        self._main_layout = QVBoxLayout(content)
        self._main_layout.setContentsMargins(16, 12, 16, 16)
        self._main_layout.setSpacing(12)

        # Titulo
        title = QLabel("Auditoria y Trazabilidad")
        title.setFont(QFont("Lato", 17, QFont.Weight.Bold))
        title.setStyleSheet("color: #1a1a1a;")
        self._main_layout.addWidget(title)

        # Tabs
        self._tabs = QTabWidget()
        self._build_tab_log()
        self._build_tab_stats()
        self._build_tab_task_tracking()
        self._main_layout.addWidget(self._tabs)

        scroll.setWidget(content)
        outer.addWidget(scroll)

    # ══════════════════════════════════════════════
    #  TAB 1: Log de Actividad
    # ══════════════════════════════════════════════

    def _build_tab_log(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # ── Filtros ──
        filter_frame = QFrame()
        filter_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setSpacing(10)

        # Usuario
        filter_layout.addWidget(QLabel("Usuario:"))
        self._cmb_usuario = QComboBox()
        self._cmb_usuario.addItem("Todos", "")
        self._cmb_usuario.setMinimumWidth(130)
        filter_layout.addWidget(self._cmb_usuario)

        # Modulo
        filter_layout.addWidget(QLabel("Modulo:"))
        self._cmb_modulo = QComboBox()
        self._cmb_modulo.addItem("Todos", "")
        for key, label in COLECCION_LABELS.items():
            self._cmb_modulo.addItem(label, key)
        self._cmb_modulo.setMinimumWidth(130)
        filter_layout.addWidget(self._cmb_modulo)

        # Accion
        filter_layout.addWidget(QLabel("Accion:"))
        self._cmb_accion = QComboBox()
        self._cmb_accion.addItem("Todas", "")
        for key, label in ACCION_LABELS.items():
            self._cmb_accion.addItem(label, key)
        self._cmb_accion.setMinimumWidth(100)
        filter_layout.addWidget(self._cmb_accion)

        # Fecha desde
        filter_layout.addWidget(QLabel("Desde:"))
        self._date_desde = NoWheelDateEdit()
        self._date_desde.setCalendarPopup(True)
        self._date_desde.setDate(QDate.currentDate().addDays(-30))
        self._date_desde.setDisplayFormat("dd/MM/yyyy")
        filter_layout.addWidget(self._date_desde)

        # Fecha hasta
        filter_layout.addWidget(QLabel("Hasta:"))
        self._date_hasta = NoWheelDateEdit()
        self._date_hasta.setCalendarPopup(True)
        self._date_hasta.setDate(QDate.currentDate())
        self._date_hasta.setDisplayFormat("dd/MM/yyyy")
        filter_layout.addWidget(self._date_hasta)

        # Botones
        btn_filtrar = QPushButton("Filtrar")
        btn_filtrar.clicked.connect(self._apply_filters)
        filter_layout.addWidget(btn_filtrar)

        btn_limpiar = QPushButton("Limpiar")
        btn_limpiar.setProperty("variant", "secondary")
        btn_limpiar.clicked.connect(self._clear_filters)
        filter_layout.addWidget(btn_limpiar)

        filter_layout.addStretch()
        layout.addWidget(filter_frame)

        # ── Tabla de log ──
        self._log_table = QTableWidget()
        self._log_table.setColumnCount(9)
        self._log_table.setHorizontalHeaderLabels([
            "Fecha/Hora", "Usuario", "Accion", "Modulo", "Carpeta", "Cliente",
            "Documento", "Cambio clave", "Resumen"
        ])
        self._log_table.horizontalHeader().setStretchLastSection(True)
        self._log_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._log_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._log_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._log_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._log_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._log_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self._log_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self._log_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        self._log_table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        self._log_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._log_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._log_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._log_table.setAlternatingRowColors(True)
        self._log_table.verticalHeader().setVisible(False)
        self._log_table.doubleClicked.connect(self._on_log_double_click)
        self._log_table.verticalScrollBar().valueChanged.connect(self._on_log_scroll)
        layout.addWidget(self._log_table)

        # ── Barra inferior ──
        bottom_bar = QHBoxLayout()
        self._lbl_log_count = QLabel("")
        self._lbl_log_count.setStyleSheet("color: #6b6b6b; font-size: 12px;")
        bottom_bar.addWidget(self._lbl_log_count)
        bottom_bar.addStretch()

        btn_export = QPushButton("Exportar a Excel")
        btn_export.setProperty("variant", "secondary")
        btn_export.clicked.connect(self._export_log_excel)
        bottom_bar.addWidget(btn_export)

        layout.addLayout(bottom_bar)

        self._tabs.addTab(tab, "Log de Actividad")

    # ══════════════════════════════════════════════
    #  TAB 2: Estadisticas por Empleado
    # ══════════════════════════════════════════════

    def _build_tab_stats(self):
        tab = QWidget()
        tab_scroll = QScrollArea()
        tab_scroll.setWidgetResizable(True)
        tab_scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)

        # ── KPIs globales ──
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(16)

        self._kpi_total = self._create_kpi_card("Total Acciones", "0", "#c9a84c")
        kpi_layout.addWidget(self._kpi_total["frame"])

        self._kpi_hoy = self._create_kpi_card("Acciones Hoy", "0", "#2d8f4e")
        kpi_layout.addWidget(self._kpi_hoy["frame"])

        self._kpi_usuarios = self._create_kpi_card("Usuarios Activos", "0", "#4a4a4a")
        kpi_layout.addWidget(self._kpi_usuarios["frame"])

        self._kpi_ultima = self._create_kpi_card("Ultima Actividad", "--", "#b8963c")
        kpi_layout.addWidget(self._kpi_ultima["frame"])

        layout.addLayout(kpi_layout)

        # ── Tabla resumen por usuario ──
        lbl_tabla = QLabel("Resumen por Empleado")
        lbl_tabla.setFont(QFont("Lato", 14, QFont.Weight.Bold))
        lbl_tabla.setStyleSheet("color: #c9a84c;")
        layout.addWidget(lbl_tabla)

        self._stats_table = QTableWidget()
        self._stats_table.setColumnCount(6)
        self._stats_table.setHorizontalHeaderLabels([
            "Usuario", "Total Acciones", "Creaciones", "Ediciones", "Eliminaciones", "Ultima Actividad"
        ])
        self._stats_table.horizontalHeader().setStretchLastSection(True)
        self._stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._stats_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._stats_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._stats_table.setAlternatingRowColors(True)
        self._stats_table.verticalHeader().setVisible(False)
        self._stats_table.setMinimumHeight(300)
        self._stats_table.setMaximumHeight(800)
        layout.addWidget(self._stats_table)

        # ── Graficos ──
        lbl_graficos = QLabel("Graficos de Actividad (ultimos 30 dias)")
        lbl_graficos.setFont(QFont("Lato", 14, QFont.Weight.Bold))
        lbl_graficos.setStyleSheet("color: #c9a84c;")
        layout.addWidget(lbl_graficos)

        self._chart_grid = QGridLayout()
        self._chart_grid.setSpacing(16)

        chart_positions = [
            ("por_usuario", "Actividad por Usuario", 0, 0),
            ("diaria", "Actividad Diaria", 0, 1),
            ("por_modulo", "Actividad por Modulo", 1, 0),
        ]

        self._chart_labels = {}
        for key, title_text, row, col in chart_positions:
            frame = QFrame()
            frame.setStyleSheet("""
                QFrame {
                    background: #ffffff;
                    border: 1px solid #e0e0e0;
                    border-radius: 8px;
                    padding: 8px;
                }
            """)
            fl = QVBoxLayout(frame)
            lbl_title = QLabel(title_text)
            lbl_title.setFont(QFont("Lato", 12, QFont.Weight.Bold))
            lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_title.setStyleSheet("border: none;")
            fl.addWidget(lbl_title)
            lbl_chart = QLabel()
            lbl_chart.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_chart.setMinimumSize(400, 280)
            lbl_chart.setStyleSheet("border: none;")
            fl.addWidget(lbl_chart)
            self._chart_labels[key] = lbl_chart
            self._chart_grid.addWidget(frame, row, col)

        layout.addLayout(self._chart_grid)
        layout.addStretch()

        tab_scroll.setWidget(content)
        tab_outer = QVBoxLayout(tab)
        tab_outer.setContentsMargins(0, 0, 0, 0)
        tab_outer.addWidget(tab_scroll)

        self._tabs.addTab(tab, "Estadisticas por Empleado")

    # ══════════════════════════════════════════════
    #  TAB 3: Seguimiento de Tareas
    # ══════════════════════════════════════════════

    def _build_tab_task_tracking(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        filter_frame = QFrame()
        filter_frame.setStyleSheet(
            """
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 12px;
            }
            """
        )
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setSpacing(10)

        filter_layout.addWidget(QLabel("Responsable:"))
        self._cmb_seg_responsable = QComboBox()
        self._cmb_seg_responsable.addItem("Todos", "")
        self._cmb_seg_responsable.setMinimumWidth(150)
        filter_layout.addWidget(self._cmb_seg_responsable)

        filter_layout.addWidget(QLabel("Estado:"))
        self._cmb_seg_estado = QComboBox()
        self._cmb_seg_estado.addItem("Todos", "")
        for estado in ("Pendiente", "En curso", "En espera", "Cumplida", "Completada", "Cancelada"):
            self._cmb_seg_estado.addItem(estado, estado)
        self._cmb_seg_estado.setMinimumWidth(130)
        filter_layout.addWidget(self._cmb_seg_estado)

        filter_layout.addWidget(QLabel("Asignada desde:"))
        self._date_seg_desde = NoWheelDateEdit()
        self._date_seg_desde.setCalendarPopup(True)
        self._date_seg_desde.setDate(QDate.currentDate().addDays(-30))
        self._date_seg_desde.setDisplayFormat("dd/MM/yyyy")
        filter_layout.addWidget(self._date_seg_desde)

        filter_layout.addWidget(QLabel("Hasta:"))
        self._date_seg_hasta = NoWheelDateEdit()
        self._date_seg_hasta.setCalendarPopup(True)
        self._date_seg_hasta.setDate(QDate.currentDate())
        self._date_seg_hasta.setDisplayFormat("dd/MM/yyyy")
        filter_layout.addWidget(self._date_seg_hasta)

        btn_filtrar = QPushButton("Filtrar")
        btn_filtrar.clicked.connect(self._apply_task_tracking_filters)
        filter_layout.addWidget(btn_filtrar)

        btn_limpiar = QPushButton("Limpiar")
        btn_limpiar.setProperty("variant", "secondary")
        btn_limpiar.clicked.connect(self._clear_task_tracking_filters)
        filter_layout.addWidget(btn_limpiar)

        filter_layout.addStretch()
        layout.addWidget(filter_frame)

        self._task_tracking_table = QTableWidget()
        self._task_tracking_table.setColumnCount(9)
        self._task_tracking_table.setHorizontalHeaderLabels(
            [
                "Fecha Asignacion",
                "Tarea",
                "Descripcion",
                "Asignada a",
                "Leida",
                "Fecha Lectura",
                "Estado",
                "Fecha Cumplimiento",
                "Dias sin leer",
            ]
        )
        self._task_tracking_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._task_tracking_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._task_tracking_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._task_tracking_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._task_tracking_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._task_tracking_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self._task_tracking_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self._task_tracking_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        self._task_tracking_table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
        self._task_tracking_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._task_tracking_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._task_tracking_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._task_tracking_table.setAlternatingRowColors(True)
        self._task_tracking_table.verticalHeader().setVisible(False)
        self._task_tracking_table.doubleClicked.connect(self._on_task_tracking_double_click)
        layout.addWidget(self._task_tracking_table)

        bottom_bar = QHBoxLayout()
        self._lbl_task_tracking_count = QLabel("")
        self._lbl_task_tracking_count.setStyleSheet("color: #6b6b6b; font-size: 12px;")
        bottom_bar.addWidget(self._lbl_task_tracking_count)
        bottom_bar.addStretch()
        layout.addLayout(bottom_bar)

        self._tabs.addTab(tab, "Seguimiento de Tareas")

    # ══════════════════════════════════════════════
    #  REFRESH y Carga de datos
    # ══════════════════════════════════════════════

    def refresh(self):
        """Carga datos en ambas pestanas."""
        self._load_filter_options()
        self._apply_filters()
        self._load_stats()
        self._load_task_tracking_filter_options()
        self._apply_task_tracking_filters()

    def _load_filter_options(self):
        """Carga opciones dinamicas para los filtros."""
        # Usuarios
        self._cmb_usuario.clear()
        self._cmb_usuario.addItem("Todos", "")
        for u in AuditController.get_usuarios_activos():
            self._cmb_usuario.addItem(u, u)

    def _apply_filters(self):
        """Aplica los filtros seleccionados y recarga la tabla de log."""
        if self._date_desde.date() > self._date_hasta.date():
            QMessageBox.warning(
                self,
                "Filtro de fechas",
                "La fecha 'Desde' no puede ser mayor que la fecha 'Hasta'.",
            )
            return
        self._load_log_page(reset=True)

    def _current_log_filters(self) -> dict:
        return {
            "usuario": self._cmb_usuario.currentData() or "",
            "coleccion": self._cmb_modulo.currentData() or "",
            "accion": self._cmb_accion.currentData() or "",
            "fecha_desde": self._date_desde.date().toString("yyyy-MM-dd"),
            "fecha_hasta": self._date_hasta.date().toString("yyyy-MM-dd"),
        }

    def _load_log_page(self, reset: bool = False):
        if reset or not hasattr(self, "_log_page_size"):
            self._log_page_size = 50
            self._log_offset = 0
            self._log_has_more = True
            self._loading_more_logs = False
            self._log_filters = self._current_log_filters()
            self._log_data = []
            self._log_table.setRowCount(0)
        if getattr(self, "_loading_more_logs", False) or not getattr(self, "_log_has_more", True):
            return
        self._loading_more_logs = True

        data = AuditController.get_all(
            usuario=self._log_filters["usuario"],
            coleccion=self._log_filters["coleccion"],
            accion=self._log_filters["accion"],
            fecha_desde=self._log_filters["fecha_desde"],
            fecha_hasta=self._log_filters["fecha_hasta"],
            limit=self._log_page_size,
            offset=self._log_offset,
            resumen_detallado=False,
        )
        append_mode = self._log_offset > 0
        self._populate_log_table(data, append=append_mode)
        self._log_offset += len(data)
        self._log_has_more = len(data) == self._log_page_size
        suffix = " (carga completa)" if not self._log_has_more else " (carga progresiva)"
        self._lbl_log_count.setText(f"{len(self._log_data)} registros cargados{suffix}")
        self._loading_more_logs = False

    def _on_log_scroll(self, value: int):
        if not hasattr(self, "_log_table"):
            return
        bar = self._log_table.verticalScrollBar()
        if value >= max(0, bar.maximum() - 20):
            self._load_log_page(reset=False)

    def _clear_filters(self):
        """Limpia todos los filtros."""
        self._cmb_usuario.setCurrentIndex(0)
        self._cmb_modulo.setCurrentIndex(0)
        self._cmb_accion.setCurrentIndex(0)
        self._date_desde.setDate(QDate(2000, 1, 1))
        self._date_hasta.setDate(QDate.currentDate())
        self._apply_filters()

    def _load_task_tracking_filter_options(self):
        """Carga filtros dinamicos del seguimiento de tareas."""
        self._cmb_seg_responsable.clear()
        self._cmb_seg_responsable.addItem("Todos", "")
        for username in AuditController.get_responsables_tareas_asignadas():
            self._cmb_seg_responsable.addItem(username, username)

    def _apply_task_tracking_filters(self):
        """Filtra y carga tabla de seguimiento de tareas asignadas."""
        responsable = self._cmb_seg_responsable.currentData() or ""
        estado = self._cmb_seg_estado.currentData() or ""
        fecha_desde = self._date_seg_desde.date().toString("yyyy-MM-dd")
        fecha_hasta = self._date_seg_hasta.date().toString("yyyy-MM-dd")

        data = AuditController.get_seguimiento_tareas(
            responsable=responsable,
            estado=estado,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            limit=300,
        )
        self._populate_task_tracking_table(data)
        self._lbl_task_tracking_count.setText(f"{len(data)} tareas encontradas (max 300)")

    def _clear_task_tracking_filters(self):
        """Restablece filtros del tab de seguimiento."""
        self._cmb_seg_responsable.setCurrentIndex(0)
        self._cmb_seg_estado.setCurrentIndex(0)
        self._date_seg_desde.setDate(QDate.currentDate().addDays(-30))
        self._date_seg_hasta.setDate(QDate.currentDate())
        self._apply_task_tracking_filters()

    def _populate_log_table(self, data: list[dict], append: bool = False):
        """Llena la tabla de log con los datos."""
        # Color badges para acciones
        accion_colors = {
            "create": ("#1f3d1f", "#8aff8a"),
            "update": ("#3d3520", "#c9a84c"),
            "delete": ("#3d1f1f", "#ff8a8a"),
        }
        if append and hasattr(self, "_log_data"):
            start = len(self._log_data)
            self._log_data.extend(data)
            self._log_table.setRowCount(len(self._log_data))
        else:
            self._log_data = list(data)
            start = 0
            self._log_table.setRowCount(len(self._log_data))

        for rel_idx, row in enumerate(data):
            i = start + rel_idx
            # Fecha/Hora
            ts = row.get("timestamp", "")
            if ts and len(ts) >= 19:
                fecha_fmt = ts[:10] + " " + ts[11:19]
            else:
                fecha_fmt = ts
            self._log_table.setItem(i, 0, QTableWidgetItem(fecha_fmt))

            # Usuario
            self._log_table.setItem(i, 1, QTableWidgetItem(row.get("usuario", "")))

            # Accion (con color)
            accion = row.get("accion", "")
            accion_item = QTableWidgetItem(row.get("accion_label", accion))
            bg, fg = accion_colors.get(accion, ("#2a2a2a", "#ffffff"))
            accion_item.setBackground(QColor(bg))
            accion_item.setForeground(QColor(fg))
            accion_item.setFont(QFont("Lato", 10, QFont.Weight.Bold))
            self._log_table.setItem(i, 2, accion_item)

            # Modulo
            self._log_table.setItem(i, 3, QTableWidgetItem(row.get("coleccion_label", "")))

            # Carpeta
            self._log_table.setItem(i, 4, QTableWidgetItem(row.get("carpeta_label", "-")))

            # Cliente
            self._log_table.setItem(i, 5, QTableWidgetItem(row.get("cliente_label", "-")))

            # Documento
            self._log_table.setItem(i, 6, QTableWidgetItem(row.get("documento_label", "-")))

            # Cambio clave
            self._log_table.setItem(i, 7, QTableWidgetItem(row.get("cambio_clave", "-")))

            # Resumen
            self._log_table.setItem(i, 8, QTableWidgetItem(row.get("resumen", "")))

    def _populate_task_tracking_table(self, data: list[dict]):
        """Llena la tabla de seguimiento de tareas."""
        self._task_tracking_data = data
        self._task_tracking_table.setRowCount(len(data))

        for i, row in enumerate(data):
            fecha_asig = self._fmt_ts(row.get("fecha_asignacion", ""))
            fecha_lectura = self._fmt_ts(row.get("fecha_lectura", ""))
            fecha_cump = self._fmt_ts(row.get("fecha_cumplimiento", ""))
            id_tarea = row.get("id_tarea", "")
            tarea_label = f"#{id_tarea}" if id_tarea not in ("", None) else row.get("tarea_oid", "")
            estado = row.get("estado_actual", "") or "-"
            leida = bool(row.get("leida", False))
            dias = row.get("dias_sin_leer", 0)
            dias_txt = str(dias) if isinstance(dias, int) and dias > 0 else "-"

            self._task_tracking_table.setItem(i, 0, QTableWidgetItem(fecha_asig))
            self._task_tracking_table.setItem(i, 1, QTableWidgetItem(tarea_label))
            self._task_tracking_table.setItem(i, 2, QTableWidgetItem(row.get("descripcion", "")))
            self._task_tracking_table.setItem(i, 3, QTableWidgetItem(row.get("asignada_a", "")))

            leida_item = QTableWidgetItem("Leida" if leida else "No leida")
            if leida:
                leida_item.setBackground(QColor("#1f3d1f"))
                leida_item.setForeground(QColor("#8aff8a"))
            else:
                leida_item.setBackground(QColor("#3d3520"))
                leida_item.setForeground(QColor("#ffd166"))
            leida_item.setFont(QFont("Lato", 10, QFont.Weight.Bold))
            self._task_tracking_table.setItem(i, 4, leida_item)

            self._task_tracking_table.setItem(i, 5, QTableWidgetItem(fecha_lectura))

            estado_item = QTableWidgetItem(estado)
            if estado in ("Cumplida", "Completada"):
                estado_item.setBackground(QColor("#1f3d1f"))
                estado_item.setForeground(QColor("#8aff8a"))
            elif estado == "Cancelada":
                estado_item.setBackground(QColor("#3d1f1f"))
                estado_item.setForeground(QColor("#ff8a8a"))
            self._task_tracking_table.setItem(i, 6, estado_item)

            self._task_tracking_table.setItem(i, 7, QTableWidgetItem(fecha_cump))
            self._task_tracking_table.setItem(i, 8, QTableWidgetItem(dias_txt))

    def _on_task_tracking_double_click(self, index):
        """Abrir carpeta y tarea asociadas desde Seguimiento de Tareas."""
        row_idx = index.row()
        if not hasattr(self, "_task_tracking_data") or not (0 <= row_idx < len(self._task_tracking_data)):
            return

        row = self._task_tracking_data[row_idx]
        tarea_oid = row.get("tarea_oid", "")
        if not tarea_oid:
            QMessageBox.information(
                self,
                "Seguimiento de tareas",
                "No se encontro el identificador interno de la tarea.",
            )
            return

        try:
            from controllers.tarea_controller import TareaController
            from views.expedientes.expediente_form import ExpedienteFormDialog
            from views.tareas.tarea_form import TareaFormDialog

            tarea = TareaController.get_by_id(tarea_oid)
            if not tarea:
                QMessageBox.information(
                    self,
                    "Seguimiento de tareas",
                    "La tarea ya no existe o fue eliminada.",
                )
                return

            exp_id = tarea.get("id_expediente", "") or ""
            main = self.window()

            # Paso 1: abrir carpeta correspondiente.
            if exp_id:
                try:
                    if hasattr(main, "_navigate"):
                        main._navigate("expedientes")
                except Exception:
                    pass
                dlg_exp = ExpedienteFormDialog(expediente_id=exp_id, parent=self)
                dlg_exp.exec()

            # Paso 2: abrir la tarea en su formulario.
            try:
                if hasattr(main, "_navigate"):
                    main._navigate("tareas")
            except Exception:
                pass
            dlg_tarea = TareaFormDialog(tarea_id=tarea_oid, parent=self)
            dlg_tarea.exec()

            # Refrescar seguimiento y listas relacionadas.
            self._apply_task_tracking_filters()
            if hasattr(main, "_views"):
                for key in ("tareas", "expedientes"):
                    view = main._views.get(key)
                    if view and hasattr(view, "refresh"):
                        view.refresh()
        except Exception as e:
            QMessageBox.warning(
                self,
                "Seguimiento de tareas",
                f"No se pudo abrir la carpeta y la tarea.\n\nDetalle: {e}",
            )

    def _on_log_double_click(self, index):
        """Abre el dialogo de detalle al hacer doble clic."""
        row_idx = index.row()
        if 0 <= row_idx < len(self._log_data):
            audit_id = self._log_data[row_idx].get("_id", "")
            if audit_id:
                dlg = AuditDetailDialog(audit_id, parent=self)
                dlg.exec()

    @staticmethod
    def _fmt_ts(value: str) -> str:
        if value and len(value) >= 19:
            return value[:10] + " " + value[11:19]
        return value or "-"

    # ══════════════════════════════════════════════
    #  Estadisticas
    # ══════════════════════════════════════════════

    def _load_stats(self):
        """Carga estadisticas y graficos."""
        stats = AuditController.get_stats_por_usuario()
        acciones_hoy = AuditController.get_acciones_hoy()

        # KPIs
        total = sum(s["total"] for s in stats)
        self._kpi_total["value"].setText(str(total))
        self._kpi_hoy["value"].setText(str(acciones_hoy))
        self._kpi_usuarios["value"].setText(str(len(stats)))

        if stats:
            ultima = max(s["ultima_actividad"] for s in stats if s["ultima_actividad"])
            if ultima and len(ultima) >= 19:
                self._kpi_ultima["value"].setText(ultima[:10] + " " + ultima[11:16])
            else:
                self._kpi_ultima["value"].setText(ultima or "--")

        # Tabla resumen
        self._stats_table.setRowCount(len(stats))
        for i, s in enumerate(stats):
            self._stats_table.setItem(i, 0, QTableWidgetItem(s["usuario"]))

            total_item = QTableWidgetItem(str(s["total"]))
            total_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            total_item.setFont(QFont("Lato", 11, QFont.Weight.Bold))
            self._stats_table.setItem(i, 1, total_item)

            create_item = QTableWidgetItem(str(s["creates"]))
            create_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            create_item.setForeground(QColor("#2d8f4e"))
            self._stats_table.setItem(i, 2, create_item)

            update_item = QTableWidgetItem(str(s["updates"]))
            update_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            update_item.setForeground(QColor("#c9a84c"))
            self._stats_table.setItem(i, 3, update_item)

            delete_item = QTableWidgetItem(str(s["deletes"]))
            delete_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            delete_item.setForeground(QColor("#cc3333"))
            self._stats_table.setItem(i, 4, delete_item)

            ultima = s["ultima_actividad"]
            if ultima and len(ultima) >= 19:
                ultima_fmt = ultima[:10] + " " + ultima[11:16]
            else:
                ultima_fmt = ultima or "--"
            self._stats_table.setItem(i, 5, QTableWidgetItem(ultima_fmt))

        # Graficos
        self._render_chart_por_usuario()
        self._render_chart_diaria()
        self._render_chart_por_modulo()

    # ── Helpers KPI ──

    def _create_kpi_card(self, title: str, value: str, color: str) -> dict:
        """Crea una tarjeta KPI y devuelve un dict con el frame y labels."""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 10px;
                border-left: 4px solid {color};
                padding: 16px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        layout = QVBoxLayout(frame)
        layout.setSpacing(4)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: #6b6b6b; font-size: 12px; font-weight: 600;")
        layout.addWidget(lbl_title)

        lbl_value = QLabel(value)
        lbl_value.setFont(QFont("Lato", 24, QFont.Weight.Bold))
        lbl_value.setStyleSheet(f"color: {color};")
        layout.addWidget(lbl_value)

        return {"frame": frame, "value": lbl_value}

    # ── Graficos matplotlib ──

    CHART_COLORS = [
        "#c9a84c", "#4a4a4a", "#b8963c", "#8a8a8a",
        "#a07c30", "#6b6b6b", "#d4b85c", "#333333",
        "#2d8f4e", "#cc3333",
    ]

    def _fig_to_pixmap(self, fig):
        from PySide6.QtGui import QPixmap
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight",
                    facecolor="#ffffff", edgecolor="none")
        plt.close(fig)
        buf.seek(0)
        pixmap = QPixmap()
        pixmap.loadFromData(buf.read())
        return pixmap

    def _render_chart_por_usuario(self):
        data = AuditController.get_actividad_por_usuario(30)
        if not data:
            self._chart_labels["por_usuario"].setText("Sin datos")
            return
        fig, ax = plt.subplots(figsize=(5, 3.5))
        usuarios = [d["usuario"][:15] for d in data[:8]]
        cantidades = [d["cantidad"] for d in data[:8]]
        colors = self.CHART_COLORS[:len(usuarios)]
        bars = ax.bar(usuarios, cantidades, color=colors)
        ax.set_ylabel("Acciones", color="#4a4a4a")
        ax.set_title("Actividad por Usuario (30 dias)", color="#1a1a1a", fontweight="bold", fontsize=11)
        ax.tick_params(colors="#4a4a4a")
        plt.xticks(rotation=45, ha="right")
        # Valores sobre barras
        for bar, val in zip(bars, cantidades):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(cantidades) * 0.02,
                    str(val), ha="center", fontweight="bold", color="#1a1a1a", fontsize=9)
        fig.tight_layout()
        self._chart_labels["por_usuario"].setPixmap(
            self._fig_to_pixmap(fig).scaled(400, 280, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
        )

    def _render_chart_diaria(self):
        data = AuditController.get_actividad_diaria(30)
        if not data:
            self._chart_labels["diaria"].setText("Sin datos")
            return
        fig, ax = plt.subplots(figsize=(5, 3.5))
        fechas = [d["fecha"][5:] if d["fecha"] else "" for d in data]  # MM-DD
        cantidades = [d["cantidad"] for d in data]
        x = list(range(len(fechas)))
        ax.plot(x, cantidades, color="#c9a84c", linewidth=2, marker="o", markersize=4)
        ax.fill_between(x, cantidades, alpha=0.15, color="#c9a84c")
        ax.set_ylabel("Acciones", color="#4a4a4a")
        ax.set_title("Actividad Diaria (30 dias)", color="#1a1a1a", fontweight="bold", fontsize=11)
        ax.tick_params(colors="#4a4a4a")
        # Mostrar solo algunas etiquetas para legibilidad
        if len(fechas) > 10:
            step = max(1, len(fechas) // 6)
            ax.set_xticks(range(0, len(fechas), step))
            ax.set_xticklabels([fechas[i] for i in range(0, len(fechas), step)])
        else:
            ax.set_xticks(x)
            ax.set_xticklabels(fechas)
        plt.xticks(rotation=45, ha="right")
        fig.tight_layout()
        self._chart_labels["diaria"].setPixmap(
            self._fig_to_pixmap(fig).scaled(400, 280, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
        )

    def _render_chart_por_modulo(self):
        data = AuditController.get_actividad_por_modulo(30)
        if not data:
            self._chart_labels["por_modulo"].setText("Sin datos")
            return
        fig, ax = plt.subplots(figsize=(5, 3.5))
        modulos = [d["modulo"] for d in data[:8]]
        cantidades = [d["cantidad"] for d in data[:8]]
        colors = self.CHART_COLORS[:len(modulos)]
        wedges, texts, autotexts = ax.pie(
            cantidades, labels=modulos, autopct="%1.0f%%",
            colors=colors, startangle=90,
            textprops={"color": "#1a1a1a", "fontsize": 9}
        )
        for at in autotexts:
            at.set_color("#ffffff")
            at.set_fontweight("bold")
            at.set_fontsize(8)
        ax.set_title("Actividad por Modulo (30 dias)", color="#1a1a1a", fontweight="bold", fontsize=11)
        fig.tight_layout()
        self._chart_labels["por_modulo"].setPixmap(
            self._fig_to_pixmap(fig).scaled(400, 280, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
        )

    # ══════════════════════════════════════════════
    #  Exportacion
    # ══════════════════════════════════════════════

    def _export_log_excel(self):
        """Exporta el log filtrado actual a Excel."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar Log de Auditoria",
            f"auditoria_{datetime.now():%Y%m%d_%H%M}.xlsx",
            "Excel (*.xlsx)"
        )
        if not path:
            return

        try:
            import pandas as pd

            if not hasattr(self, "_log_data") or not self._log_data:
                QMessageBox.warning(self, "Sin datos", "No hay datos para exportar.")
                return

            rows = []
            for r in self._log_data:
                ts = r.get("timestamp", "")
                rows.append({
                    "Fecha/Hora": ts[:19].replace("T", " ") if ts else "",
                    "Usuario": r.get("usuario", ""),
                    "Accion": r.get("accion_label", ""),
                    "Modulo": r.get("coleccion_label", ""),
                    "Documento ID": r.get("documento_id", ""),
                    "Resumen": r.get("resumen", ""),
                })

            df = pd.DataFrame(rows)
            df.to_excel(path, index=False, sheet_name="Auditoria")
            QMessageBox.information(self, "Exito", f"Log exportado en:\n{path}")
        except ImportError:
            QMessageBox.warning(self, "Error", "Necesita instalar pandas y openpyxl para exportar.")
        except Exception as e:
            logger.exception("Error al exportar auditoria a Excel")
            QMessageBox.warning(self, "Error", f"Error al exportar: {e}")
