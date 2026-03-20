"""Widget dinámico que renderiza campos específicos de una rama jurídica."""
from PySide6.QtWidgets import (
    QWidget, QLineEdit, QComboBox,
    QCheckBox, QGridLayout, QLabel,
)
from PySide6.QtCore import QDate, Qt, QLocale
from PySide6.QtGui import QIntValidator, QDoubleValidator, QPainter, QColor
from views.widgets.no_wheel_datetime import NoWheelDateEdit


# ── Widgets de entrada especializados ────────────────────────────────────────

class _NumericLineEdit(QLineEdit):
    """Campo de texto para números decimales (montos).

    - Acepta dígitos, punto y coma.
    - Al perder foco formatea con separador de miles.
    - Devuelve float limpio.
    """

    def __init__(self, maximo: float = 999_999_999.0, prefijo: str = "", parent=None):
        super().__init__(parent)
        self._prefijo = prefijo or ""
        locale = QLocale(QLocale.Language.Spanish, QLocale.Country.Argentina)
        val = QDoubleValidator(0.0, maximo, 2, self)
        val.setLocale(locale)
        val.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.setValidator(val)
        self.setPlaceholderText("0,00")
        self.setFixedHeight(30)
        self.setMinimumWidth(150)
        self.setMaximumWidth(180)
        if self._prefijo:
            self.setTextMargins(20, 0, 0, 0)
        self.editingFinished.connect(self._format_value)

    def _format_value(self):
        raw = self.text().strip().replace(".", "").replace(",", ".")
        if not raw:
            return
        try:
            val = float(raw)
            locale = QLocale(QLocale.Language.Spanish, QLocale.Country.Argentina)
            formatted = locale.toString(val, "f", 2)
            self.setText(formatted)
        except ValueError:
            pass

    def get_value(self) -> float:
        raw = self.text().strip()
        if self._prefijo:
            raw = raw.replace(self._prefijo, "")
        raw = raw.replace(".", "").replace(",", ".")
        try:
            return float(raw)
        except ValueError:
            return 0.0

    def set_value(self, val: float):
        if not val:
            self.clear()
            return
        locale = QLocale(QLocale.Language.Spanish, QLocale.Country.Argentina)
        self.setText(locale.toString(float(val), "f", 2))

    def paintEvent(self, event):  # noqa: N802 (Qt API naming)
        super().paintEvent(event)
        if not self._prefijo:
            return
        painter = QPainter(self)
        painter.setPen(QColor("#666666"))
        text_rect = self.rect().adjusted(6, 0, -4, 0)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._prefijo.strip())
        painter.end()


class _IntegerLineEdit(QLineEdit):
    """Campo de texto para enteros (años, cantidades).

    - Solo acepta dígitos.
    - Devuelve int limpio.
    """

    def __init__(self, maximo: int = 9_999, parent=None):
        super().__init__(parent)
        self.setValidator(QIntValidator(0, maximo, self))
        self.setPlaceholderText("0")
        self.setFixedHeight(30)
        self.setMaximumWidth(120)
        self.setMinimumWidth(100)
        self.setAlignment(Qt.AlignmentFlag.AlignRight)

    def get_value(self) -> int:
        try:
            return int(self.text().strip())
        except ValueError:
            return 0

    def set_value(self, val):
        try:
            v = int(float(val)) if val else 0
            self.setText(str(v) if v else "")
        except (ValueError, TypeError):
            self.clear()


class _SmartDateEdit(NoWheelDateEdit):
    """DateEdit que abre el calendario en el mes actual cuando el campo está vacío."""

    def showPopup(self):  # noqa: N802 (Qt API naming)
        if self.date() <= self.minimumDate():
            today = QDate.currentDate()
            calendar = self.calendarWidget()
            calendar.setCurrentPage(today.year(), today.month())
            calendar.setSelectedDate(today)
        super().showPopup()


# ── Widget principal ──────────────────────────────────────────────────────────

