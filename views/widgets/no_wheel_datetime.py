"""Widgets de fecha/hora que ignoran la rueda del mouse."""

from PySide6.QtWidgets import QDateEdit, QTimeEdit


class NoWheelDateEdit(QDateEdit):
    """Evita cambios accidentales de fecha al desplazar rueda."""

    def wheelEvent(self, event):  # noqa: N802 (Qt API naming)
        event.ignore()


class NoWheelTimeEdit(QTimeEdit):
    """Evita cambios accidentales de hora al desplazar rueda."""

    def wheelEvent(self, event):  # noqa: N802 (Qt API naming)
        event.ignore()
