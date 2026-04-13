"""Popup de inicio con alertas y asignaciones del usuario."""
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QHBoxLayout,
    QWidget,
    QFrame,
    QMessageBox,
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

from controllers.notificacion_controller import (
    DISMISSIBLE_TYPES,
    NOTIF_STYLES,
    NotificacionController,
    _DEFAULT_NOTIF_STYLE,
)
from core.auth import Session


class LoginTaskAlertsPopup(QDialog):
    """Muestra alertas activas (tareas y carpetas asignadas) al iniciar sesion."""

    _BADGE_OVERRIDES: dict[str, tuple[str, str]] = {
        "tarea_proxima_vencer": ("VENCE", "due_date"),
        "tarea_asignada": ("VENCE", "due_date"),
        "expediente_asignado": ("ASIGNADA", "expediente"),
        "expediente_etapa_encargado": ("ETAPA", "expediente"),
        "recordatorio_expediente": ("CARPETA", "expediente"),
    }

    def __init__(self, notifications: list[dict], parent=None):
        super().__init__(parent)
        self.selected_notification: dict | None = None
        self.setObjectName("LoginTaskAlertsPopup")
        self.setWindowTitle("Alertas y asignaciones")
        self.setMinimumWidth(560)
        self.setMinimumHeight(360)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("Alertas de tareas y designaciones de carpeta")
        title.setFont(QFont("Lato", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #111827; border: none; background: transparent;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Estas alertas siguen en la campana hasta descartarlas o hasta que "
            "el sistema las resuelva (por ejemplo, tarea cumplida)."
        )
        subtitle.setObjectName("login_alerts_subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self._list_widget = QListWidget()
        self._list_widget.setObjectName("login_alerts_list")
        self._list_widget.setAlternatingRowColors(True)
        self._list_widget.itemClicked.connect(self._open_from_item)

        for notif in notifications:
            item = QListWidgetItem()
            widget = self._build_item_widget(notif, item)
            item.setSizeHint(widget.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, notif)
            self._list_widget.addItem(item)
            self._list_widget.setItemWidget(item, widget)

        click_hint = QLabel("Tip: hacé clic en una alerta para abrir el detalle")
        click_hint.setObjectName("login_alerts_hint")
        layout.addWidget(click_hint)
        layout.addWidget(self._list_widget, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_dismiss_all = QPushButton("Descartar todas")
        btn_dismiss_all.setToolTip(
            "Descartar todas las alertas listadas (pide confirmación)"
        )
        btn_dismiss_all.clicked.connect(self._confirm_dismiss_all)
        btn_row.addWidget(btn_dismiss_all)
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _confirm_dismiss_item(self, notif: dict, list_item: QListWidgetItem):
        reply = QMessageBox.question(
            self,
            "Descartar alerta",
            "¿Confirmás descartar esta alerta? No volverá a mostrarse "
            "(incluido el aviso al iniciar sesión), salvo que el sistema "
            "genere un aviso nuevo con otra referencia.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        session = Session.get()
        if not session.logged_in:
            return
        ok = NotificacionController.dismiss_notification(
            notif.get("_id", ""),
            session.username,
        )
        if not ok:
            QMessageBox.warning(
                self,
                "Descartar",
                "No se pudo descartar esta notificación.",
            )
            return
        row = self._list_widget.row(list_item)
        if row >= 0:
            self._list_widget.takeItem(row)

    def _confirm_dismiss_all(self):
        if self._list_widget.count() == 0:
            return
        reply = QMessageBox.question(
            self,
            "Descartar todas las alertas",
            f"¿Confirmás descartar las {self._list_widget.count()} alertas listadas? "
            "No volverán a mostrarse de esta forma.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        session = Session.get()
        if not session.logged_in:
            return
        errors = 0
        for i in range(self._list_widget.count() - 1, -1, -1):
            item = self._list_widget.item(i)
            notif = item.data(Qt.ItemDataRole.UserRole) or {}
            if isinstance(notif, dict) and notif.get("_id"):
                if NotificacionController.dismiss_notification(
                    notif["_id"],
                    session.username,
                ):
                    self._list_widget.takeItem(i)
                else:
                    errors += 1
            else:
                self._list_widget.takeItem(i)
        if errors:
            QMessageBox.warning(
                self,
                "Descartar",
                f"No se pudieron descartar {errors} notificación(es).",
            )
        self.accept()

    def _format_date(self, iso_date: str) -> str:
        if not iso_date:
            return "-"
        raw = iso_date.strip()[:10]
        try:
            return datetime.strptime(raw, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            return raw

    def _get_due_date_text(self, notification: dict) -> str:
        task_id = notification.get("id_referencia", "")
        if not task_id:
            return "-"
        try:
            from controllers.tarea_controller import TareaController

            tarea = TareaController.get_by_id(task_id)
            if not tarea:
                return "-"
            return self._format_date(tarea.get("fecha_vencimiento", ""))
        except Exception:
            return "-"

    def _get_expediente_label(self, notification: dict) -> str:
        exp_id = notification.get("id_referencia", "")
        if not exp_id:
            return "-"
        try:
            from controllers.expediente_controller import ExpedienteController

            exp = ExpedienteController.get_by_id(exp_id)
            if not exp:
                return "-"
            exp_num = exp.get("id_expediente", "")
            return f"#{exp_num}" if exp_num else "-"
        except Exception:
            return "-"

    def _build_item_widget(
        self,
        notif: dict,
        list_item: QListWidgetItem,
    ) -> QWidget:
        tipo = notif.get("tipo", "")
        style = NOTIF_STYLES.get(tipo, _DEFAULT_NOTIF_STYLE)
        prefix = style["label"]

        override = self._BADGE_OVERRIDES.get(tipo)
        if override:
            badge_title = override[0]
            badge_value = (
                self._get_due_date_text(notif)
                if override[1] == "due_date"
                else self._get_expediente_label(notif)
            )
        else:
            badge_title = "REF."
            badge_value = "-"

        text = notif.get("mensaje", "")
        message = text
        bg = style["bg"]
        border_color = style["border"]
        icon_color = style["icon_color"]

        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background-color: {bg}; "
            f"border-top: 1px solid #cbd5e1; "
            f"border-right: 1px solid #cbd5e1; "
            f"border-bottom: 1px solid #cbd5e1; "
            f"border-left: 4px solid {border_color}; "
            f"border-radius: 8px; }}"
        )
        row = QHBoxLayout(card)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(10)

        left = QVBoxLayout()
        left.setSpacing(4)
        lbl_type = QLabel(prefix)
        lbl_type.setStyleSheet(
            f"color: {icon_color}; font-weight: 700; font-size: 10px; "
            f"border: none; background: transparent; letter-spacing: 1px;"
        )
        left.addWidget(lbl_type)
        lbl_msg = QLabel(message)
        lbl_msg.setWordWrap(True)
        lbl_msg.setStyleSheet(
            "color: #111827; font-size: 12px; border: none; background: transparent;"
        )
        left.addWidget(lbl_msg)
        row.addLayout(left, 1)

        due = QLabel(f"{badge_title}\n{badge_value}")
        due.setAlignment(Qt.AlignmentFlag.AlignCenter)
        due.setMinimumWidth(120)
        due.setStyleSheet(
            f"background-color: {border_color}22; "
            f"color: {border_color}; "
            f"border: 2px solid {border_color}; "
            f"border-radius: 8px; "
            f"font-weight: 800; font-size: 17px; padding: 6px 10px;"
        )
        row.addWidget(due)

        if tipo in DISMISSIBLE_TYPES:
            btn = QPushButton("Descartar")
            btn.setToolTip("No volver a mostrar esta alerta")
            btn.clicked.connect(
                lambda: self._confirm_dismiss_item(notif, list_item)
            )
            row.addWidget(btn, 0, Qt.AlignmentFlag.AlignTop)

        return card

    def _open_from_item(self, item: QListWidgetItem):
        notification = item.data(Qt.ItemDataRole.UserRole) or {}
        if not isinstance(notification, dict):
            return
        self.selected_notification = notification
        self.accept()
