"""
Widget de campanita de notificaciones para el topbar.
Muestra contador de no leidas y desplegable con items clickeables.
"""
import logging

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea
)
from PySide6.QtCore import Qt, Signal, QTimer, QPoint
from PySide6.QtGui import QFont

from controllers.notificacion_controller import NotificacionController
from core.auth import Session

logger = logging.getLogger(__name__)


class NotificationItem(QFrame):
    """Un item individual en el desplegable de notificaciones."""
    clicked = Signal(dict)

    def __init__(self, notification: dict, parent=None):
        super().__init__(parent)
        self._notification = notification
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("notif_item")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # Icono segun tipo
        tipo = notification.get("tipo", "")
        if tipo == "tarea_asignada":
            icon_text = "\u2611"
            color = "#2d6bcf"
        elif tipo == "expediente_asignado":
            icon_text = "\u2630"
            color = "#7b5cd6"
        elif tipo == "turno_asignado":
            icon_text = "\u23F0"
            color = "#c9a84c"
        else:
            icon_text = "\u2139"
            color = "#4a4a4a"

        icon_lbl = QLabel(icon_text)
        icon_lbl.setFixedWidth(20)
        icon_lbl.setStyleSheet(
            f"color: {color}; font-size: 14px; border: none; background: transparent;"
        )
        layout.addWidget(icon_lbl)

        # Texto del mensaje
        mensaje = notification.get("mensaje", "Sin mensaje")
        if len(mensaje) > 100:
            mensaje = mensaje[:97] + "..."
        leida = int(notification.get("leida", 0) or 0) == 1
        if leida:
            mensaje = f"{mensaje} (leida)"
        msg_lbl = QLabel(mensaje)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet(
            "color: #6b6b6b; font-size: 11px; border: none; background: transparent;"
            if leida else
            "color: #1a1a1a; font-size: 11px; border: none; background: transparent;"
        )
        layout.addWidget(msg_lbl, 1)

    def mousePressEvent(self, event):
        self.clicked.emit(self._notification)
        super().mousePressEvent(event)


class NotificationPopup(QFrame):
    """Popup desplegable con la lista de notificaciones."""
    notification_clicked = Signal(dict)
    mark_all_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self.setObjectName("notif_popup")
        self.setFixedWidth(400)
        self.setMaximumHeight(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setObjectName("notif_popup_header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 10, 14, 10)

        title = QLabel("Notificaciones")
        title.setFont(QFont("Lato", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #1a1a1a; border: none; background: transparent;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        btn_mark_all = QPushButton("Marcar todas leidas")
        btn_mark_all.setObjectName("notif_mark_all_btn")
        btn_mark_all.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_mark_all.clicked.connect(self.mark_all_clicked.emit)
        header_layout.addWidget(btn_mark_all)

        layout.addWidget(header)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #e0e0e0; max-height: 1px;")
        layout.addWidget(sep)

        # Area scrollable para items
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent; border: none;")

        self._items_widget = QWidget()
        self._items_widget.setStyleSheet("background: transparent;")
        self._items_layout = QVBoxLayout(self._items_widget)
        self._items_layout.setContentsMargins(0, 0, 0, 0)
        self._items_layout.setSpacing(0)
        self._items_layout.addStretch()

        scroll.setWidget(self._items_widget)
        layout.addWidget(scroll)

    def set_notifications(self, notifications: list[dict]):
        """Reemplaza los items del popup con las notificaciones dadas."""
        # Limpiar items previos (excepto el stretch final)
        while self._items_layout.count() > 1:
            item = self._items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not notifications:
            lbl = QLabel("No hay notificaciones nuevas")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                "color: #8a8a8a; font-style: italic; padding: 24px; border: none;"
            )
            self._items_layout.insertWidget(0, lbl)
            return

        for i, notif in enumerate(notifications):
            item = NotificationItem(notif)
            item.clicked.connect(self._on_item_clicked)
            self._items_layout.insertWidget(i, item)

    def _on_item_clicked(self, notification: dict):
        self.notification_clicked.emit(notification)
        self.close()


class NotificationBell(QWidget):
    """Widget de campanita con badge y popup de notificaciones."""
    notification_clicked = Signal(str, str)  # (tipo, id_referencia)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(0)

        # Boton de campanita
        self._btn = QPushButton("\U0001F514")
        self._btn.setObjectName("notif_bell_btn")
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setFixedSize(36, 36)
        self._btn.setToolTip("Notificaciones")
        self._btn.clicked.connect(self._toggle_popup)
        layout.addWidget(self._btn)

        # Badge de conteo (posicionado sobre el boton)
        self._badge = QLabel("0", self._btn)
        self._badge.setObjectName("notif_badge")
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setFixedSize(18, 18)
        self._badge.move(20, 0)
        self._badge.setVisible(False)

        # Popup
        self._popup = NotificationPopup()
        self._popup.notification_clicked.connect(self._handle_notification_click)
        self._popup.mark_all_clicked.connect(self._mark_all_read)

        # Cache de notificaciones
        self._notifications: list[dict] = []

        # Timer de refresco (cada 30 segundos)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(30_000)

        # Carga inicial
        self.refresh()

    def refresh(self):
        """Recargar notificaciones activas desde la base."""
        try:
            session = Session.get()
            if not session.logged_in:
                return
            # Reconciliar alertas de tareas con estado actual.
            NotificacionController.sync_task_alerts_for_user(session.username, due_days=3)
            self._notifications = NotificacionController.get_active_for_user(
                session.username, limit=50
            )
        except Exception:
            logger.exception("Error al cargar notificaciones")
            self._notifications = []

        count = len(self._notifications)
        if count > 0:
            self._badge.setText(str(min(count, 99)))
            self._badge.setVisible(True)
        else:
            self._badge.setVisible(False)

    def _toggle_popup(self):
        """Mostrar u ocultar el popup de notificaciones."""
        if self._popup.isVisible():
            self._popup.close()
            return

        # Refrescar antes de mostrar
        self.refresh()
        self._popup.set_notifications(self._notifications)

        # Posicionar popup debajo del boton, alineado a la derecha
        btn_global = self._btn.mapToGlobal(QPoint(0, self._btn.height()))
        x = btn_global.x() + self._btn.width() - self._popup.width()
        self._popup.move(x, btn_global.y() + 4)
        self._popup.show()

    def _handle_notification_click(self, notification: dict):
        """Manejar click en una notificacion individual."""
        # Marcar como leida
        nid = notification.get("_id", "")
        if nid:
            try:
                NotificacionController.mark_read(nid)
            except Exception:
                logger.exception("Error al marcar notificacion %s como leida", nid)

        tipo = notification.get("tipo", "")
        id_ref = notification.get("id_referencia", "")

        # Emitir senal para que MainWindow maneje la navegacion
        self.notification_clicked.emit(tipo, id_ref)

        # Refrescar badge
        self.refresh()

    def _mark_all_read(self):
        """Marcar todas las notificaciones como leidas."""
        try:
            session = Session.get()
            NotificacionController.mark_all_read(session.username)
        except Exception:
            logger.exception("Error al marcar todas las notificaciones como leidas")
        self.refresh()
        self._popup.set_notifications(self._notifications)
