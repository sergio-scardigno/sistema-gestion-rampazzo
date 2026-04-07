"""Referencias de expediente (ANSES, IPS, SRT, Judicial): selector compacto + lista editable."""
import json

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox,
)
from PySide6.QtCore import Qt

from controllers.expediente_controller import ExpedienteController
from views.widgets.no_wheel_combo import NoWheelComboBox


class ExpedientesReferenciaWidget(QWidget):
    """Combo + número + Agregar; filas con edición y quitar. Persistencia en datos_rama."""

    _ORDER = ("anses", "ips", "srt", "judicial")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: list[dict] = []
        self._labels = dict(ExpedienteController.TIPOS_EXPEDIENTE_REF)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 4, 0, 4)
        root.setSpacing(6)

        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self._cmb = NoWheelComboBox()
        for key, label in ExpedienteController.TIPOS_EXPEDIENTE_REF:
            self._cmb.addItem(label, key)
        self._txt_num = QLineEdit()
        self._txt_num.setPlaceholderText("Número o referencia")
        self._txt_num.setFixedHeight(30)
        self._btn_add = QPushButton("Agregar")
        self._btn_add.setFixedHeight(30)
        self._btn_add.clicked.connect(self._on_add)
        self._txt_num.returnPressed.connect(self._on_add)
        add_row.addWidget(QLabel("Tipo:"), 0, Qt.AlignmentFlag.AlignRight)
        add_row.addWidget(self._cmb)
        add_row.addWidget(self._txt_num, 1)
        add_row.addWidget(self._btn_add)
        root.addLayout(add_row)

        self._rows_layout = QVBoxLayout()
        self._rows_layout.setSpacing(4)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        root.addLayout(self._rows_layout)

    def _label_for(self, tipo: str) -> str:
        return self._labels.get(tipo, tipo)

    def _sorted_entries(self) -> list[dict]:
        order = {t: i for i, t in enumerate(self._ORDER)}
        return sorted(self._entries, key=lambda e: order.get(e.get("tipo", ""), 99))

    def _on_add(self):
        tipo = self._cmb.currentData()
        if not tipo:
            return
        num = self._txt_num.text().strip()
        if not num:
            QMessageBox.warning(self, "Atención", "Indique un número o referencia.")
            return
        for e in self._entries:
            if e.get("tipo") == tipo:
                e["numero"] = num
                self._txt_num.clear()
                self._refresh_rows()
                return
        self._entries.append({"tipo": tipo, "numero": num})
        self._txt_num.clear()
        self._refresh_rows()

    def _update_numero(self, tipo: str, texto: str):
        for e in self._entries:
            if e.get("tipo") == tipo:
                e["numero"] = texto
                return

    def _remove_tipo(self, tipo: str):
        self._entries = [e for e in self._entries if e.get("tipo") != tipo]
        self._refresh_rows()

    def _refresh_rows(self):
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for entry in self._sorted_entries():
            self._rows_layout.addWidget(self._make_row(entry))

    def _make_row(self, entry: dict) -> QWidget:
        tipo = entry.get("tipo", "")
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 2, 0, 2)
        h.setSpacing(8)
        lbl = QLabel(f"{self._label_for(tipo)}:")
        lbl.setMinimumWidth(72)
        txt = QLineEdit(entry.get("numero", "") or "")
        txt.setPlaceholderText("Número o referencia")
        txt.setFixedHeight(30)
        txt.textChanged.connect(lambda t, tp=tipo: self._update_numero(tp, t))
        btn = QPushButton("Quitar")
        btn.setProperty("variant", "secondary")
        btn.setFixedHeight(30)
        btn.clicked.connect(lambda _=False, tp=tipo: self._remove_tipo(tp))
        h.addWidget(lbl)
        h.addWidget(txt, 1)
        h.addWidget(btn)
        return w

    def get_data(self) -> dict:
        items = [
            {"tipo": e["tipo"], "numero": (e.get("numero") or "").strip()}
            for e in self._entries
            if (e.get("numero") or "").strip()
        ]
        return {"expedientes_referencia": items}

    @staticmethod
    def _normalize_list(raw) -> list[dict]:
        if not isinstance(raw, list):
            return []
        out = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            tipo = (item.get("tipo") or "").strip().lower()
            if tipo not in dict(ExpedienteController.TIPOS_EXPEDIENTE_REF):
                continue
            num = str(item.get("numero", "") or "").strip()
            if not num:
                continue
            out.append({"tipo": tipo, "numero": num})
        return out

    @classmethod
    def _migrate_legacy(cls, data: dict) -> list[dict]:
        if not isinstance(data, dict):
            return []
        out = []
        for old_key, tipo in ExpedienteController.LEGACY_KEY_TO_TIPO_EXPEDIENTE.items():
            val = data.get(old_key)
            if val is None or val == "":
                continue
            out.append({"tipo": tipo, "numero": str(val).strip()})
        return out

    def set_data(self, data: dict):
        if not isinstance(data, dict):
            self.clear()
            return
        if not data:
            self.clear()
            return
        raw = data.get("expedientes_referencia")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                raw = None
        parsed = self._normalize_list(raw) if raw is not None else []
        if parsed:
            self._entries = parsed
        else:
            self._entries = self._migrate_legacy(data)
        self._refresh_rows()

    def clear(self):
        self._entries = []
        self._txt_num.clear()
        self._refresh_rows()
