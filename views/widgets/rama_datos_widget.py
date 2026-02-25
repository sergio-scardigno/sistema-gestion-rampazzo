"""Widget dinámico que renderiza campos específicos de una rama jurídica."""
import json
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QComboBox, QDateEdit,
    QCheckBox, QDoubleSpinBox, QLabel, QFrame,
)
from PySide6.QtCore import QDate


class RamaDatosWidget(QWidget):
    """Genera un formulario dinámico a partir de una lista de definiciones de campo.

    Cada definición es un dict con:
        key    – nombre interno del campo
        label  – etiqueta visible
        tipo   – text | combo | date | number | boolean
        opciones – lista de strings (solo para tipo combo)
    """

    def __init__(self, campos: list[dict], parent=None):
        super().__init__(parent)
        self._campos = campos
        self._widgets: dict[str, QWidget] = {}
        self._build()

    def _build(self):
        layout = QFormLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        for campo in self._campos:
            key = campo["key"]
            label = campo["label"]
            tipo = campo.get("tipo", "text")

            widget = self._create_widget(tipo, campo.get("opciones", []))
            self._widgets[key] = widget
            layout.addRow(f"{label}:", widget)

    def _create_widget(self, tipo: str, opciones: list[str]) -> QWidget:
        if tipo == "combo":
            w = QComboBox()
            w.addItem("")
            for opt in opciones:
                w.addItem(opt)
            return w
        elif tipo == "date":
            w = QDateEdit()
            w.setCalendarPopup(True)
            w.setDisplayFormat("dd/MM/yyyy")
            w.setSpecialValueText(" ")
            w.setDate(w.minimumDate())
            return w
        elif tipo == "number":
            w = QDoubleSpinBox()
            w.setDecimals(2)
            w.setMaximum(999_999_999.99)
            w.setMinimum(0)
            w.setSpecialValueText(" ")
            w.setValue(0)
            return w
        elif tipo == "boolean":
            w = QCheckBox()
            return w
        else:
            w = QLineEdit()
            return w

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
                data[key] = widget.value()
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
                    widget.setValue(float(value) if value else 0)
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
            elif tipo == "number":
                widget.setValue(0)
            elif tipo == "boolean":
                widget.setChecked(False)
            else:
                widget.setText("")

    def set_enabled(self, enabled: bool):
        """Habilita o deshabilita todos los widgets del formulario."""
        for widget in self._widgets.values():
            widget.setEnabled(enabled)
