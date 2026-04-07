"""Utilidades de exportacion a PDF, Excel y CSV."""
from datetime import datetime
import json

from controllers.reporte_controller import ReporteController
from controllers.cliente_controller import ClienteController
from controllers.expediente_controller import ExpedienteController
from core import db_local


def export_report_pdf(path: str):
    """Generar reporte PDF con KPIs y listados."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.units import mm

    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    elements.append(Paragraph("Sistema Rampazzo - Reporte General", styles["Title"]))
    elements.append(Paragraph(f"Fecha: {datetime.now():%d/%m/%Y %H:%M}", styles["Normal"]))
    elements.append(Spacer(1, 10*mm))

    # KPIs
    ops = ReporteController.kpis_operativos()
    com = ReporteController.kpis_comerciales()
    eco = ReporteController.kpis_economicos()

    kpi_data = [
        ["Indicador", "Valor"],
        ["Carpetas activas", str(ops["expedientes_activos"])],
        ["Carpetas cerradas", str(ops["expedientes_cerrados"])],
        ["Tareas pendientes", str(ops["tareas_pendientes"])],
        ["Tareas vencidas", str(ops["tareas_vencidas"])],
        ["Total clientes", str(com["total_clientes"])],
        ["Ingresos cobrados", f'${eco["ingresos_cobrados"]:,.2f}'],
        ["Pendientes cobro", f'${eco["pendientes_cobro"]:,.2f}'],
    ]

    t = Table(kpi_data, colWidths=[120*mm, 50*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a1a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#c9a84c")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e0e0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(Paragraph("Indicadores Clave", styles["Heading2"]))
    elements.append(t)
    elements.append(Spacer(1, 8*mm))

    # Carpetas por tipo
    por_tipo = ReporteController.expedientes_por_tipo()
    if por_tipo:
        tipo_data = [["Tipo Tramite", "Cantidad"]]
        for d in por_tipo:
            tipo_data.append([d["tipo"], str(d["cantidad"])])
        t2 = Table(tipo_data, colWidths=[120*mm, 50*mm])
        t2.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#c9a84c")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e0e0")),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(Paragraph("Carpetas por Tipo", styles["Heading2"]))
        elements.append(t2)

    doc.build(elements)


def export_report_excel(path: str):
    """Exportar datos a Excel con multiples hojas."""
    import pandas as pd

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        # Clientes
        clientes = ClienteController.get_all(order_by="nombre_completo")
        if clientes:
            df = pd.DataFrame(clientes)
            cols = ["id_cliente", "nombre_completo", "dni", "cuil", "telefonos",
                    "email", "direccion", "observaciones"]
            df = df[[c for c in cols if c in df.columns]]
            df.to_excel(writer, sheet_name="Clientes", index=False)

        # Carpetas
        expedientes = ExpedienteController.get_all(order_by="id_expediente DESC")
        if expedientes:
            df = pd.DataFrame(expedientes)
            cols = ["id_expediente", "tipo_tramite", "estado", "responsable",
                    "fecha_apertura", "numero_expediente_anses", "observaciones"]
            df = df[[c for c in cols if c in df.columns]]
            df.to_excel(writer, sheet_name="Carpetas", index=False)

        # Movimientos
        movimientos = db_local.find_all("movimientos", order_by="fecha DESC")
        if movimientos:
            df = pd.DataFrame(movimientos)
            cols = ["id_movimiento", "tipo", "monto", "fecha",
                    "forma_pago", "estado", "saldo", "observaciones"]
            df = df[[c for c in cols if c in df.columns]]
            df.to_excel(writer, sheet_name="Movimientos", index=False)

        # KPIs
        ops = ReporteController.kpis_operativos()
        com = ReporteController.kpis_comerciales()
        eco = ReporteController.kpis_economicos()
        kpis = {**ops, **com, **eco}
        df_kpi = pd.DataFrame(list(kpis.items()), columns=["Indicador", "Valor"])
        df_kpi.to_excel(writer, sheet_name="KPIs", index=False)


def _normalize_for_analysis(rows: list[dict], columns: list[str]) -> list[dict]:
    """Normaliza campos complejos (dict/list) a JSON para export analítico."""
    normalized: list[dict] = []
    for row in rows:
        out = {}
        for col in columns:
            value = row.get(col)
            if isinstance(value, (dict, list)):
                out[col] = json.dumps(value, ensure_ascii=False, default=str)
            else:
                out[col] = value
        normalized.append(out)
    return normalized


CLIENTES_ANALISIS_COLUMNS = [
    "_id", "id_cliente", "numero_carpeta", "nombre_completo", "dni", "cuil",
    "fecha_nacimiento", "direccion", "localidad", "telefonos", "email",
    "obra_social", "actividad", "procedencia_contacto", "observaciones",
    "is_deleted", "deleted_at", "deleted_by",
    "updated_at", "version", "sync_status", "created_by_machine",
]

CARPETAS_ANALISIS_COLUMNS = [
    "_id", "id_expediente", "id_cliente", "numero_carpeta", "cliente_nombre",
    "cliente_dni", "cliente_cuil",
    "tipo_tramite", "area", "rama", "subtipo",
    "estado", "prioridad",
    "responsable", "responsable_username",
    "responsable_secundario", "responsable_secundario_username",
    "fecha_apertura", "fecha_cierre", "numero_expediente_anses",
    "ubicacion_fisica", "link_drive", "resultado", "observaciones",
    "is_deleted", "deleted_at", "deleted_by",
    "updated_at", "version", "sync_status", "created_by_machine",
]


def export_clientes_excel(path: str):
    import pandas as pd

    rows = ReporteController.clientes_para_analisis()
    norm = _normalize_for_analysis(rows, CLIENTES_ANALISIS_COLUMNS)
    df = pd.DataFrame(norm, columns=CLIENTES_ANALISIS_COLUMNS)
    df.to_excel(path, index=False, sheet_name="ClientesAnalisis")


def export_clientes_csv(path: str):
    import pandas as pd

    rows = ReporteController.clientes_para_analisis()
    norm = _normalize_for_analysis(rows, CLIENTES_ANALISIS_COLUMNS)
    df = pd.DataFrame(norm, columns=CLIENTES_ANALISIS_COLUMNS)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def export_carpetas_excel(path: str):
    import pandas as pd

    rows = ReporteController.carpetas_para_analisis()
    norm = _normalize_for_analysis(rows, CARPETAS_ANALISIS_COLUMNS)
    df = pd.DataFrame(norm, columns=CARPETAS_ANALISIS_COLUMNS)
    df.to_excel(path, index=False, sheet_name="CarpetasAnalisis")


def export_carpetas_csv(path: str):
    import pandas as pd

    rows = ReporteController.carpetas_para_analisis()
    norm = _normalize_for_analysis(rows, CARPETAS_ANALISIS_COLUMNS)
    df = pd.DataFrame(norm, columns=CARPETAS_ANALISIS_COLUMNS)
    df.to_csv(path, index=False, encoding="utf-8-sig")
