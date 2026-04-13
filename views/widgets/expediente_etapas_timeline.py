"""Timeline horizontal de etapas con fases, requerimientos y transiciones."""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, QSize, QPointF, QRectF, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QPainterPath, QLinearGradient
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

_REQ_CODES = {"req_analizar", "req_migraciones", "req_citar"}
_NEEDS_EDIT_CODES = set(_REQ_CODES)
_PHASES: list[dict] = [
    {
        "label": "Pre-tramite",
        "bg": "#fff7e6",
        "codes": [
            "para_citar_o_videollamada",
            "para_analizar",
            "en_espera_condicion",
            "para_citar",
        ],
    },
    {"label": "Turno", "bg": "#edfdf2", "codes": ["pendiente_turno", "turno"]},
    {"label": "Envio", "bg": "#ecfeff", "codes": ["enviada_iniciar"]},
    {
        "label": "Iniciada",
        "sub_label": "Virtual / Presencial",
        "bg": "#eff6ff",
        "codes": ["iniciada_virtual", "iniciada_presencial", "citado_anses"],
    },
    {
        "label": "Cierre",
        "bg": "#f8fafc",
        "codes": ["favorable", "desfavorable", "enviar_notificarse"],
    },
]


def _etapa_map(etapas: list[dict]) -> dict[str, dict]:
    return {e.get("codigo", ""): e for e in etapas if e.get("codigo")}


def _build_resumen(codes: list[str], actual: str, anterior: str, em: dict[str, dict]) -> tuple[str, str]:
    if not codes:
        return ("Estado actual: Sin etapa", "Historial: sin datos")

    def _label(code: str) -> str:
        return _SHORT_LABELS.get(code) or em.get(code, {}).get("titulo") or code

    idx_actual = codes.index(actual) if actual in codes else -1
    recorrido = codes[: idx_actual + 1] if idx_actual >= 0 else []
    if idx_actual >= 0 and not recorrido:
        recorrido = [actual]
    if not recorrido and actual:
        recorrido = [actual]
    actuales = _label(actual) if actual else "Sin etapa"
    ant_txt = _label(anterior) if anterior else "Sin anterior"
    estado_line = f"Estado actual: {actuales} | Etapa previa: {ant_txt}"

    if not recorrido:
        return (estado_line, "Historial: sin recorrido registrado")

    # Mostrar las ultimas etapas para que se entienda rapidamente por donde paso.
    max_hist = 5
    cola = recorrido[-max_hist:]
    hist = " -> ".join(_label(c) for c in cola)
    if len(recorrido) > max_hist:
        hist = f"... -> {hist}"
    return (estado_line, f"Historial reciente: {hist}")


def _format_fecha_corta(iso_date: str) -> str:
    txt = (iso_date or "")[:10]
    if len(txt) == 10 and txt[4] == "-" and txt[7] == "-":
        return f"{txt[8:10]}/{txt[5:7]}"
    return txt or "-"


def _build_plazos_resumen(plazos_por_etapa: dict[str, dict], em: dict[str, dict]) -> str:
    if not plazos_por_etapa:
        return "Plazos: sin pendientes"

    items: list[tuple[str, str]] = []
    for code, rec in plazos_por_etapa.items():
        fecha = _format_fecha_corta((rec or {}).get("fecha_disparo", ""))
        label = _SHORT_LABELS.get(code) or em.get(code, {}).get("titulo") or code
        crit = "!" if int((rec or {}).get("es_critico", 0) or 0) else ""
        items.append(((rec or {}).get("fecha_disparo", "")[:10], f"{label} {fecha}{crit}"))
    items.sort(key=lambda x: x[0] or "9999-99-99")
    top = [x[1] for x in items[:3]]
    extra = f" +{len(items) - 3}" if len(items) > 3 else ""
    return "Plazos: " + " | ".join(top) + extra


def _with_alpha(color: QColor, alpha: int) -> QColor:
    c = QColor(color)
    c.setAlpha(alpha)
    return c


