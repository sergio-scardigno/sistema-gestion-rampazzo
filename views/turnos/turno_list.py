"""Vista listado de Turnos ANSES."""
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QMessageBox, QComboBox, QDateEdit, QTimeEdit, QDialog, QFormLayout,
    QCompleter, QHeaderView
)
from PySide6.QtGui import QFont, QColor, QBrush
from PySide6.QtCore import QDate, QTime, Qt, QStringListModel

logger = logging.getLogger(__name__)

from views.widgets.filterable_table import FilterableTable
from views.widgets.no_wheel_datetime import NoWheelDateEdit, NoWheelTimeEdit
from controllers.turno_controller import TurnoController
from services import anses_oficinas_service
from config import ANSES_PROVINCIA_DEFECTO
from datetime import datetime, date

COLUMNS = [
    ("fecha_turno", "Fecha"),
    ("hora_turno", "Hora"),
    ("_nombre_cliente", "Cliente"),
    ("tipo_tramite", "Tramite"),
    ("oficina_anses", "Oficina"),
    ("estado", "Estado"),
    ("responsable", "Responsable"),
    ("documentacion_lista", "Doc.Lista"),
]


class TurnoListView(QWidget):
    BG_RED_DARK = "#e9b9c1"
    BG_RED_SOFT = "#f5d3d8"
    BG_GREEN_SOFT = "#d8efe3"
    FG_DARK = "#222222"
    FG_DARK_RED = "#4a1a22"
    FG_DARK_GREEN = "#1f4d3a"

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        # ── Header ──
        header = QHBoxLayout()
        title = QLabel("Turnos ANSES")
        title.setFont(QFont("Lato", 17, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        # Filtro estado
        self._cmb_estado = QComboBox()
        self._cmb_estado.addItem("Todos los estados", "")
        for e in TurnoController.ESTADOS:
            self._cmb_estado.addItem(e, e)
        self._cmb_estado.currentIndexChanged.connect(self.refresh)
        header.addWidget(self._cmb_estado)

        # Filtro responsable
        self._cmb_responsable = QComboBox()
        self._cmb_responsable.addItem("Todos los responsables", "")
        self._cmb_responsable.currentIndexChanged.connect(self.refresh)
        header.addWidget(self._cmb_responsable)

        # Botones
        btn_new = QPushButton("+ Nuevo Turno")
        btn_new.clicked.connect(self._new_turno)
        header.addWidget(btn_new)

        btn_edit = QPushButton("Editar")
        btn_edit.setProperty("variant", "secondary")
        btn_edit.clicked.connect(self._edit_turno)
        header.addWidget(btn_edit)

        btn_asistido = QPushButton("Marcar Asistido")
        btn_asistido.setProperty("variant", "success")
        btn_asistido.clicked.connect(self._marcar_asistido)
        header.addWidget(btn_asistido)

        btn_reprog = QPushButton("Reprogramar")
        btn_reprog.setProperty("variant", "secondary")
        btn_reprog.clicked.connect(self._reprogramar)
        header.addWidget(btn_reprog)

        layout.addLayout(header)

        # ── Tabla ──
        self._table = FilterableTable(COLUMNS, row_style_provider=self._style_turno_date_cell)
        self._table.row_double_clicked.connect(self._on_double_click)

        # Mejor legibilidad: mayor alto de fila, padding y columnas mas anchas.
        table_widget = self._table._table
        table_widget.verticalHeader().setDefaultSectionSize(36)
        table_widget.setStyleSheet("QTableWidget::item { padding: 8px 10px; }")
        table_widget.horizontalHeader().setStretchLastSection(False)
        table_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)          # Fecha
        table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) # Hora
        table_widget.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)          # Cliente
        table_widget.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # Tramite
        table_widget.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents) # Oficina
        table_widget.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents) # Estado
        table_widget.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents) # Responsable
        table_widget.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents) # Doc.Lista
        layout.addWidget(self._table)

        # ── Info inferior ──
        self._lbl_info = QLabel()
        self._lbl_info.setStyleSheet("font-size: 13px; color: #6b6b6b; padding: 4px;")
        layout.addWidget(self._lbl_info)

    def refresh(self):
        conditions = []
        params = []

        estado = self._cmb_estado.currentData()
        if estado:
            conditions.append("estado = ?")
            params.append(estado)

        responsable = self._cmb_responsable.currentData()
        if responsable:
            conditions.append("responsable = ?")
            params.append(responsable)

        where = " AND ".join(conditions)
        data = TurnoController.get_scoped(
            where=where, params=tuple(params),
            order_by="fecha_turno ASC, hora_turno ASC"
        )

        # Enriquecer con nombre de cliente
        from controllers.cliente_controller import ClienteController
        clientes_cache = {}
        for d in data:
            cid = d.get("id_cliente", "")
            if cid and cid not in clientes_cache:
                cli = ClienteController.get_by_id(cid)
                clientes_cache[cid] = cli.get("nombre_completo", "") if cli else ""
            d["_nombre_cliente"] = clientes_cache.get(cid, "")
            # Formatear documentacion_lista
            d["documentacion_lista"] = "Si" if d.get("documentacion_lista") else "No"

        self._table.set_data(data)

        # Actualizar responsables en el filtro (solo si esta vacio)
        if self._cmb_responsable.count() <= 1:
            responsables = set()
            all_turnos = TurnoController.get_all()
            for t in all_turnos:
                r = t.get("responsable", "")
                if r:
                    responsables.add(r)
            for r in sorted(responsables):
                self._cmb_responsable.addItem(r, r)

        # Info
        today = datetime.now().strftime("%Y-%m-%d")
        hoy_count = sum(1 for d in data if d.get("fecha_turno", "")[:10] == today)
        self._lbl_info.setText(
            f"Total: {len(data)} turnos  |  Turnos hoy: {hoy_count}"
        )

    def _new_turno(self):
        from views.turnos.turno_form import TurnoFormDialog
        dlg = TurnoFormDialog(parent=self)
        if dlg.exec():
            self.refresh()

    def _style_turno_date_cell(self, row_data: dict, field: str, item):
        if field not in ("fecha_turno", "estado", "tipo_tramite"):
            return
        turno_date = self._parse_ymd(row_data.get("fecha_turno", ""))
        if not turno_date:
            return
        days_left = (turno_date - date.today()).days
        estado = str(row_data.get("estado", "") or "").strip()
        is_completed = estado == "Asistido"

        bg = self.BG_GREEN_SOFT
        fg_text = self.FG_DARK_GREEN
        weight = QFont.Weight.DemiBold
        italic = False
        underline = False

        if is_completed:
            bg = self.BG_GREEN_SOFT
            fg_text = self.FG_DARK_GREEN
            weight = QFont.Weight.Bold
            italic = False
            underline = False
        elif days_left < 0:
            bg = self.BG_RED_DARK
            fg_text = self.FG_DARK_RED
            weight = QFont.Weight.Bold
            italic = False
        elif days_left <= 5:
            bg = self.BG_RED_SOFT
            fg_text = self.FG_DARK_RED
            weight = QFont.Weight.Bold
            italic = True
            underline = field == "fecha_turno"

        if field == "fecha_turno":
            raw_text = str(row_data.get("fecha_turno", "") or "")
            if is_completed:
                item.setText(f"✓ COMPLETADO {raw_text}")
            elif days_left < 0:
                item.setText(f"● VENCIDA {raw_text}")
            elif days_left <= 5:
                item.setText(f"▲ PROXIMA {raw_text}")
            else:
                item.setText(f"○ EN TIEMPO {raw_text}")

        item.setForeground(QBrush(QColor(fg_text if field in ("fecha_turno", "estado") else self.FG_DARK)))
        item.setBackground(QBrush(QColor(bg)))

        f = item.font()
        f.setWeight(weight)
        f.setItalic(italic)
        f.setUnderline(underline)
        item.setFont(f)

    @staticmethod
    def _parse_ymd(value: str) -> date | None:
        if not value:
            return None
        raw = value[:10]
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            return None

    def _edit_turno(self):
        _id = self._table.get_selected_id()
        if not _id:
            QMessageBox.information(self, "Atencion", "Seleccione un turno.")
            return
        from views.turnos.turno_form import TurnoFormDialog
        dlg = TurnoFormDialog(turno_id=_id, parent=self)
        if dlg.exec():
            self.refresh()

    def _on_double_click(self, _id):
        from views.turnos.turno_form import TurnoFormDialog
        dlg = TurnoFormDialog(turno_id=_id, parent=self)
        if dlg.exec():
            self.refresh()

    def _marcar_asistido(self):
        _id = self._table.get_selected_id()
        if not _id:
            QMessageBox.information(self, "Atencion", "Seleccione un turno.")
            return
        turno = TurnoController.get_by_id(_id)
        if not turno:
            return
        if turno.get("estado") not in ("Pendiente", "Confirmado"):
            QMessageBox.information(
                self, "Atencion",
                "Solo se pueden marcar como asistidos turnos Pendientes o Confirmados."
            )
            return
        reply = QMessageBox.question(
            self, "Confirmar",
            f"Marcar turno #{turno.get('id_turno', '')} como Asistido?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            TurnoController.marcar_asistido(_id)
            self.refresh()

    def _reprogramar(self):
        _id = self._table.get_selected_id()
        if not _id:
            QMessageBox.information(self, "Atencion", "Seleccione un turno.")
            return
        turno = TurnoController.get_by_id(_id)
        if not turno:
            return

        # Dialogo simple para nueva fecha/hora
        dlg = QDialog(self)
        dlg.setWindowTitle("Reprogramar Turno")
        dlg.setMinimumWidth(400)
        lay = QVBoxLayout(dlg)

        lay.addWidget(QLabel(
            f"Reprogramar turno #{turno.get('id_turno', '')} "
            f"del {turno.get('fecha_turno', '')} {turno.get('hora_turno', '')}"
        ))

        form = QFormLayout()
        date_new = NoWheelDateEdit()
        date_new.setCalendarPopup(True)
        date_new.setDate(QDate.currentDate().addDays(7))
        date_new.setDisplayFormat("dd/MM/yyyy")
        form.addRow("Nueva fecha:", date_new)

        hora_new = NoWheelTimeEdit()
        hora_new.setDisplayFormat("HH:mm")
        hora_prev = turno.get("hora_turno", "")
        if hora_prev:
            parsed = QTime.fromString(hora_prev, "HH:mm")
            if parsed.isValid():
                hora_new.setTime(parsed)
            else:
                hora_new.setTime(QTime(9, 0))
        else:
            hora_new.setTime(QTime(9, 0))
        form.addRow("Nueva hora *:", hora_new)

        # Provincia
        cmb_provincia = QComboBox()
        for p in TurnoController.get_provincias():
            cmb_provincia.addItem(p)

        # Oficina
        cmb_oficina = QComboBox()
        cmb_oficina.setEditable(True)
        cmb_oficina.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        oficina_completer = QCompleter()
        oficina_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        oficina_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        oficina_completer.setMaxVisibleItems(15)
        cmb_oficina.setCompleter(oficina_completer)

        def load_oficinas_reprog(provincia: str):
            cmb_oficina.blockSignals(True)
            try:
                cmb_oficina.clear()
                nombres = TurnoController.get_oficinas_anses(provincia)
                for i, nombre in enumerate(nombres):
                    cmb_oficina.addItem(nombre)
                    info = anses_oficinas_service.get_oficina_info(nombre)
                    if info:
                        tip = anses_oficinas_service.formato_tooltip_oficina(info)
                        cmb_oficina.setItemData(i, tip, Qt.ItemDataRole.ToolTipRole)
                # Actualizar modelo del completer
                c = cmb_oficina.completer()
                if c:
                    c.setModel(QStringListModel(nombres))
            except Exception:
                logger.warning("Error al cargar oficinas ANSES en turno_list", exc_info=True)
                if cmb_oficina.count() == 0:
                    cmb_oficina.addItem("Otra")
            finally:
                cmb_oficina.blockSignals(False)
            update_tooltip_reprog()

        # Label para mostrar info de la oficina seleccionada
        lbl_oficina_info = QLabel("")
        lbl_oficina_info.setWordWrap(True)
        lbl_oficina_info.setStyleSheet(
            "color: #6b6b6b; font-size: 11px; padding: 2px 4px; "
            "background-color: #f8f8f8; border: 1px solid #e0e0e0; border-radius: 4px;"
        )
        lbl_oficina_info.setVisible(False)

        def update_tooltip_reprog(*_args):
            nombre = cmb_oficina.currentText()
            info = anses_oficinas_service.get_oficina_info(nombre)
            if info:
                cmb_oficina.setToolTip(
                    anses_oficinas_service.formato_tooltip_oficina(info)
                )
                parts = []
                if info.get("address"):
                    parts.append(f"Dir: {info['address']}")
                if info.get("city"):
                    parts.append(f"Ciudad: {info['city']}")
                if info.get("schedule"):
                    parts.append(f"Horario: {info['schedule']}")
                if info.get("region"):
                    parts.append(info["region"])
                lbl_oficina_info.setText("  |  ".join(parts))
                lbl_oficina_info.setVisible(True)
            else:
                cmb_oficina.setToolTip("")
                lbl_oficina_info.setText("")
                lbl_oficina_info.setVisible(False)

        cmb_provincia.currentTextChanged.connect(load_oficinas_reprog)
        cmb_oficina.activated.connect(update_tooltip_reprog)
        cmb_oficina.currentTextChanged.connect(update_tooltip_reprog)

        # Detectar provincia de la oficina actual del turno
        oficina_actual = turno.get("oficina_anses", "")
        provincia_actual = anses_oficinas_service.get_provincia_de_oficina(oficina_actual)
        if provincia_actual:
            idx_p = cmb_provincia.findText(provincia_actual)
            if idx_p >= 0:
                cmb_provincia.setCurrentIndex(idx_p)
        else:
            idx_def = cmb_provincia.findText(ANSES_PROVINCIA_DEFECTO)
            if idx_def >= 0:
                cmb_provincia.setCurrentIndex(idx_def)

        load_oficinas_reprog(cmb_provincia.currentText())
        cmb_oficina.setCurrentText(oficina_actual)

        form.addRow("Provincia:", cmb_provincia)
        form.addRow("Oficina:", cmb_oficina)
        form.addRow("", lbl_oficina_info)

        lay.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setProperty("variant", "secondary")
        btn_cancel.clicked.connect(dlg.reject)
        btn_layout.addWidget(btn_cancel)
        btn_ok = QPushButton("Reprogramar")
        btn_layout.addWidget(btn_ok)
        lay.addLayout(btn_layout)

        def do_reprog():
            oficina_sel = cmb_oficina.currentText().strip()
            if not oficina_sel or cmb_oficina.findText(oficina_sel) < 0:
                QMessageBox.warning(
                    dlg, "Atencion",
                    "Seleccione una oficina valida de la lista."
                )
                return
            nueva_fecha = date_new.date().toString("yyyy-MM-dd")
            nueva_hora = hora_new.time().toString("HH:mm")
            TurnoController.reprogramar(
                _id, nueva_fecha, nueva_hora, oficina_sel
            )
            dlg.accept()

        btn_ok.clicked.connect(do_reprog)

        if dlg.exec():
            self.refresh()
