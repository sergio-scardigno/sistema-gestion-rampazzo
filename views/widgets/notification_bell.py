"""
Widget de campanita de notificaciones para el topbar.
Muestra contador de no leidas y desplegable con items clickeables.
"""
import logging
from collections.abc import Callable

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QTimer, QPoint
from PySide6.QtGui import QFont

from controllers.notificacion_controller import (
    NotificacionController,
    BADGE_HIDE_ON_VIEW_TYPES,
    BADGE_PERSIST_WHEN_READ_TYPES,
    DISMISSIBLE_TYPES,
    NOTIF_STYLES,
    _DEFAULT_NOTIF_STYLE,
)
from core.auth import Session

logger = logging.getLogger(__name__)

_BADGE_STYLE = (
    "background-color: #cc3333;"
    "color: #ffffff;"
    "border-radius: 9px;"
    "font-size: 10px;"
    "font-weight: bold;"
    "font-family: 'Lato', 'Segoe UI', sans-serif;"
    "border: none;"
    "min-width: 18px;"
    "min-height: 18px;"
    "padding: 0px;"
)


class NotificationItem(QFrame):
    """Un item individual en el desplegable de notificaciones."""
    clicked = Signal(dict)
    dismiss_requested = Signal(dict)

    def __init__(self, notification: dict, dimmed: bool = False, parent=None):
        super().__init__(parent)
        self._notification = notification
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("notif_item")

        tipo = notification.get("tipo", "")
        style = NOTIF_STYLES.get(tipo, _DEFAULT_NOTIF_STYLE)

        bg = style["bg"]
        border_color = style["border"]
        icon_text = style["icon"]
        icon_color = style["icon_color"]
        label_text = style["label"]

        if dimmed:
            bg = "#f5f5f5"
            icon_color = "#b0b0b0"
            border_color = "#d0d0d0"

        self.setStyleSheet(
            f"#notif_item {{ background-color: {bg}; "
            f"border-left: 4px solid {border_color}; "
            f"border-bottom: 1px solid #f0f0f0; border-top: none; "
            f"border-right: none; }}"
            f"#notif_item:hover {{ background-color: {border_color}22; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 12, 8)
        layout.setSpacing(8)

        icon_lbl = QLabel(icon_text)
        icon_lbl.setFixedWidth(22)
        icon_lbl.setStyleSheet(
            f"color: {icon_color}; font-size: 15px; border: none; background: transparent;"
        )
        layout.addWidget(icon_lbl)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        tag_lbl = QLabel(label_text)
        tag_color = "#b0b0b0" if dimmed else border_color
        tag_lbl.setStyleSheet(
            f"color: {tag_color}; font-size: 9px; font-weight: 700; "
            f"border: none; background: transparent; letter-spacing: 1px;"
        )
        text_col.addWidget(tag_lbl)

        mensaje = notification.get("mensaje", "Sin mensaje")
        if len(mensaje) > 100:
            mensaje = mensaje[:97] + "..."
        leida = int(notification.get("leida", 0) or 0) == 1

        msg_color = "#b0b0b0" if dimmed else ("#6b6b6b" if leida else "#1a1a1a")
        suffix = " (leida)" if leida and not dimmed else ""
        msg_lbl = QLabel(f"{mensaje}{suffix}")
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet(
            f"color: {msg_color}; font-size: 11px; border: none; background: transparent;"
        )
        text_col.addWidget(msg_lbl)

        layout.addLayout(text_col, 1)

        if tipo in DISMISSIBLE_TYPES:
            btn_dismiss = QPushButton("\u2715")
            btn_dismiss.setObjectName("notif_dismiss_btn")
            btn_dismiss.setFixedSize(26, 26)
            btn_dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_dismiss.setToolTip("Descartar alerta")
            btn_dismiss.clicked.connect(
                lambda: self.dismiss_requested.emit(self._notification)
            )
            layout.addWidget(btn_dismiss, 0, Qt.AlignmentFlag.AlignTop)

    def mousePressEvent(self, event):
        self.clicked.emit(self._notification)
        super().mousePressEvent(event)


class NotificationPopup(QFrame):
    """Popup desplegable con la lista de notificaciones."""
    notification_clicked = Signal(dict)
    mark_all_clicked = Signal()
    dismiss_requested = Signal(dict)

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

    def set_notifications(
        self,
        notifications: list[dict],
        is_dimmed: Callable[[dict], bool] | None = None,
    ):
        """Reemplaza los items del popup con las notificaciones dadas."""
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
            dim = bool(is_dimmed(notif)) if is_dimmed is not None else False
            item = NotificationItem(notif, dimmed=dim)
            item.clicked.connect(self._on_item_clicked)
            item.dismiss_requested.connect(self.dismiss_requested.emit)
            self._items_layout.insertWidget(i, item)

    def _on_item_clicked(self, notification: dict):
        self.notification_clicked.emit(notification)
        self.close()


class NotificationHistoryPopup(QFrame):
    """Popup desplegable con historial reciente de notificaciones."""

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self.setObjectName("notif_history_popup")
        self.setFixedWidth(430)
        self.setMaximumHeight(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("notif_history_header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 10, 14, 10)

        title = QLabel("Historial de notificaciones")
        title.setFont(QFont("Lato", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #1a1a1a; border: none; background: transparent;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        layout.addWidget(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #e0e0e0; max-height: 1px;")
        layout.addWidget(sep)

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
        while self._items_layout.count() > 1:
            item = self._items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not notifications:
            lbl = QLabel("No hay historial todavía")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                "color: #8a8a8a; font-style: italic; padding: 24px; border: none;"
            )
            self._items_layout.insertWidget(0, lbl)
            return

        for i, notif in enumerate(notifications):
            item = NotificationItem(notif, dimmed=True)
            self._items_layout.insertWidget(i, item)


class NotificationBell(QWidget):
    """Widget de campanita con badge y popup de notificaciones."""
    notification_clicked = Signal(str, str)  # (tipo, id_referencia)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(0)

        self._bell_wrap = QWidget()
        self._bell_wrap.setFixedSize(36, 36)
        self._bell_wrap.setStyleSheet("background: transparent;")

        self._history_btn = QPushButton("\u23F2")
        self._history_btn.setObjectName("notif_history_btn")
        self._history_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._history_btn.setFixedSize(36, 36)
        self._history_btn.setToolTip("Historial de notificaciones")
        self._history_btn.clicked.connect(self._toggle_history_popup)

        self._btn = QPushButton("\U0001F514", self._bell_wrap)
        self._btn.setObjectName("notif_bell_btn")
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setGeometry(0, 0, 36, 36)
        self._btn.setToolTip("Notificaciones")
        self._btn.clicked.connect(self._toggle_popup)

        layout.addWidget(self._bell_wrap)
        layout.addWidget(self._history_btn)

        self._badge = QLabel("0", self)
        self._badge.setObjectName("notif_badge")
        self._badge.setStyleSheet(_BADGE_STYLE)
        self._badge.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setFixedSize(18, 18)
        self._badge.setVisible(False)
        QTimer.singleShot(0, self._position_badge)

        self._popup = NotificationPopup()
        self._popup.notification_clicked.connect(self._handle_notification_click)
        self._popup.mark_all_clicked.connect(self._mark_all_read)
        self._popup.dismiss_requested.connect(self._on_dismiss_notification)
        self._history_popup = NotificationHistoryPopup()

        self._notifications: list[dict] = []
        self._viewed_dismissible_ids: set[str] = set()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(30_000)

        self.refresh()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_badge()

    def showEvent(self, event):
        super().showEvent(event)
        self._position_badge()

    def _position_badge(self):
        if not getattr(self, "_bell_wrap", None):
            return
        br = self._bell_wrap.geometry()
        self._badge.move(br.x() + 20, br.y())
        self._badge.raise_()

    def _counts_toward_badge(self, n: dict) -> bool:
        """True si la notificacion activa debe sumar al contador de la campana."""
        tipo = n.get("tipo", "")
        nid = n.get("_id", "")
        leida = int(n.get("leida", 0) or 0) == 1

        if tipo in BADGE_HIDE_ON_VIEW_TYPES:
            if nid in self._viewed_dismissible_ids:
                return False
            if leida:
                return False
            return True

        if leida and tipo not in BADGE_PERSIST_WHEN_READ_TYPES:
            return False
        return True

    def _badge_count(self) -> int:
        return sum(1 for n in self._notifications if self._counts_toward_badge(n))

    def reset_session(self):
        """Reinicia el set de descarte (llamar al hacer login/logout)."""
        self._viewed_dismissible_ids.clear()

    def refresh(self):
        """Recargar notificaciones activas desde la base."""
        try:
            session = Session.get()
            if not session.logged_in:
                self._notifications = []
                self._badge.setVisible(False)
                return
            NotificacionController.sync_task_alerts_for_user(session.username, due_days=30)
            self._notifications = NotificacionController.get_active_for_user(
                session.username, limit=50
            )
        except Exception:
            logger.exception("Error al cargar notificaciones")
            self._notifications = []

        count = self._badge_count()
        if count > 0:
            self._badge.setText(str(min(count, 99)))
            self._badge.setVisible(True)
            self._position_badge()
        else:
            self._badge.setVisible(False)

    def _toggle_popup(self):
        """Mostrar u ocultar el popup de notificaciones."""
        if self._history_popup.isVisible():
            self._history_popup.close()
        if self._popup.isVisible():
            self._popup.close()
            return

        self.refresh()
        for n in self._notifications:
            if n.get("tipo") in BADGE_HIDE_ON_VIEW_TYPES:
                nid = n.get("_id", "")
                if nid:
                    self._viewed_dismissible_ids.add(nid)

        self._popup.set_notifications(
            self._notifications,
            is_dimmed=lambda x: not self._counts_toward_badge(x),
        )

        btn_global = self._btn.mapToGlobal(QPoint(0, self._btn.height()))
        x = btn_global.x() + self._btn.width() - self._popup.width()
        self._popup.move(x, btn_global.y() + 4)
        self._popup.show()

        count = self._badge_count()
        if count > 0:
            self._badge.setText(str(min(count, 99)))
            self._badge.setVisible(True)
            self._position_badge()
        else:
            self._badge.setVisible(False)

    def _toggle_history_popup(self):
        """Mostrar/ocultar historial de notificaciones."""
        if self._popup.isVisible():
            self._popup.close()
        if self._history_popup.isVisible():
            self._history_popup.close()
            return
        try:
            session = Session.get()
            if not session.logged_in:
                return
            history = NotificacionController.get_recent_for_user(
                session.username,
                limit=120,
            )
        except Exception:
            logger.exception("Error al cargar historial de notificaciones")
            history = []
        self._history_popup.set_notifications(history)
        btn_global = self._history_btn.mapToGlobal(QPoint(0, self._history_btn.height()))
        x = btn_global.x() + self._history_btn.width() - self._history_popup.width()
        self._history_popup.move(x, btn_global.y() + 4)
        self._history_popup.show()

    def _handle_notification_click(self, notification: dict):
        """Manejar click en una notificacion individual."""
        nid = notification.get("_id", "")
        if nid:
            try:
                NotificacionController.mark_read(nid)
            except Exception:
                logger.exception("Error al marcar notificacion %s como leida", nid)

        tipo = notification.get("tipo", "")
        id_ref = notification.get("id_referencia", "")

        self.notification_clicked.emit(tipo, id_ref)
        self.refresh()

    def _mark_all_read(self):
        """Marcar todas las notificaciones como leidas."""
        try:
            session = Session.get()
            NotificacionController.mark_all_read(session.username)
        except Exception:
            logger.exception("Error al marcar todas las notificaciones como leidas")
        self.refresh()
        self._popup.set_notifications(
            self._notifications,
            is_dimmed=lambda x: not self._counts_toward_badge(x),
        )

    def _on_dismiss_notification(self, notification: dict):
        """Descartar una notificacion con confirmacion (no vuelve a aparecer)."""
        reply = QMessageBox.question(
            self,
            "Descartar alerta",
            "¿Confirmás descartar esta alerta? No volverá a mostrarse "
            "(incluido el aviso al iniciar sesión), salvo que cambie la situación "
            "y el sistema genere un aviso nuevo distinto.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            session = Session.get()
            if not session.logged_in:
                return
            ok = NotificacionController.dismiss_notification(
                notification.get("_id", ""),
                session.username,
            )
            if not ok:
                QMessageBox.warning(
                    self,
                    "Descartar",
                    "No se pudo descartar esta notificación.",
                )
        except Exception:
            logger.exception("Error al descartar notificacion")
            QMessageBox.warning(
                self,
                "Descartar",
                "Ocurrió un error al descartar la notificación.",
            )
        self.refresh()
        if self._popup.isVisible():
            self._popup.set_notifications(
                self._notifications,
                is_dimmed=lambda x: not self._counts_toward_badge(x),
            )
        count = self._badge_count()
        if count > 0:
            self._badge.setText(str(min(count, 99)))
            self._badge.setVisible(True)
            self._position_badge()
        else:
            self._badge.setVisible(False)
