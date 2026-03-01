"""Vista listado de Tareas / Seguimiento."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox, QComboBox, QTableWidgetItem, QHeaderView
)
from PySide6.QtGui import QFont, QColor, QBrush
from datetime import datetime, date

from views.widgets.filterable_table import FilterableTable
from controllers.tarea_controller import TareaController

COLUMNS = [
    ("descripcion", "Descripcion"),
    ("tipo_accion", "Tipo"),
    ("responsable", "Responsable"),
    ("fecha_inicio", "Inicio"),
    ("fecha_vencimiento", "Vencimiento"),
    ("estado", "Estado"),
]


class TareaListView(QWidget):
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

        header = QHBoxLayout()
        title = QLabel("Tareas y Seguimiento")
        title.setFont(QFont("Lato", 17, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        self._cmb_estado = QComboBox()
        self._cmb_estado.addItem("Todos", "")
        for e in TareaController.ESTADOS:
            self._cmb_estado.addItem(e, e)
        self._cmb_estado.currentIndexChanged.connect(self.refresh)
        header.addWidget(self._cmb_estado)

        btn_new = QPushButton("+ Nueva Tarea")
        btn_new.clicked.connect(self._new_tarea)
        header.addWidget(btn_new)

        btn_edit = QPushButton("Editar")
        btn_edit.setProperty("variant", "secondary")
        btn_edit.clicked.connect(self._edit_tarea)
        header.addWidget(btn_edit)

        btn_delete = QPushButton("Eliminar")
        btn_delete.setProperty("variant", "danger")
        btn_delete.clicked.connect(self._delete_tarea)
        header.addWidget(btn_delete)

        layout.addLayout(header)

        self._table = FilterableTable(COLUMNS, row_style_provider=self._style_due_date_cell)
        self._table.row_double_clicked.connect(self._on_double_click)

        # Mejor legibilidad: mayor alto de fila y padding de celdas.
        table_widget = self._table._table
        table_widget.verticalHeader().setDefaultSectionSize(36)
        table_widget.setStyleSheet("QTableWidget::item { padding: 8px 10px; }")
        table_widget.horizontalHeader().setStretchLastSection(False)
        table_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)         # Descripcion
        table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Tipo
        table_widget.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Responsable
        table_widget.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Inicio
        table_widget.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)         # Vencimiento
        table_widget.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Estado

        layout.addWidget(self._table)

    def refresh(self):
        estado = self._cmb_estado.currentData()
        if estado:
            data = TareaController.get_scoped(
                where="estado = ?", params=(estado,), order_by="fecha_vencimiento ASC"
            )
        else:
            data = TareaController.get_scoped(order_by="fecha_vencimiento ASC")
        self._table.set_data(data)

    def _new_tarea(self):
        from views.tareas.tarea_form import TareaFormDialog
        dlg = TareaFormDialog(parent=self)
        if dlg.exec():
            self.refresh()

    def _edit_tarea(self):
        _id = self._table.get_selected_id()
        if not _id:
            QMessageBox.information(self, "Atencion", "Seleccione una tarea.")
            return
        from views.tareas.tarea_form import TareaFormDialog
        dlg = TareaFormDialog(tarea_id=_id, parent=self)
        if dlg.exec():
            self.refresh()

    def _on_double_click(self, _id):
        from views.tareas.tarea_form import TareaFormDialog
        dlg = TareaFormDialog(tarea_id=_id, parent=self)
        if dlg.exec():
            self.refresh()

    def _delete_tarea(self):
        _id = self._table.get_selected_id()
        if not _id:
            QMessageBox.information(self, "Atencion", "Seleccione una tarea.")
            return
        reply = QMessageBox.question(
            self, "Confirmar", "Eliminar esta tarea?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            TareaController.delete(_id)
            self.refresh()

    def _style_due_date_cell(self, row_data: dict, field: str, item: QTableWidgetItem):
        if field not in ("fecha_vencimiento", "estado", "descripcion"):
            return
        due_date = self._parse_ymd(row_data.get("fecha_vencimiento", ""))
        if not due_date:
            return
        days_left = (due_date - date.today()).days
        estado = str(row_data.get("estado", "") or "").strip()
        is_completed = estado in {"Cumplida", "Completada"}

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
            underline = field == "fecha_vencimiento"

        # Etiqueta textual visible para llamar atencion en la fecha.
        if field == "fecha_vencimiento":
            raw_text = str(row_data.get("fecha_vencimiento", "") or "")
            if is_completed:
                item.setText(f"✓ COMPLETADA {raw_text}")
            elif days_left < 0:
                item.setText(f"● VENCIDA {raw_text}")
            elif days_left <= 5:
                item.setText(f"▲ PROXIMA {raw_text}")
            else:
                item.setText(f"○ EN TIEMPO {raw_text}")

        item.setForeground(QBrush(QColor(fg_text if field in ("fecha_vencimiento", "estado") else self.FG_DARK)))
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
