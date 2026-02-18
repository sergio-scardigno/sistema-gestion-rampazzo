"""
Monitor de conexion a MongoDB Atlas.
Emite senales Qt cuando cambia el estado de conexion.
"""
from PySide6.QtCore import QObject, Signal, QTimer
from core.db_remote import is_connected


class ConnectionMonitor(QObject):
    status_changed = Signal(bool)  # True = online, False = offline

    def __init__(self, check_interval_ms: int = 30000, parent=None):
        super().__init__(parent)
        self._online = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.check)
        self._timer.start(check_interval_ms)

    @property
    def online(self) -> bool:
        return self._online

    def check(self):
        was_online = self._online
        self._online = is_connected()
        if was_online != self._online:
            self.status_changed.emit(self._online)

    def start(self):
        self.check()
        self._timer.start()

    def stop(self):
        self._timer.stop()
