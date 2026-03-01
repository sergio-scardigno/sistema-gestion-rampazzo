"""QComboBox variant that ignores mouse-wheel value changes."""

from PySide6.QtWidgets import QComboBox


class NoWheelComboBox(QComboBox):
    """Prevents accidental value changes when scrolling."""

    def wheelEvent(self, event):  # noqa: N802 (Qt API naming)
        event.ignore()
