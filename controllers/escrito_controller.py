"""Controladores para modelos y escritos legales autocompletables."""
import html
import re
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from config import DOCS_DIR
from controllers.base_controller import BaseController
from controllers.cliente_controller import ClienteController
from controllers.expediente_controller import ExpedienteController


_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")


def _safe_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if v is not None)
    return str(value)


def _fecha_actual_texto() -> str:
    meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]
    now = datetime.now()
    return f"{now.day} de {meses[now.month - 1]} de {now.year}"


def _flatten(prefix: str, source: dict, target: dict):
    for key, value in (source or {}).items():
        current = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            _flatten(current, value, target)
        else:
            target[current] = _safe_text(value)


def render_placeholders(template_html: str, cliente: dict, expediente: dict) -> str:
    """Reemplaza placeholders {{ruta.campo}} por datos de cliente/carpeta."""
    context: dict[str, str] = {}
    _flatten("cliente", cliente or {}, context)
    _flatten("expediente", expediente or {}, context)
    _flatten("judicial", expediente.get("datos_judicial", {}) or {}, context)
    _flatten("rama", expediente.get("datos_rama", {}) or {}, context)

    now = datetime.now()
    context["fecha_actual"] = now.strftime("%Y-%m-%d")
    context["anio_actual"] = str(now.year)
    context["fecha_actual_texto"] = _fecha_actual_texto()

    def _replace(match: re.Match) -> str:
        key = match.group(1).strip()
        return context.get(key, "")

    return _PLACEHOLDER_RE.sub(_replace, template_html or "")


def _strip_html_to_lines(content_html: str) -> list[str]:
    if not content_html:
        return []
    text = re.sub(r"(?i)<br\s*/?>", "\n", content_html)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    lines = [line.strip() for line in text.splitlines()]
    return [line for line in lines if line]


def _safe_filename(text: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "_", text or "escrito")
    cleaned = re.sub(r"\s+", "_", cleaned).strip("._")
    return cleaned or "escrito"


class ModeloEscritoController(BaseController):
    TABLE = "modelos_escrito"
    ID_FIELD = ""

    @classmethod
    def get_activos(cls, rama: str = "") -> list[dict]:
        if rama:
            return cls.get_all(
                where="activo = 1 AND (rama = '' OR rama = ?)",
                params=(rama,),
                order_by="nombre ASC",
            )
        return cls.get_all(where="activo = 1", order_by="nombre ASC")

    @classmethod
    def seed_defaults(cls):
        existing = cls.get_all(where="nombre = ?", params=("Escrito de Inicio - Amparo Previsional",))
        if existing:
            return
        template = """
<p><b>Senor Juez:</b></p>
<p>{{cliente.nombre_completo}}, DNI {{cliente.dni}}, CUIL {{cliente.cuil}}, con domicilio en {{cliente.direccion}}, {{cliente.localidad}}, se presenta y dice:</p>
<p><b>I. OBJETO</b><br/>Que promuevo accion de amparo previsional en relacion con la carpeta Nro {{expediente.id_expediente}}.</p>
<p><b>II. HECHOS</b><br/>La parte actora tramita {{expediente.tipo_tramite}} en rama {{expediente.rama}} - {{expediente.subtipo}}.</p>
<p><b>III. DERECHO</b><br/>Fundo la presente en las normas constitucionales y legales aplicables.</p>
<p><b>IV. PETITORIO</b><br/>Por todo lo expuesto, solicito se haga lugar a la accion, con costas.</p>
<p>Proveer de conformidad,<br/>SERA JUSTICIA.</p>
<p>{{fecha_actual_texto}}</p>
"""
        cls.create({
            "nombre": "Escrito de Inicio - Amparo Previsional",
            "descripcion": "Modelo base para iniciar accion de amparo previsional.",
            "rama": "Previsional",
            "contenido_html": template.strip(),
            "activo": 1,
        })


class EscritoController(BaseController):
    TABLE = "escritos"
    ID_FIELD = ""

    @classmethod
    def get_by_expediente(cls, id_expediente: str) -> list[dict]:
        return cls.get_scoped(
            where="id_expediente = ?",
            params=(id_expediente,),
            order_by="fecha_creacion DESC, updated_at DESC",
        )

    @classmethod
    def crear_desde_modelo(cls, id_expediente: str, id_modelo: str) -> dict | None:
        modelo = ModeloEscritoController.get_by_id(id_modelo)
        expediente = ExpedienteController.get_by_id(id_expediente)
        if not modelo or not expediente:
            return None

        cliente = {}
        cliente_id = expediente.get("id_cliente", "")
        if cliente_id:
            cliente = ClienteController.get_by_id(cliente_id) or {}

        contenido = render_placeholders(
            modelo.get("contenido_html", ""),
            cliente,
            expediente,
        )

        from core.auth import Session
        session = Session.get()
        username = session.username if session.logged_in else ""
        responsable = session.nombre if session.logged_in else ""

        return cls.create({
            "id_expediente": id_expediente,
            "id_modelo": id_modelo,
            "titulo": modelo.get("nombre", "Escrito"),
            "contenido_html": contenido,
            "fecha_creacion": datetime.now(timezone.utc).date().isoformat(),
            "responsable": responsable,
            "responsable_username": username,
        })

    @classmethod
    def exportar_pdf(cls, escrito_id: str, output_path: str = "") -> str:
        escrito = cls.get_by_id(escrito_id)
        if not escrito:
            raise ValueError("Escrito no encontrado.")

        if output_path:
            out = Path(output_path)
        else:
            exp_id = escrito.get("id_expediente", "sin_expediente")
            out_dir = DOCS_DIR / exp_id / "escritos"
            out_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = _safe_filename(escrito.get("titulo", "escrito"))
            out = out_dir / f"{name}_{ts}.pdf"

        doc = SimpleDocTemplate(str(out), pagesize=A4)
        styles = getSampleStyleSheet()
        body = styles["BodyText"]

        story = []
        title = html.escape(escrito.get("titulo", "Escrito"))
        story.append(Paragraph(f"<b>{title}</b>", styles["Heading2"]))
        story.append(Spacer(1, 12))

        for line in _strip_html_to_lines(escrito.get("contenido_html", "")):
            story.append(Paragraph(html.escape(line), body))
            story.append(Spacer(1, 6))

        doc.build(story)
        return str(out)
