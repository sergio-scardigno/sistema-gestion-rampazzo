"""Dialogo de detalle de cambios campo a campo para una entrada del audit log."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

from controllers.audit_controller import AuditController, ACCION_LABELS, COLECCION_LABELS


class AuditDetailDialog(QDialog):
    """Muestra el detalle de una entrada del audit log con diff campo a campo."""

    def __init__(self, audit_id: str, parent=None):
        super().__init__(parent)
        self._audit_id = audit_id
        self.setWindowTitle("Detalle del Cambio")
        self.setMinimumSize(700, 500)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Cargar datos del registro
        from core import db_local
        row = db_local.find_by_id("audit_log", audit_id)
        if not row:
            layout.addWidget(QLabel("Registro no encontrado."))
            return

        # ── Cabecera ──
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border-radius: 8px;
                padding: 16px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setSpacing(6)

        accion = row.get("accion", "")
        accion_label = ACCION_LABELS.get(accion, accion)
        coleccion_label = COLECCION_LABELS.get(row.get("coleccion", ""), row.get("coleccion", ""))

        # Color segun accion
        color_map = {"create": "#2d8f4e", "update": "#c9a84c", "delete": "#cc3333"}
        color = color_map.get(accion, "#6b6b6b")

        titulo = QLabel(f"{accion_label} en {coleccion_label}")
        titulo.setFont(QFont("Lato", 16, QFont.Weight.Bold))
        titulo.setStyleSheet(f"color: {color};")
        header_layout.addWidget(titulo)

        # Info line
        timestamp = row.get("timestamp", "")
        if timestamp and len(timestamp) >= 19:
            fecha_fmt = timestamp[:10] + " " + timestamp[11:19]
        else:
            fecha_fmt = timestamp

        info_text = f"Usuario: {row.get('usuario', 'N/A')}  |  Fecha: {fecha_fmt}  |  Documento: {row.get('documento_id', 'N/A')[:12]}..."
        info_lbl = QLabel(info_text)
        info_lbl.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        header_layout.addWidget(info_lbl)

        layout.addWidget(header_frame)

        # ── Tabla de cambios ──
        cambios = AuditController.get_campos_modificados(audit_id)

        if not cambios:
            no_data = QLabel("No hay datos de cambios disponibles para este registro.")
            no_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_data.setStyleSheet("color: #8a8a8a; font-size: 13px; padding: 20px;")
            layout.addWidget(no_data)
        else:
            # Titulo de seccion
            if accion == "create":
                seccion_lbl = QLabel("Campos del nuevo registro")
            elif accion == "delete":
                seccion_lbl = QLabel("Campos del registro eliminado")
            else:
                seccion_lbl = QLabel(f"Campos modificados ({len(cambios)})")
            seccion_lbl.setFont(QFont("Lato", 13, QFont.Weight.Bold))
            seccion_lbl.setStyleSheet("color: #c9a84c;")
            layout.addWidget(seccion_lbl)

            table = QTableWidget()
            table.setColumnCount(3)
            table.setHorizontalHeaderLabels(["Campo", "Valor Anterior", "Valor Nuevo"])
            table.horizontalHeader().setStretchLastSection(True)
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            table.verticalHeader().setVisible(False)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.setAlternatingRowColors(True)
            table.setRowCount(len(cambios))

            for i, cambio in enumerate(cambios):
                # Campo
                campo_item = QTableWidgetItem(cambio["campo"])
                campo_item.setFont(QFont("Lato", 10, QFont.Weight.Bold))
                table.setItem(i, 0, campo_item)

                # Valor anterior
                ant_item = QTableWidgetItem(cambio["anterior"])
                if cambio["tipo"] == "eliminado" or (cambio["tipo"] == "modificado" and cambio["anterior"]):
                    ant_item.setBackground(QColor("#3d1f1f"))
                    ant_item.setForeground(QColor("#ff8a8a"))
                table.setItem(i, 1, ant_item)

                # Valor nuevo
                new_item = QTableWidgetItem(cambio["nuevo"])
                if cambio["tipo"] == "nuevo" or (cambio["tipo"] == "modificado" and cambio["nuevo"]):
                    new_item.setBackground(QColor("#1f3d1f"))
                    new_item.setForeground(QColor("#8aff8a"))
                table.setItem(i, 2, new_item)

            layout.addWidget(table)

        # ── Boton cerrar ──
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_close = QPushButton("Cerrar")
        btn_close.setProperty("variant", "secondary")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)
