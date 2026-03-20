"""Formulario de alta/edicion de Carpeta."""
import json
import logging

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QTextEdit, QDateEdit, QPushButton, QLabel, QComboBox, QMessageBox,
    QTabWidget, QWidget, QCompleter, QScrollArea, QFrame, QCheckBox,
)
from PySide6.QtCore import Qt, QDate, QTimer
from PySide6.QtGui import QFont

logger = logging.getLogger(__name__)

from controllers.expediente_controller import ExpedienteController
from views.widgets.rama_datos_widget import RamaDatosWidget
from controllers.cliente_controller import ClienteController
from controllers.tarea_controller import TareaController
from controllers.turno_controller import TurnoController
from controllers.comunicacion_controller import ComunicacionController
from controllers.documento_controller import DocumentoController
from controllers.escrito_controller import EscritoController
from controllers.movimiento_controller import MovimientoController
from controllers.audit_controller import AuditController
from core.lock_manager import LockManager
from core.auth import Session
from core.permissions import tiene_permiso, get_active_users
from views.widgets.filterable_table import FilterableTable
from views.widgets.no_wheel_combo import NoWheelComboBox
from views.widgets.no_wheel_datetime import NoWheelDateEdit


class ExpedienteFormDialog(QDialog):
    def __init__(self, expediente_id: str = None, cliente_id: str = None, parent=None):
        super().__init__(parent)
        self.setObjectName("expedienteFormDialog")
        self._id = expediente_id
        self._prefill_cliente_id = cliente_id or ""
        self._is_edit = expediente_id is not None
        self._locked = False
        self._is_read_only = False
        self._loaded_tabs: set[int] = set()
        self._tabs: QTabWidget | None = None
        self._suspend_rama_rebuild = False
        self._original_responsable_username = ""
        self._original_responsable_display = ""
        self._original_responsable_secundario_username = ""
        self._original_responsable_secundario_display = ""

        self.setWindowTitle("Editar Carpeta" if self._is_edit else "Nueva Carpeta")
        self.setMinimumSize(800, 560)
        # Forzar tema claro y contraste alto en todo el formulario.
        self.setStyleSheet(
            """
            QDialog#expedienteFormDialog { background-color: #f5f5f5; }
            QDialog#expedienteFormDialog QLabel { color: #1a1a1a; background: transparent; }
            QDialog#expedienteFormDialog QScrollArea { background-color: #f5f5f5; border: none; }
            QDialog#expedienteFormDialog QWidget { background-color: #f5f5f5; }
            QDialog#expedienteFormDialog QLineEdit,
            QDialog#expedienteFormDialog QTextEdit,
            QDialog#expedienteFormDialog QComboBox,
            QDialog#expedienteFormDialog QDateEdit {
                background-color: #ffffff;
                color: #1a1a1a;
                border: 1px solid #cfcfcf;
                border-radius: 4px;
                padding: 4px 6px;
            }
            """
        )

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
        self._btn_save = QPushButton("Guardar")
        self._btn_save.clicked.connect(self._save)
        btn_layout.addWidget(self._btn_save)
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
        self._tab_map: dict[int, str] = {}

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
        self._turnos_table.row_double_clicked.connect(self._edit_turno)
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

        session = Session.get()

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
        self._can_delete_docs = session.rol in {"administrador", "superusuario"}
        if self._can_delete_docs:
            btn_del_doc = QPushButton("Eliminar Documento")
            btn_del_doc.setProperty("variant", "secondary")
            btn_del_doc.clicked.connect(self._delete_documento)
            docs_layout.addWidget(btn_del_doc, alignment=Qt.AlignmentFlag.AlignLeft)
        tabs.addTab(docs_widget, "Documentos")

        self._can_read_escritos = tiene_permiso(session.rol, "escritos.read")
        self._can_edit_escritos = tiene_permiso(session.rol, "escritos.update")
        self._can_create_escritos = tiene_permiso(session.rol, "escritos.create")

        # Tab Escritos (solo con permiso de lectura)
        if self._can_read_escritos:
            escritos_widget = QWidget()
            escritos_layout = QVBoxLayout(escritos_widget)
            self._escritos_table = FilterableTable([
                ("titulo", "Titulo"),
                ("fecha_creacion", "Fecha"),
                ("responsable", "Responsable"),
            ])
            if self._can_edit_escritos:
                self._escritos_table.row_double_clicked.connect(self._edit_escrito)
            escritos_layout.addWidget(self._escritos_table)
            if self._can_create_escritos:
                btn_new_escrito = QPushButton("+ Nuevo Escrito")
                btn_new_escrito.clicked.connect(self._new_escrito)
                escritos_layout.addWidget(btn_new_escrito, alignment=Qt.AlignmentFlag.AlignLeft)
            idx_escritos = tabs.count()
            tabs.addTab(escritos_widget, "Escritos")
            self._tab_map[idx_escritos] = "escritos"

        # Tab Movimientos (solo si el rol tiene permiso economico)
        self._has_movimientos = tiene_permiso(session.rol, "movimientos.read")

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
        self._lbl_clave_mi_anses = QLabel("Clave Mi ANSES:")
        form.addRow(self._lbl_clave_mi_anses, self._txt_clave_mi_anses)

        self._txt_clave_fiscal = QLineEdit()
        self._txt_clave_fiscal.setPlaceholderText("Clave fiscal AFIP del cliente")
        self._txt_clave_fiscal.setFixedHeight(30)
        self._txt_clave_fiscal.setStyleSheet(
            "background-color: #2a2a2a; color: #c9a84c; font-weight: bold;"
            " font-size: 13px; padding: 4px 6px;"
        )
        self._lbl_clave_fiscal = QLabel("Clave Fiscal:")
        form.addRow(self._lbl_clave_fiscal, self._txt_clave_fiscal)

        # Ocultar claves por defecto (solo visibles para rama Previsional)
        self._set_claves_visible(False)
        if (not self._is_edit) and self._prefill_cliente_id:
            cliente_prefill = ClienteController.get_by_id(self._prefill_cliente_id)
            if cliente_prefill:
                self._add_cliente_to_combo(cliente_prefill)
                idx_prefill = self._cmb_cliente.findData(self._prefill_cliente_id)
                if idx_prefill >= 0:
                    self._cmb_cliente.setCurrentIndex(idx_prefill)
                    self._on_cliente_changed(idx_prefill)

        # ── Seccion: Tramite ──
        form.addRow(self._make_separator("TRAMITE"))

        self._cmb_tipo = QComboBox()
        for t in ExpedienteController.TIPOS_TRAMITE:
            self._cmb_tipo.addItem(t)
        form.addRow("Tipo tramite *:", self._cmb_tipo)

        self._cmb_rama = QComboBox()
        self._cmb_rama.addItem("")
        for r in ExpedienteController.RAMAS:
            self._cmb_rama.addItem(r)
        self._cmb_rama.currentTextChanged.connect(self._on_rama_changed)
        form.addRow("Rama:", self._cmb_rama)

        self._lbl_modalidad = QLabel("Modalidad de inicio:")
        self._cmb_modalidad = QComboBox()
        for modalidad in ExpedienteController.MODALIDADES:
            self._cmb_modalidad.addItem(modalidad)
        self._lbl_modalidad.setVisible(False)
        self._cmb_modalidad.setVisible(False)
        form.addRow(self._lbl_modalidad, self._cmb_modalidad)

        self._cmb_subtipo = QComboBox()
        self._cmb_subtipo.addItem("-- Seleccionar subtipo --")
        self._cmb_subtipo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._cmb_subtipo.setMinimumContentsLength(24)
        self._cmb_subtipo.setMinimumWidth(240)
        form.addRow("Subtipo:", self._cmb_subtipo)

        self._date_apertura = NoWheelDateEdit()
        self._date_apertura.setCalendarPopup(True)
        self._date_apertura.setDate(QDate.currentDate())
        self._date_apertura.setDisplayFormat("dd/MM/yyyy")
        form.addRow("Fecha apertura:", self._date_apertura)

        # ── Seccion: Datos especificos de la rama ──
        self._rama_separator = self._make_separator("DATOS ESPECIFICOS")
        self._rama_separator.setVisible(False)
        form.addRow(self._rama_separator)

        self._rama_datos_container = QWidget()
        self._rama_datos_layout = QVBoxLayout(self._rama_datos_container)
        self._rama_datos_layout.setContentsMargins(0, 0, 0, 0)
        self._rama_datos_widget: RamaDatosWidget | None = None
        self._rama_datos_container.setVisible(False)
        form.addRow(self._rama_datos_container)
        self._cmb_modalidad.currentTextChanged.connect(self._on_modalidad_changed)

        # ── Seccion: Modulo Judicial ──
        form.addRow(self._make_separator("MODULO JUDICIAL"))

        self._chk_judicializado = QCheckBox("Caso judicializado")
        self._chk_judicializado.toggled.connect(self._on_judicializado_changed)
        form.addRow(self._chk_judicializado)

        self._judicial_container = QWidget()
        judicial_layout = QVBoxLayout(self._judicial_container)
        judicial_layout.setContentsMargins(0, 0, 0, 0)
        self._judicial_widget = RamaDatosWidget(ExpedienteController.CAMPOS_JUDICIAL)
        judicial_layout.addWidget(self._judicial_widget)
        self._judicial_container.setVisible(False)
        form.addRow(self._judicial_container)

        # ── Seccion: Responsables ──
        form.addRow(self._make_separator("RESPONSABLES"))

        self._cmb_responsable = NoWheelComboBox()
        self._cmb_responsable.setEditable(True)
        self._cmb_responsable.setPlaceholderText("Seleccionar responsable...")
        self._cmb_responsable2 = NoWheelComboBox()
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

        self._cmb_resultado = QComboBox()
        self._cmb_resultado.addItem("-- Seleccionar resultado --", "")
        for r in ["Favorable", "Parcial", "Desfavorable", "Acuerdo"]:
            self._cmb_resultado.addItem(r, r)
        form.addRow("Resultado:", self._cmb_resultado)

        self._date_cierre = NoWheelDateEdit()
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
            self._set_read_only_ui()
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

        # Cargar rama y subtipo
        rama = data.get("rama", "") or ""
        modalidad = (data.get("modalidad", "") or "").strip()
        if rama:
            # Evita doble rebuild en apertura de edición (rama->modalidad)
            self._suspend_rama_rebuild = True
            self._cmb_rama.setCurrentText(rama)
            if rama in ExpedienteController.RAMAS_CON_MODALIDAD and modalidad in ExpedienteController.MODALIDADES:
                self._cmb_modalidad.setCurrentText(modalidad)
            elif rama in ExpedienteController.RAMAS_CON_MODALIDAD:
                self._cmb_modalidad.setCurrentText(ExpedienteController.MODALIDADES[0])
            self._suspend_rama_rebuild = False
            self._rebuild_rama_datos_widget(preserve_data=False)
        subtipo = data.get("subtipo", "") or ""
        if subtipo:
            self._cmb_subtipo.setCurrentText(subtipo)

        # Cargar datos específicos de la rama
        datos_rama = data.get("datos_rama")
        if isinstance(datos_rama, str):
            try:
                datos_rama = json.loads(datos_rama)
            except (json.JSONDecodeError, ValueError):
                datos_rama = {}
        if datos_rama and self._rama_datos_widget:
            self._rama_datos_widget.set_data(datos_rama)

        # Cargar módulo judicial
        datos_judicial = data.get("datos_judicial")
        if isinstance(datos_judicial, str):
            try:
                datos_judicial = json.loads(datos_judicial)
            except (json.JSONDecodeError, ValueError):
                datos_judicial = {}
        if datos_judicial and isinstance(datos_judicial, dict):
            self._chk_judicializado.setChecked(True)
            self._judicial_widget.set_data(datos_judicial)
        else:
            self._chk_judicializado.setChecked(False)
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
        self._original_responsable_username = data.get("responsable_username", "") or ""
        self._original_responsable_display = data.get("responsable", "") or ""

        resp2_uname = data.get("responsable_secundario_username", "")
        idx_r2 = self._cmb_responsable2.findData(resp2_uname)
        if idx_r2 >= 0:
            self._cmb_responsable2.setCurrentIndex(idx_r2)
        elif data.get("responsable_secundario", ""):
            self._cmb_responsable2.setEditText(data.get("responsable_secundario", ""))
        self._original_responsable_secundario_username = data.get("responsable_secundario_username", "") or ""
        self._original_responsable_secundario_display = data.get("responsable_secundario", "") or ""
        self._cmb_estado.setCurrentText(data.get("estado", "Activo"))
        self._cmb_prioridad.setCurrentText(data.get("prioridad", "Normal"))
        self._txt_ubicacion.setText(data.get("ubicacion_fisica", ""))
        self._txt_link_drive.setText(data.get("link_drive", ""))
        self._txt_nro_exp.setText(data.get("numero_expediente_anses", ""))
        resultado = data.get("resultado", "") or ""
        idx_res = self._cmb_resultado.findData(resultado)
        if idx_res >= 0:
            self._cmb_resultado.setCurrentIndex(idx_res)
        elif resultado:
            # Compatibilidad con resultados historicos de texto libre
            self._cmb_resultado.addItem(resultado, resultado)
            self._cmb_resultado.setCurrentIndex(self._cmb_resultado.count() - 1)
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
            if tab_name == "escritos":
                self._load_tab_escritos()
            elif tab_name == "movimientos":
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
        expediente = ExpedienteController.get_by_id(self._id) or {}
        expected_cliente_id = expediente.get("id_cliente", "") or ""
        if expected_cliente_id:
            turnos = [
                t for t in turnos
                if (t.get("id_cliente", "") or "") == expected_cliente_id
            ]
        self._turnos_table.set_data(turnos)

    def _load_tab_comms(self):
        comms = ComunicacionController.get_by_expediente(self._id)
        self._comms_table.set_data(comms)

    def _load_tab_docs(self):
        docs = DocumentoController.get_by_expediente(self._id)
        self._docs_table.set_data(docs)

    def _load_tab_escritos(self):
        escritos = EscritoController.get_by_expediente(self._id)
        self._escritos_table.set_data(escritos)

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

    def _edit_turno(self, turno_id: str):
        """Editar un turno ANSES existente desde la pestaña de la carpeta."""
        from views.turnos.turno_form import TurnoFormDialog
        dlg = TurnoFormDialog(turno_id=turno_id, parent=self)
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

    def _delete_documento(self):
        """Eliminar (soft delete) un documento de la carpeta actual."""
        if not getattr(self, "_can_delete_docs", False):
            QMessageBox.warning(self, "Sin permisos", "No tiene permisos para eliminar documentos.")
            return
        doc_id = self._docs_table.get_selected_id()
        if not doc_id:
            QMessageBox.information(self, "Atencion", "Seleccione un documento.")
            return
        ok = QMessageBox.question(
            self,
            "Confirmar",
            "Eliminar este documento? Esta accion ocultara el documento del sistema.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ok != QMessageBox.StandardButton.Yes:
            return
        if DocumentoController.delete(doc_id):
            QMessageBox.information(self, "Ok", "Documento eliminado correctamente.")
            self._load_tab_docs()
        else:
            QMessageBox.warning(self, "Error", "No se pudo eliminar el documento.")

    def _new_escrito(self):
        """Crear un escrito desde un modelo y abrir editor rich text."""
        from views.escritos.modelo_selector import ModeloSelectorDialog
        dlg = ModeloSelectorDialog(
            id_expediente=self._id,
            rama=self._cmb_rama.currentText().strip(),
            parent=self,
        )
        if dlg.exec():
            self._load_tab_escritos()

    def _edit_escrito(self, escrito_id: str):
        """Editar escrito existente."""
        from views.escritos.escrito_editor import EscritoEditorDialog
        dlg = EscritoEditorDialog(escrito_id, parent=self)
        if dlg.exec():
            self._load_tab_escritos()

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

    def _set_claves_visible(self, visible: bool):
        """Muestra u oculta los campos de Clave Mi ANSES y Clave Fiscal."""
        self._lbl_clave_mi_anses.setVisible(visible)
        self._txt_clave_mi_anses.setVisible(visible)
        self._lbl_clave_fiscal.setVisible(visible)
        self._txt_clave_fiscal.setVisible(visible)

    def _on_rama_changed(self, rama: str):
        """Actualiza subtipos disponibles y regenera los campos específicos de la rama."""
        self._cmb_subtipo.blockSignals(True)
        self._cmb_subtipo.clear()
        self._cmb_subtipo.addItem("-- Seleccionar subtipo --")
        subtipos = ExpedienteController.SUBTIPOS_POR_RAMA.get(rama, [])
        for s in subtipos:
            self._cmb_subtipo.addItem(s)
        self._cmb_subtipo.blockSignals(False)

        # Claves ANSES/Fiscal solo para rama Previsional
        self._set_claves_visible(rama == "Previsional")

        self._update_modalidad_visibility(rama)
        if not self._suspend_rama_rebuild:
            self._rebuild_rama_datos_widget(preserve_data=False)

    def _on_modalidad_changed(self, _modalidad: str):
        """Regenera campos de rama para aplicar campos exclusivos virtuales."""
        if not self._suspend_rama_rebuild:
            self._rebuild_rama_datos_widget(preserve_data=True)

    def _update_modalidad_visibility(self, rama: str):
        mostrar = rama in ExpedienteController.RAMAS_CON_MODALIDAD
        self._lbl_modalidad.setVisible(mostrar)
        self._cmb_modalidad.setVisible(mostrar)
        if mostrar and self._cmb_modalidad.currentText() not in ExpedienteController.MODALIDADES:
            self._cmb_modalidad.setCurrentText(ExpedienteController.MODALIDADES[0])

    def _get_rama_fields_for_current_context(self, rama: str) -> list[dict]:
        campos = ExpedienteController.CAMPOS_POR_RAMA.get(rama, [])
        if rama not in ExpedienteController.RAMAS_CON_MODALIDAD:
            return campos
        if self._cmb_modalidad.currentText() == "Virtual":
            return campos
        return [c for c in campos if not c.get("solo_virtual")]

    def _rebuild_rama_datos_widget(self, preserve_data: bool):
        previous_data = {}
        if preserve_data and self._rama_datos_widget:
            previous_data = self._rama_datos_widget.get_data()

        # Regenerar widget de datos específicos
        if self._rama_datos_widget:
            self._rama_datos_layout.removeWidget(self._rama_datos_widget)
            self._rama_datos_widget.deleteLater()
            self._rama_datos_widget = None

        rama = self._cmb_rama.currentText().strip()
        campos = self._get_rama_fields_for_current_context(rama)
        if campos:
            self._rama_datos_widget = RamaDatosWidget(campos)
            if previous_data:
                self._rama_datos_widget.set_data(previous_data)
            self._rama_datos_layout.addWidget(self._rama_datos_widget)
            self._rama_datos_container.setVisible(True)
            self._rama_separator.setVisible(True)
        else:
            self._rama_datos_container.setVisible(False)
            self._rama_separator.setVisible(False)

    def _on_judicializado_changed(self, checked: bool):
        """Muestra u oculta los campos del módulo judicial."""
        self._judicial_container.setVisible(checked)

    def _on_estado_changed(self, estado: str):
        """Habilitar campos de cierre solo cuando el estado es Cerrado o Archivado."""
        es_cierre = estado in ExpedienteController.ESTADOS_CIERRE
        self._date_cierre.setEnabled(es_cierre)
        self._cmb_resultado.setEnabled(es_cierre)

    def _save(self):
        if self._is_read_only:
            QMessageBox.warning(
                self,
                "Registro bloqueado",
                "Esta carpeta esta en modo solo lectura porque se encuentra bloqueada.",
            )
            return
        resp_username = self._cmb_responsable.currentData() or ""
        resp_display = self._cmb_responsable.currentText().strip()
        if not resp_username and not resp_display:
            QMessageBox.warning(self, "Atencion", "El responsable es obligatorio.")
            return

        resp2_username = self._cmb_responsable2.currentData() or ""

        if self._is_edit:
            old_primary = (self._original_responsable_username or self._original_responsable_display).strip().lower()
            new_primary = (resp_username or resp_display).strip().lower()
            old_secondary = (
                self._original_responsable_secundario_username
                or self._original_responsable_secundario_display
            ).strip().lower()
            new_secondary = (
                resp2_username or self._cmb_responsable2.currentText().strip()
            ).strip().lower()
            changed_primary = old_primary != new_primary
            changed_secondary = old_secondary != new_secondary
            if changed_primary or changed_secondary:
                mensaje = "Esta por cambiar el responsable de la carpeta."
                if changed_primary and changed_secondary:
                    mensaje = (
                        "Esta por cambiar el responsable principal y secundario de la carpeta."
                    )
                elif changed_secondary:
                    mensaje = "Esta por cambiar el responsable secundario de la carpeta."
                resp = QMessageBox.warning(
                    self,
                    "Confirmar cambio de responsable",
                    f"{mensaje}\n\nDesea confirmar este cambio?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if resp != QMessageBox.StandardButton.Yes:
                    return

        estado = self._cmb_estado.currentText()

        # Regla de negocio: cierre formal requiere resultado
        if estado in ExpedienteController.ESTADOS_CIERRE:
            if not (self._cmb_resultado.currentData() or "").strip():
                QMessageBox.warning(
                    self, "Atencion",
                    "Para cerrar una carpeta debe seleccionar un resultado."
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

        # Recolectar datos de rama
        rama = self._cmb_rama.currentText()
        subtipo = self._cmb_subtipo.currentText()
        if subtipo == "-- Seleccionar subtipo --":
            subtipo = ""
        datos_rama = {}
        if self._rama_datos_widget:
            datos_rama = self._rama_datos_widget.get_data()
        modalidad = ""
        if rama in ExpedienteController.RAMAS_CON_MODALIDAD:
            modalidad = self._cmb_modalidad.currentText().strip() or ExpedienteController.MODALIDADES[0]
            if modalidad != "Virtual":
                virtual_keys = {
                    c["key"]
                    for c in ExpedienteController.CAMPOS_POR_RAMA.get(rama, [])
                    if c.get("solo_virtual")
                }
                datos_rama = {k: v for k, v in datos_rama.items() if k not in virtual_keys}

        # Recolectar datos judiciales
        datos_judicial = {}
        if self._chk_judicializado.isChecked():
            datos_judicial = self._judicial_widget.get_data()

        data = {
            "id_cliente": cliente_id,
            "tipo_tramite": self._cmb_tipo.currentText(),
            "area": rama,
            "rama": rama,
            "subtipo": subtipo,
            "datos_rama": datos_rama,
            "modalidad": modalidad,
            "datos_judicial": datos_judicial if datos_judicial else "",
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
            data["resultado"] = (self._cmb_resultado.currentData() or "").strip()
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

    def _set_read_only_ui(self):
        """Pone el formulario en solo lectura cuando el lock no se pudo adquirir."""
        self._is_read_only = True
        self._btn_save.setEnabled(False)
        self._btn_save.setToolTip("No disponible: registro bloqueado por otro usuario.")
        widgets = self.findChildren((QLineEdit, QTextEdit, QDateEdit, QComboBox, QCheckBox))
        for w in widgets:
            w.setEnabled(False)
