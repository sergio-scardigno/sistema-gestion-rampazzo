"""Listado y detalle de requerimientos de migracion por carpeta."""
from __future__ import annotations

import json
from datetime import date

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QMessageBox,
    QWidget,
    QFrame,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QDialogButtonBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QInputDialog,
)
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QFont

from controllers.expediente_controller import ExpedienteController
from controllers.migracion_requerimiento_controller import (
    ESTADOS_AVANCE_ETAPA,
    MigracionRequerimientoController,
    MigracionRequerimientoEtapaController,
)
from controllers.tarea_controller import TareaController
from views.widgets.no_wheel_combo import NoWheelComboBox
from views.widgets.no_wheel_datetime import NoWheelDateEdit


def _detalle_historial_texto(detalle) -> str:
    """detalle puede venir como str o como dict/list tras deserializar JSON en BaseController."""
    if detalle is None:
        return ""
    if isinstance(detalle, str):
        return detalle
    if isinstance(detalle, (dict, list)):
        try:
            return json.dumps(detalle, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(detalle)
    return str(detalle)


def _fmt_vencimiento(fecha_iso: str) -> str:
    s = (fecha_iso or "").strip()[:10]
    if len(s) != 10:
        return ""
    try:
        d = date.fromisoformat(s)
        hoy = date.today()
        if d < hoy:
            return f"{s} (vencido)"
        if d == hoy:
            return f"{s} (hoy)"
        return s
    except ValueError:
        return s


class MigracionEtapaEditDialog(QDialog):
    """Fecha con calendario (dd/MM/aaaa); «Sin fecha» deja el vencimiento vacío en base."""

    _VENC_SENTINEL = QDate(1, 1, 1)

    def __init__(self, id_requerimiento: str, etapa_id: str | None, parent=None):
        super().__init__(parent)
        self._id_req = id_requerimiento
        self._etapa_id = etapa_id
        self.setWindowTitle("Etapa — requerimiento migracion")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._txt_titulo = QLineEdit()
        self._date_venc = NoWheelDateEdit()
        self._date_venc.setCalendarPopup(True)
        self._date_venc.setMinimumDate(self._VENC_SENTINEL)
        self._date_venc.setSpecialValueText("— Sin fecha —")
        self._date_venc.setDisplayFormat("dd/MM/yyyy")
        self._date_venc.setDate(self._VENC_SENTINEL)
        self._date_venc.setToolTip("Elegí la fecha con el calendario o escribí dd/mm/aaaa")
        row_v = QHBoxLayout()
        row_v.setSpacing(8)
        row_v.addWidget(self._date_venc, 1)
        btn_hoy = QPushButton("Hoy")
        btn_hoy.setProperty("variant", "secondary")
        btn_hoy.setToolTip("Fijar vencimiento a la fecha de hoy")
        btn_hoy.clicked.connect(self._vencimiento_hoy)
        row_v.addWidget(btn_hoy)
        btn_sin = QPushButton("Sin fecha")
        btn_sin.setProperty("variant", "secondary")
        btn_sin.setToolTip("Quitar fecha (sin vencimiento programado)")
        btn_sin.clicked.connect(self._vencimiento_limpiar)
        row_v.addWidget(btn_sin)
        wrap_v = QWidget()
        wrap_v.setLayout(row_v)
        self._cmb_avance = NoWheelComboBox()
        for x in sorted(ESTADOS_AVANCE_ETAPA):
            self._cmb_avance.addItem(x.replace("_", " ").title(), x)
        self._txt_notas = QTextEdit()
        self._txt_notas.setMaximumHeight(72)
        form.addRow("Titulo:", self._txt_titulo)
        form.addRow("Vencimiento:", wrap_v)
        form.addRow("Avance:", self._cmb_avance)
        form.addRow("Notas:", self._txt_notas)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if etapa_id:
            et = MigracionRequerimientoEtapaController.get_by_id(etapa_id)
            if et:
                self._txt_titulo.setText(et.get("titulo", "") or "")
                fv = (et.get("fecha_vencimiento") or "").strip()[:10]
                if len(fv) == 10:
                    qd = QDate.fromString(fv, Qt.DateFormat.ISODate)
                    if qd.isValid():
                        self._date_venc.setDate(qd)
                    else:
                        self._date_venc.setDate(self._VENC_SENTINEL)
                else:
                    self._date_venc.setDate(self._VENC_SENTINEL)
                av = (et.get("estado_avance") or "pendiente").strip()
                idx = self._cmb_avance.findData(av)
                if idx >= 0:
                    self._cmb_avance.setCurrentIndex(idx)
                self._txt_notas.setPlainText(et.get("notas", "") or "")

    def _vencimiento_hoy(self):
        self._date_venc.setDate(QDate.currentDate())

    def _vencimiento_limpiar(self):
        self._date_venc.setDate(self._VENC_SENTINEL)

    def values(self) -> dict:
        d = self._date_venc.date()
        if d == self._VENC_SENTINEL:
            fv = ""
        else:
            fv = d.toString(Qt.DateFormat.ISODate)
        return {
            "titulo": self._txt_titulo.text().strip(),
            "fecha_vencimiento": fv,
            "estado_avance": self._cmb_avance.currentData() or "pendiente",
            "notas": self._txt_notas.toPlainText().strip(),
        }


class MigracionRequerimientoHistorialDialog(QDialog):
    """Historial de eventos del requerimiento (ventana aparte para ahorrar espacio en la ficha)."""

    def __init__(self, id_requerimiento: str, parent=None):
        super().__init__(parent)
        self._id_req = id_requerimiento
        self.setWindowTitle("Historial — requerimiento de migración")
        self.setMinimumSize(640, 420)
        layout = QVBoxLayout(self)
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Fecha", "Evento", "Usuario", "Detalle"])
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table, 1)
        row = QHBoxLayout()
        row.addStretch()
        btn = QPushButton("Cerrar")
        btn.setProperty("variant", "secondary")
        btn.clicked.connect(self.accept)
        row.addWidget(btn)
        layout.addLayout(row)
        self._cargar()

    def _cargar(self):
        rows = MigracionRequerimientoController.list_historial(self._id_req)[:200]
        self._table.setRowCount(len(rows))
        for i, h in enumerate(rows):
            self._table.setItem(i, 0, QTableWidgetItem((h.get("created_at") or "")[:19]))
            self._table.setItem(i, 1, QTableWidgetItem(h.get("evento_tipo", "") or ""))
            self._table.setItem(i, 2, QTableWidgetItem(h.get("usuario", "") or ""))
            det_txt = _detalle_historial_texto(h.get("detalle"))
            self._table.setItem(i, 3, QTableWidgetItem(det_txt))


