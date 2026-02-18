"""Formulario de alta/edicion de Carpeta."""
import logging

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QTextEdit, QDateEdit, QPushButton, QLabel, QComboBox, QMessageBox,
    QTabWidget, QWidget, QCompleter, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, QDate, QTimer
from PySide6.QtGui import QFont

logger = logging.getLogger(__name__)

from controllers.expediente_controller import ExpedienteController
from controllers.cliente_controller import ClienteController
from controllers.tarea_controller import TareaController
from controllers.turno_controller import TurnoController
from controllers.comunicacion_controller import ComunicacionController
from controllers.documento_controller import DocumentoController
from controllers.movimiento_controller import MovimientoController
from controllers.audit_controller import AuditController
from core.lock_manager import LockManager
from core.auth import Session
from core.permissions import tiene_permiso, get_active_users
from views.widgets.filterable_table import FilterableTable


class ExpedienteFormDialog(QDialog):
    def __init__(self, expediente_id: str = None, parent=None):
        super().__init__(parent)
        self._id = expediente_id
        self._is_edit = expediente_id is not None
        self._locked = False
        self._loaded_tabs: set[int] = set()
        self._tabs: QTabWidget | None = None

        self.setWindowTitle("Editar Carpeta" if self._is_edit else "Nueva Carpeta")
        self.setMinimumSize(800, 560)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 8, 12, 8)

        if self._is_edit:
            self._build_tabbed_view(layout)
        else:
            self._build_form_only(layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setProperty("variant", "secondary")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        btn_save = QPushButton("Guardar")
        btn_save.clicked.connect(self._save)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

        if self._is_edit:
            self._load_data()

    def _build_form_only(self, parent_layout):
        self._has_historial = False
        title = QLabel("Nueva Carpeta")
        title.setFont(QFont("Lato", 16, QFont.Weight.Bold))
        parent_layout.addWidget(title)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._form_widget = QWidget()
        self._build_form(self._form_widget)
        scroll.setWidget(self._form_widget)
        parent_layout.addWidget(scroll)

    def _build_tabbed_view(self, parent_layout):
        title = QLabel("Detalle de Carpeta")
        title.setFont(QFont("Lato", 16, QFont.Weight.Bold))
        parent_layout.addWidget(title)

        tabs = QTabWidget()
        self._tabs = tabs

        # Tab 0 – Datos (con scroll para pantallas chicas)
        datos_scroll = QScrollArea()
        datos_scroll.setWidgetResizable(True)
        datos_scroll.setFrameShape(QFrame.Shape.NoFrame)
        datos_widget = QWidget()
        self._build_form(datos_widget)
        datos_scroll.setWidget(datos_widget)
        tabs.addTab(datos_scroll, "Datos")

        # Tab 1 – Tareas
        tareas_widget = QWidget()
        tareas_layout = QVBoxLayout(tareas_widget)
        self._tareas_table = FilterableTable([
            ("descripcion", "Descripcion"),
            ("responsable", "Responsable"),
            ("fecha_vencimiento", "Vencimiento"),
            ("estado", "Estado"),
        ])
        tareas_layout.addWidget(self._tareas_table)
        btn_new_tarea = QPushButton("+ Nueva Tarea")
        btn_new_tarea.clicked.connect(self._new_tarea)
        tareas_layout.addWidget(btn_new_tarea, alignment=Qt.AlignmentFlag.AlignLeft)
        tabs.addTab(tareas_widget, "Tareas")

        # Tab 2 – Turnos ANSES
        turnos_widget = QWidget()
        turnos_layout = QVBoxLayout(turnos_widget)
        self._turnos_table = FilterableTable([
            ("fecha_turno", "Fecha"),
            ("hora_turno", "Hora"),
            ("oficina_anses", "Oficina"),
            ("tipo_tramite", "Tramite"),
            ("estado", "Estado"),
            ("responsable", "Responsable"),
        ])
        turnos_layout.addWidget(self._turnos_table)
        btn_new_turno = QPushButton("+ Nuevo Turno")
        btn_new_turno.clicked.connect(self._new_turno)
        turnos_layout.addWidget(btn_new_turno, alignment=Qt.AlignmentFlag.AlignLeft)
        tabs.addTab(turnos_widget, "Turnos ANSES")

        # Tab 3 – Comunicaciones
        comms_widget = QWidget()
        comms_layout = QVBoxLayout(comms_widget)
        self._comms_table = FilterableTable([
            ("fecha", "Fecha"),
            ("canal", "Canal"),
            ("emisor", "Emisor"),
            ("motivo", "Motivo"),
            ("resultado", "Resultado"),
        ])
        self._comms_table.row_double_clicked.connect(self._edit_comunicacion)
        comms_layout.addWidget(self._comms_table)
        btn_new_comm = QPushButton("+ Nueva Comunicacion")
        btn_new_comm.clicked.connect(self._new_comunicacion)
        comms_layout.addWidget(btn_new_comm, alignment=Qt.AlignmentFlag.AlignLeft)
        tabs.addTab(comms_widget, "Comunicaciones")

        # Tab 4 – Documentos
        docs_widget = QWidget()
        docs_layout = QVBoxLayout(docs_widget)
        self._docs_table = FilterableTable([
            ("nombre", "Nombre"),
            ("categoria", "Categoria"),
            ("fecha", "Fecha"),
            ("responsable", "Responsable"),
        ])
        self._docs_table.row_double_clicked.connect(self._edit_documento)
        docs_layout.addWidget(self._docs_table)
        btn_new_doc = QPushButton("+ Nuevo Documento")
        btn_new_doc.clicked.connect(self._new_documento)
        docs_layout.addWidget(btn_new_doc, alignment=Qt.AlignmentFlag.AlignLeft)
        tabs.addTab(docs_widget, "Documentos")

        # Tab Movimientos (solo si el rol tiene permiso economico)
        session = Session.get()
        self._has_movimientos = tiene_permiso(session.rol, "movimientos.read")
        self._tab_map: dict[int, str] = {}

        if self._has_movimientos:
            movs_widget = QWidget()
            movs_layout = QVBoxLayout(movs_widget)
            self._movs_table = FilterableTable([
                ("fecha", "Fecha"),
                ("tipo", "Tipo"),
                ("monto", "Monto"),
                ("estado", "Estado"),
                ("forma_pago", "Forma Pago"),
            ])
            self._movs_table.row_double_clicked.connect(self._edit_movimiento)
            movs_layout.addWidget(self._movs_table)
            btn_new_mov = QPushButton("+ Nuevo Movimiento")
            btn_new_mov.clicked.connect(self._new_movimiento)
            movs_layout.addWidget(btn_new_mov, alignment=Qt.AlignmentFlag.AlignLeft)
            idx_movs = tabs.count()
            tabs.addTab(movs_widget, "Movimientos")
            self._tab_map[idx_movs] = "movimientos"

        # Tab Tiempos
        tiempos_widget = QWidget()
        tiempos_layout = QVBoxLayout(tiempos_widget)
        tiempos_layout.setSpacing(12)
        self._lbl_tiempo_total = QLabel("Tiempo total: calculando...")
        self._lbl_tiempo_total.setFont(QFont("Lato", 14, QFont.Weight.Bold))
        self._lbl_tiempo_total.setStyleSheet("color: #c9a84c;")
        tiempos_layout.addWidget(self._lbl_tiempo_total)
        self._tiempos_table = FilterableTable([
            ("estado", "Estado"),
            ("dias_fmt", "Dias"),
            ("porcentaje", "% del Total"),
        ])
        tiempos_layout.addWidget(self._tiempos_table)
        idx_tiempos = tabs.count()
        tabs.addTab(tiempos_widget, "Tiempos")
        self._tab_map[idx_tiempos] = "tiempos"

        # Tab Historial de Cambios (solo para administrador y superusuario)
        if tiene_permiso(session.rol, "auditoria.*"):
            historial_widget = QWidget()
            historial_layout = QVBoxLayout(historial_widget)
            self._historial_table = FilterableTable([
                ("timestamp_fmt", "Fecha/Hora"),
                ("usuario", "Usuario"),
                ("accion_label", "Accion"),
                ("resumen", "Resumen"),
            ])
            self._historial_table.row_double_clicked.connect(self._on_historial_double_click)
            historial_layout.addWidget(self._historial_table)
            idx_hist = tabs.count()
            tabs.addTab(historial_widget, "Historial de Cambios")
            self._tab_map[idx_hist] = "historial"
            self._has_historial = True
        else:
            self._has_historial = False

        tabs.currentChanged.connect(self._on_tab_changed)
        parent_layout.addWidget(tabs)

    def _make_separator(self, text: str = "") -> QFrame:
        """Crea un separador visual horizontal con label opcional."""
        if text:
            lbl = QLabel(text)
            lbl.setStyleSheet(
                "color: #c9a84c; font-size: 11px; font-weight: bold;"
                " letter-spacing: 1px; padding: 6px 0 2px 0; border: none;"
                " background: transparent;"
            )
            return lbl
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e0e0e0; margin: 4px 0;")
        sep.setFixedHeight(1)
        return sep

    def _build_form(self, container):
        form = QFormLayout(container)
        form.setSpacing(8)
        form.setContentsMargins(12, 8, 12, 8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # ── Seccion: Cliente ──
        form.addRow(self._make_separator("CLIENTE"))

        self._cmb_cliente = QComboBox()
        self._cmb_cliente.setEditable(True)
        self._cmb_cliente.setPlaceholderText("Escriba para buscar cliente...")
        self._cmb_cliente.addItem("-- Sin cliente --", "")
        self._clientes_cache: list[dict] = []
        self._cliente_search_timer = QTimer(self)
        self._cliente_search_timer.setSingleShot(True)
        self._cliente_search_timer.setInterval(300)
        self._cliente_search_timer.timeout.connect(self._search_clientes)
        self._cmb_cliente.lineEdit().textEdited.connect(
            lambda _: self._cliente_search_timer.start()
        )

        completer = QCompleter(self)
        completer.setModel(self._cmb_cliente.model())
        completer.setCompletionColumn(0)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.activated[str].connect(self._on_cliente_completer_activated)
        self._cmb_cliente.setCompleter(completer)
        form.addRow("Cliente:", self._cmb_cliente)

        self._txt_carpeta_cliente = QLineEdit()
        self._txt_carpeta_cliente.setReadOnly(True)
        self._txt_carpeta_cliente.setPlaceholderText("Se muestra al seleccionar un cliente")
        self._txt_carpeta_cliente.setFixedHeight(30)
        self._txt_carpeta_cliente.setStyleSheet(
            "background-color: #2a2a2a; color: #c9a84c; font-weight: bold;"
            " font-size: 13px; padding: 4px 6px;"
        )
        form.addRow("N° Carpeta cliente:", self._txt_carpeta_cliente)
        self._cmb_cliente.currentIndexChanged.connect(self._on_cliente_changed)

        self._txt_clave_mi_anses = QLineEdit()
        self._txt_clave_mi_anses.setPlaceholderText("Clave de Mi ANSES del cliente")
        self._txt_clave_mi_anses.setFixedHeight(30)
        self._txt_clave_mi_anses.setStyleSheet(
            "background-color: #2a2a2a; color: #c9a84c; font-weight: bold;"
            " font-size: 13px; padding: 4px 6px;"
        )
        form.addRow("Clave Mi ANSES:", self._txt_clave_mi_anses)

        self._txt_clave_fiscal = QLineEdit()
        self._txt_clave_fiscal.setPlaceholderText("Clave fiscal AFIP del cliente")
        self._txt_clave_fiscal.setFixedHeight(30)
        self._txt_clave_fiscal.setStyleSheet(
            "background-color: #2a2a2a; color: #c9a84c; font-weight: bold;"
            " font-size: 13px; padding: 4px 6px;"
        )
        form.addRow("Clave Fiscal:", self._txt_clave_fiscal)

        # ── Seccion: Tramite ──
        form.addRow(self._make_separator("TRAMITE"))

        self._cmb_tipo = QComboBox()
        for t in ExpedienteController.TIPOS_TRAMITE:
            self._cmb_tipo.addItem(t)
        form.addRow("Tipo tramite *:", self._cmb_tipo)

        self._txt_area = QLineEdit()
        form.addRow("Area:", self._txt_area)

        self._date_apertura = QDateEdit()
        self._date_apertura.setCalendarPopup(True)
        self._date_apertura.setDate(QDate.currentDate())
        self._date_apertura.setDisplayFormat("dd/MM/yyyy")
        form.addRow("Fecha apertura:", self._date_apertura)

        # ── Seccion: Responsables ──
        form.addRow(self._make_separator("RESPONSABLES"))

        self._cmb_responsable = QComboBox()
        self._cmb_responsable.setEditable(True)
        self._cmb_responsable.setPlaceholderText("Seleccionar responsable...")
        self._cmb_responsable2 = QComboBox()
        self._cmb_responsable2.setEditable(True)
        self._cmb_responsable2.setPlaceholderText("Seleccionar resp. secundario...")
        self._cmb_responsable2.addItem("-- Sin resp. secundario --", "")
        users = get_active_users()
        for u in users:
            label = f'{u.get("nombre_completo", "")} ({u.get("username", "")})'
            uname = u.get("username", "")
            self._cmb_responsable.addItem(label, uname)
            self._cmb_responsable2.addItem(label, uname)
        form.addRow("Responsable *:", self._cmb_responsable)
        form.addRow("Resp. secundario:", self._cmb_responsable2)

        # ── Seccion: Estado ──
        form.addRow(self._make_separator("ESTADO"))

        self._cmb_estado = QComboBox()
        for e in ExpedienteController.ESTADOS:
            self._cmb_estado.addItem(e)
        form.addRow("Estado:", self._cmb_estado)

        self._cmb_prioridad = QComboBox()
        for p in ExpedienteController.PRIORIDADES:
            self._cmb_prioridad.addItem(p)
        self._cmb_prioridad.setCurrentText("Normal")
        form.addRow("Prioridad:", self._cmb_prioridad)

        # ── Seccion: Datos adicionales ──
        form.addRow(self._make_separator("DATOS ADICIONALES"))

        self._txt_ubicacion = QLineEdit()
        form.addRow("Ubicacion fisica:", self._txt_ubicacion)

        self._txt_link_drive = QLineEdit()
        self._txt_link_drive.setPlaceholderText("https://drive.google.com/...")
        form.addRow("Link Drive:", self._txt_link_drive)

        self._txt_nro_exp = QLineEdit()
        self._txt_nro_exp.setPlaceholderText("024-XXXXXXXXXXX-XXX-XXXXXX")
        form.addRow("Nro Tramite ANSES:", self._txt_nro_exp)

        # ── Seccion: Cierre ──
        form.addRow(self._make_separator("CIERRE"))

        self._txt_resultado = QLineEdit()
        self._txt_resultado.setPlaceholderText("Resultado de la carpeta (al cerrar)")
        form.addRow("Resultado:", self._txt_resultado)

        self._date_cierre = QDateEdit()
        self._date_cierre.setCalendarPopup(True)
        self._date_cierre.setDate(QDate.currentDate())
        self._date_cierre.setDisplayFormat("dd/MM/yyyy")
        self._date_cierre.setEnabled(False)
        form.addRow("Fecha cierre:", self._date_cierre)

        self._cmb_estado.currentTextChanged.connect(self._on_estado_changed)

        self._txt_obs = QTextEdit()
        self._txt_obs.setMaximumHeight(70)
        form.addRow("Observaciones:", self._txt_obs)

    def _load_data(self):
        data = ExpedienteController.get_by_id(self._id)
        if not data:
            QMessageBox.warning(self, "Error", "Carpeta no encontrada.")
            self.reject()
            return

        ok, msg = LockManager.acquire_lock("expedientes", self._id)
        if not ok:
            QMessageBox.information(self, "Registro bloqueado", msg)
        else:
            self._locked = True

        # Asegurar que el cliente actual este en el combo antes de seleccionarlo
        id_cliente = data.get("id_cliente", "")
        cliente_actual = None
        if id_cliente:
            cliente_actual = ClienteController.get_by_id(id_cliente)
            if cliente_actual:
                self._add_cliente_to_combo(cliente_actual)
        idx = self._cmb_cliente.findData(id_cliente)
        if idx >= 0:
            self._cmb_cliente.setCurrentIndex(idx)
        self._on_cliente_changed(self._cmb_cliente.currentIndex())
        self._cmb_tipo.setCurrentText(data.get("tipo_tramite", ""))
        self._txt_area.setText(data.get("area", ""))
        fa = data.get("fecha_apertura", "")
        if fa and len(fa) >= 10:
            self._date_apertura.setDate(QDate.fromString(fa[:10], "yyyy-MM-dd"))
        # Seleccionar responsable por username
        resp_uname = data.get("responsable_username", "")
        idx_r = self._cmb_responsable.findData(resp_uname)
        if idx_r >= 0:
            self._cmb_responsable.setCurrentIndex(idx_r)
        elif data.get("responsable", ""):
            # Fallback: mostrar texto legacy
            self._cmb_responsable.setEditText(data.get("responsable", ""))

        resp2_uname = data.get("responsable_secundario_username", "")
        idx_r2 = self._cmb_responsable2.findData(resp2_uname)
        if idx_r2 >= 0:
            self._cmb_responsable2.setCurrentIndex(idx_r2)
        elif data.get("responsable_secundario", ""):
            self._cmb_responsable2.setEditText(data.get("responsable_secundario", ""))
        self._cmb_estado.setCurrentText(data.get("estado", "Activo"))
        self._cmb_prioridad.setCurrentText(data.get("prioridad", "Normal"))
        self._txt_ubicacion.setText(data.get("ubicacion_fisica", ""))
        self._txt_link_drive.setText(data.get("link_drive", ""))
        self._txt_nro_exp.setText(data.get("numero_expediente_anses", ""))
        self._txt_resultado.setText(data.get("resultado", ""))
        fc = data.get("fecha_cierre", "")
        if fc and len(fc) >= 10:
            self._date_cierre.setDate(QDate.fromString(fc[:10], "yyyy-MM-dd"))
        self._on_estado_changed(data.get("estado", "Activo"))
        self._txt_obs.setPlainText(data.get("observaciones", ""))

        # Cargar claves: prioridad snapshot del expediente, fallback al cliente
        clave_anses = data.get("clave_mi_anses", "") or ""
        clave_fiscal = data.get("clave_fiscal", "") or ""
        if (not clave_anses or not clave_fiscal) and id_cliente:
            cli = cliente_actual if id_cliente and cliente_actual else None
            if cli:
                if not clave_anses:
                    clave_anses = cli.get("clave_mi_anses", "") or ""
                if not clave_fiscal:
                    clave_fiscal = cli.get("clave_fiscal", "") or ""
        self._txt_clave_mi_anses.setText(clave_anses)
        self._txt_clave_fiscal.setText(clave_fiscal)

        # Las pestañas relacionadas se cargan on-demand al activarlas (lazy).

    # ------------------------------------------------------------------
    # Carga diferida (lazy) de pestanas
    # ------------------------------------------------------------------

    def _on_tab_changed(self, index: int):
        """Cargar datos de la pestana solo la primera vez que se activa."""
        if not self._is_edit or not self._id or index in self._loaded_tabs:
            return
        self._loaded_tabs.add(index)

        # Tabs fijos (indices 0-4 siempre presentes)
        if index == 1:
            self._load_tab_tareas()
        elif index == 2:
            self._load_tab_turnos()
        elif index == 3:
            self._load_tab_comms()
        elif index == 4:
            self._load_tab_docs()
        else:
            # Tabs dinamicos (movimientos, tiempos, historial)
            tab_name = self._tab_map.get(index)
            if tab_name == "movimientos":
                self._load_tab_movs()
            elif tab_name == "tiempos":
                self._load_tab_tiempos()
            elif tab_name == "historial":
                self._load_tab_historial()

    def _load_tab_tareas(self):
        tareas = TareaController.get_by_expediente(self._id)
        self._tareas_table.set_data(tareas)

    def _load_tab_turnos(self):
        turnos = TurnoController.get_by_expediente(self._id)
        self._turnos_table.set_data(turnos)

    def _load_tab_comms(self):
        comms = ComunicacionController.get_by_expediente(self._id)
        self._comms_table.set_data(comms)

    def _load_tab_docs(self):
        docs = DocumentoController.get_by_expediente(self._id)
        self._docs_table.set_data(docs)

    def _load_tab_movs(self):
        movs = MovimientoController.get_by_expediente(self._id)
        self._movs_table.set_data(movs)

    def _load_tab_tiempos(self):
        """Cargar desglose de tiempos por estado para esta carpeta."""
        from controllers.reporte_controller import ReporteController
        result = ReporteController.tiempos_por_estado_expediente(self._id)
        total_dias = result.get("total_dias", 0)
        estados = result.get("estados", [])

        if total_dias > 0:
            anios = int(total_dias // 365)
            meses = int((total_dias % 365) // 30)
            dias_rest = int(total_dias % 30)
            partes = []
            if anios:
                partes.append(f"{anios} {'anio' if anios == 1 else 'anios'}")
            if meses:
                partes.append(f"{meses} {'mes' if meses == 1 else 'meses'}")
            partes.append(f"{dias_rest} {'dia' if dias_rest == 1 else 'dias'}")
            self._lbl_tiempo_total.setText(
                f"Tiempo total: {' '.join(partes)} ({total_dias:.1f} dias)"
            )
        else:
            self._lbl_tiempo_total.setText("Tiempo total: sin datos de historial")

        rows = []
        for e in estados:
            dias = e["dias"]
            pct = (dias / total_dias * 100) if total_dias > 0 else 0
            rows.append({
                "_id": e["estado"],
                "estado": e["estado"],
                "dias_fmt": f"{dias:.1f}",
                "porcentaje": f"{pct:.1f}%",
            })
        self._tiempos_table.set_data(rows)

    def _load_tab_historial(self):
        historial = AuditController.get_by_document("expedientes", self._id)
        for h in historial:
            ts = h.get("timestamp", "")
            h["timestamp_fmt"] = (ts[:10] + " " + ts[11:19]) if ts and len(ts) >= 19 else ts
        self._historial_table.set_data(historial)

    # ------------------------------------------------------------------
    # Busqueda incremental de clientes para el combo
    # ------------------------------------------------------------------

    def _search_clientes(self):
        """Buscar clientes segun el texto ingresado y poblar el combo."""
        text = self._cmb_cliente.lineEdit().text().strip()
        if len(text) < 2:
            return
        results = ClienteController.search_clientes(text)[:50]
        current_data = self._cmb_cliente.currentData()
        self._cmb_cliente.blockSignals(True)
        self._cmb_cliente.clear()
        self._cmb_cliente.addItem("-- Sin cliente --", "")
        self._clientes_cache = results
        for c in results:
            nc = c.get("numero_carpeta", "")
            nc_label = f" [Carpeta {nc}]" if nc else ""
            label = f'{c.get("nombre_completo", "")} ({c.get("cuil", "")}){nc_label}'
            self._cmb_cliente.addItem(label, c["_id"])
        # Restaurar seleccion si existia
        if current_data:
            idx = self._cmb_cliente.findData(current_data)
            if idx >= 0:
                self._cmb_cliente.setCurrentIndex(idx)
        self._cmb_cliente.blockSignals(False)
        self._cmb_cliente.lineEdit().setText(text)
        self._cmb_cliente.lineEdit().setCursorPosition(len(text))
        self._cmb_cliente.showPopup()

    def _add_cliente_to_combo(self, cliente: dict):
        """Agregar un cliente al combo si no esta ya presente."""
        cid = cliente["_id"]
        if self._cmb_cliente.findData(cid) >= 0:
            return
        nc = cliente.get("numero_carpeta", "")
        nc_label = f" [Carpeta {nc}]" if nc else ""
        label = f'{cliente.get("nombre_completo", "")} ({cliente.get("cuil", "")}){nc_label}'
        self._cmb_cliente.addItem(label, cid)
        self._clientes_cache.append(cliente)

    def _on_cliente_completer_activated(self, text: str):
        """Seleccionar el cliente del combo cuando se elige del autocompletado."""
        idx = self._cmb_cliente.findText(text)
        if idx >= 0:
            self._cmb_cliente.setCurrentIndex(idx)

    def _on_cliente_changed(self, index: int):
        """Actualizar N° de carpeta y claves al cambiar el cliente seleccionado."""
        cliente_id = self._cmb_cliente.currentData() or ""
        if not cliente_id:
            self._txt_carpeta_cliente.setText("")
            return
        # Buscar en cache local primero
        cliente = None
        for c in self._clientes_cache:
            if c["_id"] == cliente_id:
                cliente = c
                break
        # Fallback: buscar en BD
        if not cliente:
            cliente = ClienteController.get_by_id(cliente_id)
        if cliente:
            self._txt_carpeta_cliente.setText(str(cliente.get("numero_carpeta", "") or ""))
            if not self._txt_clave_mi_anses.text().strip():
                self._txt_clave_mi_anses.setText(cliente.get("clave_mi_anses", "") or "")
            if not self._txt_clave_fiscal.text().strip():
                self._txt_clave_fiscal.setText(cliente.get("clave_fiscal", "") or "")
        else:
            self._txt_carpeta_cliente.setText("")

    def _new_tarea(self):
        """Crear una nueva tarea pre-vinculada a este expediente."""
        from views.tareas.tarea_form import TareaFormDialog
        dlg = TareaFormDialog(expediente_id=self._id, parent=self)
        if dlg.exec():
            self._load_tab_tareas()

    def _new_turno(self):
        """Crear un nuevo turno pre-vinculado a este expediente."""
        from views.turnos.turno_form import TurnoFormDialog
        cliente_id = self._cmb_cliente.currentData() or ""
        dlg = TurnoFormDialog(
            expediente_id=self._id,
            cliente_id=cliente_id if cliente_id else None,
            parent=self
        )
        if dlg.exec():
            self._load_tab_turnos()

    def _new_comunicacion(self):
        """Crear una nueva comunicacion pre-vinculada a este expediente."""
        from views.comunicaciones.comunicacion_form import ComunicacionFormDialog
        dlg = ComunicacionFormDialog(expediente_id=self._id, parent=self)
        if dlg.exec():
            self._load_tab_comms()

    def _edit_comunicacion(self, comunicacion_id: str):
        """Editar una comunicacion existente."""
        from views.comunicaciones.comunicacion_form import ComunicacionFormDialog
        dlg = ComunicacionFormDialog(comunicacion_id=comunicacion_id, parent=self)
        if dlg.exec():
            self._load_tab_comms()

    def _new_documento(self):
        """Crear un nuevo documento pre-vinculado a este expediente."""
        from views.documentos.documento_form import DocumentoFormDialog
        dlg = DocumentoFormDialog(expediente_id=self._id, parent=self)
        if dlg.exec():
            self._load_tab_docs()

    def _edit_documento(self, doc_id: str):
        """Editar un documento existente."""
        from views.documentos.documento_form import DocumentoFormDialog
        dlg = DocumentoFormDialog(doc_id=doc_id, parent=self)
        if dlg.exec():
            self._load_tab_docs()

    def _new_movimiento(self):
        """Crear un nuevo movimiento pre-vinculado a este expediente y cliente."""
        from views.administracion.movimiento_form import MovimientoFormDialog
        cliente_id = self._cmb_cliente.currentData() or ""
        dlg = MovimientoFormDialog(
            expediente_id=self._id,
            cliente_id=cliente_id if cliente_id else None,
            parent=self
        )
        if dlg.exec():
            self._load_tab_movs()

    def _edit_movimiento(self, mov_id: str):
        """Editar un movimiento existente."""
        from views.administracion.movimiento_form import MovimientoFormDialog
        dlg = MovimientoFormDialog(movimiento_id=mov_id, parent=self)
        if dlg.exec():
            self._load_tab_movs()

    def _on_historial_double_click(self, audit_id: str):
        """Abre el detalle de un cambio del historial."""
        from views.auditoria.audit_detail import AuditDetailDialog
        dlg = AuditDetailDialog(audit_id, parent=self)
        dlg.exec()

    def _on_estado_changed(self, estado: str):
        """Habilitar campos de cierre solo cuando el estado es Cerrado o Archivado."""
        es_cierre = estado in ExpedienteController.ESTADOS_CIERRE
        self._date_cierre.setEnabled(es_cierre)
        self._txt_resultado.setEnabled(es_cierre)

    def _save(self):
        resp_username = self._cmb_responsable.currentData() or ""
        resp_display = self._cmb_responsable.currentText().strip()
        if not resp_username and not resp_display:
            QMessageBox.warning(self, "Atencion", "El responsable es obligatorio.")
            return

        resp2_username = self._cmb_responsable2.currentData() or ""

        estado = self._cmb_estado.currentText()

        # Regla de negocio: cierre formal requiere resultado
        if estado in ExpedienteController.ESTADOS_CIERRE:
            if not self._txt_resultado.text().strip():
                QMessageBox.warning(
                    self, "Atencion",
                    "Para cerrar una carpeta debe ingresar un resultado."
                )
                return

        # Regla de negocio: al mantener activo, advertir si no tiene tarea activa
        if (self._is_edit
                and estado not in ExpedienteController.ESTADOS_CIERRE
                and not ExpedienteController.tiene_tarea_activa(self._id)):
            resp = QMessageBox.warning(
                self, "Sin tarea activa",
                "Esta carpeta no tiene ninguna tarea activa.\n"
                "Toda carpeta activa deberia tener al menos una tarea pendiente.\n\n"
                "¿Desea guardar de todas formas?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if resp == QMessageBox.StandardButton.No:
                return

        # Nombre legible para compatibilidad
        responsable_legible = resp_display.split("(")[0].strip() if resp_username else resp_display
        resp2_legible = self._cmb_responsable2.currentText().split("(")[0].strip() if resp2_username else ""

        clave_mi_anses = self._txt_clave_mi_anses.text().strip()
        clave_fiscal = self._txt_clave_fiscal.text().strip()
        cliente_id = self._cmb_cliente.currentData() or ""

        data = {
            "id_cliente": cliente_id,
            "tipo_tramite": self._cmb_tipo.currentText(),
            "area": self._txt_area.text().strip(),
            "fecha_apertura": self._date_apertura.date().toString("yyyy-MM-dd"),
            "responsable": responsable_legible.upper(),
            "responsable_username": resp_username,
            "responsable_secundario": resp2_legible.upper(),
            "responsable_secundario_username": resp2_username,
            "estado": estado,
            "prioridad": self._cmb_prioridad.currentText(),
            "ubicacion_fisica": self._txt_ubicacion.text().strip(),
            "link_drive": self._txt_link_drive.text().strip(),
            "numero_expediente_anses": self._txt_nro_exp.text().strip(),
            "clave_mi_anses": clave_mi_anses,
            "clave_fiscal": clave_fiscal,
            "observaciones": self._txt_obs.toPlainText().strip(),
        }

        # Agregar datos de cierre formal si aplica
        if estado in ExpedienteController.ESTADOS_CIERRE:
            data["resultado"] = self._txt_resultado.text().strip()
            data["fecha_cierre"] = self._date_cierre.date().toString("yyyy-MM-dd")

        # Sincronizar claves al cliente (sin abortar si falla)
        if cliente_id and (clave_mi_anses or clave_fiscal):
            try:
                ClienteController.update(cliente_id, {
                    "clave_mi_anses": clave_mi_anses,
                    "clave_fiscal": clave_fiscal,
                })
            except Exception:
                logger.warning("Error al sincronizar claves al cliente %s", cliente_id, exc_info=True)

        if self._is_edit:
            ExpedienteController.update(self._id, data)
        else:
            ExpedienteController.create(data)
        self.accept()

    def closeEvent(self, event):
        if self._locked and self._id:
            LockManager.release_lock("expedientes", self._id)
        super().closeEvent(event)

    def reject(self):
        if self._locked and self._id:
            LockManager.release_lock("expedientes", self._id)
        super().reject()
