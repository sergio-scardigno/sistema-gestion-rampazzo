"""
Tabla reutilizable con busqueda integrada, paginacion y doble clic para abrir.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLineEdit, QPushButton, QLabel, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Signal, Qt
from typing import Callable


class FilterableTable(QWidget):
    row_double_clicked = Signal(str)  # Emite _id del registro
    row_selected = Signal(str)

    def __init__(self, columns: list[tuple[str, str]], parent=None,
                 search_fields: list[str] | None = None,
                 search_placeholder: str = "Buscar...",
                 row_style_provider: Callable[[dict, str, QTableWidgetItem], None] | None = None):
        """
        columns: lista de (field_name, display_name)
        search_fields: campos extra sobre los que buscar (sin mostrar columna).
                       Si es None se busca solo en las columnas visibles.
        search_placeholder: texto placeholder para el campo de busqueda.
        """
        super().__init__(parent)
        self._columns = columns
        self._search_fields: list[str] = (
            [c[0] for c in columns] + (search_fields or [])
        )
        self._search_placeholder = search_placeholder
        self._row_style_provider = row_style_provider
        self._data: list[dict] = []
        self._page = 0
        self._page_size = 50

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Search bar
        search_layout = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText(self._search_placeholder)
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_search)
        search_layout.addWidget(self._search)
        layout.addLayout(search_layout)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(len(columns))
        self._table.setHorizontalHeaderLabels([c[1] for c in columns])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._on_double_click)
        self._table.itemSelectionChanged.connect(self._on_selection)
        layout.addWidget(self._table)

        # Pagination
        pag_layout = QHBoxLayout()
        self._lbl_info = QLabel()
        self._btn_prev = QPushButton("Anterior")
        self._btn_prev.setProperty("variant", "secondary")
        self._btn_prev.clicked.connect(self._prev_page)
        self._btn_next = QPushButton("Siguiente")
        self._btn_next.setProperty("variant", "secondary")
        self._btn_next.clicked.connect(self._next_page)
        pag_layout.addWidget(self._lbl_info)
        pag_layout.addStretch()
        pag_layout.addWidget(self._btn_prev)
        pag_layout.addWidget(self._btn_next)
        layout.addLayout(pag_layout)

    def set_data(self, data: list[dict]):
        self._data = data
        self._page = 0
        self._refresh()

    def _on_search(self, text: str):
        self._page = 0
        self._refresh()

    def _refresh(self):
        import re as _re
        search_text = self._search.text().lower().strip()
        search_digits = _re.sub(r'[^\d]', '', search_text)
        if search_text:
            scored: list[tuple[int, int, dict]] = []
            for idx, row in enumerate(self._data):
                best = 0
                for field in self._search_fields:
                    val = str(row.get(field, "")).lower()
                    if val == search_text:
                        best = max(best, 3)
                    elif val.startswith(search_text):
                        best = max(best, 2)
                    elif search_text in val:
                        best = max(best, 1)
                    if search_digits and field in ("cli_dni", "dni"):
                        val_digits = _re.sub(r'[^\d]', '', val)
                        if val_digits == search_digits:
                            best = max(best, 3)
                        elif val_digits.startswith(search_digits):
                            best = max(best, 2)
                        elif search_digits in val_digits:
                            best = max(best, 1)
                if best > 0:
                    scored.append((best, idx, row))
            scored.sort(key=lambda t: (-t[0], t[1]))
            filtered = [t[2] for t in scored]
        else:
            filtered = self._data

        total = len(filtered)
        start = self._page * self._page_size
        end = min(start + self._page_size, total)
        page_data = filtered[start:end]

        self._table.setRowCount(len(page_data))
        for row_idx, row_data in enumerate(page_data):
            for col_idx, (field, _) in enumerate(self._columns):
                val = row_data.get(field, "")
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val)
                item = QTableWidgetItem(str(val) if val is not None else "")
                item.setData(Qt.ItemDataRole.UserRole, row_data.get("_id", ""))
                if self._row_style_provider:
                    try:
                        self._row_style_provider(row_data, field, item)
                    except Exception:
                        # El estilo visual nunca debe romper el render de la tabla.
                        pass
                self._table.setItem(row_idx, col_idx, item)

        self._lbl_info.setText(f"Mostrando {start + 1}-{end} de {total}")
        self._btn_prev.setEnabled(self._page > 0)
        self._btn_next.setEnabled(end < total)

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._refresh()

    def _next_page(self):
        self._page += 1
        self._refresh()

    def _on_double_click(self, index):
        item = self._table.item(index.row(), 0)
        if item:
            _id = item.data(Qt.ItemDataRole.UserRole)
            if _id:
                self.row_double_clicked.emit(_id)

    def _on_selection(self):
        items = self._table.selectedItems()
        if items:
            _id = items[0].data(Qt.ItemDataRole.UserRole)
            if _id:
                self.row_selected.emit(_id)

    def get_selected_id(self) -> str | None:
        items = self._table.selectedItems()
        if items:
            return items[0].data(Qt.ItemDataRole.UserRole)
        return None

    def refresh_data(self, data: list[dict]):
        self.set_data(data)
