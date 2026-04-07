"""Formulario de alta/edicion de Turno ANSES."""
import logging
import re
from datetime import date
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QTextEdit, QPushButton, QLabel, QComboBox,
    QMessageBox, QCheckBox, QCompleter, QScrollArea, QFrame, QWidget,
    QFileDialog,
)
from PySide6.QtCore import QDate, QTime, Qt, QStringListModel, QUrl
from PySide6.QtGui import QFont, QDesktopServices

logger = logging.getLogger(__name__)

from controllers.turno_controller import TurnoController
from controllers.documento_controller import DocumentoController
from controllers.cliente_controller import ClienteController
from controllers.expediente_controller import ExpedienteController
from controllers.notificacion_controller import NotificacionController
from services import anses_oficinas_service
from config import ANSES_PROVINCIA_DEFECTO
from core.auth import Session
from core.permissions import get_active_users_fresh
from views.widgets.no_wheel_combo import NoWheelComboBox
from views.widgets.no_wheel_datetime import NoWheelDateEdit, NoWheelTimeEdit


class TurnoFormDialog(QDialog):
    def __init__(self, turno_id: str = None, cliente_id: str = None,
                 expediente_id: str = None, parent=None):
        super().__init__(parent)
        self._id = turno_id
        self._is_edit = turno_id is not None
        self._fixed_cliente = cliente_id
        self._fixed_expediente = expediente_id
        self._selected_cliente_id: str = cliente_id or ""
        self._original_responsable_username = ""
        self._original_responsable_display = ""
        self._pending_constancia_path = ""
        self._remove_constancia = False
        self._loaded_constancia_doc_id = ""

        self.setWindowTitle("Editar Turno" if self._is_edit else "Nuevo Turno ANSES")
        self.setMinimumWidth(640)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("Editar Turno" if self._is_edit else "Nuevo Turno ANSES")
        title.setFont(QFont("Lato", 15, QFont.Weight.Bold))
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        form_container = QWidget()

        form = QFormLayout(form_container)
        form.setSpacing(10)
        form.setContentsMargins(4, 4, 4, 4)

        # ── Sección CLIENTE ──────────────────────────────────────────────────
        if self._fixed_cliente:
            # Viene prefijado desde otra pantalla: solo mostrar info, sin búsqueda.
            self._txt_buscar_cliente = None
            self._btn_buscar_cliente = None
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
            # Búsqueda libre: campo de texto + botón + label de resultado.
            cli_widget = QWidget()
            cli_vlay = QVBoxLayout(cli_widget)
            cli_vlay.setContentsMargins(0, 0, 0, 0)
            cli_vlay.setSpacing(4)

            search_row = QHBoxLayout()
            search_row.setSpacing(6)

            self._txt_buscar_cliente = QLineEdit()
            self._txt_buscar_cliente.setPlaceholderText(
                "Buscar por nombre o DNI (presione Enter o haga clic en Buscar)..."
            )
            self._txt_buscar_cliente.returnPressed.connect(self._buscar_cliente)
            search_row.addWidget(self._txt_buscar_cliente)

            self._btn_buscar_cliente = QPushButton("Buscar")
            self._btn_buscar_cliente.setFixedWidth(80)
            self._btn_buscar_cliente.clicked.connect(self._buscar_cliente)
            search_row.addWidget(self._btn_buscar_cliente)

            cli_vlay.addLayout(search_row)

            self._lbl_cliente_sel = QLabel("— Ningún cliente seleccionado —")
            self._lbl_cliente_sel.setWordWrap(True)
            self._lbl_cliente_sel.setStyleSheet("color: #888; font-size: 11px; padding: 2px 0;")
            cli_vlay.addWidget(self._lbl_cliente_sel)

            form.addRow("Cliente *:", cli_widget)

        # ── Sección CARPETA ──────────────────────────────────────────────────
        self._cmb_expediente = QComboBox()
        self._cmb_expediente.addItem("-- Sin carpeta --", "")

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
        elif self._fixed_cliente:
            self._reload_expedientes_for_cliente(self._fixed_cliente)

        form.addRow("Carpeta:", self._cmb_expediente)

        # ── Fecha y hora ─────────────────────────────────────────────────────
        self._date_turno = NoWheelDateEdit()
        self._date_turno.setCalendarPopup(True)
        self._date_turno.setDate(QDate.currentDate().addDays(7))
        self._date_turno.setDisplayFormat("dd/MM/yyyy")
        form.addRow("Fecha turno *:", self._date_turno)

        self._time_hora = NoWheelTimeEdit()
        self._time_hora.setDisplayFormat("HH:mm")
        self._time_hora.setTime(QTime(9, 0))
        form.addRow("Hora turno *:", self._time_hora)

        # ── Provincia ────────────────────────────────────────────────────────
        self._cmb_provincia = QComboBox()
        for p in TurnoController.get_provincias():
            self._cmb_provincia.addItem(p)
        idx_prov = self._cmb_provincia.findText(ANSES_PROVINCIA_DEFECTO)
        if idx_prov >= 0:
            self._cmb_provincia.setCurrentIndex(idx_prov)
        self._cmb_provincia.currentTextChanged.connect(self._on_provincia_changed)
        form.addRow("Provincia:", self._cmb_provincia)

        # ── Oficina ──────────────────────────────────────────────────────────
        self._cmb_oficina = QComboBox()
        self._cmb_oficina.setEditable(True)
        self._cmb_oficina.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        oficina_completer = QCompleter()
        oficina_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        oficina_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        oficina_completer.setMaxVisibleItems(15)
        self._cmb_oficina.setCompleter(oficina_completer)

        self._lbl_oficina_info = QLabel("")
        self._lbl_oficina_info.setWordWrap(True)
        self._lbl_oficina_info.setStyleSheet(
            "color: #6b6b6b; font-size: 11px; padding: 2px 4px; "
            "background-color: #f8f8f8; border: 1px solid #e0e0e0; border-radius: 4px;"
        )
        self._lbl_oficina_info.setVisible(False)

        self._load_oficinas(self._cmb_provincia.currentText())
        self._cmb_oficina.activated.connect(self._on_oficina_selected)
        self._cmb_oficina.currentTextChanged.connect(self._on_oficina_text_changed)
        form.addRow("Oficina ANSES *:", self._cmb_oficina)
        form.addRow("", self._lbl_oficina_info)

        # ── Tipo tramite ─────────────────────────────────────────────────────
        self._cmb_tipo = QComboBox()
        for t in TurnoController.TIPOS_TRAMITE:
            self._cmb_tipo.addItem(t)
        form.addRow("Tipo tramite:", self._cmb_tipo)

        # ── Codigo turno ─────────────────────────────────────────────────────
        self._txt_codigo = QLineEdit()
        self._txt_codigo.setPlaceholderText("Codigo de confirmacion de ANSES")
        form.addRow("Codigo turno:", self._txt_codigo)

        # ── Estado ───────────────────────────────────────────────────────────
        self._cmb_estado = QComboBox()
        for e in TurnoController.ESTADOS:
            self._cmb_estado.addItem(e)
        form.addRow("Estado:", self._cmb_estado)

        # ── Responsable ──────────────────────────────────────────────────────
        self._cmb_responsable = NoWheelComboBox()
        self._cmb_responsable.setEditable(True)
        self._cmb_responsable.setPlaceholderText("Quien del estudio gestiona")
        for u in get_active_users_fresh():
            label = f'{u.get("nombre_completo", "")} ({u.get("username", "")})'
            self._cmb_responsable.addItem(label, u.get("username", ""))
        form.addRow("Responsable *:", self._cmb_responsable)

        # ── Documentacion ────────────────────────────────────────────────────
        self._chk_doc = QCheckBox("La documentacion esta preparada")
        form.addRow("Documentacion:", self._chk_doc)

        # ── Notas preparacion ────────────────────────────────────────────────
        self._txt_notas = QTextEdit()
        self._txt_notas.setMaximumHeight(70)
        self._txt_notas.setPlaceholderText("Documentos a llevar, requisitos previos...")
        form.addRow("Notas preparacion:", self._txt_notas)

        # ── Resultado ────────────────────────────────────────────────────────
        self._txt_resultado = QTextEdit()
        self._txt_resultado.setMaximumHeight(70)
        self._txt_resultado.setPlaceholderText("Resultado del turno (completar despues)")
        form.addRow("Resultado:", self._txt_resultado)

        # ── Seguimiento ──────────────────────────────────────────────────────
        self._chk_nuevo = QCheckBox("Requiere sacar un nuevo turno")
        form.addRow("Seguimiento:", self._chk_nuevo)

        # ── Observaciones ────────────────────────────────────────────────────
        self._txt_observaciones = QTextEdit()
        self._txt_observaciones.setMaximumHeight(60)
        form.addRow("Observaciones:", self._txt_observaciones)

        constancia_row = QWidget()
        constancia_lay = QHBoxLayout(constancia_row)
        constancia_lay.setContentsMargins(0, 0, 0, 0)
        constancia_lay.setSpacing(8)
        self._lbl_constancia = QLabel("Sin constancia PDF")
        self._lbl_constancia.setWordWrap(True)
        self._lbl_constancia.setStyleSheet("color: #4a5568; font-size: 11px;")
        constancia_lay.addWidget(self._lbl_constancia, 1)
        self._btn_const_examinar = QPushButton("Examinar PDF...")
        self._btn_const_examinar.clicked.connect(self._pick_constancia_pdf)
        self._btn_const_ver = QPushButton("Ver")
        self._btn_const_ver.setEnabled(False)
        self._btn_const_ver.clicked.connect(self._view_constancia_pdf)
        self._btn_const_quitar = QPushButton("Quitar")
        self._btn_const_quitar.setEnabled(False)
        self._btn_const_quitar.clicked.connect(self._remove_constancia_pdf)
        constancia_lay.addWidget(self._btn_const_examinar)
        constancia_lay.addWidget(self._btn_const_ver)
        constancia_lay.addWidget(self._btn_const_quitar)
        form.addRow("Constancia PDF:", constancia_row)

        scroll.setWidget(form_container)
        layout.addWidget(scroll)

        # ── Botones ──────────────────────────────────────────────────────────
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
        else:
            self._refresh_constancia_ui()
            if self._fixed_cliente:
                self._sugerir_oficina_por_cliente()

    # ── Helpers: formato ─────────────────────────────────────────────────────

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
            parts.append(f"N° Carpeta física: {carpeta}")
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
        return " — ".join(partes)

    @staticmethod
    def _exp_sort_key(exp: dict) -> tuple[int, str]:
        raw = str(exp.get("id_expediente", "") or "").strip()
        try:
            return (int(raw), raw)
        except ValueError:
            return (0, raw)

    # ── Búsqueda de cliente ──────────────────────────────────────────────────

    def _buscar_clientes(self, text: str) -> list[dict]:
        query = str(text or "").strip()
        if not query:
            return []
        digits = self._digits(query)
        seen: set[str] = set()
        out: list[dict] = []
        if digits:
            for cli in ClienteController.search_by_dni(digits):
                cid = cli.get("_id", "")
                if cid and cid not in seen:
                    seen.add(cid)
                    out.append(cli)
        for cli in ClienteController.search_clientes(query):
            cid = cli.get("_id", "")
            if cid and cid not in seen:
                seen.add(cid)
                out.append(cli)
        # Priorizar clientes que ya tienen alguna carpeta activa.
        def _score(cli: dict) -> tuple[int, str]:
            cid = cli.get("_id", "")
            activos = 0
            if cid:
                exps = ExpedienteController.get_by_cliente(cid, limit=50)
                activos = sum(
                    1 for e in exps
                    if (e.get("estado", "") or "") not in ("Cerrado", "Archivado")
                )
            return (activos, str(cli.get("nombre_completo", "") or ""))

        out.sort(key=_score, reverse=True)
        return out[:200]

    def _buscar_cliente(self):
        if not self._txt_buscar_cliente:
            return
        text = self._txt_buscar_cliente.text().strip()
        if not text:
            QMessageBox.information(self, "Atencion", "Ingrese nombre o DNI para buscar.")
            return
        clientes = self._buscar_clientes(text)
        if not clientes:
            QMessageBox.information(
                self, "Sin resultados",
                "No se encontraron clientes con ese dato.\n"
                "Verifique el nombre o DNI ingresado."
            )
            return
        if len(clientes) == 1:
            self._set_cliente(clientes[0])
        else:
            from views.widgets.cliente_picker_dialog import ClientePickerDialog
            dlg = ClientePickerDialog(clientes, titulo="Seleccionar cliente", parent=self)
            if dlg.exec():
                cli_id = dlg.selected_id
                if cli_id:
                    cli = ClienteController.get_by_id(cli_id)
                    if cli:
                        self._set_cliente(cli)

    def _set_cliente(self, cli: dict):
        self._selected_cliente_id = cli.get("_id", "")
        self._lbl_cliente_sel.setText(self._format_cliente_info(cli))
        self._lbl_cliente_sel.setStyleSheet(
            "color: #1a5fa8; font-weight: bold; font-size: 12px; padding: 3px 0;"
        )
        if not self._fixed_expediente:
            self._reload_expedientes_for_cliente(self._selected_cliente_id)
            # Fallback visual inmediato: si no hay expediente vinculable, mostrar
            # la carpeta física del cliente para evitar que quede en "-- Sin carpeta --".
            if self._cmb_expediente.count() <= 1:
                nro_fisico = str(cli.get("numero_carpeta", "") or "").strip()
                if nro_fisico:
                    self._cmb_expediente.addItem(
                        f"N° Carpeta física: {nro_fisico} (sin vincular expediente)",
                        "",
                    )
                    self._cmb_expediente.setCurrentIndex(1)
        if not self._is_edit:
            self._sugerir_oficina_por_cliente()

    # ── Carpeta ──────────────────────────────────────────────────────────────

    def _reload_expedientes_for_cliente(self, cliente_id: str,
                                        selected_expediente_id: str = ""):
        if self._fixed_expediente:
            return
        self._cmb_expediente.blockSignals(True)
        self._cmb_expediente.clear()
        self._cmb_expediente.addItem("-- Sin carpeta --", "")
        cliente_data = ClienteController.get_by_id(cliente_id) if cliente_id else None
        if cliente_id:
            exps = ExpedienteController.get_scoped(
                where="e.id_cliente = ? AND e.estado NOT IN ('Cerrado','Archivado')",
                params=(cliente_id,),
                order_by="id_expediente DESC",
                limit=200,
            )
            # Fallback: si el alcance del usuario deja fuera expedientes en esta vista,
            # intentar por cliente para poder vincular turno a carpeta.
            if not exps:
                exps_all = ExpedienteController.get_by_cliente(cliente_id, limit=200)
                exps = [
                    e for e in exps_all
                    if (e.get("estado", "") or "") not in ("Cerrado", "Archivado")
                ]
                exps.sort(key=self._exp_sort_key, reverse=True)
            # Fallback adicional: si hay clientes duplicados por DNI (distinto _id),
            # traer también carpetas activas de esos registros para no dejar "Sin carpeta".
            if not exps:
                cli = ClienteController.get_by_id(cliente_id)
                dni = (cli or {}).get("dni", "")
                if dni:
                    clientes_mismo_dni = ClienteController.search_by_dni(dni)
                    cliente_ids = [
                        c.get("_id", "") for c in clientes_mismo_dni if c.get("_id", "")
                    ]
                    tmp: list[dict] = []
                    for cid in cliente_ids:
                        exps_cid = ExpedienteController.get_by_cliente(cid, limit=200)
                        for e in exps_cid:
                            if (e.get("estado", "") or "") not in ("Cerrado", "Archivado"):
                                tmp.append(e)
                    # Deduplicar por _id
                    seen: set[str] = set()
                    exps = []
                    for e in tmp:
                        eid = e.get("_id", "")
                        if eid and eid not in seen:
                            seen.add(eid)
                            exps.append(e)
                    exps.sort(key=self._exp_sort_key, reverse=True)
            for e in exps:
                self._cmb_expediente.addItem(self._format_expediente_label(e), e["_id"])
            if not exps and cliente_data:
                nro_fisico = str(cliente_data.get("numero_carpeta", "") or "").strip()
                if nro_fisico:
                    # No hay expediente activo/vinculado; mostrar al menos la carpeta física del cliente.
                    self._cmb_expediente.addItem(
                        f"N° Carpeta física: {nro_fisico} (sin vincular expediente)",
                        "",
                    )

        # Prioridad de selección:
        # 1. ID explícito pedido (modo edición o pre-selección)
        # 2. Carpeta más reciente del cliente (primera en la lista, orden DESC)
        # 3. "-- Sin carpeta --" si no hay ninguna activa
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

    # ── Oficinas ─────────────────────────────────────────────────────────────

    def _load_oficinas(self, provincia: str):
        self._cmb_oficina.blockSignals(True)
        try:
            self._cmb_oficina.clear()
            nombres = TurnoController.get_oficinas_anses(provincia)
            for i, nombre in enumerate(nombres):
                self._cmb_oficina.addItem(nombre)
                info = anses_oficinas_service.get_oficina_info(nombre)
                if info:
                    tip = anses_oficinas_service.formato_tooltip_oficina(info)
                    self._cmb_oficina.setItemData(i, tip, Qt.ItemDataRole.ToolTipRole)
            completer = self._cmb_oficina.completer()
            if completer:
                completer.setModel(QStringListModel(nombres))
        except Exception:
            logger.warning("Error al cargar oficinas ANSES en turno_form", exc_info=True)
            if self._cmb_oficina.count() == 0:
                self._cmb_oficina.addItem("Otra")
        finally:
            self._cmb_oficina.blockSignals(False)
        self._update_oficina_tooltip()

    def _on_provincia_changed(self, provincia: str):
        self._load_oficinas(provincia)

    def _on_oficina_selected(self, _index: int):
        self._update_oficina_tooltip()

    def _on_oficina_text_changed(self, _text: str):
        self._update_oficina_tooltip()

    def _update_oficina_tooltip(self):
        nombre = self._cmb_oficina.currentText()
        info = anses_oficinas_service.get_oficina_info(nombre)
        if info:
            self._cmb_oficina.setToolTip(anses_oficinas_service.formato_tooltip_oficina(info))
            parts = []
            if info.get("address"):
                parts.append(f"Dir: {info['address']}")
            if info.get("city"):
                parts.append(f"Ciudad: {info['city']}")
            if info.get("schedule"):
                parts.append(f"Horario: {info['schedule']}")
            if info.get("region"):
                parts.append(info["region"])
            self._lbl_oficina_info.setText("  |  ".join(parts))
            self._lbl_oficina_info.setVisible(True)
        else:
            self._cmb_oficina.setToolTip("")
            self._lbl_oficina_info.setText("")
            self._lbl_oficina_info.setVisible(False)

    def _sugerir_oficina_por_cliente(self):
        cliente_id = self._selected_cliente_id
        if not cliente_id:
            return
        try:
            localidad = TurnoController.get_localidad_cliente(cliente_id)
            if not localidad:
                return
            oficina = TurnoController.buscar_oficina_por_localidad(localidad)
            if not oficina:
                return
            provincia = oficina.get("province", "")
            if provincia:
                idx_p = self._cmb_provincia.findText(provincia)
                if idx_p >= 0:
                    self._cmb_provincia.setCurrentIndex(idx_p)
            nombre_oficina = oficina.get("office_name", "")
            if nombre_oficina:
                idx_o = self._cmb_oficina.findText(nombre_oficina)
                if idx_o >= 0:
                    self._cmb_oficina.setCurrentIndex(idx_o)
                else:
                    self._cmb_oficina.setCurrentText(nombre_oficina)
                self._update_oficina_tooltip()
        except Exception:
            logger.debug("Auto-deteccion de oficina fallo (no critico)", exc_info=True)

    # ── Carga de datos (edición) ──────────────────────────────────────────────

    def _load_data(self):
        data = TurnoController.get_by_id(self._id)
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
        else:
            if id_exp:
                idx = self._cmb_expediente.findData(id_exp)
                if idx >= 0:
                    self._cmb_expediente.setCurrentIndex(idx)

        ft = data.get("fecha_turno", "")
        if ft and len(ft) >= 10:
            self._date_turno.setDate(QDate.fromString(ft[:10], "yyyy-MM-dd"))

        hora_str = data.get("hora_turno", "")
        if hora_str:
            parsed = QTime.fromString(hora_str, "HH:mm")
            if parsed.isValid():
                self._time_hora.setTime(parsed)

        oficina_guardada = data.get("oficina_anses", "")
        provincia_oficina = anses_oficinas_service.get_provincia_de_oficina(oficina_guardada)
        if provincia_oficina:
            idx_p = self._cmb_provincia.findText(provincia_oficina)
            if idx_p >= 0:
                self._cmb_provincia.setCurrentIndex(idx_p)
        self._cmb_oficina.setCurrentText(oficina_guardada)

        self._cmb_tipo.setCurrentText(data.get("tipo_tramite", ""))
        self._txt_codigo.setText(data.get("codigo_turno", ""))
        self._cmb_estado.setCurrentText(data.get("estado", "Pendiente"))

        resp_uname = data.get("responsable_username", "")
        idx_r = self._cmb_responsable.findData(resp_uname)
        if idx_r >= 0:
            self._cmb_responsable.setCurrentIndex(idx_r)
        elif data.get("responsable", ""):
            self._cmb_responsable.setEditText(data.get("responsable", ""))
        self._original_responsable_username = data.get("responsable_username", "") or ""
        self._original_responsable_display = data.get("responsable", "") or ""

        self._chk_doc.setChecked(bool(data.get("documentacion_lista", 0)))
        self._txt_notas.setPlainText(data.get("notas_preparacion", ""))
        self._txt_resultado.setPlainText(data.get("resultado", ""))
        self._chk_nuevo.setChecked(bool(data.get("requiere_nuevo_turno", 0)))
        self._txt_observaciones.setPlainText(data.get("observaciones", ""))

        self._pending_constancia_path = ""
        self._remove_constancia = False
        self._loaded_constancia_doc_id = (data.get("id_constancia_doc") or "").strip()
        self._refresh_constancia_ui()

    def _refresh_constancia_ui(self):
        if self._pending_constancia_path:
            p = Path(self._pending_constancia_path)
            self._lbl_constancia.setText(f"Pendiente: {p.name}")
            self._btn_const_ver.setEnabled(True)
            self._btn_const_quitar.setEnabled(True)
            return
        if self._remove_constancia:
            self._lbl_constancia.setText("Se quitará la constancia al guardar.")
            self._btn_const_ver.setEnabled(False)
            self._btn_const_quitar.setEnabled(False)
            return
        if self._loaded_constancia_doc_id:
            doc = DocumentoController.get_by_id(self._loaded_constancia_doc_id)
            if doc:
                self._lbl_constancia.setText(doc.get("nombre", "Constancia PDF"))
                self._btn_const_ver.setEnabled(True)
                self._btn_const_quitar.setEnabled(True)
                return
        self._lbl_constancia.setText("Sin constancia PDF")
        self._btn_const_ver.setEnabled(False)
        self._btn_const_quitar.setEnabled(False)

    def _pick_constancia_pdf(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Constancia del turno (PDF)",
            "",
            "PDF (*.pdf)",
        )
        if not path:
            return
        p = Path(path)
        if p.suffix.lower() != ".pdf":
            QMessageBox.warning(self, "Constancia", "Solo se permiten archivos PDF.")
            return
        ok, err = DocumentoController.validate_file(str(p))
        if not ok:
            QMessageBox.warning(self, "Constancia", err or "Archivo no valido.")
            return
        self._pending_constancia_path = str(p.resolve())
        self._remove_constancia = False
        self._refresh_constancia_ui()

    def _view_constancia_pdf(self):
        if self._pending_constancia_path:
            p = Path(self._pending_constancia_path)
            if p.is_file():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.resolve())))
            return
        if not self._loaded_constancia_doc_id:
            return
        local = DocumentoController.ensure_local_file(self._loaded_constancia_doc_id)
        if local and local.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(local.resolve())))
        else:
            QMessageBox.warning(self, "Constancia", "No se pudo abrir el archivo.")

    def _remove_constancia_pdf(self):
        if self._pending_constancia_path:
            self._pending_constancia_path = ""
            self._remove_constancia = False
            self._refresh_constancia_ui()
            return
        if self._loaded_constancia_doc_id:
            self._remove_constancia = True
            self._refresh_constancia_ui()

    # ── Guardar ───────────────────────────────────────────────────────────────

    def _save(self):
        cliente_id = self._selected_cliente_id
        if not cliente_id:
            QMessageBox.warning(
                self, "Atencion",
                "Seleccione un cliente antes de guardar.\n"
                "Use el campo de búsqueda para encontrarlo por nombre o DNI."
            )
            if self._txt_buscar_cliente:
                self._txt_buscar_cliente.setFocus()
            return

        hora = self._time_hora.time().toString("HH:mm")

        resp_username = self._cmb_responsable.currentData() or ""
        resp_display = self._cmb_responsable.currentText().strip()
        if not resp_username and not resp_display:
            QMessageBox.warning(self, "Atencion", "Ingrese el responsable.")
            return

        if self._is_edit:
            old_key = (
                self._original_responsable_username or self._original_responsable_display
            ).strip().lower()
            new_key = (resp_username or resp_display).strip().lower()
            if old_key and new_key and old_key != new_key:
                resp = QMessageBox.warning(
                    self,
                    "Confirmar cambio de responsable",
                    "Esta por cambiar el responsable del turno.\n\nDesea confirmar este cambio?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if resp != QMessageBox.StandardButton.Yes:
                    return

        oficina = self._cmb_oficina.currentText().strip()
        if not oficina:
            QMessageBox.warning(self, "Atencion", "Seleccione una oficina.")
            return
        if self._cmb_oficina.findText(oficina) < 0:
            QMessageBox.warning(
                self, "Atencion",
                "La oficina ingresada no es valida.\n"
                "Seleccione una oficina de la lista desplegable."
            )
            self._cmb_oficina.setFocus()
            return

        responsable_legible = (
            resp_display.split("(")[0].strip() if resp_username else resp_display
        )

        data = {
            "id_cliente": cliente_id,
            "id_expediente": self._fixed_expediente or self._cmb_expediente.currentData() or "",
            "fecha_turno": self._date_turno.date().toString("yyyy-MM-dd"),
            "hora_turno": hora,
            "oficina_anses": oficina,
            "tipo_tramite": self._cmb_tipo.currentText(),
            "codigo_turno": self._txt_codigo.text().strip(),
            "estado": self._cmb_estado.currentText(),
            "responsable": responsable_legible.upper(),
            "responsable_username": resp_username,
            "documentacion_lista": 1 if self._chk_doc.isChecked() else 0,
            "notas_preparacion": self._txt_notas.toPlainText().strip(),
            "resultado": self._txt_resultado.toPlainText().strip(),
            "requiere_nuevo_turno": 1 if self._chk_nuevo.isChecked() else 0,
            "observaciones": self._txt_observaciones.toPlainText().strip(),
        }

        expediente_id = data.get("id_expediente", "")
        if not expediente_id and cliente_id:
            # Si no se eligió expediente, intentar resolver automáticamente por DNI
            # para vincular el turno a la carpeta correspondiente.
            direct_exps = ExpedienteController.get_by_cliente(cliente_id, limit=200)
            direct_exps = [
                e for e in direct_exps
                if (e.get("estado", "") or "") not in ("Cerrado", "Archivado")
            ]
            if direct_exps:
                direct_exps.sort(key=self._exp_sort_key, reverse=True)
                elegido = direct_exps[0]
                data["id_expediente"] = elegido.get("_id", "") or ""
                if data["id_expediente"]:
                    data["id_cliente"] = elegido.get("id_cliente", "") or cliente_id
                    expediente_id = data["id_expediente"]
            cli = ClienteController.get_by_id(cliente_id)
            dni = (cli or {}).get("dni", "")
            if not expediente_id and dni:
                candidatos: list[dict] = []
                for c in ClienteController.search_by_dni(dni):
                    cid = c.get("_id", "")
                    if not cid:
                        continue
                    exps = ExpedienteController.get_by_cliente(cid, limit=200)
                    for e in exps:
                        if (e.get("estado", "") or "") not in ("Cerrado", "Archivado"):
                            candidatos.append(e)
                if candidatos:
                    # Elegir carpeta activa más reciente por id_expediente (numérico).
                    candidatos.sort(key=self._exp_sort_key, reverse=True)
                    elegido = candidatos[0]
                    data["id_expediente"] = elegido.get("_id", "") or ""
                    if data["id_expediente"]:
                        data["id_cliente"] = elegido.get("id_cliente", "") or cliente_id
                        expediente_id = data["id_expediente"]
            if not expediente_id:
                # Último fallback: buscar clientes equivalentes por CUIL/nombre
                # y usar su carpeta activa más reciente.
                cli = ClienteController.get_by_id(cliente_id)
                raw_cuil = (cli or {}).get("cuil", "")
                cuil_digits = self._digits(raw_cuil)
                nombre_cli = str((cli or {}).get("nombre_completo", "") or "").strip()
                alt_clientes: list[dict] = []
                seen_alt: set[str] = set()

                if cuil_digits:
                    for c in ClienteController.search_clientes(cuil_digits):
                        cid = c.get("_id", "")
                        if cid and cid not in seen_alt:
                            seen_alt.add(cid)
                            alt_clientes.append(c)
                if nombre_cli:
                    for c in ClienteController.search_clientes(nombre_cli):
                        cid = c.get("_id", "")
                        if cid and cid not in seen_alt:
                            seen_alt.add(cid)
                            alt_clientes.append(c)

                candidatos_alt: list[dict] = []
                for c in alt_clientes:
                    cid = c.get("_id", "")
                    if not cid:
                        continue
                    exps = ExpedienteController.get_by_cliente(cid, limit=200)
                    for e in exps:
                        if (e.get("estado", "") or "") not in ("Cerrado", "Archivado"):
                            candidatos_alt.append(e)

                if candidatos_alt:
                    candidatos_alt.sort(key=self._exp_sort_key, reverse=True)
                    elegido = candidatos_alt[0]
                    data["id_expediente"] = elegido.get("_id", "") or ""
                    if data["id_expediente"]:
                        data["id_cliente"] = elegido.get("id_cliente", "") or data["id_cliente"]
                        expediente_id = data["id_expediente"]

        if expediente_id:
            exp_data = ExpedienteController.get_by_id(expediente_id)
            if not exp_data:
                QMessageBox.warning(
                    self, "Atencion",
                    "La carpeta seleccionada no existe. Seleccione una carpeta valida."
                )
                return
            if (exp_data.get("id_cliente", "") or "") != (cliente_id or ""):
                # En casos de duplicados de cliente por mismo DNI, al guardar
                # alineamos el cliente al de la carpeta para no perder la vinculación.
                data["id_cliente"] = exp_data.get("id_cliente", "") or data["id_cliente"]

        expediente_id = (data.get("id_expediente") or "").strip()

        doc_id_final = ""
        if self._is_edit:
            cur_t = TurnoController.get_by_id(self._id)
            doc_id_final = (cur_t or {}).get("id_constancia_doc", "") or ""

        if self._remove_constancia and doc_id_final:
            DocumentoController.delete(doc_id_final)
            doc_id_final = ""

        if self._pending_constancia_path:
            if not expediente_id:
                QMessageBox.warning(
                    self,
                    "Constancia",
                    "Para adjuntar la constancia PDF debe vincular el turno a una carpeta.",
                )
                return
            path = Path(self._pending_constancia_path)
            if not path.is_file():
                QMessageBox.warning(self, "Constancia", "El archivo seleccionado ya no existe.")
                return
            if path.suffix.lower() != ".pdf":
                QMessageBox.warning(self, "Constancia", "Solo se permiten archivos PDF.")
                return
            ok, err = DocumentoController.validate_file(str(path))
            if not ok:
                QMessageBox.warning(self, "Constancia", err or "Archivo no valido.")
                return
            if doc_id_final:
                DocumentoController.delete(doc_id_final)
                doc_id_final = ""
            session = Session.get()
            fecha = self._date_turno.date().toString("yyyy-MM-dd")
            hora_s = self._time_hora.time().toString("HH:mm")
            try:
                doc = DocumentoController.create({
                    "id_expediente": expediente_id,
                    "categoria": "Turnos ANSES",
                    "subcategoria": "Constancia",
                    "nombre": f"Constancia turno {fecha} {hora_s}",
                    "descripcion": "Constancia PDF turno ANSES",
                    "ruta_archivo": str(path.resolve()),
                    "fecha": date.today().isoformat(),
                    "mime_type": "application/pdf",
                    "responsable": session.nombre.upper() if session.logged_in else "",
                    "responsable_username": session.username if session.logged_in else "",
                })
            except ValueError as exc:
                QMessageBox.warning(self, "Constancia", str(exc))
                return
            doc_id_final = doc["_id"]

        data["id_constancia_doc"] = doc_id_final

        if self._is_edit:
            TurnoController.update(self._id, data)
        else:
            result = TurnoController.create(data)
            session = Session.get()
            if resp_username and resp_username != session.username:
                cli = ClienteController.get_by_id(cliente_id)
                cli_nombre = cli.get("nombre_completo", "") if cli else ""
                fecha_legible = self._date_turno.date().toString("dd/MM/yyyy")
                mensaje = (
                    f"Turno ANSES asignado: {cli_nombre} - "
                    f"{data['tipo_tramite']} el {fecha_legible} a las {hora} "
                    f"en {oficina}. Asignado por {session.nombre}."
                )
                NotificacionController.create_for_turno_asignado(
                    target_username=resp_username,
                    mensaje=mensaje,
                    id_referencia=result.get("_id", ""),
                )
        self.accept()
