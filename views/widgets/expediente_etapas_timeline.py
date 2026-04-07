"""Franja horizontal lineal de etapas de carpeta; flecha anterior -> actual."""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, QSize, QPointF, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QPainterPath
from PySide6.QtWidgets import QWidget

# Etiquetas cortas para caber en la franja
_SHORT_LABELS: dict[str, str] = {
    "para_citar_o_videollamada": "Citar / video",
    "para_analizar": "Analizar",
    "en_espera_condicion": "En espera",
    "para_citar": "Para citar",
    "pendiente_turno": "Pend. turno",
    "turno": "Turno",
    "enviada_iniciar": "Enviada iniciar",
    "iniciada_virtual": "Inic. virtual",
    "iniciada_presencial": "Inic. presenc.",
    "req_analizar": "Req. analizar",
    "req_migraciones": "Req. migrac.",
    "req_citar": "Req. citar",
    "citado_anses": "Citado ANSES",
    "favorable": "Favorable",
    "desfavorable": "Desfavorable",
    "enviar_notificarse": "A notificar",
}


def _etapa_map(etapas: list[dict]) -> dict[str, dict]:
    return {e.get("codigo", ""): e for e in etapas if e.get("codigo")}


def _draw_arrow_along_path(painter: QPainter, path: QPainterPath, color: QColor, width: float = 2):
    painter.strokePath(path, QPen(color, width))
    if path.elementCount() < 2:
        return
    end = path.pointAtPercent(1.0)
    prev = path.pointAtPercent(0.92)
    dx = end.x() - prev.x()
    dy = end.y() - prev.y()
    ln = math.hypot(dx, dy) or 1.0
    dx /= ln
    dy /= ln
    size = 7.0
    left = QPointF(end.x() - dx * size + dy * 3, end.y() - dy * size - dx * 3)
    right = QPointF(end.x() - dx * size - dy * 3, end.y() - dy * size + dx * 3)
    painter.setBrush(QBrush(color))
    painter.setPen(Qt.PenStyle.NoPen)
    poly = QPainterPath()
    poly.moveTo(end)
    poly.lineTo(left)
    poly.lineTo(right)
    poly.closeSubpath()
    painter.drawPath(poly)


class ExpedienteEtapasTimeline(QWidget):
    """Una sola fila: orden de ETAPAS, riel entre nodos, flecha verde si hay transicion."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._etapas: list[dict] = []
        self._actual = ""
        self._anterior = ""
        self.setMinimumHeight(130)
        self.setMinimumWidth(400)

    def sizeHint(self) -> QSize:
        n = max(len(self._etapas), 1)
        return QSize(max(640, n * 72), 140)

    def minimumSizeHint(self) -> QSize:
        n = max(len(self._etapas), 1)
        return QSize(max(520, n * 68), 128)

    def set_data(self, etapas: list[dict], actual: str, anterior: str = ""):
        self._etapas = list(etapas or [])
        self._actual = actual or ""
        self._anterior = anterior or ""
        self.updateGeometry()
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = float(self.width()), float(self.height())
        painter.fillRect(self.rect(), QColor("#f7f9fc"))

        if not self._etapas:
            painter.setPen(QColor("#6b6b6b"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin etapas configuradas")
            return

        em = _etapa_map(self._etapas)
        codes = [e.get("codigo", "") for e in self._etapas if e.get("codigo")]
        n = len(codes)
        if n == 0:
            return

        margin_x = 24.0
        usable_w = max(40.0, w - 2 * margin_x)
        step = usable_w / max(1, n - 1) if n > 1 else 0.0
        cy = h * 0.34
        radius = 13.0
        centers: list[tuple[str, QPointF]] = []
        for i, code in enumerate(codes):
            if n == 1:
                cx = w / 2
            else:
                cx = margin_x + step * i
            centers.append((code, QPointF(cx, cy)))

        code_to_point = {c: p for c, p in centers}
        rail_pen = QPen(QColor("#cbd5e1"), 2)
        painter.setPen(rail_pen)
        for i in range(len(centers) - 1):
            p0 = centers[i][1]
            p1 = centers[i + 1][1]
            painter.drawLine(
                QPointF(p0.x() + radius, p0.y()),
                QPointF(p1.x() - radius, p1.y()),
            )

        # Flecha verde entre anterior y actual
        pa = code_to_point.get(self._anterior)
        pb = code_to_point.get(self._actual)
        if (
            pa is not None and pb is not None
            and self._anterior
            and self._actual
            and self._anterior != self._actual
        ):
            path = QPainterPath()
            path.moveTo(pa)
            lift = min(36.0, h * 0.22)
            mid_x = (pa.x() + pb.x()) / 2
            c1 = QPointF(mid_x, pa.y() - lift)
            c2 = QPointF(mid_x, pb.y() - lift)
            path.cubicTo(c1, c2, pb)
            _draw_arrow_along_path(painter, path, QColor("#2d8f4e"), 2.5)

        label_h = min(52.0, h - cy - radius - 10)
        for code, p in centers:
            et = em.get(code, {})
            titulo = _SHORT_LABELS.get(code) or (et.get("titulo") or code)[:18]
            color = QColor(et.get("color", "#4a90d9"))
            is_current = code == self._actual
            is_previous = code == self._anterior
            fill = QColor(color)
            if not is_current and not is_previous:
                fill.setAlpha(120)
            rect = QRectF(p.x() - radius, p.y() - radius, radius * 2, radius * 2)
            painter.setBrush(QBrush(fill))
            painter.setPen(QPen(QColor("#1f2d3d") if is_current else QColor("#94a3b8"), 2 if is_current else 1))
            painter.drawEllipse(rect)
            if is_current:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor("#0f6be5"), 2))
                painter.drawEllipse(rect.adjusted(-3, -3, 3, 3))
            painter.setPen(QColor("#1e293b"))
            painter.setFont(QFont("Lato", 7, QFont.Weight.Bold))
            painter.drawText(
                QRectF(p.x() - 46, p.y() + radius + 4, 92, label_h),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                titulo,
            )

        painter.setPen(QColor("#94a3b8"))
        painter.setFont(QFont("Lato", 6))
        painter.drawText(
            QRectF(6, h - 16, w - 12, 14),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "Flecha verde: ultimo cambio de etapa en el historial.",
        )
