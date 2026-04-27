"""Vista: carpetas en etapa de citar sin cita Pendiente/Confirmada en el modulo Citas."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QHBoxLayout, QAbstractItemView, QDialog,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from controllers.expediente_controller import ExpedienteController
from core.auth import Session
from core.permissions import tiene_permiso


class PendientesCitarView(QWidget):
    """Listado de carpetas «Para citar» / «Para citar o videollamada» sin cita agendada."""

    def __init__(self, parent=None):
        super().__init__(parent)
        session = Session.get()
        self._can_create_citas = tiene_permiso(session.rol, "citas.create")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("Pendientes de citar sin cita agendada")
        title.setFont(QFont("Lato", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        lbl = QLabel(
            "<b>Carpetas en etapa «Para citar» o «Para citar o videollamada»</b> sin cita "
            "Pendiente o Confirmada en el modulo Citas. Use las acciones para registrar "
            "la cita o abrir la carpeta."
        )
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setStyleSheet("color: #1565c0; font-size: 12px;")
        layout.addWidget(lbl)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels([
            "Carpeta", "Cliente", "Etapa", "Responsable", "Acciones",
        ])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(40)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self._table, 1)

    def refresh(self):
        session = Session.get()
        if not session.logged_in:
            self._table.setRowCount(0)
            return
        rows = ExpedienteController.get_pendientes_citar_sin_cita(
            username=session.username or "",
            limit=200,
        )
        etapas_map = {x["codigo"]: x for x in ExpedienteController.ETAPAS}
        self._table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            eid = (row.get("_id") or "").strip()
            cid = (row.get("id_cliente") or "").strip()
            ec = row.get("etapa_codigo", "")
            etapa_meta = etapas_map.get(ec, {})
            it0 = QTableWidgetItem(str(row.get("id_expediente", "")))
            it0.setData(Qt.ItemDataRole.UserRole, (eid, cid))
            self._table.setItem(i, 0, it0)
            self._table.setItem(i, 1, QTableWidgetItem(row.get("cli_nombre", "")))
            self._table.setItem(
                i, 2, QTableWidgetItem(etapa_meta.get("titulo", row.get("etapa_codigo", "")))
            )
            self._table.setItem(i, 3, QTableWidgetItem(row.get("responsable", "")))
            self._table.setCellWidget(
                i, 4, self._widget_acciones(eid, cid)
            )

    def _widget_acciones(self, expediente_id: str, cliente_id: str) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(4)
        btn_cita = QPushButton("Crear cita")
        if not self._can_create_citas:
            btn_cita.setEnabled(False)
            btn_cita.setToolTip("Sin permiso para crear citas")
        btn_exp = QPushButton("Abrir carpeta")
        btn_cita.clicked.connect(
            lambda _=False, eid=expediente_id, cid=cliente_id: self._on_crear_cita(eid, cid)
        )
        btn_exp.clicked.connect(
            lambda _=False, eid=expediente_id: self._on_abrir_carpeta(eid)
        )
        lay.addWidget(btn_cita)
        lay.addWidget(btn_exp)
        return w

    def _on_crear_cita(self, expediente_id: str, cliente_id: str):
        from views.citas.cita_form import CitaFormDialog
        dlg = CitaFormDialog(
            cliente_id=cliente_id or None,
            expediente_id=expediente_id,
            parent=self,
        )
        if dlg.exec():
            self.refresh()

    def _on_abrir_carpeta(self, expediente_id: str):
        if not (expediente_id or "").strip():
            return
        self._open_expediente(expediente_id.strip())

    def _open_expediente(self, expediente_id: str):
        from views.expedientes.expediente_form import ExpedienteFormDialog
        dlg = ExpedienteFormDialog(expediente_id=expediente_id, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()
