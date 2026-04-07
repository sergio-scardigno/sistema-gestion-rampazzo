"""Formulario de alta/edicion de Tarea."""
import logging
import re
import time

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QTextEdit, QDateEdit, QPushButton, QLabel, QComboBox, QMessageBox,
    QCompleter, QScrollArea, QFrame, QWidget,
)
from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtGui import QFont

from controllers.tarea_controller import TareaController
from controllers.expediente_controller import ExpedienteController
from controllers.cliente_controller import ClienteController
from controllers.notificacion_controller import NotificacionController
from core.auth import Session
from core.permissions import get_active_users_fresh
from views.widgets.no_wheel_combo import NoWheelComboBox
from views.widgets.no_wheel_datetime import NoWheelDateEdit

logger = logging.getLogger(__name__)

_INITIAL_EXP_LIMIT = 50
_SEARCH_DEBOUNCE_MS = 300
_SEARCH_MIN_CHARS = 2
_SEARCH_RESULT_LIMIT = 50


class TareaFormDialog(QDialog):
    def __init__(self, tarea_id: str = None, expediente_id: str = None, parent=None):
        t0 = time.perf_counter()
        super().__init__(parent)
        self.setObjectName("tareaFormDialog")
        self._id = tarea_id
        self._is_edit = tarea_id is not None
        self._fixed_expediente = expediente_id
        self._original_responsable_username = ""
        self._original_responsable_display = ""

        self.setWindowTitle("Editar Tarea" if self._is_edit else "Nueva Tarea")
        self.setMinimumWidth(550)
        # Forzar contraste consistente al abrir desde notificaciones.
        self.setStyleSheet(
            """
            QDialog#tareaFormDialog { background-color: #f5f5f5; }
            QDialog#tareaFormDialog QLabel { color: #1a1a1a; background: transparent; }
            QDialog#tareaFormDialog QScrollArea { background-color: #f5f5f5; border: none; }
            QDialog#tareaFormDialog QWidget#tareaFormContainer { background-color: #f5f5f5; }
            """
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("Editar Tarea" if self._is_edit else "Nueva Tarea")
        title.setFont(QFont("Lato", 15, QFont.Weight.Bold))
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        form_container = QWidget()
        form_container.setObjectName("tareaFormContainer")

        form = QFormLayout(form_container)
        form.setSpacing(8)
        form.setContentsMargins(4, 4, 4, 4)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Carpeta selector (solo carpetas del usuario si rol restringido)
        self._cmb_expediente = QComboBox()
        self._cmb_expediente.setEditable(True)
        self._cmb_expediente.lineEdit().setPlaceholderText("Escriba para buscar carpeta...")
        self._cmb_expediente.addItem("-- Sin carpeta --", "")

        if self._fixed_expediente:
            # Caso optimizado: solo cargar la carpeta fija (evita query masiva)
            self._ensure_expediente_in_combo(self._fixed_expediente)
            idx = self._cmb_expediente.findData(self._fixed_expediente)
            if idx >= 0:
                self._cmb_expediente.setCurrentIndex(idx)
                self._cmb_expediente.setEnabled(False)
        else:
            # Carga inicial minima (top N carpetas activas con datos del cliente)
            self._load_initial_expedientes()

        # Autocompletado por subcadena al escribir en el combo de expediente
        exp_completer = QCompleter(self)
        exp_completer.setModel(self._cmb_expediente.model())
        exp_completer.setCompletionColumn(0)
        exp_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        exp_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        exp_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        exp_completer.activated[str].connect(self._on_expediente_completer_activated)
        self._cmb_expediente.setCompleter(exp_completer)

        # Busqueda incremental con debounce (solo si la carpeta no esta fija)
        self._exp_search_timer = QTimer(self)
        self._exp_search_timer.setSingleShot(True)
        self._exp_search_timer.setInterval(_SEARCH_DEBOUNCE_MS)
        self._exp_search_timer.timeout.connect(self._search_expedientes)
        if not self._fixed_expediente:
            self._cmb_expediente.lineEdit().textEdited.connect(
                lambda _: self._exp_search_timer.start()
            )

        # Layout horizontal: combo de carpeta + boton "Ir a la Carpeta"
        exp_row = QHBoxLayout()
        exp_row.addWidget(self._cmb_expediente, 1)
        self._btn_ir_expediente = QPushButton("Ir a la Carpeta")
        self._btn_ir_expediente.setProperty("variant", "secondary")
        self._btn_ir_expediente.setFixedWidth(130)
        self._btn_ir_expediente.clicked.connect(self._abrir_expediente)
        self._btn_ir_expediente.setVisible(False)
        exp_row.addWidget(self._btn_ir_expediente)
        form.addRow("Carpeta:", exp_row)

        # Mostrar/ocultar boton al cambiar el expediente seleccionado
        self._cmb_expediente.currentIndexChanged.connect(self._actualizar_btn_expediente)
        self._actualizar_btn_expediente()

        self._cmb_tipo = QComboBox()
        for t in TareaController.TIPOS_ACCION:
            self._cmb_tipo.addItem(t)
        form.addRow("Tipo accion:", self._cmb_tipo)

        self._txt_descripcion = QTextEdit()
        self._txt_descripcion.setMaximumHeight(80)
        form.addRow("Descripcion *:", self._txt_descripcion)

        self._cmb_responsable = NoWheelComboBox()
        self._cmb_responsable.setEditable(True)
        self._cmb_responsable.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._cmb_responsable.setPlaceholderText("Buscar por nombre o usuario...")
        users = get_active_users_fresh()
        self._users_cache = list(users)
        for u in users:
            label = f'{u.get("nombre_completo", "")} ({u.get("username", "")})'
            self._cmb_responsable.addItem(label, u.get("username", ""))
        resp_completer = QCompleter(self)
        resp_completer.setModel(self._cmb_responsable.model())
        resp_completer.setCompletionColumn(0)
        resp_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        resp_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        resp_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        resp_completer.activated[str].connect(self._on_responsable_completer)
        self._cmb_responsable.setCompleter(resp_completer)
        form.addRow("Responsable *:", self._cmb_responsable)

        self._date_inicio = NoWheelDateEdit()
        self._date_inicio.setCalendarPopup(True)
        self._date_inicio.setDate(QDate.currentDate())
        self._date_inicio.setDisplayFormat("dd/MM/yyyy")
        form.addRow("Fecha inicio:", self._date_inicio)

        self._date_vencimiento = NoWheelDateEdit()
        self._date_vencimiento.setCalendarPopup(True)
        self._date_vencimiento.setDate(QDate.currentDate().addDays(30))
        self._date_vencimiento.setDisplayFormat("dd/MM/yyyy")
        form.addRow("Fecha vencimiento:", self._date_vencimiento)

        self._cmb_estado = QComboBox()
        for e in TareaController.ESTADOS:
            self._cmb_estado.addItem(e)
        form.addRow("Estado:", self._cmb_estado)

        self._txt_resultado = QTextEdit()
        self._txt_resultado.setMaximumHeight(60)
        form.addRow("Resultado:", self._txt_resultado)

        scroll.setWidget(form_container)
        layout.addWidget(scroll)

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

        elapsed = time.perf_counter() - t0
        logger.info(
            "TareaFormDialog.__init__ tardo %.3fs (items expediente: %d, fixed: %s)",
            elapsed, self._cmb_expediente.count(), bool(self._fixed_expediente),
        )

    # ------------------------------------------------------------------
    # Helpers de carga de carpetas (combo expediente)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_expediente_label(e: dict) -> str:
        """Construir etiqueta para un item del combo de carpetas."""
        partes = [f'Carpeta #{e.get("id_expediente", "")}']
        nro_anses = e.get("numero_expediente_anses", "")
        if nro_anses:
            partes.append(f'ANSES {nro_anses}')
        partes.append(e.get("tipo_tramite", ""))
        cli_nombre = e.get("cli_nombre", "")
        cli_dni = e.get("cli_dni", "")
        if cli_nombre:
            cli_label = cli_nombre
            if cli_dni:
                cli_label += f' DNI {cli_dni}'
            partes.append(cli_label)
        partes.append(f'({e.get("responsable", "")})')
        return " - ".join(p for p in partes if p)

    def _load_initial_expedientes(self):
        """Carga las N carpetas mas recientes activas con datos del cliente (JOIN)."""
        exps = ExpedienteController.search_scoped_with_cliente(
            where="e.estado NOT IN ('Cerrado','Archivado')",
            order_by="e.id_expediente DESC",
            limit=_INITIAL_EXP_LIMIT,
        )
        for e in exps:
            self._cmb_expediente.addItem(self._build_expediente_label(e), e["_id"])

    def _search_expedientes(self):
        """Busqueda incremental de carpetas al escribir en el combo."""
        text = self._cmb_expediente.lineEdit().text().strip()
        if len(text) < _SEARCH_MIN_CHARS:
            return
        results = ExpedienteController.search_scoped_with_cliente(
            text=text,
            where="e.estado NOT IN ('Cerrado','Archivado')",
            order_by="e.id_expediente DESC",
            limit=_SEARCH_RESULT_LIMIT,
        )
        current_data = self._cmb_expediente.currentData()
        self._cmb_expediente.blockSignals(True)
        self._cmb_expediente.clear()
        self._cmb_expediente.addItem("-- Sin carpeta --", "")
        for e in results:
            self._cmb_expediente.addItem(self._build_expediente_label(e), e["_id"])
        if current_data:
            idx = self._cmb_expediente.findData(current_data)
            if idx >= 0:
                self._cmb_expediente.setCurrentIndex(idx)
        self._cmb_expediente.blockSignals(False)
        self._cmb_expediente.lineEdit().setText(text)
        self._cmb_expediente.lineEdit().setCursorPosition(len(text))
        self._cmb_expediente.showPopup()

    # ------------------------------------------------------------------
    # Acciones de UI
    # ------------------------------------------------------------------

    def _on_expediente_completer_activated(self, text: str):
        """Seleccionar la carpeta del combo cuando se elige del autocompletado."""
        idx = self._cmb_expediente.findText(text)
        if idx >= 0:
            self._cmb_expediente.setCurrentIndex(idx)

    def _on_responsable_completer(self, text: str):
        """Al elegir del popup de autocompletado, fijar el item del combo (username en data)."""
        idx = self._cmb_responsable.findText(text)
        if idx >= 0:
            self._cmb_responsable.setCurrentIndex(idx)

    def _actualizar_btn_expediente(self):
        """Mostrar u ocultar el boton 'Ir a la Carpeta' segun la seleccion."""
        exp_id = self._cmb_expediente.currentData()
        self._btn_ir_expediente.setVisible(bool(exp_id))

    def _abrir_expediente(self):
        """Abrir el formulario completo de la carpeta vinculada."""
        exp_id = self._cmb_expediente.currentData()
        if not exp_id:
            return
        from views.expedientes.expediente_form import ExpedienteFormDialog
        dlg = ExpedienteFormDialog(expediente_id=exp_id, parent=self)
        dlg.exec()

    def _ensure_expediente_in_combo(self, exp_id: str) -> int:
        """Asegura que una carpeta este en el combo, aunque no sea visible por scope.

        Retorna el indice del item en el combo, o -1 si no se pudo agregar.
        """
        if not exp_id:
            return -1
        idx = self._cmb_expediente.findData(exp_id)
        if idx >= 0:
            return idx
        exp_data = ExpedienteController.get_by_id(exp_id)
        if not exp_data:
            return -1
        # Enriquecer con datos del cliente para la etiqueta
        cid = exp_data.get("id_cliente", "")
        if cid:
            cli = ClienteController.get_by_id(cid)
            if cli:
                exp_data["cli_nombre"] = cli.get("nombre_completo", "")
                exp_data["cli_dni"] = cli.get("dni", "")
        label = self._build_expediente_label(exp_data)
        self._cmb_expediente.addItem(label, exp_data["_id"])
        return self._cmb_expediente.findData(exp_data["_id"])

    @staticmethod
    def _label_usuario(u: dict) -> str:
        return f'{u.get("nombre_completo", "").strip()} ({u.get("username", "")})'.strip()

    def _resolve_responsable(self) -> tuple[str, str]:
        """Devuelve (username, etiqueta) a partir del combo; resuelve si solo se escribio texto."""
        username = self._cmb_responsable.currentData() or ""
        text = self._cmb_responsable.currentText().strip()
        if username:
            return username, text
        if not text:
            return "", ""
        # Coincidencia exacta con algun item del combo
        for i in range(self._cmb_responsable.count()):
            if self._cmb_responsable.itemText(i).strip().lower() == text.lower():
                un = self._cmb_responsable.itemData(i)
                if un:
                    return str(un), self._cmb_responsable.itemText(i)
        # Patron "... (usuario)"
        m = re.search(r"\(\s*([^)]+)\s*\)\s*$", text)
        if m:
            u_try = m.group(1).strip().lower()
            for u in self._users_cache:
                if (u.get("username") or "").lower() == u_try:
                    return u.get("username", "") or "", self._label_usuario(u)
        t = text.lower()
        for u in self._users_cache:
            if (u.get("username") or "").lower() == t:
                return u.get("username", "") or "", self._label_usuario(u)
        for u in self._users_cache:
            nc = (u.get("nombre_completo") or "").strip().lower()
            if nc and nc == t:
                return u.get("username", "") or "", self._label_usuario(u)
        candidates = []
        for u in self._users_cache:
            nc = (u.get("nombre_completo") or "").strip().lower()
            if not nc:
                continue
            if t in nc or nc.startswith(t):
                candidates.append(u)
        if len(candidates) == 1:
            u = candidates[0]
            return u.get("username", "") or "", self._label_usuario(u)
        if len(candidates) > 1:
            starts = [
                u for u in candidates
                if (u.get("nombre_completo") or "").strip().lower().startswith(t)
            ]
            if len(starts) == 1:
                u = starts[0]
                return u.get("username", "") or "", self._label_usuario(u)
        return "", text

    # ------------------------------------------------------------------
    # Carga / guardado
    # ------------------------------------------------------------------

    def _load_data(self):
        data = TareaController.get_by_id(self._id)
        if not data:
            self.reject()
            return
        exp_id = data.get("id_expediente", "")
        idx = self._cmb_expediente.findData(exp_id)
        if idx < 0 and exp_id:
            idx = self._ensure_expediente_in_combo(exp_id)
        if idx >= 0:
            self._cmb_expediente.setCurrentIndex(idx)
        self._cmb_tipo.setCurrentText(data.get("tipo_accion", ""))
        self._txt_descripcion.setPlainText(data.get("descripcion", ""))
        resp_uname = data.get("responsable_username", "")
        idx_r = self._cmb_responsable.findData(resp_uname)
        if idx_r >= 0:
            self._cmb_responsable.setCurrentIndex(idx_r)
        elif data.get("responsable", ""):
            self._cmb_responsable.setEditText(data.get("responsable", ""))
        self._original_responsable_username = data.get("responsable_username", "") or ""
        self._original_responsable_display = data.get("responsable", "") or ""
        fi = data.get("fecha_inicio", "")
        if fi and len(fi) >= 10:
            self._date_inicio.setDate(QDate.fromString(fi[:10], "yyyy-MM-dd"))
        fv = data.get("fecha_vencimiento", "")
        if fv and len(fv) >= 10:
            self._date_vencimiento.setDate(QDate.fromString(fv[:10], "yyyy-MM-dd"))
        self._cmb_estado.setCurrentText(data.get("estado", "Pendiente"))
        self._txt_resultado.setPlainText(data.get("resultado", ""))

    def _save(self):
        desc = self._txt_descripcion.toPlainText().strip()
        resp_username, resp_resolved_label = self._resolve_responsable()
        resp_display = self._cmb_responsable.currentText().strip()
        if not desc:
            QMessageBox.warning(self, "Atencion", "La descripcion es obligatoria.")
            return
        if not resp_username:
            QMessageBox.warning(
                self,
                "Atencion",
                "No se encontro un usuario activo para el responsable.\n\n"
                "Escriba para buscar y elija de la lista, o nombre completo "
                "como figura en el sistema (entre varias personas, elija de la lista).",
            )
            return
        if resp_resolved_label:
            resp_display = resp_resolved_label

        if self._is_edit:
            old_key = (self._original_responsable_username or self._original_responsable_display).strip().lower()
            new_key = (resp_username or resp_display).strip().lower()
            if old_key and new_key and old_key != new_key:
                resp = QMessageBox.warning(
                    self,
                    "Confirmar cambio de responsable",
                    "Esta por cambiar el responsable de la tarea.\n\n"
                    "Desea confirmar este cambio?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if resp != QMessageBox.StandardButton.Yes:
                    return

        responsable_legible = resp_display.split("(")[0].strip() if resp_username else resp_display

        data = {
            "id_expediente": self._cmb_expediente.currentData() or "",
            "tipo_accion": self._cmb_tipo.currentText(),
            "descripcion": desc,
            "responsable": responsable_legible.upper(),
            "responsable_username": resp_username,
            "fecha_inicio": self._date_inicio.date().toString("yyyy-MM-dd"),
            "fecha_vencimiento": self._date_vencimiento.date().toString("yyyy-MM-dd"),
            "estado": self._cmb_estado.currentText(),
            "resultado": self._txt_resultado.toPlainText().strip(),
        }

        if self._is_edit:
            TareaController.update(self._id, data)
        else:
            session = Session.get()
            data["creado_por_username"] = session.username
            data["creado_por_nombre"] = session.nombre
            result = TareaController.create(data)
            # Notificar al responsable (si es distinto del creador)
            if resp_username and resp_username != session.username:
                exp_id = data.get("id_expediente", "")
                exp_label = ""
                if exp_id:
                    exp_data = ExpedienteController.get_by_id(exp_id)
                    if exp_data:
                        exp_label = f'#{exp_data.get("id_expediente", "")}'
                desc_corta = desc[:60] + ("..." if len(desc) > 60 else "")
                mensaje = (
                    f"Nueva tarea asignada en carpeta {exp_label}: "
                    f"{desc_corta}. Creada por {session.nombre}."
                )
                NotificacionController.create_for_tarea_asignada(
                    target_username=resp_username,
                    mensaje=mensaje,
                    id_referencia=result.get("_id", ""),
                )
        self.accept()
