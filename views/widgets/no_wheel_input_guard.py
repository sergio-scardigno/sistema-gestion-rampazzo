"""Filtro global para evitar cambios de inputs con rueda del mouse."""

from PySide6.QtCore import QObject, QEvent
from PySide6.QtWidgets import QAbstractSpinBox, QComboBox


class NoWheelInputGuard(QObject):
    """Bloquea rueda en combos y spin/date/time en toda la app."""

    def eventFilter(self, obj, event):  # noqa: N802 (Qt API naming)
        if event.type() != QEvent.Type.Wheel:
            return False

        current = obj
        while current is not None:
            if isinstance(current, (QComboBox, QAbstractSpinBox)):
                event.ignore()
                return True
            current = current.parent()
        return False
