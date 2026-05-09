"""Vista Carpetas Iniciadas: carpetas Previsional (P/V) y requerimientos migracion (P/V)."""
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QMessageBox,
    QFrame,
)
from PySide6.QtGui import QFont

from controllers.expediente_controller import ExpedienteController
from controllers.migracion_requerimiento_controller import MigracionRequerimientoController
from views.widgets.filterable_table import FilterableTable
from views.expedientes.migracion_requerimientos_view import MigracionRequerimientoDetailDialog


COLUMNS_CARPETAS = [
    ("numero_carpeta_cliente", "N° Carpeta Cliente"),
    ("subtipo", "Subtipo"),
    ("estado", "Estado"),
    ("responsable", "Responsable"),
    ("fecha_apertura", "Fecha Apertura"),
    ("numero_expediente_anses", "Nro Tramite ANSES"),
]

COLUMNS_MIGRACION = [
    ("numero_carpeta_cliente", "N° Carpeta Cliente"),
    ("cli_dni", "DNI"),
    ("cli_cuil", "CUIT/CUIL"),
    ("cli_nro_tramite_dni", "Nro trámite DNI"),
    ("clave_mi_anses", "Clave Mi ANSES"),
    ("clave_fiscal", "Clave fiscal"),
    ("nro_tramite_anses", "Nro trámite ANSES"),
    ("req_titulo", "Requerimiento"),
    ("tipo", "Tipo"),
    ("estado_ciclo", "Ciclo"),
    ("prox_venc", "Prox. venc. etapa"),
    ("prox_alarma", "Prox. alarma"),
    ("cli_nombre", "Cliente"),
]


