"""Vista de Reportes con graficos y exportacion."""
import io
import logging
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QScrollArea,
    QFrame, QFileDialog, QMessageBox, QGridLayout, QTabWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap

logger = logging.getLogger(__name__)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from controllers.reporte_controller import ReporteController
from core.auth import Session
from core.permissions import tiene_permiso


class ReportesView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Guard de permisos: si no tiene reportes.*, mostrar mensaje y salir
        session = Session.get()
        self._has_access = tiene_permiso(session.rol, "reportes.*")
        self._has_eco = tiene_permiso(session.rol, "movimientos.read")

        if not self._has_access:
            lbl = QLabel("No tiene permisos para ver esta seccion.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFont(QFont("Lato", 16))
            lbl.setStyleSheet("color: #8a8a8a; padding: 40px;")
            outer.addWidget(lbl)
            return

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(16, 12, 16, 16)
        self._layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("Reportes y Control")
        title.setFont(QFont("Lato", 17, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        btn_export_pdf = QPushButton("Exportar PDF")
        btn_export_pdf.clicked.connect(self._export_pdf)
        header.addWidget(btn_export_pdf)

        btn_export_excel = QPushButton("Exportar Excel")
        btn_export_excel.setProperty("variant", "secondary")
        btn_export_excel.clicked.connect(self._export_excel)
        header.addWidget(btn_export_excel)

        btn_export_clientes_excel = QPushButton("Clientes Excel")
        btn_export_clientes_excel.setProperty("variant", "secondary")
        btn_export_clientes_excel.clicked.connect(self._export_clientes_excel)
        header.addWidget(btn_export_clientes_excel)

        btn_export_clientes_csv = QPushButton("Clientes CSV")
        btn_export_clientes_csv.setProperty("variant", "secondary")
        btn_export_clientes_csv.clicked.connect(self._export_clientes_csv)
        header.addWidget(btn_export_clientes_csv)

        btn_export_carpetas_excel = QPushButton("Carpetas Excel")
        btn_export_carpetas_excel.setProperty("variant", "secondary")
        btn_export_carpetas_excel.clicked.connect(self._export_carpetas_excel)
        header.addWidget(btn_export_carpetas_excel)

        btn_export_carpetas_csv = QPushButton("Carpetas CSV")
        btn_export_carpetas_csv.setProperty("variant", "secondary")
        btn_export_carpetas_csv.clicked.connect(self._export_carpetas_csv)
        header.addWidget(btn_export_carpetas_csv)

        self._layout.addLayout(header)

        # Tabs de reportes
        tabs = QTabWidget()
        self._tabs = tabs
        self._rendered_tabs: set[int] = set()

        # ── Tab 1: Graficos principales ──
        tab_graficos = QWidget()
        tab_graf_layout = QVBoxLayout(tab_graficos)

        self._chart_grid = QGridLayout()
        self._chart_grid.setSpacing(16)
        tab_graf_layout.addLayout(self._chart_grid)

        self._chart_labels = {}
        chart_positions = [
            ("por_tipo", "Carpetas por Tipo", 0, 0),
            ("por_responsable", "Carga por Responsable", 0, 1),
            ("por_procedencia", "Clientes por Procedencia", 1, 0),
        ]
        if self._has_eco:
            chart_positions.append(("economico", "Resumen Economico", 1, 1))
        for key, title_text, row, col in chart_positions:
            frame = self._create_chart_frame(key, title_text)
            self._chart_grid.addWidget(frame, row, col)

        tab_graf_layout.addStretch()
        tabs.addTab(tab_graficos, "Graficos Principales")

        # ── Tab 2: Tiempos y Retrasos ──
        tab_tiempos = QWidget()
        tab_tiempos_layout = QVBoxLayout(tab_tiempos)

        self._chart_grid2 = QGridLayout()
        self._chart_grid2.setSpacing(16)
        tab_tiempos_layout.addLayout(self._chart_grid2)

        for key, title_text, row, col in [
            ("tiempo_resolucion", "Tiempo Promedio de Resolucion", 0, 0),
            ("retrasos_etapa", "Retrasos por Etapa", 0, 1),
            ("turnos_vs_casos", "Turnos vs Casos", 1, 0),
            ("clientes_sin_carpeta", "Clientes sin Carpeta", 1, 1),
            ("tiempo_estado_responsable", "Tiempo por Estado por Responsable", 2, 0),
            ("aperturas_cierres", "Aperturas y Cierres por Responsable", 2, 1),
        ]:
            frame = self._create_chart_frame(key, title_text)
            self._chart_grid2.addWidget(frame, row, col)

        tab_tiempos_layout.addStretch()
        tabs.addTab(tab_tiempos, "Tiempos y Retrasos")

        # ── Tab 3: Indicadores Humanos ──
        tab_humanos = QWidget()
        tab_humanos_layout = QVBoxLayout(tab_humanos)

        self._chart_grid3 = QGridLayout()
        self._chart_grid3.setSpacing(16)
        tab_humanos_layout.addLayout(self._chart_grid3)

        for key, title_text, row, col in [
            ("carga_responsable", "Carga de Trabajo por Responsable", 0, 0),
            ("vencidas_responsable", "Tareas Vencidas por Responsable", 0, 1),
        ]:
            frame = self._create_chart_frame(key, title_text)
            self._chart_grid3.addWidget(frame, row, col)

        tab_humanos_layout.addStretch()
        tabs.addTab(tab_humanos, "Indicadores Humanos")

        self._layout.addWidget(tabs)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self._tabs.currentChanged.connect(self._on_tab_changed)

    def _create_chart_frame(self, key: str, title_text: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 8px;")
        fl = QVBoxLayout(frame)
        lbl_title = QLabel(title_text)
        lbl_title.setFont(QFont("Lato", 12, QFont.Weight.Bold))
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fl.addWidget(lbl_title)
        lbl_chart = QLabel()
        lbl_chart.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_chart.setMinimumSize(400, 300)
        fl.addWidget(lbl_chart)
        self._chart_labels[key] = lbl_chart
        return frame

    def refresh(self):
        if not self._has_access:
            return
        # Carga diferida: renderizar solo la pestaña activa.
        self._rendered_tabs.clear()
        self._render_tab(self._tabs.currentIndex())

    def _on_tab_changed(self, index: int):
        self._render_tab(index)

    def _render_tab(self, index: int):
        if index in self._rendered_tabs:
            return
        self._rendered_tabs.add(index)

        if index == 0:  # Graficos principales
            self._render_chart_por_tipo()
            self._render_chart_por_responsable()
            self._render_chart_por_procedencia()
            if self._has_eco:
                self._render_chart_economico()
        elif index == 1:  # Tiempos y retrasos
            self._render_chart_tiempo_resolucion()
            self._render_chart_retrasos_etapa()
            self._render_chart_turnos_vs_casos()
            self._render_chart_clientes_sin_carpeta()
            self._render_chart_tiempo_estado_responsable()
            self._render_chart_aperturas_cierres()
        elif index == 2:  # Indicadores humanos
            self._render_chart_indicadores_humanos()

    # Paleta de colores para graficos (dorado/gris/negro)
    CHART_COLORS = [
        "#c9a84c", "#4a4a4a", "#b8963c", "#8a8a8a",
        "#a07c30", "#6b6b6b", "#d4b85c", "#333333",
    ]

    def _fig_to_pixmap(self, fig) -> QPixmap:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight",
                    facecolor="#ffffff", edgecolor="none")
        plt.close(fig)
        buf.seek(0)
        pixmap = QPixmap()
        pixmap.loadFromData(buf.read())
        return pixmap

    def _render_chart_por_tipo(self):
        data = ReporteController.expedientes_por_tipo()
        if not data:
            return
        fig, ax = plt.subplots(figsize=(5, 3.5))
        tipos = [d["tipo"][:20] for d in data[:8]]
        cantidades = [d["cantidad"] for d in data[:8]]
        colors = self.CHART_COLORS[:len(tipos)]
        ax.barh(tipos, cantidades, color=colors)
        ax.set_xlabel("Cantidad", color="#4a4a4a")
        ax.set_title("Carpetas por Tipo de Tramite", color="#1a1a1a", fontweight="bold")
        ax.tick_params(colors="#4a4a4a")
        ax.invert_yaxis()
        fig.tight_layout()
        self._chart_labels["por_tipo"].setPixmap(
            self._fig_to_pixmap(fig).scaled(400, 300, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
        )

    def _render_chart_por_responsable(self):
        data = ReporteController.expedientes_por_responsable()
        if not data:
            return
        fig, ax = plt.subplots(figsize=(5, 3.5))
        responsables = [d["responsable"][:15] for d in data[:8]]
        cantidades = [d["cantidad"] for d in data[:8]]
        colors = self.CHART_COLORS[:len(responsables)]
        ax.bar(responsables, cantidades, color=colors)
        ax.set_ylabel("Carpetas Activas", color="#4a4a4a")
        ax.set_title("Carga por Responsable", color="#1a1a1a", fontweight="bold")
        ax.tick_params(colors="#4a4a4a")
        plt.xticks(rotation=45, ha="right")
        fig.tight_layout()
        self._chart_labels["por_responsable"].setPixmap(
            self._fig_to_pixmap(fig).scaled(400, 300, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
        )

    def _render_chart_por_procedencia(self):
        data = ReporteController.clientes_por_procedencia()
        if not data:
            self._chart_labels["por_procedencia"].setText("Sin datos de procedencia")
            return
        fig, ax = plt.subplots(figsize=(5, 3.5))
        procedencias = [d["procedencia"] for d in data[:8]]
        cantidades = [d["cantidad"] for d in data[:8]]
        colors = self.CHART_COLORS[:len(procedencias)]
        wedges, texts, autotexts = ax.pie(cantidades, labels=procedencias, autopct="%1.0f%%",
                                           colors=colors, startangle=90,
                                           textprops={"color": "#1a1a1a"})
        for at in autotexts:
            at.set_color("#ffffff")
            at.set_fontweight("bold")
        ax.set_title("Clientes por Procedencia", color="#1a1a1a", fontweight="bold")
        fig.tight_layout()
        self._chart_labels["por_procedencia"].setPixmap(
            self._fig_to_pixmap(fig).scaled(400, 300, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
        )

    def _render_chart_economico(self):
        eco = ReporteController.kpis_economicos()
        fig, ax = plt.subplots(figsize=(5, 3.5))
        categorias = ["Cobrado", "Pendiente"]
        valores = [eco["ingresos_cobrados"], eco["pendientes_cobro"]]
        colors = ["#2d8f4e", "#c9a84c"]
        ax.bar(categorias, valores, color=colors, width=0.5)
        ax.set_ylabel("Monto ($)", color="#4a4a4a")
        ax.set_title("Resumen Economico", color="#1a1a1a", fontweight="bold")
        ax.tick_params(colors="#4a4a4a")
        for i, v in enumerate(valores):
            ax.text(i, v + max(valores) * 0.02, f"${v:,.0f}", ha="center",
                    fontweight="bold", color="#1a1a1a")
        fig.tight_layout()
        self._chart_labels["economico"].setPixmap(
            self._fig_to_pixmap(fig).scaled(400, 300, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
        )

    # ── Nuevos graficos ──

    def _render_chart_tiempo_resolucion(self):
        data = ReporteController.tiempo_promedio_por_tipo()
        if not data:
            self._chart_labels["tiempo_resolucion"].setText("Sin datos de resolucion")
            return
        fig, ax = plt.subplots(figsize=(5, 3.5))
        tipos = [d["tipo"][:18] for d in data[:8]]
        promedios = [d["promedio_dias"] for d in data[:8]]
        colors = self.CHART_COLORS[:len(tipos)]
        ax.barh(tipos, promedios, color=colors)
        ax.set_xlabel("Dias promedio", color="#4a4a4a")
        ax.set_title("Tiempo Promedio de Resolucion por Tipo", color="#1a1a1a", fontweight="bold", fontsize=10)
        ax.tick_params(colors="#4a4a4a")
        ax.invert_yaxis()
        for i, v in enumerate(promedios):
            ax.text(v + 0.5, i, f"{v:.0f}d", va="center", color="#1a1a1a", fontsize=8)
        fig.tight_layout()
        self._chart_labels["tiempo_resolucion"].setPixmap(
            self._fig_to_pixmap(fig).scaled(400, 300, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
        )

    def _render_chart_retrasos_etapa(self):
        data = ReporteController.retrasos_por_etapa()
        if not data:
            self._chart_labels["retrasos_etapa"].setText("Sin retrasos detectados")
            return
        fig, ax = plt.subplots(figsize=(5, 3.5))
        etapas = [d["etapa"][:18] for d in data[:8]]
        vencidas = [d["vencidas"] for d in data[:8]]
        retraso_prom = [d["dias_retraso_prom"] for d in data[:8]]
        x = range(len(etapas))
        bars = ax.bar(x, vencidas, color="#c9a84c", label="Vencidas")
        ax2 = ax.twinx()
        ax2.plot(x, retraso_prom, color="#d43f3f", marker="o", label="Retraso prom. (dias)")
        ax2.set_ylabel("Dias retraso", color="#d43f3f")
        ax.set_ylabel("Tareas vencidas", color="#4a4a4a")
        ax.set_xticks(x)
        ax.set_xticklabels(etapas, rotation=45, ha="right", fontsize=7)
        ax.set_title("Retrasos por Etapa", color="#1a1a1a", fontweight="bold", fontsize=10)
        ax.tick_params(colors="#4a4a4a")
        fig.tight_layout()
        self._chart_labels["retrasos_etapa"].setPixmap(
            self._fig_to_pixmap(fig).scaled(400, 300, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
        )

    def _render_chart_turnos_vs_casos(self):
        data = ReporteController.turnos_vs_casos()
        fig, ax = plt.subplots(figsize=(5, 3.5))
        labels = ["Turnos\nTotal", "Turnos\nRealizados", "Turnos\nPendientes", "Carpetas\nActivas"]
        values = [data["total_turnos"], data["turnos_realizados"],
                  data["turnos_pendientes"], data["expedientes_activos"]]
        colors = ["#c9a84c", "#2d8f4e", "#d4b85c", "#4a4a4a"]
        bars = ax.bar(labels, values, color=colors, width=0.6)
        ax.set_title("Turnos ANSES vs Casos", color="#1a1a1a", fontweight="bold", fontsize=10)
        ax.tick_params(colors="#4a4a4a")
        for bar, v in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                    str(v), ha="center", fontweight="bold", color="#1a1a1a", fontsize=9)
        fig.tight_layout()
        self._chart_labels["turnos_vs_casos"].setPixmap(
            self._fig_to_pixmap(fig).scaled(400, 300, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
        )

    def _render_chart_clientes_sin_carpeta(self):
        data = ReporteController.analisis_clientes_sin_carpeta()
        fig, ax = plt.subplots(figsize=(5, 3.5))
        if data["total_clientes"] == 0:
            ax.text(0.5, 0.5, "Sin clientes", ha="center", va="center",
                    transform=ax.transAxes, fontsize=14, color="#8a8a8a")
        else:
            sizes = [data["con_carpeta"], data["sin_carpeta"]]
            labels = [f"Con carpeta\n({data['con_carpeta']})",
                      f"Sin carpeta\n({data['sin_carpeta']})"]
            colors = ["#2d8f4e", "#d43f3f"]
            wedges, texts, autotexts = ax.pie(
                sizes, labels=labels, autopct="%1.1f%%", colors=colors,
                startangle=90, textprops={"color": "#1a1a1a", "fontsize": 8}
            )
            for at in autotexts:
                at.set_color("#ffffff")
                at.set_fontweight("bold")
        ax.set_title(f"Clientes sin Carpeta – {data['tasa_sin_carpeta']}%", color="#1a1a1a",
                     fontweight="bold", fontsize=10)
        fig.tight_layout()
        self._chart_labels["clientes_sin_carpeta"].setPixmap(
            self._fig_to_pixmap(fig).scaled(400, 300, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
        )

    def _render_chart_tiempo_estado_responsable(self):
        data = ReporteController.tiempos_por_estado_responsable()
        if not data:
            self._chart_labels["tiempo_estado_responsable"].setText("Sin datos de historial")
            return
        # Agrupar por responsable, sumar promedios por estado
        resps: dict[str, float] = {}
        for d in data:
            resp = d["responsable"][:15]
            resps[resp] = resps.get(resp, 0) + d["promedio_dias"]
        # Top 8 responsables
        sorted_resps = sorted(resps.items(), key=lambda x: x[1], reverse=True)[:8]
        if not sorted_resps:
            self._chart_labels["tiempo_estado_responsable"].setText("Sin datos")
            return
        fig, ax = plt.subplots(figsize=(5, 3.5))
        nombres = [r[0] for r in sorted_resps]
        dias = [r[1] for r in sorted_resps]
        colors = self.CHART_COLORS[:len(nombres)]
        ax.barh(nombres, dias, color=colors)
        ax.set_xlabel("Dias promedio (total estados)", color="#4a4a4a")
        ax.set_title("Tiempo por Estado por Responsable", color="#1a1a1a", fontweight="bold", fontsize=10)
        ax.tick_params(colors="#4a4a4a")
        ax.invert_yaxis()
        for i, v in enumerate(dias):
            ax.text(v + 0.3, i, f"{v:.0f}d", va="center", color="#1a1a1a", fontsize=8)
        fig.tight_layout()
        self._chart_labels["tiempo_estado_responsable"].setPixmap(
            self._fig_to_pixmap(fig).scaled(400, 300, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
        )

    def _render_chart_aperturas_cierres(self):
        data = ReporteController.aperturas_y_cierres_por_responsable()
        if not data:
            self._chart_labels["aperturas_cierres"].setText("Sin datos")
            return
        fig, ax = plt.subplots(figsize=(5, 3.5))
        responsables = [d["responsable"][:12] for d in data[:8]]
        iniciadas = [d["iniciadas"] for d in data[:8]]
        cerradas = [d["cerradas"] for d in data[:8]]
        x = range(len(responsables))
        w = 0.35
        ax.bar([i - w / 2 for i in x], iniciadas, w, label="Iniciadas", color="#c9a84c")
        ax.bar([i + w / 2 for i in x], cerradas, w, label="Cerradas", color="#2d8f4e")
        ax.set_xticks(x)
        ax.set_xticklabels(responsables, rotation=45, ha="right", fontsize=7)
        ax.set_title("Aperturas y Cierres por Responsable", color="#1a1a1a", fontweight="bold", fontsize=10)
        ax.legend(fontsize=7)
        ax.tick_params(colors="#4a4a4a")
        fig.tight_layout()
        self._chart_labels["aperturas_cierres"].setPixmap(
            self._fig_to_pixmap(fig).scaled(400, 300, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
        )

    def _render_chart_indicadores_humanos(self):
        data = ReporteController.indicadores_humanos()
        if not data:
            self._chart_labels["carga_responsable"].setText("Sin datos")
            self._chart_labels["vencidas_responsable"].setText("Sin datos")
            return

        # Carga por responsable (expedientes + tareas)
        fig, ax = plt.subplots(figsize=(5, 3.5))
        responsables = [d["responsable"][:12] for d in data[:8]]
        exp_activos = [d["exp_activos"] for d in data[:8]]
        tar_pend = [d["tareas_pendientes"] for d in data[:8]]
        x = range(len(responsables))
        w = 0.35
        ax.bar([i - w / 2 for i in x], exp_activos, w, label="Carpetas activas", color="#c9a84c")
        ax.bar([i + w / 2 for i in x], tar_pend, w, label="Tareas pend.", color="#4a4a4a")
        ax.set_xticks(x)
        ax.set_xticklabels(responsables, rotation=45, ha="right", fontsize=7)
        ax.set_title("Carga de Trabajo", color="#1a1a1a", fontweight="bold", fontsize=10)
        ax.legend(fontsize=7)
        ax.tick_params(colors="#4a4a4a")
        fig.tight_layout()
        self._chart_labels["carga_responsable"].setPixmap(
            self._fig_to_pixmap(fig).scaled(400, 300, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
        )

        # Vencidas por responsable
        fig2, ax2 = plt.subplots(figsize=(5, 3.5))
        vencidas = [d.get("tareas_vencidas", 0) for d in data[:8]]
        colors = ["#d43f3f" if v > 0 else "#2d8f4e" for v in vencidas]
        ax2.bar(responsables, vencidas, color=colors)
        ax2.set_title("Tareas Vencidas por Responsable", color="#1a1a1a", fontweight="bold", fontsize=10)
        ax2.tick_params(colors="#4a4a4a")
        plt.xticks(rotation=45, ha="right", fontsize=7)
        fig2.tight_layout()
        self._chart_labels["vencidas_responsable"].setPixmap(
            self._fig_to_pixmap(fig2).scaled(400, 300, Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation)
        )

    def _export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar Reporte PDF", f"reporte_{datetime.now():%Y%m%d}.pdf",
            "PDF (*.pdf)"
        )
        if not path:
            return
        try:
            from utils.export import export_report_pdf
            export_report_pdf(path)
            QMessageBox.information(self, "Exito", f"Reporte guardado en:\n{path}")
        except Exception as e:
            logger.exception("Error al exportar reporte PDF")
            QMessageBox.warning(self, "Error", f"Error al exportar: {e}")

    def _export_excel(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar Reporte Excel", f"reporte_{datetime.now():%Y%m%d}.xlsx",
            "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            from utils.export import export_report_excel
            export_report_excel(path)
            QMessageBox.information(self, "Exito", f"Reporte guardado en:\n{path}")
        except Exception as e:
            logger.exception("Error al exportar reporte Excel")
            QMessageBox.warning(self, "Error", f"Error al exportar: {e}")

    def _export_clientes_excel(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar Clientes (Excel)", f"clientes_analisis_{datetime.now():%Y%m%d}.xlsx",
            "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            from utils.export import export_clientes_excel
            export_clientes_excel(path)
            QMessageBox.information(self, "Exito", f"Clientes exportados en:\n{path}")
        except Exception as e:
            logger.exception("Error al exportar clientes Excel")
            QMessageBox.warning(self, "Error", f"Error al exportar clientes: {e}")

    def _export_clientes_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar Clientes (CSV)", f"clientes_analisis_{datetime.now():%Y%m%d}.csv",
            "CSV (*.csv)"
        )
        if not path:
            return
        try:
            from utils.export import export_clientes_csv
            export_clientes_csv(path)
            QMessageBox.information(self, "Exito", f"Clientes exportados en:\n{path}")
        except Exception as e:
            logger.exception("Error al exportar clientes CSV")
            QMessageBox.warning(self, "Error", f"Error al exportar clientes: {e}")

    def _export_carpetas_excel(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar Carpetas (Excel)", f"carpetas_analisis_{datetime.now():%Y%m%d}.xlsx",
            "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            from utils.export import export_carpetas_excel
            export_carpetas_excel(path)
            QMessageBox.information(self, "Exito", f"Carpetas exportadas en:\n{path}")
        except Exception as e:
            logger.exception("Error al exportar carpetas Excel")
            QMessageBox.warning(self, "Error", f"Error al exportar carpetas: {e}")

    def _export_carpetas_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar Carpetas (CSV)", f"carpetas_analisis_{datetime.now():%Y%m%d}.csv",
            "CSV (*.csv)"
        )
        if not path:
            return
        try:
            from utils.export import export_carpetas_csv
            export_carpetas_csv(path)
            QMessageBox.information(self, "Exito", f"Carpetas exportadas en:\n{path}")
        except Exception as e:
            logger.exception("Error al exportar carpetas CSV")
            QMessageBox.warning(self, "Error", f"Error al exportar carpetas: {e}")
