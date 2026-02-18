"""
Widget indicador de estado de sincronizacion y conexion.
Muestra: circulo verde/amarillo/rojo + texto + hora ultimo sync.
"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt


class SyncIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)

        self._dot = QLabel()
        self._dot.setFixedSize(12, 12)
        self._label = QLabel("Conectando...")
        self._label.setStyleSheet("font-size: 12px; color: #6b6b6b;")

        layout.addWidget(self._dot)
        layout.addWidget(self._label)

        self.set_status("connecting")

    def set_status(self, status: str, detail: str = ""):
        colors = {
            "online": ("#2d8f4e", "Sincronizado"),
            "syncing": ("#c9a84c", "Sincronizando..."),
            "offline": ("#cc3333", "Sin conexion - Modo offline"),
            "connecting": ("#8a8a8a", "Conectando..."),
        }
        color, text = colors.get(status, ("#8a8a8a", "Desconocido"))
        if detail:
            text += f" | {detail}"
        self._dot.setStyleSheet(
            f"background-color: {color}; border-radius: 6px; min-width: 12px; min-height: 12px;"
        )
        self._label.setText(text)
