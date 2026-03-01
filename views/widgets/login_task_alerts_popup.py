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
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt


class LoginTaskAlertsPopup(QDialog):
    """Muestra alertas activas (tareas y carpetas asignadas) al iniciar sesion."""

    def __init__(self, notifications: list[dict], parent=None):
        super().__init__(parent)
        self.selected_notification: dict | None = None
        self.setWindowTitle("Alertas y asignaciones")
        self.setMinimumWidth(560)
        self.setMinimumHeight(360)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("Alertas de tareas y carpetas asignadas")
        title.setFont(QFont("Lato", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        subtitle = QLabel(
            "Estas alertas quedan visibles en la campana hasta que se resuelvan."
        )
        subtitle.setStyleSheet("color: #6b6b6b; font-size: 11px;")
        layout.addWidget(subtitle)

        self._list_widget = QListWidget()
        self._list_widget.setAlternatingRowColors(True)
        self._list_widget.setStyleSheet(
            """
            QListWidget { background-color: #ffffff; border: 1px solid #e0e0e0; }
            QListWidget::item { margin: 4px 6px; }
            QListWidget::item:selected { background-color: #e9f2ff; }
            """
        )
        self._list_widget.itemClicked.connect(self._open_from_item)

        for notif in notifications:
            tipo = notif.get("tipo", "")
            if tipo == "tarea_proxima_vencer":
                prefix = "PROXIMA"
                badge_title = "VENCE"
                badge_value = self._get_due_date_text(notif)
            elif tipo == "expediente_asignado":
                prefix = "ASIGNADA"
                badge_title = "CARPETA"
                badge_value = self._get_expediente_label(notif)
            else:
                prefix = "ASIGNADA"
                badge_title = "VENCE"
                badge_value = self._get_due_date_text(notif)
            text = notif.get("mensaje", "")

            widget = self._build_item_widget(prefix, text, badge_title, badge_value)
            item = QListWidgetItem()
            item.setSizeHint(widget.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, notif)
            self._list_widget.addItem(item)
            self._list_widget.setItemWidget(item, widget)

        click_hint = QLabel("Tip: hace clic en una alerta para abrir el detalle")
        click_hint.setStyleSheet("color: #4a4a4a; font-size: 11px; font-style: italic;")
        layout.addWidget(click_hint)
        layout.addWidget(self._list_widget, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

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
        self, prefix: str, message: str, badge_title: str, badge_value: str
    ) -> QWidget:
        card = QFrame()
        card.setStyleSheet(
            """
            QFrame {
                background-color: #f9fafb;
                border: 1px solid #dfe5ec;
                border-radius: 8px;
            }
            """
        )
        row = QHBoxLayout(card)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(10)

        left = QVBoxLayout()
        left.setSpacing(4)
        lbl_type = QLabel(prefix)
        lbl_type.setStyleSheet("color: #2d4c7a; font-weight: 700; font-size: 10px;")
        left.addWidget(lbl_type)
        lbl_msg = QLabel(message)
        lbl_msg.setWordWrap(True)
        lbl_msg.setStyleSheet("color: #1f2937; font-size: 12px;")
        left.addWidget(lbl_msg)
        row.addLayout(left, 1)

        # Fecha de vencimiento destacada y muy visible
        due = QLabel(f"{badge_title}\n{badge_value}")
        due.setAlignment(Qt.AlignmentFlag.AlignCenter)
        due.setMinimumWidth(120)
        due.setStyleSheet(
            """
            background-color: #fff4d6;
            color: #7a2f2f;
            border: 2px solid #d8a84c;
            border-radius: 8px;
            font-weight: 800;
            font-size: 17px;
            padding: 6px 10px;
            """
        )
        row.addWidget(due)
        return card

    def _open_from_item(self, item: QListWidgetItem):
        notification = item.data(Qt.ItemDataRole.UserRole) or {}
        if not isinstance(notification, dict):
            return
        self.selected_notification = notification
        self.accept()
