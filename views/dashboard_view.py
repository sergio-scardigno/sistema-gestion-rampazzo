"""Dashboard principal con KPIs y tareas pendientes."""
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QPushButton, QMessageBox, QSplitter, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

logger = logging.getLogger(__name__)

from controllers.reporte_controller import ReporteController
from controllers.tarea_controller import TareaController
from controllers.turno_controller import TurnoController
from controllers.audit_controller import AuditController
from controllers.cliente_controller import ClienteController
from controllers.expediente_controller import ExpedienteController
from controllers.notificacion_controller import NotificacionController
from core.auth import Session
from core.permissions import tiene_permiso, es_rol_global, scope_where
from core.scheduler import get_alertas_pendientes, get_recordatorios_turnos, get_alertas_sin_tarea


class KPICard(QFrame):
    def __init__(self, title: str, value: str, color: str = "#c9a84c", parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                border-left: 4px solid {color};
                padding: 10px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(2, 2, 2, 2)

        self._lbl_title = QLabel(title)
        self._lbl_title.setStyleSheet("color: #6b6b6b; font-size: 11px; font-weight: 600; border: none;")
        layout.addWidget(self._lbl_title)

        self._lbl_value = QLabel(str(value))
        self._lbl_value.setFont(QFont("Lato", 20, QFont.Weight.Bold))
        self._lbl_value.setStyleSheet(f"color: {color}; border: none;")
        layout.addWidget(self._lbl_value)

    def update_value(self, value: str):
        self._lbl_value.setText(str(value))


class DashboardView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._kpi_cards: dict[str, KPICard] = {}

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(16, 12, 16, 16)
        self._layout.setSpacing(12)

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

        # KPI Grid
        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(10)

        session = Session.get()
        self._show_eco_kpis = tiene_permiso(session.rol, "movimientos.read")

        cards_config = [
            ("exp_activos", "Carpetas Activas", "0", "#c9a84c"),
            ("exp_cerrados", "Carpetas Cerradas", "0", "#2d8f4e"),
            ("tareas_pend", "Tareas Pendientes", "0", "#b8963c"),
            ("tareas_venc", "Tareas Vencidas", "0", "#cc3333"),
            ("total_clientes", "Total Clientes", "0", "#4a4a4a"),
        ]

        if self._show_eco_kpis:
            cards_config.append(("ingresos", "Ingresos Cobrados", "$0", "#2d8f4e"))
            cards_config.append(("pendientes", "Pendientes Cobro", "$0", "#a07c30"))

        cards_config.append(("tiempo_prom", "Tiempo Prom. Resolucion", "-", "#4a90d9"))

        for i, (key, title_text, default, color) in enumerate(cards_config):
            card = KPICard(title_text, default, color)
            self._kpi_cards[key] = card
            kpi_grid.addWidget(card, i // 4, i % 4)

        # Turnos KPIs (tercera fila)
        turnos_kpis = [
            ("turnos_prox", "Turnos Prox. 7 dias", "0", "#c9a84c"),
            ("turnos_hoy", "Turnos Hoy", "0", "#b8963c"),
            ("turnos_sin_doc", "Sin Documentacion", "0", "#cc3333"),
            ("turnos_pend_res", "Pend. Resultado", "0", "#a07c30"),
        ]
        for j, (key, title_text, default, color) in enumerate(turnos_kpis):
            card = KPICard(title_text, default, color)
            self._kpi_cards[key] = card
            kpi_grid.addWidget(card, 2, j)

        # KPI Auditoria (solo admin/superusuario)
        self._show_audit_kpi = False
        if tiene_permiso(session.rol, "auditoria.*"):
            self._show_audit_kpi = True
            card = KPICard("Acciones Hoy", "0", "#4a4a4a")
            self._kpi_cards["acciones_hoy"] = card
            kpi_grid.addWidget(card, 3, 0)

        self._layout.addLayout(kpi_grid)

        # ── Layout de 2 columnas: Turnos (izq) + Alertas/Vencidas (der) ──
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        bottom_splitter.setHandleWidth(6)
        bottom_splitter.setChildrenCollapsible(False)

        # --- Columna izquierda: Turnos de Hoy ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 4, 0)
        left_layout.setSpacing(6)

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
        self._table_turnos_hoy.horizontalHeader().setMinimumHeight(28)
        self._table_turnos_hoy.verticalHeader().setVisible(False)
        self._table_turnos_hoy.verticalHeader().setDefaultSectionSize(32)
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
                padding: 6px;
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
        left_layout.addWidget(self._table_turnos_hoy)

        bottom_splitter.addWidget(left_panel)

        # --- Columna derecha: Alertas + Tareas Vencidas ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(6)

        lbl_alertas = QLabel("Alertas y Recordatorios")
        lbl_alertas.setFont(QFont("Lato", 13, QFont.Weight.Bold))
        lbl_alertas.setStyleSheet("color: #cc3333;")
        right_layout.addWidget(lbl_alertas)

        self._alertas_scroll = QScrollArea()
        self._alertas_scroll.setWidgetResizable(True)
        self._alertas_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._alertas_scroll.setMaximumHeight(180)
        alertas_widget = QWidget()
        self._alertas_container = QVBoxLayout(alertas_widget)
        self._alertas_container.setContentsMargins(0, 0, 0, 0)
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
        self._table_vencidas.horizontalHeader().setMinimumHeight(28)
        self._table_vencidas.verticalHeader().setVisible(False)
        self._table_vencidas.verticalHeader().setDefaultSectionSize(32)
        self._table_vencidas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._table_vencidas.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
            }
        """)
        right_layout.addWidget(self._table_vencidas)

        bottom_splitter.addWidget(right_panel)

        # Proporciones iniciales: 60% turnos, 40% alertas/vencidas
        bottom_splitter.setStretchFactor(0, 6)
        bottom_splitter.setStretchFactor(1, 4)

        self._layout.addWidget(bottom_splitter, 1)

        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def refresh(self):
        session = Session.get()
        is_global = es_rol_global(session.rol)

        # KPIs operativos (con scope)
        from controllers.expediente_controller import ExpedienteController
        exp_activos = len(ExpedienteController.get_scoped(
            where="estado NOT IN ('Cerrado','Archivado')"))
        exp_cerrados = len(ExpedienteController.get_scoped(
            where="estado IN ('Cerrado','Archivado')"))
        tareas_pend = len(TareaController.get_scoped(
            where="estado IN ('Pendiente','En curso','En espera')"))
        from datetime import datetime, timedelta
        today = datetime.now().strftime("%Y-%m-%d")  # Fecha LOCAL (no UTC)
        tareas_venc = len(TareaController.get_scoped(
            where="estado IN ('Pendiente','En curso') AND fecha_vencimiento < ?",
            params=(today,)))

        self._kpi_cards["exp_activos"].update_value(str(exp_activos))
        self._kpi_cards["exp_cerrados"].update_value(str(exp_cerrados))
        self._kpi_cards["tareas_pend"].update_value(str(tareas_pend))
        self._kpi_cards["tareas_venc"].update_value(str(tareas_venc))

        # KPI total de clientes
        total_clientes = ClienteController.count_all()
        self._kpi_cards["total_clientes"].update_value(str(total_clientes))

        # KPI tiempo promedio de resolucion
        tiempo_data = ReporteController.tiempo_promedio_resolucion()
        prom = tiempo_data.get("promedio_dias", 0)
        total_cerr = tiempo_data.get("total_cerrados", 0)
        if total_cerr > 0:
            self._kpi_cards["tiempo_prom"].update_value(f"{prom:.0f} dias")
        else:
            self._kpi_cards["tiempo_prom"].update_value("-")

        # KPIs economicos (solo roles con permiso de movimientos)
        if self._show_eco_kpis:
            eco = ReporteController.kpis_economicos()
            self._kpi_cards["ingresos"].update_value(f'${eco["ingresos_cobrados"]:,.0f}')
            self._kpi_cards["pendientes"].update_value(f'${eco["pendientes_cobro"]:,.0f}')

        # KPIs turnos (con scope)
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
            self._table_turnos_hoy.setItem(i, 0, QTableWidgetItem(t.get("hora_turno", "")))
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

        # KPI Auditoria
        if self._show_audit_kpi:
            acciones_hoy = AuditController.get_acciones_hoy()
            self._kpi_cards["acciones_hoy"].update_value(str(acciones_hoy))

        # Alertas del scheduler
        self._refresh_alertas()

        # Tareas vencidas (con scope)
        vencidas = TareaController.get_scoped(
            where="estado IN ('Pendiente','En curso') AND fecha_vencimiento < ?",
            params=(today,), order_by="fecha_vencimiento ASC")
        expediente_cache: dict[str, dict | None] = {}
        cliente_cache_vencidas: dict[str, dict | None] = {}
        self._table_vencidas.setRowCount(len(vencidas[:20]))
        for i, t in enumerate(vencidas[:20]):
            self._table_vencidas.setItem(i, 0, QTableWidgetItem(t.get("descripcion", "")))
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

        if not alertas:
            lbl = QLabel("Sin alertas pendientes")
            lbl.setStyleSheet("color: #6b6b6b; font-style: italic; padding: 8px;")
            self._alertas_container.addWidget(lbl)
            return

        for alerta in alertas[:20]:
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
            else:
                icon = "\u2139"
                color = "#4a4a4a"

            lbl = QLabel(f"{icon}  {alerta.get('mensaje', '')}")
            lbl.setStyleSheet(f"""
                color: {color};
                background: #fafafa;
                border: 1px solid #e0e0e0;
                border-left: 3px solid {color};
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 11px;
            """)
            lbl.setWordWrap(True)
            self._alertas_container.addWidget(lbl)

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
