"""QLineEdit que copia el contenido al portapapeles al hacer clic."""

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QGuiApplication, QMouseEvent
from PySide6.QtWidgets import QLineEdit, QToolTip

# Estilo legible para campos de clave (ANSES / fiscal)
CLICK_COPY_CLAVE_STYLESHEET = """
QLineEdit {
    background-color: #ffffff;
    color: #1a1a1a;
    border: 1px solid #d0d0d0;
    font-weight: bold;
    font-size: 13px;
    padding: 4px 6px;
}
QLineEdit::placeholder {
    color: #757575;
}
"""


class ClickCopyLineEdit(QLineEdit):
    """Al clic izquierdo copia el texto del campo si no está vacío."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        if event.button() != Qt.MouseButton.LeftButton:
            return
        text = self.text()
        if not text:
            return
        QGuiApplication.clipboard().setText(text)
        QToolTip.showText(
            self.mapToGlobal(event.pos()),
            "Copiado",
            self,
            QRect(),
            2000,
        )
