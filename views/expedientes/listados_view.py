"""Vista Listados: filtros por estado/etapa y gestion rapida de carpeta."""
from __future__ import annotations
import json

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QMessageBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QPlainTextEdit,
    QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from controllers.expediente_controller import ExpedienteController
from core.auth import Session
from views.widgets.filterable_table import FilterableTable
from views.expedientes.expediente_form import ExpedienteFormDialog

COLUMNS = [
    ("id_expediente", "Carpeta"),
    ("cli_dni", "DNI"),
    ("clave_fiscal", "Clave CUIT"),
    ("clave_mi_anses", "Clave ANSES"),
    ("numero_expediente_anses", "Nro Tramite"),
    ("estado", "Estado"),
    ("etapa_label", "Etapa"),
    ("observaciones", "Observacion al equipo"),
]


class EstadoEtapaDialog(QDialog):
    """Dialogo simple para actualizar estado y etapa."""

    def __init__(self, estado_actual: str, etapa_actual: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Actualizar estado del tramite")
        self.setMinimumWidth(430)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._cmb_estado = QComboBox()
        for estado in ExpedienteController.ESTADOS:
            self._cmb_estado.addItem(estado, estado)
        idx_estado = max(self._cmb_estado.findData(estado_actual), 0)
        self._cmb_estado.setCurrentIndex(idx_estado)
        form.addRow("Estado:", self._cmb_estado)

        self._cmb_etapa = QComboBox()
        for etapa in ExpedienteController.ETAPAS:
            self._cmb_etapa.addItem(etapa["titulo"], etapa["codigo"])
        ExpedienteController.aplicar_colores_items_combo_etapas(self._cmb_etapa)
        idx_etapa = max(self._cmb_etapa.findData(etapa_actual), 0)
        self._cmb_etapa.setCurrentIndex(idx_etapa)
        self._cmb_etapa.currentIndexChanged.connect(self._on_etapa_changed)
        form.addRow("Etapa:", self._cmb_etapa)

        layout.addLayout(form)
        actions = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        actions.accepted.connect(self.accept)
        actions.rejected.connect(self.reject)
        layout.addWidget(actions)

    def _on_etapa_changed(self):
        sugerido = self._estado_sugerido_por_etapa(self._cmb_etapa.currentData() or "")
        if sugerido:
            idx = self._cmb_estado.findData(sugerido)
            if idx >= 0:
                self._cmb_estado.setCurrentIndex(idx)

    @staticmethod
    def _estado_sugerido_por_etapa(etapa_codigo: str) -> str:
        if etapa_codigo == "favorable":
            return "Favorable"
        if etapa_codigo == "desfavorable":
            return "Desfavorable"
        if etapa_codigo in {"en_espera_condicion"}:
            return "En espera"
        if etapa_codigo:
            return "En tramite"
        return ""

    def values(self) -> tuple[str, str]:
        return (
            self._cmb_estado.currentData() or "",
            self._cmb_etapa.currentData() or "",
        )


class ListadosView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Listados")
        title.setFont(QFont("Lato", 17, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        self._cmb_estado = QComboBox()
        self._cmb_estado.addItem("Todos los estados", "")
        for estado in ExpedienteController.ESTADOS:
            self._cmb_estado.addItem(estado, estado)
        self._cmb_estado.currentIndexChanged.connect(self.refresh)
        header.addWidget(self._cmb_estado)

        self._cmb_etapa = QComboBox()
        self._cmb_etapa.addItem("Todas las etapas", "")
        for etapa in ExpedienteController.ETAPAS:
            self._cmb_etapa.addItem(etapa["titulo"], etapa["codigo"])
        ExpedienteController.aplicar_colores_items_combo_etapas(self._cmb_etapa)
        self._cmb_etapa.currentIndexChanged.connect(self.refresh)
        header.addWidget(self._cmb_etapa)

        self._cmb_cambios = QComboBox()
        self._cmb_cambios.addItem("Todos", "")
        self._cmb_cambios.addItem("Con cambios recientes (7 dias)", "recentes")
        self._cmb_cambios.currentIndexChanged.connect(self.refresh)
        header.addWidget(self._cmb_cambios)

        btn_refresh = QPushButton("Actualizar")
        btn_refresh.setProperty("variant", "secondary")
        btn_refresh.clicked.connect(self.refresh)
        header.addWidget(btn_refresh)

        self._lbl_copy_hint = QLabel("Click en DNI/Clave/Nro tramite para copiar")
        self._lbl_copy_hint.setStyleSheet("color: #5f6b7a; font-size: 11px;")
        header.addWidget(self._lbl_copy_hint)

        btn_estado = QPushButton("Cambiar estado/etapa")
        btn_estado.clicked.connect(self._cambiar_estado_etapa)
        header.addWidget(btn_estado)

        btn_open = QPushButton("Abrir carpeta")
        btn_open.setProperty("variant", "secondary")
        btn_open.clicked.connect(self._abrir_carpeta)
        header.addWidget(btn_open)

        layout.addLayout(header)

        self._table = FilterableTable(
            COLUMNS,
            search_fields=["cli_nombre", "cli_dni", "id_expediente", "numero_expediente_anses"],
            search_placeholder="Buscar por carpeta, DNI o nro tramite...",
        )
        self._table.row_double_clicked.connect(self._open_detail)
        self._table.row_selected.connect(self._on_row_selected)
        self._table._table.cellClicked.connect(self._copy_cell_if_needed)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._table, 1)

        self._editor_panel = QWidget()
        self._editor_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        editor_block = QVBoxLayout(self._editor_panel)
        editor_block.setContentsMargins(0, 0, 0, 0)
        editor_block.setSpacing(6)
        self._lbl_selected = QLabel("Carpeta seleccionada: -")
        self._lbl_selected.setStyleSheet("font-weight: 600; color: #1f2937;")
        editor_block.addWidget(self._lbl_selected)

        # Campos compactos (~10% de la altura que tomaban al expandirse); scroll si hace falta.
        _compact_h = 36

        self._txt_obs_editor = QPlainTextEdit()
        self._txt_obs_editor.setPlaceholderText(
            "Observacion de carpeta (interna de la carpeta)..."
        )
        self._txt_obs_editor.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        self._txt_obs_editor.setMinimumHeight(27)
        self._txt_obs_editor.setMaximumHeight(_compact_h)
        self._txt_obs_editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        editor_block.addWidget(self._txt_obs_editor)

        self._txt_msg_notif = QPlainTextEdit()
        self._txt_msg_notif.setPlaceholderText(
            "Mensaje para notificacion al responsable primario/secundario..."
        )
        self._txt_msg_notif.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        self._txt_msg_notif.setMinimumHeight(27)
        self._txt_msg_notif.setMaximumHeight(_compact_h)
        self._txt_msg_notif.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        editor_block.addWidget(self._txt_msg_notif)

        self._txt_para_chequear = QPlainTextEdit()
        self._txt_para_chequear.setPlaceholderText(
            "Observacion para chequear (seguimiento de la carpeta)..."
        )
        self._txt_para_chequear.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        self._txt_para_chequear.setMinimumHeight(27)
        self._txt_para_chequear.setMaximumHeight(_compact_h)
        self._txt_para_chequear.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        editor_block.addWidget(self._txt_para_chequear)

        actions = QHBoxLayout()
        actions.addStretch()
        btn_guardar_obs = QPushButton("Guardar observacion")
        btn_guardar_obs.clicked.connect(self._guardar_observacion_inline)
        actions.addWidget(btn_guardar_obs)
        editor_block.addLayout(actions)
        layout.addWidget(self._editor_panel, 0)

        self._current_expediente_id = ""

    def refresh(self):
        conditions: list[str] = []
        params: tuple = ()

        estado = self._cmb_estado.currentData()
        if estado:
            conditions.append("e.estado = ?")
            params += (estado,)

        etapa = self._cmb_etapa.currentData()
        if etapa:
            conditions.append("e.etapa_codigo = ?")
            params += (etapa,)

        cambios = self._cmb_cambios.currentData()
        if cambios == "recentes":
            conditions.append("SUBSTR(e.updated_at, 1, 10) >= date('now', '-7 day')")

        where = " AND ".join(conditions)
        data = ExpedienteController.get_scoped_with_cliente(
            where=where,
            params=params,
            order_by="e.updated_at DESC",
        )
        etapas_map = {x["codigo"]: x["titulo"] for x in ExpedienteController.ETAPAS}
        for row in data:
            row["etapa_label"] = etapas_map.get(row.get("etapa_codigo", ""), row.get("etapa_codigo", ""))
        self._table.set_data(data)
        if self._current_expediente_id:
            self._reload_selected_context(self._current_expediente_id)

    def _selected_row(self) -> dict | None:
        selected_id = self._table.get_selected_id()
        if not selected_id:
            QMessageBox.information(self, "Atencion", "Seleccione una carpeta del listado.")
            return None
        selected = ExpedienteController.get_by_id(selected_id)
        if not selected:
            QMessageBox.warning(self, "Carpeta", "La carpeta seleccionada no existe.")
            return None
        return selected

    def _can_edit_team_notes(self, expediente: dict) -> bool:
        session = Session.get()
        if not session.logged_in:
            return False
        if session.rol == "secretaria":
            return True
        username = session.username
        if username == (expediente.get("responsable_username", "") or "").strip():
            return True
        secundario = ExpedienteController.secundario_efectivo_username(expediente)
        return username == secundario

    def _guardar_observacion_inline(self):
        expediente = self._selected_row()
        if not expediente:
            return
        if not self._can_edit_team_notes(expediente):
            QMessageBox.warning(
                self,
                "Sin permisos",
                "Solo secretaria y encargados de la carpeta pueden editar la observacion al equipo.",
            )
            return
        actual = (expediente.get("observaciones", "") or "").strip()
        nuevo = self._txt_obs_editor.toPlainText().strip()
        datos_rama = self._build_datos_rama(expediente)
        msg_notif = self._txt_msg_notif.toPlainText().strip()
        para_chequear = self._txt_para_chequear.toPlainText().strip()
        old_msg_notif = (datos_rama.get("listados_mensaje_notificacion_equipo", "") or "").strip()
        old_para_chequear = (datos_rama.get("listados_para_chequear", "") or "").strip()
        if (
            nuevo == actual.strip()
            and msg_notif == old_msg_notif
            and para_chequear == old_para_chequear
        ):
            return
        datos_rama["listados_mensaje_notificacion_equipo"] = msg_notif
        datos_rama["listados_para_chequear"] = para_chequear
        updated = ExpedienteController.update(
            expediente["_id"],
            {
                "observaciones": nuevo,
                "datos_rama": datos_rama,
            },
        )
        if not updated:
            QMessageBox.warning(self, "Error", "No se pudo guardar la observacion.")
            return
        self.refresh()

    def _cambiar_estado_etapa(self):
        expediente = self._selected_row()
        if not expediente:
            return
        if not self._can_edit_team_notes(expediente):
            QMessageBox.warning(
                self,
                "Sin permisos",
                "Solo secretaria y encargados de la carpeta pueden cambiar estado o etapa desde este listado.",
            )
            return
        dlg = EstadoEtapaDialog(
            expediente.get("estado", ""),
            expediente.get("etapa_codigo", ""),
            parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        estado, etapa = dlg.values()
        payload = {"estado": estado, "etapa_codigo": etapa}
        datos_rama = self._build_datos_rama(expediente)
        msg_notif = self._txt_msg_notif.toPlainText().strip()
        para_chequear = self._txt_para_chequear.toPlainText().strip()
        payload["mensaje_notificacion_equipo"] = msg_notif
        datos_rama["listados_mensaje_notificacion_equipo"] = msg_notif
        datos_rama["listados_para_chequear"] = para_chequear
        payload["datos_rama"] = datos_rama
        nota = para_chequear
        if nota:
            payload["observacion_transicion"] = nota
        if (
            (estado or "") == (expediente.get("estado", "") or "")
            and (etapa or "") == (expediente.get("etapa_codigo", "") or "")
            and not msg_notif
            and not para_chequear
        ):
            QMessageBox.information(
                self,
                "Sin cambios",
                "No hay cambios para guardar en estado, etapa ni observaciones.",
            )
            return
        updated = ExpedienteController.update(expediente["_id"], payload)
        if not updated:
            QMessageBox.warning(self, "Error", "No se pudo actualizar el estado de la carpeta.")
            return
        self.refresh()
        self._reload_selected_context(expediente["_id"])
        QMessageBox.information(self, "Guardado", "Se guardo el cambio en la carpeta.")

    def _abrir_carpeta(self):
        _id = self._table.get_selected_id()
        if not _id:
            QMessageBox.information(self, "Atencion", "Seleccione una carpeta.")
            return
        self._open_detail(_id)

    def _open_detail(self, _id: str):
        dlg = ExpedienteFormDialog(expediente_id=_id, parent=self)
        if dlg.exec():
            self.refresh()

    def _on_row_selected(self, expediente_id: str):
        self._reload_selected_context(expediente_id)

    def _reload_selected_context(self, expediente_id: str):
        if not expediente_id:
            return
        expediente = ExpedienteController.get_by_id(expediente_id)
        if not expediente:
            return
        self._current_expediente_id = expediente_id
        self._lbl_selected.setText(
            f"Carpeta seleccionada: #{expediente.get('id_expediente', '')} | "
            f"Estado: {expediente.get('estado', '')} | Etapa: {expediente.get('etapa_codigo', '')}"
        )
        self._txt_obs_editor.setPlainText(expediente.get("observaciones", "") or "")
        datos_rama = self._build_datos_rama(expediente)
        self._txt_msg_notif.setPlainText(
            (datos_rama.get("listados_mensaje_notificacion_equipo", "") or "")
        )
        self._txt_para_chequear.setPlainText(
            (datos_rama.get("listados_para_chequear", "") or "")
        )
        self._txt_obs_editor.setReadOnly(not self._can_edit_team_notes(expediente))
        readonly = not self._can_edit_team_notes(expediente)
        self._txt_msg_notif.setReadOnly(readonly)
        self._txt_para_chequear.setReadOnly(readonly)

    def _copy_cell_if_needed(self, row_idx: int, col_idx: int):
        field = COLUMNS[col_idx][0]
        if field not in {"cli_dni", "clave_fiscal", "clave_mi_anses", "numero_expediente_anses"}:
            return
        item = self._table._table.item(row_idx, col_idx)
        if not item:
            return
        value = (item.text() or "").strip()
        if not value:
            return
        QApplication.clipboard().setText(value)
        self._lbl_copy_hint.setText(f"Copiado: {COLUMNS[col_idx][1]} = {value}")

    @staticmethod
    def _build_datos_rama(expediente: dict) -> dict:
        raw = expediente.get("datos_rama", {})
        if isinstance(raw, dict):
            return dict(raw)
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        return {}