class _CountCard(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QFrame { background-color: #0f213b; border: 1px solid #1f3658; border-radius: 10px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: #dce8ff; font-size: 12px; font-weight: 600;")
        layout.addWidget(lbl_title)
        self._lbl_count = QLabel("0")
        self._lbl_count.setFont(QFont("Lato", 18, QFont.Weight.Bold))
        self._lbl_count.setStyleSheet("color: #ffffff;")
        layout.addWidget(self._lbl_count)

    def set_count(self, value: int):
        self._lbl_count.setText(str(value))


class CarpetasIniciadasView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 16)
        root.setSpacing(10)

        title = QLabel("Carpetas Iniciadas")
        title.setFont(QFont("Lato", 17, QFont.Weight.Bold))
        root.addWidget(title)

        self._outer_tabs = QTabWidget()

        # --- Pestaña: Carpetas (Previsional modalidad) ---
        tab_carpetas = QWidget()
        lay_c = QVBoxLayout(tab_carpetas)
        lay_c.setContentsMargins(0, 8, 0, 0)
        lay_c.setSpacing(12)

        header_c = QHBoxLayout()
        btn_new = QPushButton("+ Nueva Carpeta")
        btn_new.clicked.connect(self._new_expediente)
        header_c.addWidget(btn_new)
        btn_edit = QPushButton("Editar")
        btn_edit.setProperty("variant", "secondary")
        btn_edit.clicked.connect(self._edit_selected_carpeta)
        header_c.addWidget(btn_edit)
        btn_delete = QPushButton("Eliminar")
        btn_delete.setProperty("variant", "danger")
        btn_delete.clicked.connect(self._delete_selected_carpeta)
        header_c.addWidget(btn_delete)
        header_c.addStretch()
        lay_c.addLayout(header_c)

        cards_c = QHBoxLayout()
        cards_c.setSpacing(10)
        self._card_presencial = _CountCard("Iniciadas Presenciales")
        self._card_virtual = _CountCard("Iniciadas Virtuales")
        cards_c.addWidget(self._card_presencial)
        cards_c.addWidget(self._card_virtual)
        cards_c.addStretch()
        lay_c.addLayout(cards_c)

        self._tabs_carpetas = QTabWidget()
        self._table_presencial = FilterableTable(
            COLUMNS_CARPETAS,
            search_fields=["id_expediente", "cli_nombre", "cli_dni", "cli_cuil"],
            search_placeholder="Buscar por N° carpeta, DNI/CUIL o nombre...",
        )
        self._table_presencial.row_double_clicked.connect(self._open_carpeta)
        w_pres = QWidget()
        lp = QVBoxLayout(w_pres)
        lp.setContentsMargins(0, 0, 0, 0)
        lp.addWidget(self._table_presencial)
        self._tabs_carpetas.addTab(w_pres, "Presenciales")

        self._table_virtual = FilterableTable(
            COLUMNS_CARPETAS,
            search_fields=["id_expediente", "cli_nombre", "cli_dni", "cli_cuil"],
            search_placeholder="Buscar por N° carpeta, DNI/CUIL o nombre...",
        )
        self._table_virtual.row_double_clicked.connect(self._open_carpeta)
        w_vir = QWidget()
        lv = QVBoxLayout(w_vir)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addWidget(self._table_virtual)
        self._tabs_carpetas.addTab(w_vir, "Virtuales")
        lay_c.addWidget(self._tabs_carpetas)

        self._outer_tabs.addTab(tab_carpetas, "Carpetas")

        # --- Pestaña: Req. migraciones (ciclo iniciado; modalidad / etapa global) ---
        tab_migr = QWidget()
        lay_m = QVBoxLayout(tab_migr)
        lay_m.setContentsMargins(0, 8, 0, 0)
        lay_m.setSpacing(12)

        hint = QLabel(
            "Requerimientos con ciclo iniciado (cualquier área de la carpeta). Presenciales: etapa INICIADA "
            "presencial o modalidad Presencial en la carpeta; Virtuales: INICIADA virtual o modalidad Virtual. "
            "En etapas Requerimientos - Migraciones / analizar / citar debe estar definida la modalidad en la ficha "
            "para que aparezca en la sub-pestaña correspondiente. "
            "Prox. venc. etapa: siguiente fecha de etapa interna no hecha. Prox. alarma: recordatorio "
            "vinculado al requerimiento. Claves y Nro trámite ANSES: carpeta o, si falta, cliente. "
            "Doble clic en una fila para abrir el requerimiento; con la fila seleccionada, use Ir a carpeta "
            "para abrir la ficha de la carpeta."
        )
        hint.setStyleSheet("color: #5f6b7a; font-size: 11px;")
        hint.setWordWrap(True)
        lay_m.addWidget(hint)

        header_m = QHBoxLayout()
        btn_ir_carpeta_migr = QPushButton("Ir a carpeta")
        btn_ir_carpeta_migr.setProperty("variant", "secondary")
        btn_ir_carpeta_migr.clicked.connect(self._open_carpeta_from_migr_selected)
        header_m.addWidget(btn_ir_carpeta_migr)
        header_m.addStretch()
        lay_m.addLayout(header_m)

        cards_m = QHBoxLayout()
        cards_m.setSpacing(10)
        self._card_migr_pres = _CountCard("Req. migr. Presenciales")
        self._card_migr_vir = _CountCard("Req. migr. Virtuales")
        cards_m.addWidget(self._card_migr_pres)
        cards_m.addWidget(self._card_migr_vir)
        cards_m.addStretch()
        lay_m.addLayout(cards_m)

        self._tabs_migr = QTabWidget()
        self._table_migr_pres = FilterableTable(
            COLUMNS_MIGRACION,
            search_fields=[
                "carpeta_id",
                "cli_nombre",
                "cli_dni",
                "cli_cuil",
                "cli_nro_tramite_dni",
                "clave_mi_anses",
                "clave_fiscal",
                "nro_tramite_anses",
                "numero_carpeta_cliente",
                "req_titulo",
                "tipo",
                "prox_venc",
                "prox_alarma",
            ],
            search_placeholder="Buscar por N° carpeta, DNI/CUIL, claves, trámite ANSES o nombre...",
        )
        self._table_migr_pres.row_double_clicked.connect(self._on_migracion_row_double_click)
        wm_p = QWidget()
        lmp = QVBoxLayout(wm_p)
        lmp.setContentsMargins(0, 0, 0, 0)
        lmp.addWidget(self._table_migr_pres)
        self._tabs_migr.addTab(wm_p, "Presenciales")

        self._table_migr_vir = FilterableTable(
            COLUMNS_MIGRACION,
            search_fields=[
                "carpeta_id",
                "cli_nombre",
                "cli_dni",
                "cli_cuil",
                "cli_nro_tramite_dni",
                "clave_mi_anses",
                "clave_fiscal",
                "nro_tramite_anses",
                "numero_carpeta_cliente",
                "req_titulo",
                "tipo",
                "prox_venc",
                "prox_alarma",
            ],
            search_placeholder="Buscar por N° carpeta, DNI/CUIL, claves, trámite ANSES o nombre...",
        )
        self._table_migr_vir.row_double_clicked.connect(self._on_migracion_row_double_click)
        wm_v = QWidget()
        lmv = QVBoxLayout(wm_v)
        lmv.setContentsMargins(0, 0, 0, 0)
        lmv.addWidget(self._table_migr_vir)
        self._tabs_migr.addTab(wm_v, "Virtuales")
        lay_m.addWidget(self._tabs_migr)

        self._outer_tabs.addTab(tab_migr, "Req. migraciones")

        root.addWidget(self._outer_tabs)

    def _where_for_modalidad(self, modalidad: str) -> tuple[str, tuple]:
        return "e.rama = ? AND e.modalidad = ?", ("Previsional", modalidad)

    def refresh(self):
        where_p, params_p = self._where_for_modalidad("Presencial")
        data_p = ExpedienteController.get_scoped_with_cliente(
            where=where_p, params=params_p, order_by="e.fecha_apertura DESC"
        )
        where_v, params_v = self._where_for_modalidad("Virtual")
        data_v = ExpedienteController.get_scoped_with_cliente(
            where=where_v, params=params_v, order_by="e.fecha_apertura DESC"
        )
        self._table_presencial.set_data(data_p)
        self._table_virtual.set_data(data_v)
        self._card_presencial.set_count(len(data_p))
        self._card_virtual.set_count(len(data_v))

        data_mp = MigracionRequerimientoController.list_iniciados_tabla_por_modalidad_scoped("Presencial")
        data_mv = MigracionRequerimientoController.list_iniciados_tabla_por_modalidad_scoped("Virtual")
        self._table_migr_pres.set_data(data_mp)
        self._table_migr_vir.set_data(data_mv)
        self._card_migr_pres.set_count(len(data_mp))
        self._card_migr_vir.set_count(len(data_mv))

    def _active_table_carpetas(self) -> FilterableTable:
        if self._tabs_carpetas.currentIndex() == 1:
            return self._table_virtual
        return self._table_presencial

    def _active_table_migracion(self) -> FilterableTable:
        if self._tabs_migr.currentIndex() == 1:
            return self._table_migr_vir
        return self._table_migr_pres

    def _new_expediente(self):
        from views.expedientes.expediente_form import ExpedienteFormDialog

        dlg = ExpedienteFormDialog(parent=self)
        if dlg.exec():
            self.refresh()

    def _edit_selected_carpeta(self):
        table = self._active_table_carpetas()
        _id = table.get_selected_id()
        if not _id:
            QMessageBox.information(self, "Atencion", "Seleccione una carpeta.")
            return
        from views.expedientes.expediente_form import ExpedienteFormDialog

        dlg = ExpedienteFormDialog(expediente_id=_id, parent=self)
        if dlg.exec():
            self.refresh()

    def _delete_selected_carpeta(self):
        table = self._active_table_carpetas()
        _id = table.get_selected_id()
        if not _id:
            QMessageBox.information(self, "Atencion", "Seleccione una carpeta.")
            return
        reply = QMessageBox.question(
            self,
            "Confirmar",
            "Eliminar esta carpeta?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            ExpedienteController.delete(_id)
            self.refresh()

    def _open_carpeta(self, _id: str):
        from views.expedientes.expediente_form import ExpedienteFormDialog

        dlg = ExpedienteFormDialog(expediente_id=_id, parent=self)
        if dlg.exec():
            self.refresh()

    def _on_migracion_row_double_click(self, req_id: str):
        rec = MigracionRequerimientoController.get_by_id(req_id)
        if not rec:
            return
        id_exp = (rec.get("id_expediente") or "").strip()
        dlg = MigracionRequerimientoDetailDialog(req_id, id_exp, self)
        dlg.exec()
        self.refresh()

    def _open_carpeta_from_migr_selected(self):
        table = self._active_table_migracion()
        req_id = table.get_selected_id()
        if not req_id:
            QMessageBox.information(
                self,
                "Atención",
                "Seleccione una fila del listado para abrir su carpeta.",
            )
            return
        rec = MigracionRequerimientoController.get_by_id(req_id)
        if not rec:
            QMessageBox.information(self, "Atención", "No se encontró el requerimiento seleccionado.")
            return
        id_exp = (rec.get("id_expediente") or "").strip()
        if not id_exp:
            QMessageBox.information(self, "Atención", "La fila no tiene carpeta asociada.")
            return
        self._open_carpeta(id_exp)
