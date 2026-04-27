"""Formulario de alta/edicion de Carpeta."""
import json
import logging
from datetime import date
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QTextEdit, QDateEdit, QPushButton, QLabel, QComboBox, QMessageBox,
    QTabWidget, QWidget, QCompleter, QScrollArea, QFrame, QCheckBox,
    QGroupBox, QSpinBox,
)
from PySide6.QtCore import Qt, QDate, QTimer, QUrl
from PySide6.QtGui import QFont, QColor, QDesktopServices

logger = logging.getLogger(__name__)

from controllers.expediente_controller import ExpedienteController
from views.widgets.rama_datos_widget import RamaDatosWidget
from views.widgets.expedientes_referencia_widget import ExpedientesReferenciaWidget
from controllers.cliente_controller import ClienteController
from controllers.tarea_controller import TareaController
from controllers.turno_controller import TurnoController
from controllers.comunicacion_controller import ComunicacionController
from controllers.documento_controller import DocumentoController
from controllers.escrito_controller import EscritoController
from controllers.movimiento_controller import MovimientoController
from controllers.audit_controller import AuditController
from core import db_local
from core.lock_manager import LockManager
from core.auth import Session
from core.permissions import tiene_permiso, get_active_users_fresh
from views.widgets.filterable_table import FilterableTable
from views.widgets.no_wheel_combo import NoWheelComboBox
from views.widgets.no_wheel_datetime import NoWheelDateEdit
from views.widgets.expediente_etapas_timeline import ExpedienteEtapasTimeline
from views.widgets.click_copy_line_edit import ClickCopyLineEdit, CLICK_COPY_CLAVE_STYLESHEET
from controllers.expediente_recordatorio_controller import ExpedienteRecordatorioController
from core.dias_habiles import restar_dias_habiles
from controllers.expediente_etapa_responsable_controller import ExpedienteEtapaResponsableController
from controllers.expediente_estado_controller import get_segmento_abierto


