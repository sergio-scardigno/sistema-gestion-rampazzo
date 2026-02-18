"""Dialogo para seleccionar un cliente de una lista de resultados."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

_COLUMNS = [
    ("numero_carpeta", "N° Carpeta"),
    ("nombre_completo", "Nombre Completo"),
    ("dni", "DNI"),
    ("cuil", "CUIL"),
    ("telefonos", "Telefonos"),
]


class ClientePickerDialog(QDialog):
    """Muestra una tabla con varios clientes y permite elegir uno."""

    def __init__(self, clientes: list[dict], titulo: str = "Seleccionar cliente",
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setMinimumSize(750, 400)
        self._selected_id: str | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        lbl = QLabel(f"Se encontraron {len(clientes)} clientes. Seleccione uno:")
        lbl.setFont(QFont("Lato", 12, QFont.Weight.Bold))
        layout.addWidget(lbl)

        # Tabla
        self._table = QTableWidget()
        self._table.setColumnCount(len(_COLUMNS))
        self._table.setHorizontalHeaderLabels([c[1] for c in _COLUMNS])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._on_double_click)

        self._table.setRowCount(len(clientes))
        self._clientes = clientes
        for row_idx, cli in enumerate(clientes):
            for col_idx, (field, _) in enumerate(_COLUMNS):
                val = cli.get(field, "")
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val)
                item = QTableWidgetItem(str(val) if val is not None else "")
                item.setData(Qt.ItemDataRole.UserRole, cli.get("_id", ""))
                self._table.setItem(row_idx, col_idx, item)

        layout.addWidget(self._table)

        # Botones
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setProperty("variant", "secondary")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_select = QPushButton("Seleccionar")
        btn_select.clicked.connect(self._on_select)
        btn_layout.addWidget(btn_select)

        layout.addLayout(btn_layout)

    @property
    def selected_id(self) -> str | None:
        return self._selected_id

    def _get_current_id(self) -> str | None:
        items = self._table.selectedItems()
        if items:
            return items[0].data(Qt.ItemDataRole.UserRole)
        return None

    def _on_select(self):
        _id = self._get_current_id()
        if _id:
            self._selected_id = _id
            self.accept()

    def _on_double_click(self, index):
        item = self._table.item(index.row(), 0)
        if item:
            _id = item.data(Qt.ItemDataRole.UserRole)
            if _id:
                self._selected_id = _id
                self.accept()