def _draw_arrow_along_path(
    painter: QPainter,
    path: QPainterPath,
    color: QColor,
    width: float = 2,
    gradient: QLinearGradient | None = None,
):
    pen = QPen(color, width)
    if gradient is not None:
        pen.setBrush(QBrush(gradient))
    painter.strokePath(path, pen)
    if path.elementCount() < 2:
        return
    end = path.pointAtPercent(1.0)
    prev = path.pointAtPercent(0.92)
    dx = end.x() - prev.x()
    dy = end.y() - prev.y()
    ln = math.hypot(dx, dy) or 1.0
    dx /= ln
    dy /= ln
    size = 8.0
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
    """Timeline por fases: flujo principal + fila No Iniciada (requerimientos)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._etapas: list[dict] = []
        self._actual = ""
        self._anterior = ""
        self._plazos_por_etapa: dict[str, dict] = {}
        self._blink_on = True
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(600)
        self._blink_timer.timeout.connect(self._toggle_blink)
        self.setMinimumHeight(200)
        self.setMinimumWidth(420)

    def sizeHint(self) -> QSize:
        n = max(len(self._etapas), 1)
        return QSize(max(560, n * 52), 210)

    def minimumSizeHint(self) -> QSize:
        n = max(len(self._etapas), 1)
        return QSize(max(460, n * 48), 200)

    def _toggle_blink(self):
        self._blink_on = not self._blink_on
        self.update()

    def _sync_blink_state(self):
        if self._actual in _NEEDS_EDIT_CODES:
            if not self._blink_timer.isActive():
                self._blink_on = True
                self._blink_timer.start()
        elif self._blink_timer.isActive():
            self._blink_timer.stop()
            self._blink_on = True

    def set_data(
        self,
        etapas: list[dict],
        actual: str,
        anterior: str = "",
        plazos_por_etapa: dict[str, dict] | None = None,
    ):
        self._etapas = list(etapas or [])
        self._actual = actual or ""
        self._anterior = anterior or ""
        self._plazos_por_etapa = dict(plazos_por_etapa or {})
        self._sync_blink_state()
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

        current_requires_edit = self._actual in _NEEDS_EDIT_CODES
        compact_mode = w < 900.0
        ultra_compact_mode = w < 760.0
        top_pad = 6.0
        banner_h = (20.0 if compact_mode else 24.0) if current_requires_edit else 0.0
        phase_top = top_pad + (banner_h + 4.0 if current_requires_edit else 0.0)
        phase_h = 52.0 if compact_mode else 60.0
        main_cy = phase_top + (24.0 if compact_mode else 28.0)
        req_cy = phase_top + phase_h + (18.0 if compact_mode else 22.0)
        pill_w = 56.0 if ultra_compact_mode else (60.0 if compact_mode else 66.0)
        pill_h = 19.0 if ultra_compact_mode else (20.0 if compact_mode else 21.0)
        radius = 5.0 if compact_mode else 6.0

        if current_requires_edit:
            brect = QRectF(10.0, top_pad, w - 20.0, banner_h)
            painter.setPen(QPen(QColor("#f59e0b"), 1.0))
            painter.setBrush(QBrush(QColor("#fffbeb")))
            painter.drawRoundedRect(brect, 9.0, 9.0)
            actual_label = _SHORT_LABELS.get(self._actual) or self._actual.replace("_", " ")
            painter.setPen(QColor("#92400e"))
            painter.setFont(QFont("Lato", 7 if compact_mode else 8, QFont.Weight.Bold))
            banner_txt = (
                f"ATENCION: Carpeta NO INICIADA - requiere edicion ({actual_label})."
                if not compact_mode
                else f"ATENCION: NO INICIADA - req. edicion ({actual_label})."
            )
            painter.drawText(
                brect.adjusted(9, 0, -9, 0),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                banner_txt,
            )

        margin_x = 10.0 if compact_mode else 14.0
        usable_w = max(40.0, w - 2 * margin_x)
        main_codes = [c for c in codes if c not in _REQ_CODES]
        req_codes = [c for c in codes if c in _REQ_CODES]
        main_n = len(main_codes)
        step = usable_w / max(1, main_n - 1) if main_n > 1 else 0.0
        centers: list[tuple[str, QPointF]] = []
        for i, code in enumerate(main_codes):
            if main_n == 1:
                cx = w / 2
            else:
                cx = margin_x + step * i
            centers.append((code, QPointF(cx, main_cy)))

        phase_code_to_x = {c: p.x() for c, p in centers}
        for phase in _PHASES:
            xs = [phase_code_to_x[c] for c in phase["codes"] if c in phase_code_to_x]
            if not xs:
                continue
            x0 = min(xs) - pill_w / 2 - 5.0
            x1 = max(xs) + pill_w / 2 + 5.0
            phase_rect = QRectF(x0, phase_top + 5.0, x1 - x0, phase_h - 10.0)
            painter.setPen(QPen(QColor("#d7e0ea"), 1))
            painter.setBrush(QBrush(QColor(phase["bg"])))
            painter.drawRoundedRect(phase_rect, 9.0, 9.0)
            if not ultra_compact_mode:
                painter.setPen(QColor("#64748b"))
                painter.setFont(QFont("Lato", 6 if compact_mode else 7, QFont.Weight.DemiBold))
                sub = phase.get("sub_label") or ""
                label_txt = phase["label"]
                if sub:
                    label_txt = f"{label_txt} ({sub})"
                painter.drawText(
                    phase_rect.adjusted(6, 2, -6, -2),
                    Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                    label_txt,
                )

        if req_codes:
            candidate_x = [
                phase_code_to_x[c]
                for c in ("iniciada_virtual", "iniciada_presencial", "citado_anses")
                if c in phase_code_to_x
            ]
            anchor_x = sum(candidate_x) / len(candidate_x) if candidate_x else (w * 0.64)
            req_spacing = 58.0 if ultra_compact_mode else (64.0 if compact_mode else 70.0)
            start_x = anchor_x - (req_spacing * (len(req_codes) - 1) / 2.0)
            for i, code in enumerate(req_codes):
                centers.append((code, QPointF(start_x + i * req_spacing, req_cy)))

            req_xs = [p.x() for c, p in centers if c in req_codes]
            req_rect = QRectF(
                min(req_xs) - pill_w / 2 - 10.0,
                req_cy - 18.0,
                (max(req_xs) - min(req_xs)) + pill_w + 20.0,
                34.0,
            )
            painter.setPen(QPen(QColor("#ddd6fe"), 1))
            painter.setBrush(QBrush(QColor("#f5f3ff")))
            painter.drawRoundedRect(req_rect, 8.0, 8.0)
            if not ultra_compact_mode:
                painter.setPen(QColor("#6d28d9"))
                painter.setFont(QFont("Lato", 6, QFont.Weight.DemiBold))
                painter.drawText(
                    req_rect.adjusted(6, -10, -6, 0),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                    "No Iniciada",
                )

        code_to_point = {c: p for c, p in centers}
        rail_pen = QPen(QColor("#cbd5e1"), 1.4)
        painter.setPen(rail_pen)
        for i in range(len(main_codes) - 1):
            p0 = code_to_point[main_codes[i]]
            p1 = code_to_point[main_codes[i + 1]]
            painter.drawLine(
                QPointF(p0.x() + pill_w / 2 - 3.0, p0.y()),
                QPointF(p1.x() - pill_w / 2 + 3.0, p1.y()),
            )

        if req_codes:
            for i in range(len(req_codes) - 1):
                p0 = code_to_point[req_codes[i]]
                p1 = code_to_point[req_codes[i + 1]]
                painter.drawLine(
                    QPointF(p0.x() + pill_w / 2 - 3.0, p0.y()),
                    QPointF(p1.x() - pill_w / 2 + 3.0, p1.y()),
                )
            show_req_return = (
                self._actual in _REQ_CODES
                or self._anterior in _REQ_CODES
                or (self._actual in {"para_analizar", "para_citar"} and self._anterior in _REQ_CODES)
            )
            if show_req_return:
                target_back = (
                    code_to_point.get("para_analizar")
                    or code_to_point.get("para_citar")
                    or code_to_point.get("para_citar_o_videollamada")
                )
                source_req = code_to_point.get(req_codes[-1])
                if target_back and source_req:
                    ret_path = QPainterPath()
                    ret_path.moveTo(source_req)
                    ret_path.cubicTo(
                        QPointF(source_req.x() + 36.0, source_req.y() - 12.0),
                        QPointF(target_back.x() + 22.0, target_back.y() + 14.0),
                        target_back,
                    )
                    painter.setPen(QPen(QColor("#7c3aed"), 1.5, Qt.PenStyle.DashLine))
                    painter.drawPath(ret_path)

        def _draw_pill_node(code: str, p: QPointF):
            etapa = em.get(code, {})
            label = _SHORT_LABELS.get(code) or (etapa.get("titulo") or code)[:24]
            if ultra_compact_mode and len(label) > 10:
                label = label[:9] + "."
            color = QColor(etapa.get("color", "#4a90d9"))
            is_current = code == self._actual
            is_previous = code == self._anterior
            r = QRectF(p.x() - pill_w / 2, p.y() - pill_h / 2, pill_w, pill_h)
            if is_current:
                fill = QColor(color)
            else:
                fill = _with_alpha(color, 72 if is_previous else 48)
            painter.setBrush(QBrush(fill))
            border_color = QColor("#1d4ed8") if is_current else QColor("#94a3b8")
            border_w = 1.8 if is_current else 0.9
            painter.setPen(QPen(border_color, border_w))
            painter.drawRoundedRect(r, radius, radius)
            if is_current and code in _NEEDS_EDIT_CODES and self._blink_on:
                pulse = r.adjusted(-3.0, -2.0, 3.0, 2.0)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor("#f59e0b"), 1.7))
                painter.drawRoundedRect(pulse, radius + 2.0, radius + 2.0)
            painter.setPen(QColor("#0f172a"))
            painter.setFont(QFont("Lato", 5 if ultra_compact_mode else 6, QFont.Weight.Bold))
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, label)
            if is_current and code in _NEEDS_EDIT_CODES:
                tag = QRectF(r.right() - 12.0, r.top() - 6.0, 12.0, 10.0)
                painter.setPen(QPen(QColor("#f59e0b"), 0.9))
                painter.setBrush(QBrush(QColor("#fff7ed")))
                painter.drawRoundedRect(tag, 4.0, 4.0)
                painter.setPen(QColor("#9a3412"))
                painter.setFont(QFont("Lato", 5, QFont.Weight.Bold))
                painter.drawText(tag, Qt.AlignmentFlag.AlignCenter, "ed")

        for code in main_codes:
            _draw_pill_node(code, code_to_point[code])
        for code in req_codes:
            _draw_pill_node(code, code_to_point[code])

        # Flecha principal: ultimo movimiento de etapa
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
            same_row = abs(pa.y() - pb.y()) < 10.0
            lift = min(26.0, h * 0.16) if same_row else -14.0
            mid_x = (pa.x() + pb.x()) / 2
            c1 = QPointF(mid_x, pa.y() - lift)
            c2 = QPointF(mid_x, pb.y() - lift)
            path.cubicTo(c1, c2, pb)
            origin_c = QColor(em.get(self._anterior, {}).get("color", "#0ea5e9"))
            target_c = QColor(em.get(self._actual, {}).get("color", "#2563eb"))
            grad = QLinearGradient(pa, pb)
            grad.setColorAt(0.0, _with_alpha(origin_c, 235))
            grad.setColorAt(1.0, _with_alpha(target_c, 245))
            _draw_arrow_along_path(painter, path, target_c, 2.2, gradient=grad)
            tip = path.pointAtPercent(0.53)
            if not ultra_compact_mode:
                tip_rect = QRectF(tip.x() - 34.0, tip.y() - 11.0, 68.0, 11.0)
                painter.setPen(QPen(QColor("#bfdbfe"), 1))
                painter.setBrush(QBrush(QColor("#eff6ff")))
                painter.drawRoundedRect(tip_rect, 5.0, 5.0)
                painter.setPen(QColor("#1d4ed8"))
                painter.setFont(QFont("Lato", 5, QFont.Weight.DemiBold))
                painter.drawText(tip_rect, Qt.AlignmentFlag.AlignCenter, "mov.")

        estado_line, historial_line = _build_resumen(codes, self._actual, self._anterior, em)
        plazos_line = _build_plazos_resumen(self._plazos_por_etapa, em)
        resumen_rect = QRectF(8, h - 60, w - 16, 48)
        painter.setPen(QPen(QColor("#dbe4ef"), 1))
        painter.setBrush(QBrush(QColor("#f8fafc")))
        painter.drawRoundedRect(resumen_rect, 6.0, 6.0)
        painter.setPen(QColor("#334155"))
        painter.setFont(QFont("Lato", 5 if compact_mode else 6, QFont.Weight.Bold))
        painter.drawText(
            resumen_rect.adjusted(8, 3, -8, -30),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            estado_line,
        )
        painter.setPen(QColor("#475569"))
        painter.setFont(QFont("Lato", 5 if compact_mode else 6, QFont.Weight.DemiBold))
        painter.drawText(
            resumen_rect.adjusted(8, 18, -8, -16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            historial_line,
        )
        painter.setPen(QColor("#64748b"))
        painter.setFont(QFont("Lato", 5 if compact_mode else 6, QFont.Weight.DemiBold))
        painter.drawText(
            resumen_rect.adjusted(8, 33, -8, -2),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            plazos_line,
        )

        if not ultra_compact_mode:
            painter.setPen(QColor("#94a3b8"))
            painter.setFont(QFont("Lato", 5))
            painter.drawText(
                QRectF(6, h - 12, w - 12, 10),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                "Linea curva: ultimo cambio de etapa en el historial.",
            )