class RecordatorioEditDialog(QDialog):
    """Alta o edicion de un recordatorio / hito de carpeta."""

    def __init__(
        self,
        parent=None,
        *,
        users: list[dict],
        initial: dict | None = None,
        default_etapa_codigo: str = "",
        fecha_referencia_inicial: str | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Editar recordatorio" if initial else "Nuevo recordatorio")
        self._initial = initial
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._date_ref = NoWheelDateEdit()
        self._date_ref.setCalendarPopup(True)
        self._date_ref.setDisplayFormat("dd/MM/yyyy")
        if (fecha_referencia_inicial or "").strip():
            self._date_ref.setDate(
                QDate.fromString(fecha_referencia_inicial[:10], "yyyy-MM-dd")
            )
        else:
            self._date_ref.setDate(QDate.currentDate())
        form.addRow(
            "Fecha de referencia (vencimiento / plazo):",
            self._date_ref,
        )
        grp_hab = QGroupBox("Calcular fecha de disparo en dias habiles (Argentina)")
        hab_layout = QVBoxLayout(grp_hab)
        row_presets = QHBoxLayout()
        btn30 = QPushButton("30 dias habiles antes")
        btn30.clicked.connect(lambda: self._aplicar_dias_habiles(30))
        btn60 = QPushButton("60 dias habiles antes")
        btn60.clicked.connect(lambda: self._aplicar_dias_habiles(60))
        row_presets.addWidget(btn30)
        row_presets.addWidget(btn60)
        hab_layout.addLayout(row_presets)
        row_custom = QHBoxLayout()
        row_custom.addWidget(QLabel("Otros (dias habiles):"))
        self._spin_habiles = QSpinBox()
        self._spin_habiles.setRange(1, 365)
        self._spin_habiles.setValue(45)
        row_custom.addWidget(self._spin_habiles)
        btn_aplicar = QPushButton("Aplicar")
        btn_aplicar.clicked.connect(self._aplicar_spin_habiles)
        row_custom.addWidget(btn_aplicar)
        row_custom.addStretch()
        hab_layout.addLayout(row_custom)
        lbl_info = QLabel(
            "La fecha de disparo sera N dias habiles antes de la fecha de referencia "
            "(sin contar sabados, domingos ni feriados nacionales)."
        )
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet("color: #555; font-size: 11px;")
        hab_layout.addWidget(lbl_info)
        form.addRow(grp_hab)
        self._date = NoWheelDateEdit()
        self._date.setCalendarPopup(True)
        self._date.setDisplayFormat("dd/MM/yyyy")
        if initial and (initial.get("fecha_disparo") or "").strip():
            self._date.setDate(
                QDate.fromString(initial["fecha_disparo"][:10], "yyyy-MM-dd")
            )
        else:
            self._date.setDate(QDate.currentDate())
        form.addRow("Fecha de disparo:", self._date)
        self._cmb_etapa_rec = NoWheelComboBox()
        self._cmb_etapa_rec.addItem("(sin etapa vinculada)", "")
        for et in ExpedienteController.ETAPAS:
            self._cmb_etapa_rec.addItem(et["titulo"], et["codigo"])
        ExpedienteController.aplicar_colores_items_combo_etapas(self._cmb_etapa_rec)
        ec = (initial or {}).get("etapa_codigo", "") or ""
        if not ec and (default_etapa_codigo or "").strip():
            ec = default_etapa_codigo.strip()
        idx_e = self._cmb_etapa_rec.findData(ec)
        if idx_e >= 0:
            self._cmb_etapa_rec.setCurrentIndex(idx_e)
        form.addRow("Etapa (opcional):", self._cmb_etapa_rec)
        self._chk_critico = QCheckBox("Plazo critico (prioridad en avisos y panel)")
        self._chk_critico.setChecked(bool(int((initial or {}).get("es_critico", 0) or 0)))
        form.addRow("", self._chk_critico)
        self._titulo = QLineEdit()
        self._titulo.setText((initial or {}).get("titulo", "") or "")
        form.addRow("Titulo:", self._titulo)
        self._mensaje = QTextEdit()
        self._mensaje.setMaximumHeight(100)
        self._mensaje.setPlainText((initial or {}).get("mensaje", "") or "")
        form.addRow("Mensaje:", self._mensaje)
        self._cmb_user = NoWheelComboBox()
        self._cmb_user.setEditable(True)
        self._cmb_user.setPlaceholderText("Usuario a notificar...")
        self._cmb_user.addItem("-- Usar responsable de la carpeta --", "")
        for u in users:
            label = f'{u.get("nombre_completo", "")} ({u.get("username", "")})'
            self._cmb_user.addItem(label, u.get("username", ""))
        un = (initial or {}).get("notificar_a_username", "") or ""
        idx = self._cmb_user.findData(un)
        if idx >= 0:
            self._cmb_user.setCurrentIndex(idx)
        form.addRow("Notificar a:", self._cmb_user)
        layout.addLayout(form)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setProperty("variant", "secondary")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Guardar")
        btn_ok.clicked.connect(self._on_accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def _qdate_to_pydate(self, qd: QDate) -> date:
        return date(qd.year(), qd.month(), qd.day())

    def _set_fecha_disparo_qdate(self, d: date) -> None:
        self._date.setDate(QDate(d.year, d.month, d.day))

    def _aplicar_dias_habiles(self, n: int) -> None:
        ref = self._qdate_to_pydate(self._date_ref.date())
        calc = restar_dias_habiles(ref, n)
        self._set_fecha_disparo_qdate(calc)

    def _aplicar_spin_habiles(self) -> None:
        self._aplicar_dias_habiles(self._spin_habiles.value())

    def _on_accept(self):
        if not self._titulo.text().strip():
            QMessageBox.warning(self, "Atencion", "Indique un titulo para el recordatorio.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "fecha_disparo": self._date.date().toString("yyyy-MM-dd"),
            "titulo": self._titulo.text().strip(),
            "mensaje": self._mensaje.toPlainText().strip(),
            "notificar_a_username": self._cmb_user.currentData() or "",
            "etapa_codigo": self._cmb_etapa_rec.currentData() or "",
            "es_critico": 1 if self._chk_critico.isChecked() else 0,
        }


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
        self._original_etapa_codigo = ""

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
        btn_cancel.setObjectName("expediente_readonly_allow_close")
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
        self._tareas_table.row_double_clicked.connect(self._edit_tarea)
        tareas_layout.addWidget(self._tareas_table)
        btn_new_tarea = QPushButton("+ Nueva Tarea")
        btn_new_tarea.clicked.connect(self._new_tarea)
        tareas_layout.addWidget(btn_new_tarea, alignment=Qt.AlignmentFlag.AlignLeft)
        tabs.addTab(tareas_widget, "Movimientos")

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
            ("constancia_label", "Constancia"),
        ])
        self._turnos_table.row_double_clicked.connect(self._edit_turno)
        self._turnos_table.row_selected.connect(self._on_turno_row_selected)
        turnos_layout.addWidget(self._turnos_table)
        turnos_btn_row = QHBoxLayout()
        btn_new_turno = QPushButton("+ Nuevo Turno")
        btn_new_turno.clicked.connect(self._new_turno)
        turnos_btn_row.addWidget(btn_new_turno, alignment=Qt.AlignmentFlag.AlignLeft)
        self._btn_turno_abrir_constancia = QPushButton("Abrir constancia PDF")
        self._btn_turno_abrir_constancia.setToolTip(
            "Abre el PDF de constancia del turno seleccionado (si existe)."
        )
        self._btn_turno_abrir_constancia.clicked.connect(self._open_turno_constancia_pdf)
        self._btn_turno_abrir_constancia.setEnabled(False)
        turnos_btn_row.addWidget(self._btn_turno_abrir_constancia)
        turnos_btn_row.addStretch()
        turnos_layout.addLayout(turnos_btn_row)
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

        # Tab Recordatorios / Hitos
        rec_widget = QWidget()
        rec_layout = QVBoxLayout(rec_widget)
        self._recordatorios_table = FilterableTable([
            ("fecha_disparo", "Fecha disparo"),
            ("titulo", "Titulo"),
            ("etapa_label", "Etapa"),
            ("critico", "Crit."),
            ("mensaje_preview", "Mensaje"),
            ("notificar_a", "Notificar a"),
            ("estado", "Estado"),
        ])
        self._recordatorios_table.row_double_clicked.connect(self._edit_recordatorio)
        rec_layout.addWidget(self._recordatorios_table)
        rec_btns = QHBoxLayout()
        btn_new_rec = QPushButton("+ Nuevo recordatorio")
        btn_new_rec.clicked.connect(self._new_recordatorio)
        btn_del_rec = QPushButton("Eliminar")
        btn_del_rec.setProperty("variant", "secondary")
        btn_del_rec.clicked.connect(self._delete_recordatorio)
        rec_btns.addWidget(btn_new_rec, alignment=Qt.AlignmentFlag.AlignLeft)
        rec_btns.addWidget(btn_del_rec, alignment=Qt.AlignmentFlag.AlignLeft)
        rec_btns.addStretch()
        rec_layout.addLayout(rec_btns)
        tabs.addTab(rec_widget, "Recordatorios")

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

        # Tab 5 - Calculo Derecho
        calc_widget = QWidget()
        calc_layout = QVBoxLayout(calc_widget)
        self._txt_calculo_nota = QTextEdit()
        self._txt_calculo_nota.setMaximumHeight(80)
        self._txt_calculo_nota.setPlaceholderText(
            "Breve descripcion del calculo de derecho (monto estimado, criterios, etc.)."
        )
        calc_layout.addWidget(self._txt_calculo_nota)
        self._calc_docs_table = FilterableTable([
            ("nombre", "Nombre"),
            ("categoria", "Categoria"),
            ("fecha", "Fecha"),
            ("responsable", "Responsable"),
        ])
        self._calc_docs_table.row_double_clicked.connect(self._edit_calculo_documento)
        calc_layout.addWidget(self._calc_docs_table)
        btn_new_calc_doc = QPushButton("+ Nuevo Documento")
        btn_new_calc_doc.clicked.connect(self._new_calculo_documento)
        calc_layout.addWidget(btn_new_calc_doc, alignment=Qt.AlignmentFlag.AlignLeft)
        if self._can_delete_docs:
            btn_del_calc_doc = QPushButton("Eliminar Documento")
            btn_del_calc_doc.setProperty("variant", "secondary")
            btn_del_calc_doc.clicked.connect(self._delete_calculo_documento)
            calc_layout.addWidget(btn_del_calc_doc, alignment=Qt.AlignmentFlag.AlignLeft)
        idx_calc = tabs.count()
        tabs.addTab(calc_widget, "Calculo Derecho")
        tabs.tabBar().setTabTextColor(idx_calc, QColor("#c9a84c"))

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
            tabs.addTab(movs_widget, "Contable")
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
            tabs.addTab(historial_widget, "Historial de tiempos")
            self._tab_map[idx_hist] = "historial"
            self._has_historial = True
        else:
            self._has_historial = False

        self._reorder_tabs(tabs)
        tabs.currentChanged.connect(self._on_tab_changed)
        parent_layout.addWidget(tabs)

    def _reorder_tabs(self, tabs: QTabWidget):
        desired_order = [
            "Datos",
            "Movimientos",
            "Calculo Derecho",
            "Turnos ANSES",
            "Documentos",
            "Comunicaciones",
            "Recordatorios",
            "Escritos",
            "Contable",
            "Tiempos",
            "Historial de tiempos",
        ]
        for target_idx, target_name in enumerate(desired_order):
            current_idx = next(
                (i for i in range(tabs.count()) if tabs.tabText(i) == target_name),
                -1,
            )
            if current_idx >= 0 and current_idx != target_idx:
                tab_widget = tabs.widget(current_idx)
                icon = tabs.tabIcon(current_idx)
                tab_text = tabs.tabText(current_idx)
                tooltip = tabs.tabToolTip(current_idx)
                whats_this = tabs.tabWhatsThis(current_idx)
                text_color = tabs.tabBar().tabTextColor(current_idx)
                tabs.removeTab(current_idx)
                tabs.insertTab(target_idx, tab_widget, icon, tab_text)
                tabs.setTabToolTip(target_idx, tooltip)
                tabs.setTabWhatsThis(target_idx, whats_this)
                tabs.tabBar().setTabTextColor(target_idx, text_color)

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
        cliente_row = QWidget()
        cliente_row_lay = QHBoxLayout(cliente_row)
        cliente_row_lay.setContentsMargins(0, 0, 0, 0)
        cliente_row_lay.setSpacing(6)
        cliente_row_lay.addWidget(self._cmb_cliente, 1)
        self._btn_ir_cliente = QPushButton("Ir a cliente")
        self._btn_ir_cliente.setToolTip("Abrir ficha del cliente seleccionado")
        self._btn_ir_cliente.clicked.connect(self._open_selected_cliente)
        cliente_row_lay.addWidget(self._btn_ir_cliente)
        form.addRow("Cliente:", cliente_row)

        self._txt_cuil_cliente = ClickCopyLineEdit()
        self._txt_cuil_cliente.setReadOnly(True)
        self._txt_cuil_cliente.setPlaceholderText("CUIL/CUIT del cliente (clic para copiar)")
        self._txt_cuil_cliente.setFixedHeight(30)
        self._txt_cuil_cliente.setStyleSheet(CLICK_COPY_CLAVE_STYLESHEET)
        form.addRow("CUIL/CUIT:", self._txt_cuil_cliente)

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
        self._sync_ir_cliente_button_state()

        self._txt_clave_mi_anses = ClickCopyLineEdit()
        self._txt_clave_mi_anses.setPlaceholderText("Clave de Mi ANSES del cliente")
        self._txt_clave_mi_anses.setFixedHeight(30)
        self._txt_clave_mi_anses.setStyleSheet(CLICK_COPY_CLAVE_STYLESHEET)
        self._lbl_clave_mi_anses = QLabel("Clave Mi ANSES:")
        form.addRow(self._lbl_clave_mi_anses, self._txt_clave_mi_anses)

        self._txt_clave_fiscal = ClickCopyLineEdit()
        self._txt_clave_fiscal.setPlaceholderText("Clave fiscal AFIP del cliente")
        self._txt_clave_fiscal.setFixedHeight(30)
        self._txt_clave_fiscal.setStyleSheet(CLICK_COPY_CLAVE_STYLESHEET)
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
        self._rama_separator.setVisible(True)
        form.addRow(self._rama_separator)

        self._rama_datos_container = QWidget()
        self._rama_datos_layout = QVBoxLayout(self._rama_datos_container)
        self._rama_datos_layout.setContentsMargins(0, 0, 0, 0)
        self._rama_datos_widget: RamaDatosWidget | None = None
        self._expedientes_ref_widget = ExpedientesReferenciaWidget()
        self._rama_datos_layout.addWidget(self._expedientes_ref_widget)
        self._rama_datos_container.setVisible(True)
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
        self._cmb_responsable.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._cmb_responsable.setPlaceholderText("Seleccionar responsable...")
        self._cmb_responsable2 = NoWheelComboBox()
        self._cmb_responsable2.setEditable(True)
        self._cmb_responsable2.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._cmb_responsable2.setPlaceholderText("Seleccionar resp. secundario...")
        self._cmb_responsable2.addItem("-- Sin resp. secundario --", "")
        users = get_active_users_fresh()
        for u in users:
            label = f'{u.get("nombre_completo", "")} ({u.get("username", "")})'
            uname = u.get("username", "")
            self._cmb_responsable.addItem(label, uname)
            self._cmb_responsable2.addItem(label, uname)
        resp_primary_completer = QCompleter(self)
        resp_primary_completer.setModel(self._cmb_responsable.model())
        resp_primary_completer.setCompletionColumn(0)
        resp_primary_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        resp_primary_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        resp_primary_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        resp_primary_completer.activated[str].connect(self._on_responsable_completer_activated)
        self._cmb_responsable.setCompleter(resp_primary_completer)

        resp_secondary_completer = QCompleter(self)
        resp_secondary_completer.setModel(self._cmb_responsable2.model())
        resp_secondary_completer.setCompletionColumn(0)
        resp_secondary_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        resp_secondary_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        resp_secondary_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        resp_secondary_completer.activated[str].connect(self._on_responsable_secundario_completer_activated)
        self._cmb_responsable2.setCompleter(resp_secondary_completer)
        form.addRow("Responsable *:", self._cmb_responsable)
        form.addRow("Resp. secundario:", self._cmb_responsable2)

        # ── Seccion: Estado ──
        form.addRow(self._make_separator("ESTADO"))

        self._timeline_container = QScrollArea()
        self._timeline_container.setWidgetResizable(True)
        self._timeline_container.setFrameShape(QFrame.Shape.NoFrame)
        self._timeline_container.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._timeline_container.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._timeline_widget = ExpedienteEtapasTimeline()
        self._timeline_container.setWidget(self._timeline_widget)
        self._timeline_container.setFixedHeight(282)
        form.addRow(self._timeline_container)

        self._cmb_etapa = QComboBox()
        for etapa in ExpedienteController.ETAPAS:
            self._cmb_etapa.addItem(etapa["titulo"], etapa["codigo"])
        ExpedienteController.aplicar_colores_items_combo_etapas(self._cmb_etapa)
        self._cmb_etapa.currentIndexChanged.connect(self._refresh_etapa_timeline)
        form.addRow("Etapa de flujo:", self._cmb_etapa)

        self._lbl_etapa_instruccion = QLabel("")
        self._lbl_etapa_instruccion.setStyleSheet("color: #5a6475; font-style: italic;")
        form.addRow("Accion sugerida:", self._lbl_etapa_instruccion)

        self._lbl_clasificacion_etapa = QLabel("")
        self._lbl_clasificacion_etapa.setWordWrap(True)
        self._lbl_clasificacion_etapa.setMinimumHeight(0)
        self._lbl_clasificacion_etapa.hide()
        form.addRow("Clasificacion:", self._lbl_clasificacion_etapa)

        lbl_pe = QLabel(
            "Agregue solo las etapas que necesite. El responsable principal es el de RESPONSABLES; "
            "(Heredar) usa el secundario global. Los plazos se definen con el boton Plazo."
        )
        lbl_pe.setWordWrap(True)
        lbl_pe.setStyleSheet("color: #5a6475; font-size: 11px;")
        form.addRow(lbl_pe)
        self._scroll_estado_etapas = QScrollArea()
        self._scroll_estado_etapas.setWidgetResizable(True)
        self._scroll_estado_etapas.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_estado_etapas.setFixedHeight(300)
        self._estado_etapas_content = QWidget()
        self._estado_etapas_rows_layout = QVBoxLayout()
        self._estado_etapas_rows_layout.setContentsMargins(6, 6, 6, 0)
        self._estado_etapas_rows_layout.setSpacing(8)
        self._btn_add_estado_etapa = QPushButton("+ Agregar etapa")
        self._btn_add_estado_etapa.setProperty("variant", "secondary")
        self._btn_add_estado_etapa.clicked.connect(self._on_add_estado_etapa_row)
        _etapas_outer = QVBoxLayout(self._estado_etapas_content)
        _etapas_outer.setContentsMargins(10, 8, 10, 10)
        _etapas_outer.addLayout(self._estado_etapas_rows_layout)
        _etapas_outer.addStretch(1)
        _etapas_outer.addWidget(self._btn_add_estado_etapa)
        self._scroll_estado_etapas.setWidget(self._estado_etapas_content)
        form.addRow(self._scroll_estado_etapas)

        self._txt_indicaciones_transicion = QTextEdit()
        self._txt_indicaciones_transicion.setMaximumHeight(76)
        self._txt_indicaciones_transicion.setPlaceholderText(
            "Si al guardar cambia la etapa o algun responsable, puede escribir aqui indicaciones "
            "para quien gestiona la carpeta (historial y notificacion)."
        )
        form.addRow("Indicaciones al equipo:", self._txt_indicaciones_transicion)

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
            intro = (
                "Otro usuario tiene la edicion de esta carpeta en este momento. "
                "Podes revisar todos los datos en modo solo lectura desde esta PC o en simultaneo con otras. "
                "No podes guardar la carpeta ni crear ni modificar tareas, documentos u otros registros "
                "hasta que libere la ventana o venza el bloqueo en el servidor.\n\n"
            )
            QMessageBox.information(self, "Solo lectura", intro + msg)
            self._insert_readonly_banner(intro.strip().replace("\n\n", " "))
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

        # Cargar datos específicos de la rama (dinámico + referencias fijas en datos_rama)
        datos_rama = data.get("datos_rama")
        if isinstance(datos_rama, str):
            try:
                datos_rama = json.loads(datos_rama)
            except (json.JSONDecodeError, ValueError):
                datos_rama = {}
        if not isinstance(datos_rama, dict):
            datos_rama = {}
        ref_keys = ExpedienteController.KEYS_TODAS_REFERENCIAS_EXPEDIENTE_RAMA
        datos_rama_solo = {
            k: v for k, v in datos_rama.items() if k not in ref_keys
        }
        datos_ref = {k: v for k, v in datos_rama.items() if k in ref_keys}
        if datos_rama_solo and self._rama_datos_widget:
            self._rama_datos_widget.set_data(datos_rama_solo)
        elif self._rama_datos_widget:
            self._rama_datos_widget.clear()
        if datos_ref:
            self._expedientes_ref_widget.set_data(datos_ref)
        else:
            self._expedientes_ref_widget.clear()

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
        etapa_codigo = data.get("etapa_codigo", "para_citar_o_videollamada")
        idx_et = self._cmb_etapa.findData(etapa_codigo)
        if idx_et >= 0:
            self._cmb_etapa.setCurrentIndex(idx_et)
        self._original_etapa_codigo = data.get("etapa_codigo", "para_citar_o_videollamada") or "para_citar_o_videollamada"
        if hasattr(self, "_txt_indicaciones_transicion"):
            seg = get_segmento_abierto(self._id)
            obs_seg = (seg.get("observacion_transicion") or "").strip() if seg else ""
            self._txt_indicaciones_transicion.setPlainText(obs_seg)
        self._cmb_estado.setCurrentText(data.get("estado", "Activo"))
        self._cmb_prioridad.setCurrentText(data.get("prioridad", "Normal"))
        self._txt_ubicacion.setText(data.get("ubicacion_fisica", ""))
        self._txt_link_drive.setText(data.get("link_drive", ""))
        self._txt_nro_exp.setText(data.get("numero_expediente_anses", ""))
        if hasattr(self, "_txt_calculo_nota"):
            self._txt_calculo_nota.setPlainText(data.get("calculo_derecho_nota", "") or "")
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
        self._refresh_etapa_timeline()
        self._refresh_estado_etapas_panel()
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

        self._apply_responsables_y_flujo_lock()

        # Las pestañas relacionadas se cargan on-demand al activarlas (lazy).

    # ------------------------------------------------------------------
    # Carga diferida (lazy) de pestanas
    # ------------------------------------------------------------------

    def _on_tab_changed(self, index: int):
        """Cargar datos de la pestana solo la primera vez que se activa."""
        if not self._is_edit or not self._id or index in self._loaded_tabs:
            return
        self._loaded_tabs.add(index)

        if not self._tabs:
            return
        tab_name = self._tabs.tabText(index)

        if tab_name == "Movimientos":
            self._load_tab_tareas()
        elif tab_name == "Turnos ANSES":
            self._load_tab_turnos()
        elif tab_name == "Comunicaciones":
            self._load_tab_comms()
        elif tab_name == "Recordatorios":
            self._load_tab_recordatorios()
        elif tab_name == "Documentos":
            self._load_tab_docs()
        elif tab_name == "Calculo Derecho":
            self._load_tab_calculo_derecho()
        elif tab_name == "Escritos":
            self._load_tab_escritos()
        elif tab_name == "Contable":
            self._load_tab_movs()
        elif tab_name == "Tiempos":
            self._load_tab_tiempos()
        elif tab_name == "Historial de tiempos":
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
        rows = []
        for t in turnos:
            row = dict(t)
            did = (row.get("id_constancia_doc") or "").strip()
            if did and DocumentoController.get_by_id(did):
                row["constancia_label"] = "PDF"
            else:
                row["constancia_label"] = ""
            rows.append(row)
        self._turnos_table.set_data(rows)
        self._on_turno_row_selected("")

    def _on_turno_row_selected(self, _turno_id: str):
        tid = self._turnos_table.get_selected_id()
        if not tid:
            self._btn_turno_abrir_constancia.setEnabled(False)
            return
        t = TurnoController.get_by_id(tid)
        doc_id = (t or {}).get("id_constancia_doc", "") or ""
        self._btn_turno_abrir_constancia.setEnabled(bool(doc_id and DocumentoController.get_by_id(doc_id)))

    def _open_turno_constancia_pdf(self):
        if self._readonly_guard():
            return
        tid = self._turnos_table.get_selected_id()
        if not tid:
            return
        t = TurnoController.get_by_id(tid)
        doc_id = (t or {}).get("id_constancia_doc", "") or ""
        if not doc_id:
            return
        local = DocumentoController.ensure_local_file(doc_id)
        if local and local.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(local.resolve())))
        else:
            QMessageBox.warning(self, "Constancia", "No se pudo abrir el archivo.")

    def _load_tab_comms(self):
        comms = ComunicacionController.get_by_expediente(self._id)
        self._comms_table.set_data(comms)

    def _proximos_plazos_por_etapa(self) -> dict[str, dict]:
        """Primer plazo pendiente por etapa (menor fecha_disparo)."""
        if not self._id:
            return {}
        raw = ExpedienteRecordatorioController.list_by_expediente(self._id)
        pend = [r for r in raw if not (r.get("disparado_en") or "").strip()]
        by_etapa: dict[str, dict] = {}
        for r in pend:
            ec = (r.get("etapa_codigo") or "").strip()
            if not ec:
                continue
            fd = (r.get("fecha_disparo") or "")[:10]
            if ec not in by_etapa:
                by_etapa[ec] = r
            else:
                prev = (by_etapa[ec].get("fecha_disparo") or "")[:10]
                if fd < prev:
                    by_etapa[ec] = r
        return by_etapa

    def _format_plazo_etapa_text(self, rec: dict | None) -> str:
        if not rec:
            return "-"
        fd = (rec.get("fecha_disparo") or "")[:10]
        tl = (rec.get("titulo") or "").strip()
        fds = fd
        if len(fd) >= 10:
            qd = QDate.fromString(fd[:10], "yyyy-MM-dd")
            if qd.isValid():
                fds = qd.toString("dd/MM/yyyy")
        text = f"{fds} — {tl}" if tl else (fds or "-")
        if int(rec.get("es_critico", 0) or 0):
            text = "[CRITICO] " + text
        return text

    def _clear_estado_etapas_rows(self):
        if not hasattr(self, "_estado_etapas_rows_layout"):
            return
        lay = self._estado_etapas_rows_layout
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _iter_estado_etapa_rows(self):
        if not hasattr(self, "_estado_etapas_rows_layout"):
            return
        lay = self._estado_etapas_rows_layout
        for i in range(lay.count()):
            item = lay.itemAt(i)
            w = item.widget() if item else None
            if w is not None and getattr(w, "_cmb_etapa", None) is not None:
                yield w

    def _codigos_etapa_a_mostrar_en_panel(self) -> list[str]:
        """Union de etapas con override de encargado y etapas con plazo pendiente."""
        if not self._id:
            return []
        overrides = {
            r["etapa_codigo"]
            for r in ExpedienteEtapaResponsableController.list_by_expediente(self._id)
        }
        plazos = self._proximos_plazos_por_etapa()
        codes = overrides | set(plazos.keys())
        orden = [e["codigo"] for e in ExpedienteController.ETAPAS]
        ordered = [c for c in orden if c in codes]
        for c in sorted(codes):
            if c not in ordered:
                ordered.append(c)
        return ordered

    def _update_plazo_label_for_row(self, row: QWidget):
        plazos = self._proximos_plazos_por_etapa()
        cmb = getattr(row, "_cmb_etapa", None)
        lbl = getattr(row, "_lbl_plazo", None)
        if cmb is None or lbl is None:
            return
        code = (cmb.currentData() or "").strip()
        lbl.setText(self._format_plazo_etapa_text(plazos.get(code) if code else None))

    def _update_plazo_labels_for_all_rows(self):
        plazos = self._proximos_plazos_por_etapa()
        for row in self._iter_estado_etapa_rows():
            cmb = getattr(row, "_cmb_etapa", None)
            lbl = getattr(row, "_lbl_plazo", None)
            if cmb is None or lbl is None:
                continue
            code = (cmb.currentData() or "").strip()
            lbl.setText(self._format_plazo_etapa_text(plazos.get(code) if code else None))

    def _add_estado_etapa_row(self, etapa_codigo: str, encargado_username: str):
        """Una fila: etapa, encargado secundario, texto de plazo, botones."""
        row = QWidget()
        row.setMinimumHeight(40)
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 4, 0, 4)
        h.setSpacing(8)
        cmb_etapa = NoWheelComboBox()
        cmb_etapa.addItem("-- Elija etapa --", "")
        for et in ExpedienteController.ETAPAS:
            cmb_etapa.addItem(et["titulo"], et["codigo"])
        ExpedienteController.aplicar_colores_items_combo_etapas(cmb_etapa)
        cmb_enc = NoWheelComboBox()
        cmb_enc.addItem("(Heredar de la carpeta)", "")
        users = get_active_users_fresh()
        for u in users:
            lab = f'{u.get("nombre_completo", "")} ({u.get("username", "")})'
            cmb_enc.addItem(lab, u.get("username", ""))
        idx_e = cmb_etapa.findData(etapa_codigo)
        if idx_e >= 0:
            cmb_etapa.setCurrentIndex(idx_e)
        cur = (encargado_username or "").strip()
        idx_u = cmb_enc.findData(cur)
        if idx_u >= 0:
            cmb_enc.setCurrentIndex(idx_u)
        lbl_plazo = QLabel("-")
        lbl_plazo.setMinimumWidth(100)
        lbl_plazo.setStyleSheet("color: #374151; font-size: 11px;")
        lbl_plazo.setWordWrap(False)
        btn_plazo = QPushButton("Plazo...")
        btn_plazo.setProperty("variant", "secondary")
        btn_remove = QPushButton("Quitar")
        btn_remove.setProperty("variant", "secondary")
        btn_remove.setToolTip("Quitar esta fila")
        row._cmb_etapa = cmb_etapa  # type: ignore[attr-defined]
        row._cmb_encargado = cmb_enc  # type: ignore[attr-defined]
        row._lbl_plazo = lbl_plazo  # type: ignore[attr-defined]
        btn_plazo.clicked.connect(lambda _=False, r=row: self._edit_plazo_etapa_from_row(r))
        btn_remove.clicked.connect(lambda _=False, r=row: self._remove_estado_etapa_row(r))
        cmb_etapa.currentIndexChanged.connect(lambda _i, r=row: self._update_plazo_label_for_row(r))
        h.addWidget(cmb_etapa, 2)
        h.addWidget(cmb_enc, 2)
        h.addWidget(lbl_plazo, 2)
        h.addWidget(btn_plazo)
        h.addWidget(btn_remove)
        self._estado_etapas_rows_layout.addWidget(row)
        self._update_plazo_label_for_row(row)

    def _remove_estado_etapa_row(self, row: QWidget):
        if self._readonly_guard() or self._responsables_flujo_bloqueado():
            return
        self._estado_etapas_rows_layout.removeWidget(row)
        row.deleteLater()

    def _on_add_estado_etapa_row(self):
        if self._readonly_guard() or self._responsables_flujo_bloqueado() or not self._id:
            return
        self._add_estado_etapa_row("", "")

    def _edit_plazo_etapa_from_row(self, row: QWidget):
        if self._readonly_guard() or self._responsables_flujo_bloqueado() or not self._id:
            return
        cmb = getattr(row, "_cmb_etapa", None)
        if cmb is None:
            return
        etapa_codigo = (cmb.currentData() or "").strip()
        if not etapa_codigo:
            QMessageBox.warning(
                self,
                "Etapa",
                "Seleccione una etapa en la fila antes de definir o editar el plazo.",
            )
            return
        self._edit_plazo_etapa(etapa_codigo)

    def _refresh_estado_etapas_panel(self):
        """Filas en seccion ESTADO: solo etapas con dato (override o plazo) o vacio si no hay carpeta."""
        if not hasattr(self, "_estado_etapas_rows_layout"):
            return
        self._clear_estado_etapas_rows()
        self._btn_add_estado_etapa.setEnabled(bool(self._id))
        if not self._id:
            return
        overrides = {
            r["etapa_codigo"]: (r.get("responsable_secundario_username") or "").strip()
            for r in ExpedienteEtapaResponsableController.list_by_expediente(self._id)
        }
        for code in self._codigos_etapa_a_mostrar_en_panel():
            self._add_estado_etapa_row(code, overrides.get(code, ""))
        self._apply_responsables_y_flujo_lock()

    def _edit_plazo_etapa(self, etapa_codigo: str):
        if self._readonly_guard() or self._responsables_flujo_bloqueado() or not self._id:
            return
        pend = [
            r for r in ExpedienteRecordatorioController.list_by_expediente(self._id)
            if (r.get("etapa_codigo") or "").strip() == etapa_codigo
            and not (r.get("disparado_en") or "").strip()
        ]
        pend.sort(key=lambda x: (x.get("fecha_disparo") or ""))
        initial = pend[0] if pend else None
        session = Session.get()
        dlg = RecordatorioEditDialog(
            self,
            users=get_active_users_fresh(),
            initial=initial,
            default_etapa_codigo="" if initial else etapa_codigo,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.get_data()
        data["creado_por_username"] = session.username if session.logged_in else ""
        if initial:
            ExpedienteRecordatorioController.update(initial["_id"], {
                "fecha_disparo": data["fecha_disparo"],
                "titulo": data["titulo"],
                "mensaje": data["mensaje"],
                "notificar_a_username": data["notificar_a_username"],
                "etapa_codigo": data.get("etapa_codigo", ""),
                "es_critico": data.get("es_critico", 0),
            })
        else:
            ExpedienteRecordatorioController.create_for_expediente(self._id, data)
        self._update_plazo_labels_for_all_rows()
        # Si aparece una etapa nueva por el dialogo, puede faltar fila
        ec_new = (data.get("etapa_codigo") or "").strip()
        if ec_new and ec_new != etapa_codigo:
            self._refresh_estado_etapas_panel()
        self._refresh_etapa_timeline()
        if hasattr(self, "_recordatorios_table"):
            self._load_tab_recordatorios()

    def _persist_estado_etapas_encargados(self, expediente_id: str | None = None):
        eid = expediente_id or self._id
        if not eid or not hasattr(self, "_estado_etapas_rows_layout"):
            return
        existing = {
            r["etapa_codigo"]: r
            for r in ExpedienteEtapaResponsableController.list_by_expediente(eid)
        }
        seen: set[str] = set()
        for row in self._iter_estado_etapa_rows():
            cmb_e = getattr(row, "_cmb_etapa", None)
            cmb_u = getattr(row, "_cmb_encargado", None)
            if cmb_e is None or cmb_u is None or not hasattr(cmb_e, "currentData"):
                continue
            code = (cmb_e.currentData() or "").strip()
            if not code:
                continue
            seen.add(code)
            uname = cmb_u.currentData() or ""
            ExpedienteEtapaResponsableController.upsert_encargado(eid, code, uname)
        for code in set(existing.keys()) - seen:
            ExpedienteEtapaResponsableController.upsert_encargado(eid, code, "")

    def _load_tab_recordatorios(self):
        rows_raw = ExpedienteRecordatorioController.list_by_expediente(self._id)
        users = {u["username"]: u.get("nombre_completo", u["username"]) for u in get_active_users_fresh()}
        etapas_map = {x["codigo"]: x["titulo"] for x in ExpedienteController.ETAPAS}
        display = []
        for r in rows_raw:
            msg = (r.get("mensaje") or "").strip()
            disp = (r.get("disparado_en") or "").strip()
            ec = (r.get("etapa_codigo") or "").strip()
            display.append({
                "_id": r["_id"],
                "fecha_disparo": r.get("fecha_disparo", "") or "",
                "titulo": r.get("titulo", "") or "",
                "etapa_label": etapas_map.get(ec, ec or "-"),
                "critico": "Si" if int(r.get("es_critico", 0) or 0) else "",
                "mensaje_preview": (msg[:120] + "...") if len(msg) > 120 else msg,
                "notificar_a": users.get(
                    r.get("notificar_a_username", "") or "",
                    r.get("notificar_a_username", "") or "",
                ),
                "estado": (
                    f"Disparado {disp[:10]}"
                    if disp
                    else "Pendiente"
                ),
            })
        self._recordatorios_table.set_data(display)

    def _new_recordatorio(self):
        if self._readonly_guard():
            return
        if not self._id:
            return
        session = Session.get()
        dlg = RecordatorioEditDialog(self, users=get_active_users_fresh())
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.get_data()
        data["creado_por_username"] = session.username if session.logged_in else ""
        ExpedienteRecordatorioController.create_for_expediente(self._id, data)
        self._load_tab_recordatorios()
        self._refresh_estado_etapas_panel()

    def _edit_recordatorio(self, rec_id: str):
        if self._readonly_guard():
            return
        rec = ExpedienteRecordatorioController.get_by_id(rec_id)
        if not rec:
            return
        if (rec.get("disparado_en") or "").strip():
            QMessageBox.information(
                self,
                "Recordatorio",
                "Este recordatorio ya fue disparado y no se puede editar.",
            )
            return
        dlg = RecordatorioEditDialog(self, users=get_active_users_fresh(), initial=rec)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        payload = dlg.get_data()
        ExpedienteRecordatorioController.update(rec_id, {
            "fecha_disparo": payload["fecha_disparo"],
            "titulo": payload["titulo"],
            "mensaje": payload["mensaje"],
            "notificar_a_username": payload["notificar_a_username"],
            "etapa_codigo": payload.get("etapa_codigo", ""),
            "es_critico": payload.get("es_critico", 0),
        })
        self._load_tab_recordatorios()
        self._refresh_estado_etapas_panel()

    def _delete_recordatorio(self):
        if self._readonly_guard():
            return
        rid = self._recordatorios_table.get_selected_id()
        if not rid:
            QMessageBox.information(self, "Recordatorios", "Seleccione un recordatorio de la tabla.")
            return
        rec = ExpedienteRecordatorioController.get_by_id(rid)
        if not rec:
            return
        if (rec.get("disparado_en") or "").strip():
            QMessageBox.warning(
                self,
                "Recordatorios",
                "No se puede eliminar un recordatorio que ya fue disparado.",
            )
            return
        ok = QMessageBox.question(
            self,
            "Confirmar",
            "¿Eliminar este recordatorio?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ok != QMessageBox.StandardButton.Yes:
            return
        ExpedienteRecordatorioController.delete(rid)
        self._load_tab_recordatorios()
        self._refresh_estado_etapas_panel()

    def _maybe_suggest_recordatorio_espera(self):
        hoy = date.today().isoformat()
        recs = ExpedienteRecordatorioController.list_by_expediente(self._id)
        futuros = [
            r for r in recs
            if not (r.get("disparado_en") or "").strip()
            and (r.get("fecha_disparo") or "") >= hoy
        ]
        if futuros:
            return
        QMessageBox.information(
            self,
            "Recordatorios",
            "La carpeta esta en etapa «En espera / Aguardando condicion». "
            "Si corresponde, agregue un recordatorio en la pestana Recordatorios "
            "para no perder de vista el proximo hito.",
        )

    def _maybe_suggest_cita(self):
        """Tras guardar en etapa de citar: sugerir crear cita si no hay pendiente/confirmada."""
        eid = (self._id or "").strip()
        if not eid:
            return
        from controllers.cita_controller import CitaController

        if CitaController.tiene_cita_pendiente(eid):
            return
        resp = QMessageBox.question(
            self,
            "Cita",
            "La carpeta esta en etapa de citar y aun no tiene una cita Pendiente o Confirmada "
            "en el modulo de Citas.\n\n"
            "¿Desea crear una cita ahora?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        if not tiene_permiso(Session.get().rol, "citas.create"):
            QMessageBox.information(
                self,
                "Citas",
                "No tiene permiso para crear citas. Solicite a un usuario con permiso "
                "que registre la cita en el modulo Citas.",
            )
            return
        cliente_id = (self._cmb_cliente.currentData() or "").strip()
        from views.citas.cita_form import CitaFormDialog

        dlg = CitaFormDialog(
            cliente_id=cliente_id or None,
            expediente_id=eid,
            parent=self,
        )
        dlg.exec()

    def _load_tab_docs(self):
        docs = DocumentoController.get_by_expediente(self._id)
        self._docs_table.set_data(docs)

    def _load_tab_calculo_derecho(self):
        docs = DocumentoController.get_by_expediente(self._id)
        calculos = [d for d in docs if (d.get("categoria", "") or "").strip() == "Calculo Derecho"]
        self._calc_docs_table.set_data(calculos)

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
                "estado": e.get("estado_label") or e["estado"],
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

    def _on_responsable_completer_activated(self, text: str):
        """Seleccionar responsable principal al elegir una opcion del autocompletado."""
        idx = self._cmb_responsable.findText(text)
        if idx >= 0:
            self._cmb_responsable.setCurrentIndex(idx)

    def _on_responsable_secundario_completer_activated(self, text: str):
        """Seleccionar responsable secundario al elegir una opcion del autocompletado."""
        idx = self._cmb_responsable2.findText(text)
        if idx >= 0:
            self._cmb_responsable2.setCurrentIndex(idx)

    def _on_cliente_changed(self, index: int):
        """Actualizar N° de carpeta y claves al cambiar el cliente seleccionado."""
        del index
        cliente_id = self._cmb_cliente.currentData() or ""
        if not cliente_id:
            self._txt_carpeta_cliente.setText("")
            self._txt_cuil_cliente.setText("")
            self._sync_ir_cliente_button_state()
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
            self._txt_cuil_cliente.setText((cliente.get("cuil") or "").strip())
            if not self._txt_clave_mi_anses.text().strip():
                self._txt_clave_mi_anses.setText(cliente.get("clave_mi_anses", "") or "")
            if not self._txt_clave_fiscal.text().strip():
                self._txt_clave_fiscal.setText(cliente.get("clave_fiscal", "") or "")
        else:
            self._txt_carpeta_cliente.setText("")
            self._txt_cuil_cliente.setText("")
        self._sync_ir_cliente_button_state()

    def _sync_ir_cliente_button_state(self):
        if not hasattr(self, "_btn_ir_cliente"):
            return
        self._btn_ir_cliente.setEnabled(bool((self._cmb_cliente.currentData() or "").strip()))

    def _open_selected_cliente(self):
        cliente_id = (self._cmb_cliente.currentData() or "").strip()
        if not cliente_id:
            QMessageBox.information(
                self,
                "Cliente",
                "Seleccione un cliente para abrir su ficha.",
            )
            return
        from views.clientes.cliente_form import ClienteFormDialog
        dlg = ClienteFormDialog(cliente_id=cliente_id, parent=self)
        dlg.exec()

    def _new_tarea(self):
        """Crear una nueva tarea pre-vinculada a este expediente."""
        if self._readonly_guard():
            return
        from views.tareas.tarea_form import TareaFormDialog
        dlg = TareaFormDialog(expediente_id=self._id, parent=self)
        if dlg.exec():
            self._load_tab_tareas()

    def _edit_tarea(self, tarea_id: str):
        """Editar una tarea existente desde la pestana de la carpeta."""
        if self._readonly_guard():
            return
        from views.tareas.tarea_form import TareaFormDialog
        dlg = TareaFormDialog(tarea_id=tarea_id, parent=self)
        if dlg.exec():
            self._load_tab_tareas()

    def _new_turno(self):
        """Crear un nuevo turno pre-vinculado a este expediente."""
        if self._readonly_guard():
            return
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
        if self._readonly_guard():
            return
        from views.turnos.turno_form import TurnoFormDialog
        dlg = TurnoFormDialog(turno_id=turno_id, parent=self)
        if dlg.exec():
            self._load_tab_turnos()

    def _new_comunicacion(self):
        """Crear una nueva comunicacion pre-vinculada a este expediente."""
        if self._readonly_guard():
            return
        from views.comunicaciones.comunicacion_form import ComunicacionFormDialog
        dlg = ComunicacionFormDialog(expediente_id=self._id, parent=self)
        if dlg.exec():
            self._load_tab_comms()

    def _edit_comunicacion(self, comunicacion_id: str):
        """Editar una comunicacion existente."""
        if self._readonly_guard():
            return
        from views.comunicaciones.comunicacion_form import ComunicacionFormDialog
        dlg = ComunicacionFormDialog(comunicacion_id=comunicacion_id, parent=self)
        if dlg.exec():
            self._load_tab_comms()

    def _new_documento(self):
        """Crear un nuevo documento pre-vinculado a este expediente."""
        if self._readonly_guard():
            return
        from views.documentos.documento_form import DocumentoFormDialog
        dlg = DocumentoFormDialog(expediente_id=self._id, parent=self)
        if dlg.exec():
            self._load_tab_docs()

    def _edit_documento(self, doc_id: str):
        """Editar un documento existente."""
        if self._readonly_guard():
            return
        from views.documentos.documento_form import DocumentoFormDialog
        dlg = DocumentoFormDialog(doc_id=doc_id, parent=self)
        if dlg.exec():
            self._load_tab_docs()

    def _delete_documento(self):
        """Eliminar (soft delete) un documento de la carpeta actual."""
        if self._readonly_guard():
            return
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

    def _new_calculo_documento(self):
        """Crear documento en categoria fija Calculo Derecho."""
        if self._readonly_guard():
            return
        from views.documentos.documento_form import DocumentoFormDialog
        dlg = DocumentoFormDialog(
            expediente_id=self._id,
            categoria_preset="Calculo Derecho",
            lock_categoria=True,
            parent=self,
        )
        if dlg.exec():
            self._load_tab_calculo_derecho()

    def _edit_calculo_documento(self, doc_id: str):
        """Editar un documento de Calculo Derecho."""
        if self._readonly_guard():
            return
        from views.documentos.documento_form import DocumentoFormDialog
        dlg = DocumentoFormDialog(
            doc_id=doc_id,
            categoria_preset="Calculo Derecho",
            lock_categoria=True,
            parent=self,
        )
        if dlg.exec():
            self._load_tab_calculo_derecho()

    def _delete_calculo_documento(self):
        """Eliminar documento seleccionado en Calculo Derecho."""
        if self._readonly_guard():
            return
        if not getattr(self, "_can_delete_docs", False):
            QMessageBox.warning(self, "Sin permisos", "No tiene permisos para eliminar documentos.")
            return
        doc_id = self._calc_docs_table.get_selected_id()
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
            self._load_tab_calculo_derecho()
        else:
            QMessageBox.warning(self, "Error", "No se pudo eliminar el documento.")

    def _new_escrito(self):
        """Crear un escrito desde un modelo y abrir editor rich text."""
        if self._readonly_guard():
            return
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
        if self._readonly_guard():
            return
        from views.escritos.escrito_editor import EscritoEditorDialog
        dlg = EscritoEditorDialog(escrito_id, parent=self)
        if dlg.exec():
            self._load_tab_escritos()

    def _new_movimiento(self):
        """Crear un nuevo movimiento pre-vinculado a este expediente y cliente."""
        if self._readonly_guard():
            return
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
        if self._readonly_guard():
            return
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
        if hasattr(self, "_refresh_etapa_timeline"):
            self._refresh_etapa_timeline()

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
            self._rama_datos_layout.insertWidget(0, self._rama_datos_widget)
        self._rama_datos_container.setVisible(True)
        self._rama_separator.setVisible(True)

    def _on_judicializado_changed(self, checked: bool):
        """Muestra u oculta los campos del módulo judicial."""
        self._judicial_container.setVisible(checked)

    def _on_estado_changed(self, estado: str):
        """Habilitar campos de cierre solo cuando el estado es Cerrado o Archivado."""
        es_cierre = estado in ExpedienteController.ESTADOS_CIERRE
        self._date_cierre.setEnabled(es_cierre)
        self._cmb_resultado.setEnabled(es_cierre)

    def _ultima_transicion_etapa(self) -> tuple[str, str]:
        if not self._id:
            return "", self._cmb_etapa.currentData() or "para_citar_o_videollamada"
        conn = db_local.get_connection()
        row = conn.execute(
            "SELECT etapa_anterior, estado FROM expediente_estado_historial "
            "WHERE id_expediente = ? ORDER BY inicio_ts DESC LIMIT 1",
            (self._id,),
        ).fetchone()
        conn.close()
        if not row:
            return "", self._cmb_etapa.currentData() or "para_citar_o_videollamada"
        return row[0] or "", row[1] or (self._cmb_etapa.currentData() or "para_citar_o_videollamada")

    def _refresh_etapa_timeline(self):
        etapa_codigo = self._cmb_etapa.currentData() or "para_citar_o_videollamada"
        etapa_meta = ExpedienteController.etapa_por_codigo(etapa_codigo)
        self._lbl_etapa_instruccion.setText(etapa_meta.get("instruccion_corta", ""))
        self._sync_modalidad_con_etapa_iniciada(etapa_codigo)
        self._refresh_clasificacion_etapa_label(etapa_codigo)
        anterior, actual_hist = self._ultima_transicion_etapa() if self._is_edit else ("", etapa_codigo)
        actual = etapa_codigo or actual_hist
        plazos_por_etapa = self._proximos_plazos_por_etapa() if self._id else {}
        self._timeline_widget.set_data(
            ExpedienteController.ETAPAS,
            actual=actual,
            anterior=anterior,
            plazos_por_etapa=plazos_por_etapa,
        )

    def _sync_modalidad_con_etapa_iniciada(self, etapa_codigo: str):
        """Si la rama usa modalidad y la etapa es INICIADA, alinear combo con la etapa."""
        rama = self._cmb_rama.currentText().strip()
        if rama not in ExpedienteController.RAMAS_CON_MODALIDAD:
            return
        if etapa_codigo == "iniciada_virtual":
            if self._cmb_modalidad.currentText() != "Virtual":
                self._cmb_modalidad.setCurrentText("Virtual")
        elif etapa_codigo == "iniciada_presencial":
            if self._cmb_modalidad.currentText() != "Presencial":
                self._cmb_modalidad.setCurrentText("Presencial")

    def _refresh_clasificacion_etapa_label(self, etapa_codigo: str):
        info = ExpedienteController.clasificacion_etapa(etapa_codigo)
        if not info.get("mostrar"):
            self._lbl_clasificacion_etapa.hide()
            self._lbl_clasificacion_etapa.clear()
            return
        cat = info.get("categoria") or ""
        estilos = {
            "no_iniciada": (
                "background-color: #fff7ed; color: #9a3412; border: 1px solid #fdba74; "
                "border-radius: 6px; padding: 8px;"
            ),
            "iniciada": (
                "background-color: #eff6ff; color: #1e40af; border: 1px solid #93c5fd; "
                "border-radius: 6px; padding: 8px;"
            ),
            "citado_anses": (
                "background-color: #e0f2fe; color: #075985; border: 1px solid #7dd3fc; "
                "border-radius: 6px; padding: 8px;"
            ),
            "resultado_favorable": (
                "background-color: #ecfdf5; color: #166534; border: 1px solid #86efac; "
                "border-radius: 6px; padding: 8px;"
            ),
            "resultado_desfavorable": (
                "background-color: #fef2f2; color: #991b1b; border: 1px solid #fca5a5; "
                "border-radius: 6px; padding: 8px;"
            ),
        }
        self._lbl_clasificacion_etapa.setStyleSheet(estilos.get(cat, "padding: 8px;"))
        self._lbl_clasificacion_etapa.setText(info.get("texto", ""))
        self._lbl_clasificacion_etapa.show()

    def _save(self):
        if self._is_read_only:
            QMessageBox.warning(
                self,
                "Solo lectura",
                "Esta carpeta esta en modo solo lectura (otro usuario edita o bloqueo no disponible).",
            )
            return
        if self._is_edit and not self._puede_editar_responsables_y_flujo():
            resp_username = (self._original_responsable_username or "").strip()
            resp2_username = (self._original_responsable_secundario_username or "").strip()
            if resp_username:
                idx_r = self._cmb_responsable.findData(resp_username)
                resp_display = (
                    self._cmb_responsable.itemText(idx_r).strip()
                    if idx_r >= 0
                    else (self._original_responsable_display or "").strip()
                )
            else:
                resp_display = (self._original_responsable_display or "").strip()
            if resp2_username:
                idx_r2 = self._cmb_responsable2.findData(resp2_username)
                resp2_display = (
                    self._cmb_responsable2.itemText(idx_r2).strip()
                    if idx_r2 >= 0
                    else (self._original_responsable_secundario_display or "").strip()
                )
            else:
                resp2_display = (self._original_responsable_secundario_display or "").strip()
        else:
            resp_username = self._cmb_responsable.currentData() or ""
            resp_display = self._cmb_responsable.currentText().strip()
            resp2_username = self._cmb_responsable2.currentData() or ""
            resp2_display = self._cmb_responsable2.currentText().strip()

        if not resp_username and not resp_display:
            QMessageBox.warning(self, "Atencion", "El responsable es obligatorio.")
            return

        if hasattr(self, "_iter_estado_etapa_rows") and not (
            self._is_edit and not self._puede_editar_responsables_y_flujo()
        ):
            codes_fila: list[str] = []
            for row in self._iter_estado_etapa_rows():
                cmb = getattr(row, "_cmb_etapa", None)
                if cmb is None or not hasattr(cmb, "currentData"):
                    continue
                c = (cmb.currentData() or "").strip()
                if c:
                    codes_fila.append(c)
            if len(codes_fila) != len(set(codes_fila)):
                QMessageBox.warning(
                    self,
                    "Etapas",
                    "Hay etapas repetidas en las filas de encargado por etapa. "
                    "Quite las filas duplicadas o cambie la etapa en cada una.",
                )
                return

        if self._is_edit:
            old_primary = (self._original_responsable_username or self._original_responsable_display).strip().lower()
            new_primary = (resp_username or resp_display).strip().lower()
            old_secondary = (
                self._original_responsable_secundario_username
                or self._original_responsable_secundario_display
            ).strip().lower()
            new_secondary = (resp2_username or resp2_display).strip().lower()
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
        if self._is_edit and not self._puede_editar_responsables_y_flujo():
            etapa_codigo = self._original_etapa_codigo or "para_citar_o_videollamada"
        else:
            etapa_codigo = self._cmb_etapa.currentData() or "para_citar_o_videollamada"

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
        resp2_legible = resp2_display.split("(")[0].strip() if resp2_username else ""

        clave_mi_anses = self._txt_clave_mi_anses.text().strip()
        clave_fiscal = self._txt_clave_fiscal.text().strip()
        cliente_id = self._cmb_cliente.currentData() or ""

        # Recolectar datos de rama
        rama = self._cmb_rama.currentText()
        subtipo = self._cmb_subtipo.currentText()
        if subtipo == "-- Seleccionar subtipo --":
            subtipo = ""

        # Coherencia etapa INICIADA vs modalidad (rama Previsional)
        if rama in ExpedienteController.RAMAS_CON_MODALIDAD:
            modalidad_ui = self._cmb_modalidad.currentText().strip() or ExpedienteController.MODALIDADES[0]
            if etapa_codigo == "iniciada_virtual" and modalidad_ui != "Virtual":
                QMessageBox.warning(
                    self,
                    "Etapa y modalidad",
                    "La etapa 'INICIADA - Virtual' requiere modalidad Virtual.\n"
                    "Seleccione Virtual en modalidad o cambie la etapa de flujo.",
                )
                return
            if etapa_codigo == "iniciada_presencial" and modalidad_ui != "Presencial":
                QMessageBox.warning(
                    self,
                    "Etapa y modalidad",
                    "La etapa 'INICIADA - Presencial' requiere modalidad Presencial.\n"
                    "Seleccione Presencial en modalidad o cambie la etapa de flujo.",
                )
                return

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
        datos_rama.update(self._expedientes_ref_widget.get_data())

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
            "etapa_codigo": etapa_codigo,
            "prioridad": self._cmb_prioridad.currentText(),
            "ubicacion_fisica": self._txt_ubicacion.text().strip(),
            "link_drive": self._txt_link_drive.text().strip(),
            "numero_expediente_anses": self._txt_nro_exp.text().strip(),
            "calculo_derecho_nota": (
                self._txt_calculo_nota.toPlainText().strip()
                if hasattr(self, "_txt_calculo_nota")
                else ""
            ),
            "clave_mi_anses": clave_mi_anses,
            "clave_fiscal": clave_fiscal,
            "observaciones": self._txt_obs.toPlainText().strip(),
        }

        if self._is_edit:
            etapa_cambiada = etapa_codigo != (self._original_etapa_codigo or "para_citar_o_videollamada")
            resp_cambiado = (resp_username or "") != (self._original_responsable_username or "")
            sec_cambiado = (resp2_username or "") != (self._original_responsable_secundario_username or "")
            if etapa_cambiada or resp_cambiado or sec_cambiado:
                obs = self._txt_indicaciones_transicion.toPlainText().strip()
                if len(obs) > 4000:
                    obs = obs[:4000]
                if obs:
                    data["observacion_transicion"] = obs

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
            if self._puede_editar_responsables_y_flujo():
                self._persist_estado_etapas_encargados()
            if etapa_codigo == "en_espera_condicion":
                self._maybe_suggest_recordatorio_espera()
            if etapa_codigo in ("para_citar_o_videollamada", "para_citar"):
                self._maybe_suggest_cita()
            if data.get("observacion_transicion"):
                self._txt_indicaciones_transicion.clear()
        else:
            created = ExpedienteController.create(data)
            self._persist_estado_etapas_encargados(expediente_id=created.get("_id", ""))
            new_id = (created.get("_id", "") or "").strip()
            if new_id:
                self._id = new_id
            if etapa_codigo in ("para_citar_o_videollamada", "para_citar") and new_id:
                self._maybe_suggest_cita()
        self.accept()

    def closeEvent(self, event):
        if self._locked and self._id:
            LockManager.release_lock("expedientes", self._id)
        super().closeEvent(event)

    def reject(self):
        if self._locked and self._id:
            LockManager.release_lock("expedientes", self._id)
        super().reject()

    def _insert_readonly_banner(self, summary: str):
        """Barra visible bajo el titulo: consulta simultanea permitida, edicion no."""
        lay = self.layout()
        if not isinstance(lay, QVBoxLayout):
            return
        banner = QLabel(summary)
        banner.setWordWrap(True)
        banner.setStyleSheet(
            "background-color: #fff8e6; color: #5c4a00; border: 1px solid #e6c35c; "
            "border-radius: 6px; padding: 10px 12px; font-size: 12px;"
        )
        # Tras el titulo "Detalle de Carpeta" (indice 0), antes de las pestañas
        lay.insertWidget(1, banner)

    def _set_read_only_ui(self):
        """Pone el formulario en solo lectura cuando el lock no se pudo adquirir."""
        self._is_read_only = True
        self._btn_save.setEnabled(False)
        self._btn_save.setToolTip("No disponible: otro usuario edita esta carpeta (solo lectura).")
        widgets = self.findChildren((QLineEdit, QTextEdit, QDateEdit, QComboBox, QCheckBox))
        for w in widgets:
            w.setEnabled(False)
        for container in (
            getattr(self, "_rama_datos_container", None),
            getattr(self, "_judicial_container", None),
            getattr(self, "_timeline_container", None),
            getattr(self, "_scroll_estado_etapas", None),
        ):
            if container is not None:
                container.setEnabled(False)
        for btn in self.findChildren(QPushButton):
            if btn.objectName() != "expediente_readonly_allow_close":
                btn.setEnabled(False)
        self._apply_filterable_tables_double_click(False)
        # El historial de auditoria es solo consulta (sin persistir en esta accion).
        if getattr(self, "_historial_table", None):
            self._historial_table.set_open_on_double_click_enabled(True)
        for ft in self.findChildren(FilterableTable):
            ft.enable_browse_controls()

    def _apply_filterable_tables_double_click(self, enabled: bool):
        for name in (
            "_tareas_table",
            "_turnos_table",
            "_comms_table",
            "_recordatorios_table",
            "_docs_table",
            "_calc_docs_table",
            "_escritos_table",
            "_movs_table",
            "_tiempos_table",
            "_historial_table",
        ):
            t = getattr(self, name, None)
            if t is not None and hasattr(t, "set_open_on_double_click_enabled"):
                t.set_open_on_double_click_enabled(enabled)

    _ROLES_EDICION_RESPONSABLES_FLUJO = frozenset(
        {"administrador", "admin_visor", "superusuario"}
    )

    def _puede_editar_responsables_y_flujo(self) -> bool:
        """Quien puede cambiar responsables, etapa de flujo y encargados por etapa."""
        if self._readonly_guard():
            return False
        if not self._is_edit:
            return True
        session = Session.get()
        rol = (session.rol or "").strip()
        if rol == "secretaria":
            return False
        if rol in self._ROLES_EDICION_RESPONSABLES_FLUJO:
            return True
        uname = (session.username or "").strip().lower()
        p = (self._original_responsable_username or "").strip().lower()
        s = (self._original_responsable_secundario_username or "").strip().lower()
        return bool(uname) and (uname == p or uname == s)

    def _responsables_flujo_bloqueado(self) -> bool:
        """True en edicion cuando no se puede modificar responsables ni flujo."""
        return self._is_edit and not self._puede_editar_responsables_y_flujo()

    def _apply_responsables_y_flujo_lock(self):
        """Deshabilita controles de responsables y etapa si el rol no puede editarlos."""
        if self._readonly_guard() or not getattr(self, "_cmb_responsable", None):
            return
        can = self._puede_editar_responsables_y_flujo()
        tip = (
            "Solo el responsable principal o secundario de la carpeta, o administracion, "
            "pueden modificar esto."
        )
        for w in (
            self._cmb_responsable,
            self._cmb_responsable2,
            self._cmb_etapa,
        ):
            w.setEnabled(can)
            w.setToolTip("" if can else tip)
        if hasattr(self, "_txt_indicaciones_transicion"):
            self._txt_indicaciones_transicion.setReadOnly(not can)
            self._txt_indicaciones_transicion.setToolTip("" if can else tip)
        if hasattr(self, "_btn_add_estado_etapa"):
            self._btn_add_estado_etapa.setEnabled(bool(self._id) and can)
            self._btn_add_estado_etapa.setToolTip("" if can else tip)
        for row in self._iter_estado_etapa_rows():
            for attr in ("_cmb_etapa", "_cmb_encargado"):
                c = getattr(row, attr, None)
                if c is not None:
                    c.setEnabled(can)
                    c.setToolTip("" if can else tip)
            for btn in row.findChildren(QPushButton):
                btn.setEnabled(can)
                btn.setToolTip("" if can else tip)

    def _readonly_guard(self) -> bool:
        return bool(getattr(self, "_is_read_only", False))