class RamaDatosWidget(QWidget):
    """Genera un formulario dinámico a partir de una lista de definiciones de campo.

    Cada definición es un dict con:
        key      – nombre interno del campo
        label    – etiqueta visible
        tipo     – text | combo | date | number | integer | boolean
        opciones – lista de strings (solo para tipo combo)
        prefijo  – prefijo visible (ej. '$ ') para tipo number
        maximo   – valor máximo para number/integer
    """

    def __init__(self, campos: list[dict], parent=None):
        super().__init__(parent)
        self._campos = campos
        self._widgets: dict[str, QWidget] = {}
        self._build()

    def _build(self):
        layout = QGridLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)

        row = 0
        column_group = 0
        for campo in self._campos:
            key = campo["key"]
            label = campo["label"]
            widget = self._create_widget(campo)
            self._widgets[key] = widget
            label_widget = QLabel(f"{label}:")

            if self._use_full_row(campo):
                if column_group == 1:
                    row += 1
                    column_group = 0
                layout.addWidget(label_widget, row, 0)
                layout.addWidget(widget, row, 1, 1, 3)
                row += 1
                continue

            base_col = 0 if column_group == 0 else 2
            layout.addWidget(label_widget, row, base_col)
            layout.addWidget(widget, row, base_col + 1)
            if column_group == 0:
                column_group = 1
            else:
                column_group = 0
                row += 1

    def _use_full_row(self, campo: dict) -> bool:
        """Texto largo ocupa fila completa; el resto se distribuye en 2 columnas."""
        tipo = campo.get("tipo", "text")
        if tipo != "text":
            return False
        label = (campo.get("label", "") or "").strip()
        return len(label) > 22

    def _create_widget(self, campo: dict) -> QWidget:
        tipo = campo.get("tipo", "text")
        opciones = campo.get("opciones", [])
        maximo = campo.get("maximo", None)
        prefijo = campo.get("prefijo", "")

        if tipo == "combo":
            w = QComboBox()
            w.setMinimumWidth(200)
            w.setFixedHeight(30)
            w.addItem("")
            for opt in opciones:
                w.addItem(opt)
            return w

        elif tipo == "date":
            w = _SmartDateEdit()
            w.setCalendarPopup(True)
            w.setDisplayFormat("dd/MM/yyyy")
            w.setSpecialValueText(" ")
            w.setDate(w.minimumDate())
            w.setFixedHeight(30)
            w.setMinimumWidth(155)
            w.setMaximumWidth(190)
            return w

        elif tipo == "integer":
            return _IntegerLineEdit(maximo=int(maximo) if maximo is not None else 9_999)

        elif tipo == "number":
            w = _NumericLineEdit(
                maximo=float(maximo) if maximo is not None else 999_999_999.0,
                prefijo=str(prefijo),
            )
            return w

        elif tipo == "boolean":
            return QCheckBox()

        else:
            w = QLineEdit()
            w.setFixedHeight(30)
            return w

    # ── Acceso a datos ──────────────────────────────────────────────────────

    def get_data(self) -> dict:
        """Retorna un dict con los valores actuales de todos los campos."""
        data = {}
        for campo in self._campos:
            key = campo["key"]
            tipo = campo.get("tipo", "text")
            widget = self._widgets.get(key)
            if widget is None:
                continue

            if tipo == "combo":
                data[key] = widget.currentText()
            elif tipo == "date":
                if widget.date() > widget.minimumDate():
                    data[key] = widget.date().toString("yyyy-MM-dd")
                else:
                    data[key] = ""
            elif tipo == "number":
                data[key] = widget.get_value()
            elif tipo == "integer":
                data[key] = widget.get_value()
            elif tipo == "boolean":
                data[key] = widget.isChecked()
            else:
                data[key] = widget.text().strip()
        return data

    def set_data(self, data: dict):
        """Carga valores desde un dict en los widgets."""
        if not data or not isinstance(data, dict):
            return
        for campo in self._campos:
            key = campo["key"]
            tipo = campo.get("tipo", "text")
            widget = self._widgets.get(key)
            value = data.get(key)
            if widget is None or value is None:
                continue
            try:
                if tipo == "combo":
                    idx = widget.findText(str(value))
                    if idx >= 0:
                        widget.setCurrentIndex(idx)
                    else:
                        widget.setCurrentText(str(value))
                elif tipo == "date":
                    if value and isinstance(value, str) and len(value) >= 10:
                        widget.setDate(QDate.fromString(value[:10], "yyyy-MM-dd"))
                elif tipo == "number":
                    widget.set_value(float(value) if value else 0.0)
                elif tipo == "integer":
                    widget.set_value(value)
                elif tipo == "boolean":
                    widget.setChecked(bool(value))
                else:
                    widget.setText(str(value))
            except (ValueError, TypeError):
                pass

    def clear(self):
        """Resetea todos los campos a su estado vacío."""
        for campo in self._campos:
            key = campo["key"]
            tipo = campo.get("tipo", "text")
            widget = self._widgets.get(key)
            if widget is None:
                continue
            if tipo == "combo":
                widget.setCurrentIndex(0)
            elif tipo == "date":
                widget.setDate(widget.minimumDate())
            elif tipo in ("number", "integer"):
                widget.clear()
            elif tipo == "boolean":
                widget.setChecked(False)
            else:
                widget.setText("")

    def set_enabled(self, enabled: bool):
        """Habilita o deshabilita todos los widgets del formulario."""
        for widget in self._widgets.values():
            widget.setEnabled(enabled)
