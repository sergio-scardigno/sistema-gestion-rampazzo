"""Formulario de alta/edicion de Cita del estudio."""
import logging
import re

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QTextEdit, QPushButton, QLabel, QComboBox,
    QMessageBox, QScrollArea, QFrame, QWidget,
    QCompleter,
)
from PySide6.QtCore import QDate, QTime, Qt, QTimer, QStringListModel, QEvent
from PySide6.QtGui import QFont

from controllers.cita_controller import CitaController
from controllers.cliente_controller import ClienteController
from controllers.expediente_controller import ExpedienteController
from core.auth import Session
from core.permissions import tiene_permiso
from views.widgets.no_wheel_combo import NoWheelComboBox
from views.widgets.no_wheel_datetime import NoWheelDateEdit, NoWheelTimeEdit

logger = logging.getLogger(__name__)


class CitaFormDialog(QDialog):
    def __init__(self, cita_id: str = None, cliente_id: str = None,
                 expediente_id: str = None, fecha_default: str = None,
                 parent=None):
        super().__init__(parent)
        self._id = cita_id
        self._is_edit = cita_id is not None
        self._fixed_cliente = cliente_id
        self._fixed_expediente = expediente_id
        self._selected_cliente_id: str = cliente_id or ""

        session = Session.get()
        self._readonly = not tiene_permiso(session.rol, "citas.create") and not self._is_edit

        self.setWindowTitle("Editar Cita" if self._is_edit else "Nueva Cita")
        self.setMinimumWidth(600)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("Editar Cita" if self._is_edit else "Nueva Cita")
        title.setFont(QFont("Lato", 15, QFont.Weight.Bold))
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        form_container = QWidget()

        form = QFormLayout(form_container)
        form.setSpacing(10)
        form.setContentsMargins(4, 4, 4, 4)

        # -- CLIENTE --
        if self._fixed_cliente:
            self._txt_buscar_cliente = None
            cli = ClienteController.get_by_id(self._fixed_cliente)
            self._lbl_cliente_sel = QLabel(
                self._format_cliente_info(cli) if cli else "(Sin datos)"
            )
            self._lbl_cliente_sel.setWordWrap(True)
            self._lbl_cliente_sel.setStyleSheet(
                "color: #1a5fa8; font-weight: bold; font-size: 12px; padding: 3px 0;"
            )
            form.addRow("Cliente *:", self._lbl_cliente_sel)
        else:
            cli_widget = QWidget()
            cli_vlay = QVBoxLayout(cli_widget)
            cli_vlay.setContentsMargins(0, 0, 0, 0)
            cli_vlay.setSpacing(4)

            search_row = QHBoxLayout()
            search_row.setSpacing(6)

            self._txt_buscar_cliente = QLineEdit()
            self._txt_buscar_cliente.setPlaceholderText(
                "Nombre, DNI, N\u00b0 carpeta f\u00edsica o N\u00b0 carpeta sistema (autocompletado)..."
            )
            self._txt_buscar_cliente.returnPressed.connect(self._buscar_cliente)
            self._completer_pick: dict[str, tuple[str, str]] = {}
            self._completer_model = QStringListModel(self)
            self._completer = QCompleter(self)
            self._completer.setModel(self._completer_model)
            self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            self._completer.setMaxVisibleItems(18)
            self._completer.activated.connect(self._on_completer_activated)
            self._txt_buscar_cliente.setCompleter(self._completer)
            self._complete_timer = QTimer(self)
            self._complete_timer.setSingleShot(True)
            self._complete_timer.setInterval(220)
            self._complete_timer.timeout.connect(self._refresh_completer_suggestions)
            self._txt_buscar_cliente.textChanged.connect(self._on_search_text_changed)
            search_row.addWidget(self._txt_buscar_cliente)

            btn_buscar = QPushButton("Buscar")
            btn_buscar.setFixedWidth(80)
            btn_buscar.clicked.connect(self._buscar_cliente)
            search_row.addWidget(btn_buscar)

            cli_vlay.addLayout(search_row)

            self._lbl_cliente_sel = QLabel("\u2014 Ningun cliente seleccionado \u2014")
            self._lbl_cliente_sel.setWordWrap(True)
            self._lbl_cliente_sel.setStyleSheet("color: #888; font-size: 11px; padding: 2px 0;")
            cli_vlay.addWidget(self._lbl_cliente_sel)

            form.addRow("Cliente *:", cli_widget)

        # -- CARPETA (doble clic abre el modulo Carpetas) --
        self._cmb_expediente = QComboBox()
        self._cmb_expediente.addItem("-- Sin carpeta --", "")
        self._cmb_expediente.setToolTip(
            "Doble clic para abrir esta carpeta en el modulo Carpetas"
        )

        if self._fixed_expediente:
            exp_data = ExpedienteController.get_by_id(self._fixed_expediente)
            if exp_data:
                self._cmb_expediente.addItem(
                    self._format_expediente_label(exp_data), exp_data["_id"]
                )
            idx = self._cmb_expediente.findData(self._fixed_expediente)
            if idx >= 0:
                self._cmb_expediente.setCurrentIndex(idx)
            self._cmb_expediente.setEnabled(False)
            self._sync_carpeta_mouse_transparency()
        elif self._fixed_cliente:
            self._reload_expedientes_for_cliente(self._fixed_cliente)

        self._wrap_carpeta = QWidget()
        lay_carp = QVBoxLayout(self._wrap_carpeta)
        lay_carp.setContentsMargins(0, 0, 0, 0)
        lay_carp.setSpacing(2)
        lay_carp.addWidget(self._cmb_expediente)
        self._btn_ir_carpeta = QPushButton("Ir a carpeta")
        self._btn_ir_carpeta.clicked.connect(self._abrir_carpeta_seleccionada)
        lay_carp.addWidget(self._btn_ir_carpeta, alignment=Qt.AlignmentFlag.AlignLeft)
        self._cmb_expediente.currentIndexChanged.connect(self._sync_ir_carpeta_button_state)
        self._wrap_carpeta.installEventFilter(self)
        self._cmb_expediente.installEventFilter(self)
        form.addRow("Carpeta:", self._wrap_carpeta)
        self._sync_ir_carpeta_button_state()

        # -- FECHA --
        self._date_cita = NoWheelDateEdit()
        self._date_cita.setCalendarPopup(True)
        if fecha_default and len(fecha_default) >= 10:
            self._date_cita.setDate(QDate.fromString(fecha_default[:10], "yyyy-MM-dd"))
        else:
            self._date_cita.setDate(QDate.currentDate().addDays(1))
        self._date_cita.setDisplayFormat("dd/MM/yyyy")
        form.addRow("Fecha *:", self._date_cita)

        # -- HORA --
        self._time_cita = NoWheelTimeEdit()
        self._time_cita.setDisplayFormat("HH:mm")
        self._time_cita.setTime(QTime(9, 0))
        form.addRow("Hora *:", self._time_cita)

        # -- MOTIVO --
        self._txt_motivo = QTextEdit()
        self._txt_motivo.setMaximumHeight(80)
        self._txt_motivo.setPlaceholderText("Motivo de la cita (por que se cita al cliente)...")
        form.addRow("Motivo *:", self._txt_motivo)

        # -- ESTADO --
        self._cmb_estado = NoWheelComboBox()
        for e in CitaController.ESTADOS:
            self._cmb_estado.addItem(e)
        form.addRow("Estado:", self._cmb_estado)

        # -- OBSERVACIONES --
        self._txt_observaciones = QTextEdit()
        self._txt_observaciones.setMaximumHeight(60)
        self._txt_observaciones.setPlaceholderText("Observaciones adicionales (opcional)...")
        form.addRow("Observaciones:", self._txt_observaciones)

        scroll.setWidget(form_container)
        layout.addWidget(scroll)

        # -- BOTONES --
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        if self._readonly:
            btn_close = QPushButton("Cerrar")
            btn_close.clicked.connect(self.reject)
            btn_layout.addWidget(btn_close)
        else:
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

        if self._readonly:
            self._set_fields_readonly()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonDblClick:
            if obj is self._cmb_expediente:
                self._abrir_carpeta_seleccionada()
                return True
            if obj is self._wrap_carpeta:
                pt = event.position().toPoint()
                if self._cmb_expediente.geometry().contains(pt):
                    self._abrir_carpeta_seleccionada()
                    return True
        return super().eventFilter(obj, event)

    def _abrir_carpeta_seleccionada(self):
        exp_id = self._cmb_expediente.currentData()
        if not exp_id:
            QMessageBox.information(
                self,
                "Carpeta",
                "No hay una carpeta del sistema vinculada.\n"
                "Seleccione una carpeta en el desplegable antes de abrirla.",
            )
            return
        main = self.window()
        try:
            if hasattr(main, "_navigate"):
                main._navigate("expedientes")
        except Exception:
            logger.exception("cita_form: navegar a expedientes")
        from views.expedientes.expediente_form import ExpedienteFormDialog
        dlg = ExpedienteFormDialog(expediente_id=exp_id, parent=self)
        dlg.exec()
        try:
            if hasattr(main, "_views"):
                view = main._views.get("expedientes")
                if view and hasattr(view, "refresh"):
                    view.refresh()
        except Exception:
            logger.exception("cita_form: refrescar lista expedientes")

    # -- Helpers: formato --

    @staticmethod
    def _digits(value: str) -> str:
        return re.sub(r"[^\d]", "", str(value or "").strip())

    @staticmethod
    def _format_cliente_info(cliente: dict) -> str:
        nombre = cliente.get("nombre_completo", "")
        dni = cliente.get("dni", "")
        carpeta = cliente.get("numero_carpeta", "")
        parts = [nombre] if nombre else []
        if dni:
            parts.append(f"DNI: {dni}")
        if carpeta:
            parts.append(f"N\u00b0 Carpeta: {carpeta}")
        return "  |  ".join(parts) if parts else "(Sin datos)"

    @staticmethod
    def _format_expediente_label(exp: dict) -> str:
        num = exp.get("id_expediente", "")
        tipo = exp.get("tipo_tramite", "")
        rama = exp.get("rama", "")
        resp = exp.get("responsable", "")
        partes = [f"Carpeta #{num}"]
        if tipo:
            partes.append(tipo)
        if rama:
            partes.append(rama)
        if resp:
            partes.append(f"Resp: {resp}")
        return " \u2014 ".join(partes)

    @staticmethod
    def _exp_sort_key(exp: dict) -> tuple[int, str]:
        raw = str(exp.get("id_expediente", "") or "").strip()
        try:
            return (int(raw), raw)
        except ValueError:
            return (0, raw)

    def _sync_carpeta_mouse_transparency(self):
        """Con combo deshabilitado, el doble clic lo recibe el contenedor (_wrap_carpeta)."""
        self._cmb_expediente.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            not self._cmb_expediente.isEnabled(),
        )

    def _set_fields_readonly(self):
        if self._txt_buscar_cliente:
            self._txt_buscar_cliente.setEnabled(False)
        self._cmb_expediente.setEnabled(False)
        self._sync_carpeta_mouse_transparency()
        self._sync_ir_carpeta_button_state()
        self._date_cita.setEnabled(False)
        self._time_cita.setEnabled(False)
        self._txt_motivo.setReadOnly(True)
        self._cmb_estado.setEnabled(False)
        self._txt_observaciones.setReadOnly(True)

    # -- Busqueda de cliente + autocompletado --

    def _on_search_text_changed(self, _text: str):
        if not self._txt_buscar_cliente or not self._txt_buscar_cliente.isEnabled():
            return
        self._complete_timer.start()

    def _format_suggestion_label(self, cli: dict, exp: dict | None = None) -> str:
        nombre = (cli.get("nombre_completo") or "").strip() or "(Sin nombre)"
        parts = [nombre]
        dni = (cli.get("dni") or "").strip()
        if dni:
            parts.append(f"DNI {dni}")
        nc = (cli.get("numero_carpeta") or "").strip()
        if nc:
            parts.append(f"Carp. {nc}")
        if exp:
            ie = exp.get("id_expediente", "")
            tipo = (exp.get("tipo_tramite") or "").strip()
            frag = f"Exp #{ie}" if ie != "" else "Carpeta"
            if tipo:
                frag = f"{frag} — {tipo}"
            parts.append(frag)
        return "  |  ".join(parts)

    def _unique_suggestion_label(self, base: str, used: set[str]) -> str:
        if base not in used:
            used.add(base)
            return base
        n = 2
        while f"{base} ({n})" in used:
            n += 1
        s = f"{base} ({n})"
        used.add(s)
        return s

    def _gather_suggestion_rows(self, query: str) -> list[tuple[str, str, str]]:
        """(texto_popup, id_cliente, id_expediente_mongo_para_preseleccion)."""
        q = str(query or "").strip()
        if len(q) < 1:
            return []
        rows: list[tuple[str, str, str]] = []
        seen_pair: set[str] = set()
        used_labels: set[str] = set()

        def add_row(cli: dict | None, exp: dict | None, exp_pre: str):
            if not cli:
                return
            cid = cli.get("_id", "")
            if not cid:
                return
            key = f"{cid}|{exp_pre}"
            if key in seen_pair:
                return
            seen_pair.add(key)
            label = self._format_suggestion_label(cli, exp)
            label = self._unique_suggestion_label(label, used_labels)
            rows.append((label, cid, exp_pre))

        # 1) Coincidencias por expediente / cliente enlazado (numero sistema, tipo, etc.)
        try:
            exps = ExpedienteController.search_scoped_with_cliente(
                text=q, order_by="e.id_expediente DESC", limit=40,
            )
            for exp in exps:
                cid = exp.get("id_cliente", "")
                if not cid:
                    continue
                cli = ClienteController.get_by_id(cid)
                add_row(cli, exp, exp.get("_id", "") or "")
        except Exception:
            logger.exception("cita_form: busqueda por expediente")

        digits = self._digits(q)
        if digits:
            for cli in ClienteController.search_by_dni(digits):
                add_row(cli, None, "")

        # 2) Numero de carpeta fisica exacto
        exact_carp = ClienteController.get_by_numero_carpeta(q)
        if exact_carp:
            add_row(exact_carp, None, "")

        # 3) Busqueda amplia (nombre, DNI, CUIL, email, telefonos, numero_carpeta LIKE)
        for cli in ClienteController.search_clientes(q):
            add_row(cli, None, "")

        return rows[:50]

    def _refresh_completer_suggestions(self):
        if not self._txt_buscar_cliente:
            return
        text = self._txt_buscar_cliente.text().strip()
        self._completer_pick.clear()
        if len(text) < 1:
            self._completer_model.setStringList([])
            return
        suggestion_rows = self._gather_suggestion_rows(text)
        labels: list[str] = []
        for label, cid, exp_id in suggestion_rows:
            labels.append(label)
            self._completer_pick[label] = (cid, exp_id)
        self._completer_model.setStringList(labels)

    def _on_completer_activated(self, text: str):
        if not text:
            return
        tup = self._completer_pick.get(text.strip())
        if not tup:
            return
        cid, exp_pre = tup
        cli = ClienteController.get_by_id(cid)
        if cli:
            self._set_cliente(cli, preselect_expediente_id=exp_pre or "")

    def _buscar_cliente(self):
        if not self._txt_buscar_cliente:
            return
        text = self._txt_buscar_cliente.text().strip()
        if not text:
            QMessageBox.information(
                self, "Atencion",
                "Ingrese nombre, DNI, N\u00b0 de carpeta u otro dato para buscar.",
            )
            return
        suggestion_rows = self._gather_suggestion_rows(text)
        if not suggestion_rows:
            QMessageBox.information(
                self, "Sin resultados",
                "No se encontraron clientes o carpetas con ese dato.\n"
                "Pruebe con nombre, DNI, n\u00b0 de carpeta f\u00edsica o n\u00b0 de carpeta del sistema.",
            )
            return
        clientes_map: dict[str, dict] = {}
        preselect_by_cid: dict[str, str] = {}
        for _lbl, cid, exp_pre in suggestion_rows:
            if cid not in clientes_map:
                cli = ClienteController.get_by_id(cid)
                if cli:
                    clientes_map[cid] = cli
            if exp_pre and cid not in preselect_by_cid:
                preselect_by_cid[cid] = exp_pre
        clientes = list(clientes_map.values())
        if len(clientes) == 1:
            cid = clientes[0].get("_id", "")
            self._set_cliente(
                clientes[0],
                preselect_expediente_id=preselect_by_cid.get(cid, ""),
            )
            return
        from views.widgets.cliente_picker_dialog import ClientePickerDialog
        dlg = ClientePickerDialog(clientes, titulo="Seleccionar cliente", parent=self)
        if dlg.exec():
            cli_id = dlg.selected_id
            if cli_id:
                cli = ClienteController.get_by_id(cli_id)
                if cli:
                    self._set_cliente(
                        cli,
                        preselect_expediente_id=preselect_by_cid.get(cli_id, ""),
                    )

    def _set_cliente(self, cli: dict, preselect_expediente_id: str = ""):
        self._selected_cliente_id = cli.get("_id", "")
        self._lbl_cliente_sel.setText(self._format_cliente_info(cli))
        self._lbl_cliente_sel.setStyleSheet(
            "color: #1a5fa8; font-weight: bold; font-size: 12px; padding: 3px 0;"
        )
        if not self._fixed_expediente:
            self._reload_expedientes_for_cliente(
                self._selected_cliente_id,
                selected_expediente_id=preselect_expediente_id,
            )

    # -- Carpeta --

    def _reload_expedientes_for_cliente(self, cliente_id: str,
                                        selected_expediente_id: str = ""):
        if self._fixed_expediente:
            return
        self._cmb_expediente.blockSignals(True)
        self._cmb_expediente.clear()
        self._cmb_expediente.addItem("-- Sin carpeta --", "")
        if cliente_id:
            exps = ExpedienteController.get_by_cliente(cliente_id, limit=200)
            exps = [
                e for e in exps
                if (e.get("estado", "") or "") not in ("Cerrado", "Archivado")
            ]
            exps.sort(key=self._exp_sort_key, reverse=True)
            for e in exps:
                self._cmb_expediente.addItem(self._format_expediente_label(e), e["_id"])

        idx = -1
        if selected_expediente_id:
            idx = self._cmb_expediente.findData(selected_expediente_id)
        if idx >= 0:
            self._cmb_expediente.setCurrentIndex(idx)
        elif cliente_id and self._cmb_expediente.count() > 1:
            self._cmb_expediente.setCurrentIndex(1)
        else:
            self._cmb_expediente.setCurrentIndex(0)
        self._cmb_expediente.blockSignals(False)
        self._sync_ir_carpeta_button_state()

    # -- Carga de datos (edicion) --

    def _load_data(self):
        data = CitaController.get_by_id(self._id)
        if not data:
            self.reject()
            return

        id_cli = data.get("id_cliente", "")
        if id_cli:
            cli = ClienteController.get_by_id(id_cli)
            if cli:
                self._selected_cliente_id = id_cli
                self._lbl_cliente_sel.setText(self._format_cliente_info(cli))
                self._lbl_cliente_sel.setStyleSheet(
                    "color: #1a5fa8; font-weight: bold; font-size: 12px; padding: 3px 0;"
                )
                if self._txt_buscar_cliente:
                    self._txt_buscar_cliente.setText(cli.get("nombre_completo", ""))

        id_exp = data.get("id_expediente", "")
        if not self._fixed_expediente:
            self._reload_expedientes_for_cliente(id_cli, selected_expediente_id=id_exp)

        ft = data.get("fecha_cita", "")
        if ft and len(ft) >= 10:
            self._date_cita.setDate(QDate.fromString(ft[:10], "yyyy-MM-dd"))

        hora_str = data.get("hora_cita", "")
        if hora_str:
            parsed = QTime.fromString(hora_str, "HH:mm")
            if parsed.isValid():
                self._time_cita.setTime(parsed)

        self._txt_motivo.setPlainText(data.get("motivo", ""))
        self._cmb_estado.setCurrentText(data.get("estado", "Pendiente"))
        self._txt_observaciones.setPlainText(data.get("observaciones", ""))
        self._sync_ir_carpeta_button_state()

    def _sync_ir_carpeta_button_state(self):
        if not hasattr(self, "_btn_ir_carpeta"):
            return
        exp_id = self._cmb_expediente.currentData()
        self._btn_ir_carpeta.setEnabled(bool(exp_id))

    # -- Guardar --

    def _save(self):
        cliente_id = self._selected_cliente_id
        if not cliente_id:
            QMessageBox.warning(
                self, "Atencion",
                "Seleccione un cliente antes de guardar.\n"
                "Use el campo de busqueda para encontrarlo por nombre o DNI."
            )
            if self._txt_buscar_cliente:
                self._txt_buscar_cliente.setFocus()
            return

        motivo = self._txt_motivo.toPlainText().strip()
        if not motivo:
            QMessageBox.warning(self, "Atencion", "Ingrese el motivo de la cita.")
            self._txt_motivo.setFocus()
            return

        session = Session.get()

        data = {
            "id_cliente": cliente_id,
            "id_expediente": (
                self._fixed_expediente
                or self._cmb_expediente.currentData()
                or ""
            ),
            "fecha_cita": self._date_cita.date().toString("yyyy-MM-dd"),
            "hora_cita": self._time_cita.time().toString("HH:mm"),
            "motivo": motivo,
            "estado": self._cmb_estado.currentText(),
            "observaciones": self._txt_observaciones.toPlainText().strip(),
        }

        if not self._is_edit:
            data["citado_por"] = (session.nombre or "").upper()
            data["citado_por_username"] = session.username or ""
            data["responsable"] = (session.nombre or "").upper()
            data["responsable_username"] = session.username or ""

        if self._is_edit:
            CitaController.update(self._id, data)
        else:
            CitaController.create(data)

        self.accept()