class MigracionRequerimientoDetailDialog(QDialog):
    """Ficha de un requerimiento: datos, etapas, historial, tareas."""

    def __init__(self, id_requerimiento: str, id_expediente: str, parent=None):
        super().__init__(parent)
        self._id_req = id_requerimiento
        self._id_exp = id_expediente
        self.setWindowTitle("Requerimiento de migracion")
        self.setMinimumSize(720, 480)
        root = QVBoxLayout(self)

        self._form_header = QFormLayout()
        self._txt_titulo = QLineEdit()
        self._cmb_tipo = NoWheelComboBox()
        self._cmb_tipo.addItem("")
        for st in ExpedienteController.SUBTIPOS_POR_RAMA.get("Migraciones", []):
            self._cmb_tipo.addItem(st)
        self._cmb_ciclo = NoWheelComboBox()
        self._cmb_ciclo.addItem("Iniciado", "iniciado")
        self._cmb_ciclo.addItem("Finalizado", "finalizado")
        self._txt_notas = QTextEdit()
        self._txt_notas.setMaximumHeight(64)
        self._form_header.addRow("Titulo:", self._txt_titulo)
        self._form_header.addRow("Tipo / subtipo:", self._cmb_tipo)
        self._form_header.addRow("Estado ciclo:", self._cmb_ciclo)
        self._form_header.addRow("Notas:", self._txt_notas)
        root.addLayout(self._form_header)

        lbl_et = QLabel("Etapas internas (ordenadas por vencimiento; sin fecha al final)")
        lbl_et.setFont(QFont("Lato", 12, QFont.Weight.Bold))
        lbl_et.setStyleSheet("color: #3d4a5c;")
        root.addWidget(lbl_et)
        self._tab_etapas = QTableWidget()
        self._tab_etapas.setColumnCount(5)
        self._tab_etapas.setHorizontalHeaderLabels(
            ["Titulo", "Vencimiento", "Avance", "Notas", "Id"]
        )
        self._tab_etapas.hideColumn(4)
        self._tab_etapas.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._tab_etapas.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tab_etapas.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        root.addWidget(self._tab_etapas, 1)

        row_et_btns = QHBoxLayout()
        self._btn_add_et = QPushButton("+ Etapa")
        self._btn_add_et.clicked.connect(self._add_etapa)
        self._btn_edit_et = QPushButton("Editar etapa")
        self._btn_edit_et.setProperty("variant", "secondary")
        self._btn_edit_et.clicked.connect(self._edit_etapa)
        self._btn_del_et = QPushButton("Eliminar etapa")
        self._btn_del_et.setProperty("variant", "secondary")
        self._btn_del_et.clicked.connect(self._del_etapa)
        row_et_btns.addWidget(self._btn_add_et)
        row_et_btns.addWidget(self._btn_edit_et)
        row_et_btns.addWidget(self._btn_del_et)
        row_et_btns.addStretch()
        root.addLayout(row_et_btns)

        row_hist = QHBoxLayout()
        self._btn_historial = QPushButton("Ver historial…")
        self._btn_historial.setProperty("variant", "secondary")
        self._btn_historial.clicked.connect(self._abrir_historial)
        row_hist.addWidget(self._btn_historial)
        row_hist.addStretch()
        root.addLayout(row_hist)

        lbl_tar = QLabel("Tareas asociadas")
        lbl_tar.setFont(QFont("Lato", 11, QFont.Weight.Bold))
        root.addWidget(lbl_tar)
        self._tab_tareas = QTableWidget()
        self._tab_tareas.setColumnCount(4)
        self._tab_tareas.setHorizontalHeaderLabels(["Estado", "Vence", "Descripcion", "_id"])
        self._tab_tareas.hideColumn(3)
        self._tab_tareas.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._tab_tareas.setMaximumHeight(120)
        root.addWidget(self._tab_tareas)
        row_tar = QHBoxLayout()
        btn_nueva_t = QPushButton("+ Nueva tarea")
        btn_nueva_t.clicked.connect(self._nueva_tarea)
        row_tar.addWidget(btn_nueva_t)
        row_tar.addStretch()
        root.addLayout(row_tar)

        bottom = QHBoxLayout()
        self._btn_guardar = QPushButton("Guardar datos")
        self._btn_guardar.clicked.connect(self._guardar_cabecera)
        self._btn_finalizar = QPushButton("Marcar finalizado")
        self._btn_finalizar.setProperty("variant", "secondary")
        self._btn_finalizar.clicked.connect(self._finalizar)
        btn_close = QPushButton("Cerrar")
        btn_close.setProperty("variant", "secondary")
        btn_close.clicked.connect(self.accept)
        bottom.addWidget(self._btn_guardar)
        bottom.addWidget(self._btn_finalizar)
        bottom.addStretch()
        bottom.addWidget(btn_close)
        root.addLayout(bottom)

        self._refresh_header()
        self._refresh_etapas()
        self._refresh_tareas()
        self._apply_editable()

    def _req(self) -> dict | None:
        return MigracionRequerimientoController.get_by_id(self._id_req)

    def _apply_editable(self):
        req = self._req()
        fin = req and (req.get("estado_ciclo") or "").strip() == "finalizado"
        for w in (
            self._txt_titulo,
            self._cmb_tipo,
            self._cmb_ciclo,
            self._txt_notas,
            self._btn_add_et,
            self._btn_edit_et,
            self._btn_del_et,
            self._btn_guardar,
            self._btn_finalizar,
        ):
            w.setEnabled(not fin)
        # superusuario could edit finalized - omit for simplicity

    def _abrir_historial(self):
        dlg = MigracionRequerimientoHistorialDialog(self._id_req, self)
        dlg.exec()

    def _refresh_header(self):
        req = self._req()
        if not req:
            return
        self._txt_titulo.setText(req.get("titulo", "") or "")
        tipo = (req.get("tipo") or "").strip()
        if tipo:
            idx = self._cmb_tipo.findText(tipo)
            if idx >= 0:
                self._cmb_tipo.setCurrentIndex(idx)
            else:
                self._cmb_tipo.addItem(tipo)
                self._cmb_tipo.setCurrentIndex(self._cmb_tipo.count() - 1)
        ciclo = (req.get("estado_ciclo") or "iniciado").strip()
        idxc = self._cmb_ciclo.findData(ciclo)
        if idxc >= 0:
            self._cmb_ciclo.setCurrentIndex(idxc)
        self._txt_notas.setPlainText(req.get("notas", "") or "")

    def _refresh_etapas(self):
        rows = list(MigracionRequerimientoEtapaController.list_by_requerimiento(self._id_req))

        def _orden_etapa(et: dict) -> tuple:
            fv = (et.get("fecha_vencimiento") or "").strip()[:10]
            if len(fv) != 10:
                return ("9999-12-31", (et.get("titulo") or "").lower())
            return (fv, (et.get("titulo") or "").lower())

        rows.sort(key=_orden_etapa)
        self._tab_etapas.setRowCount(len(rows))
        for i, et in enumerate(rows):
            self._tab_etapas.setItem(i, 0, QTableWidgetItem(et.get("titulo", "") or ""))
            fv = (et.get("fecha_vencimiento") or "").strip()[:10]
            self._tab_etapas.setItem(i, 1, QTableWidgetItem(_fmt_vencimiento(fv)))
            self._tab_etapas.setItem(i, 2, QTableWidgetItem(et.get("estado_avance", "") or ""))
            self._tab_etapas.setItem(i, 3, QTableWidgetItem((et.get("notas") or "")[:80]))
            it_id = QTableWidgetItem(et.get("_id", "") or "")
            self._tab_etapas.setItem(i, 4, it_id)

    def _refresh_tareas(self):
        rows = TareaController.get_by_migracion_requerimiento(self._id_req)
        self._tab_tareas.setRowCount(len(rows))
        for i, t in enumerate(rows):
            self._tab_tareas.setItem(i, 0, QTableWidgetItem(t.get("estado", "") or ""))
            self._tab_tareas.setItem(i, 1, QTableWidgetItem((t.get("fecha_vencimiento") or "")[:10]))
            d = (t.get("descripcion") or "")[:120]
            self._tab_tareas.setItem(i, 2, QTableWidgetItem(d))
            self._tab_tareas.setItem(i, 3, QTableWidgetItem(t.get("_id", "") or ""))

    def _selected_etapa_id(self) -> str:
        r = self._tab_etapas.currentRow()
        if r < 0:
            return ""
        it = self._tab_etapas.item(r, 4)
        return (it.text() if it else "").strip()

    def _guardar_cabecera(self):
        if not MigracionRequerimientoController.puede_operar_expediente(self._id_exp):
            QMessageBox.warning(self, "Permisos", "No puede editar esta carpeta.")
            return
        titulo = self._txt_titulo.text().strip()
        if not titulo:
            QMessageBox.warning(self, "Validacion", "El titulo es obligatorio.")
            return
        upd = {
            "titulo": titulo,
            "tipo": self._cmb_tipo.currentText().strip(),
            "notas": self._txt_notas.toPlainText().strip(),
            "estado_ciclo": self._cmb_ciclo.currentData() or "iniciado",
        }
        MigracionRequerimientoController.update(self._id_req, upd)
        self._refresh_header()
        self._apply_editable()
        QMessageBox.information(self, "Guardado", "Datos actualizados.")

    def _finalizar(self):
        if not MigracionRequerimientoController.puede_operar_expediente(self._id_exp):
            QMessageBox.warning(self, "Permisos", "No puede editar esta carpeta.")
            return
        if QMessageBox.question(
            self,
            "Finalizar",
            "Al finalizar no se podran editar las etapas. Continuar?",
        ) != QMessageBox.StandardButton.Yes:
            return
        MigracionRequerimientoController.update(self._id_req, {"estado_ciclo": "finalizado"})
        self._refresh_header()
        self._apply_editable()

    def _add_etapa(self):
        if not MigracionRequerimientoController.puede_operar_expediente(self._id_exp):
            QMessageBox.warning(self, "Permisos", "No puede editar esta carpeta.")
            return
        dlg = MigracionEtapaEditDialog(self._id_req, None, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        v = dlg.values()
        if not v["titulo"]:
            return
        max_ord = len(MigracionRequerimientoEtapaController.list_by_requerimiento(self._id_req))
        MigracionRequerimientoEtapaController.create(
            {
                "id_requerimiento": self._id_req,
                "titulo": v["titulo"],
                "fecha_vencimiento": v["fecha_vencimiento"],
                "estado_avance": v["estado_avance"],
                "notas": v["notas"],
                "orden": max_ord,
            }
        )
        self._refresh_etapas()

    def _edit_etapa(self):
        eid = self._selected_etapa_id()
        if not eid:
            QMessageBox.information(self, "Etapa", "Seleccione una fila.")
            return
        dlg = MigracionEtapaEditDialog(self._id_req, eid, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        v = dlg.values()
        if not v["titulo"]:
            return
        MigracionRequerimientoEtapaController.update(
            eid,
            {
                "titulo": v["titulo"],
                "fecha_vencimiento": v["fecha_vencimiento"],
                "estado_avance": v["estado_avance"],
                "notas": v["notas"],
            },
        )
        self._refresh_etapas()

    def _del_etapa(self):
        eid = self._selected_etapa_id()
        if not eid:
            return
        if QMessageBox.question(self, "Confirmar", "Eliminar esta etapa?") != QMessageBox.StandardButton.Yes:
            return
        MigracionRequerimientoEtapaController.delete(eid)
        self._refresh_etapas()

    def _nueva_tarea(self):
        from views.tareas.tarea_form import TareaFormDialog

        dlg = TareaFormDialog(
            expediente_id=self._id_exp,
            id_migracion_requerimiento=self._id_req,
            parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._refresh_tareas()


class MigracionRequerimientosForCarpetaWidget(QWidget):
    """Listado de requerimientos de migracion de una carpeta; abre detalle con flujo y alertas."""

    def __init__(self, id_expediente: str, parent=None):
        super().__init__(parent)
        self._id_exp = id_expediente
        lay = QVBoxLayout(self)
        info = QLabel(
            "Cada requerimiento tiene etapas internas con vencimientos; las alertas aparecen en "
            "la pestana Recordatorios. Doble clic en una fila o use Abrir detalle."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #5a6475; font-size: 11px;")
        lay.addWidget(info)
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["Titulo", "Ciclo", "Prox. venc.", "Tipo", "_id"]
        )
        self._table.hideColumn(4)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.doubleClicked.connect(self._open_detail)
        lay.addWidget(self._table, 1)
        row = QHBoxLayout()
        btn_nuevo = QPushButton("+ Nuevo requerimiento")
        btn_nuevo.clicked.connect(self._nuevo)
        btn_abrir = QPushButton("Abrir detalle")
        btn_abrir.setProperty("variant", "secondary")
        btn_abrir.clicked.connect(self._open_detail)
        row.addWidget(btn_nuevo)
        row.addWidget(btn_abrir)
        row.addStretch()
        lay.addLayout(row)
        self._refresh()

    def refresh(self):
        """Vuelve a cargar filas desde la base (p. ej. al cambiar de pestana)."""
        self._refresh()

    def _refresh(self):
        rows = MigracionRequerimientoController.list_by_expediente(self._id_exp)
        self._table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self._table.setItem(i, 0, QTableWidgetItem(r.get("titulo", "") or ""))
            self._table.setItem(i, 1, QTableWidgetItem(r.get("estado_ciclo", "") or ""))
            pv = MigracionRequerimientoController.proxima_fecha_vencimiento_req(r.get("_id", ""))
            self._table.setItem(i, 2, QTableWidgetItem(_fmt_vencimiento(pv)))
            self._table.setItem(i, 3, QTableWidgetItem(r.get("tipo", "") or ""))
            self._table.setItem(i, 4, QTableWidgetItem(r.get("_id", "") or ""))

    def _selected_id(self) -> str:
        r = self._table.currentRow()
        if r < 0:
            return ""
        it = self._table.item(r, 4)
        return (it.text() if it else "").strip()

    def _nuevo(self):
        if not MigracionRequerimientoController.puede_operar_expediente(self._id_exp):
            QMessageBox.warning(self, "Permisos", "No puede crear requerimientos en esta carpeta.")
            return
        titulo, ok = QInputDialog.getText(self, "Nuevo requerimiento", "Titulo:")
        if not ok or not titulo.strip():
            return
        tipo, ok2 = QInputDialog.getItem(
            self,
            "Tipo",
            "Subtipo (opcional):",
            [""] + list(ExpedienteController.SUBTIPOS_POR_RAMA.get("Migraciones", [])),
            0,
            False,
        )
        if not ok2:
            tipo = ""
        rec = MigracionRequerimientoController.create(
            {"id_expediente": self._id_exp, "titulo": titulo.strip(), "tipo": (tipo or "").strip()}
        )
        if not rec:
            QMessageBox.warning(self, "Error", "No se pudo crear (permisos o datos).")
            return
        self._refresh()
        dlg = MigracionRequerimientoDetailDialog(rec["_id"], self._id_exp, self)
        dlg.exec()
        self._refresh()

    def _open_detail(self):
        rid = self._selected_id()
        if not rid:
            QMessageBox.information(self, "Detalle", "Seleccione un requerimiento.")
            return
        dlg = MigracionRequerimientoDetailDialog(rid, self._id_exp, self)
        dlg.exec()
        self._refresh()


class MigracionRequerimientosForCarpetaDialog(QDialog):
    """Ventana modal con el mismo contenido que la pestana Req. Migraciones (uso puntual)."""

    def __init__(self, id_expediente: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Requerimientos de migracion — carpeta")
        self.setMinimumSize(560, 400)
        lay = QVBoxLayout(self)
        self._widget = MigracionRequerimientosForCarpetaWidget(id_expediente, self)
        lay.addWidget(self._widget)
        row = QHBoxLayout()
        row.addStretch()
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.setProperty("variant", "secondary")
        btn_cerrar.clicked.connect(self.reject)
        row.addWidget(btn_cerrar)
        lay.addLayout(row)
