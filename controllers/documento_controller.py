"""Controlador de Documentos – gestion documental con categorias y versionado."""
import shutil
import uuid
import logging
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from controllers.base_controller import BaseController
from core import db_local
from core import file_service
from config import DOCS_DIR

logger = logging.getLogger(__name__)


class DocumentoController(BaseController):
    TABLE = "documentos"
    ID_FIELD = ""
    ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".doc", ".docx"}
    MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024

    # Categorias del pliego tecnico
    CATEGORIAS = [
        "Identidad", "Laboral", "Medicos", "Judiciales",
        "Administrativos", "Resoluciones", "Escritos",
        "Calculo Derecho",
        "Notificaciones", "Comunicaciones", "Otro"
    ]

    # Subcategorias por categoria (carpetas logicas del pliego)
    SUBCATEGORIAS = {
        "Identidad": ["DNI", "Partida nacimiento", "Certificado domicilio", "CUIL", "Otro"],
        "Laboral": ["Recibos sueldo", "Certificado trabajo", "ART", "ANSES", "Otro"],
        "Medicos": ["Certificado medico", "Historia clinica", "Junta medica", "CUD", "Otro"],
        "Judiciales": ["Demanda", "Contestacion", "Sentencia", "Apelacion", "Recurso", "Otro"],
        "Administrativos": ["Expediente ANSES", "Resolucion", "Recurso admin.", "Dictamen", "Otro"],
        "Resoluciones": ["Favorable", "Desfavorable", "Parcial", "Otro"],
        "Escritos": ["Inicio", "Ampliacion", "Alegato", "Memorial", "Otro"],
        "Calculo Derecho": ["Liquidacion", "Pericia", "Otro"],
        "Notificaciones": ["Cedula", "Carta documento", "Telegrama", "Otro"],
        "Comunicaciones": ["Email", "Nota", "Informe", "Otro"],
        "Otro": ["General"],
    }

    @classmethod
    def create(cls, data: dict) -> dict:
        """Crear documento: copia archivo al repo local, sube al VPS, guarda ruta relativa."""
        ruta_original = data.get("ruta_archivo", "")
        id_expediente = data.get("id_expediente", "")

        if ruta_original and id_expediente and Path(ruta_original).is_file():
            ok, _ = cls.validate_file(ruta_original)
            if not ok:
                raise ValueError("Archivo no permitido o supera el tamano maximo de 5 MB.")
            ruta_abs, ruta_rel = _copy_file_to_repo(ruta_original, id_expediente)
            data["ruta_archivo"] = ruta_rel
            if not data.get("tamano_bytes") and Path(ruta_abs).is_file():
                data["tamano_bytes"] = Path(ruta_abs).stat().st_size
            file_service.upload_file_async(Path(ruta_abs), ruta_rel)

        record = super().create(data)
        return record

    @classmethod
    def update(cls, _id: str, data: dict) -> dict | None:
        """Actualizar documento: si cambia el archivo, copiar + subir."""
        ruta_nueva = data.get("ruta_archivo", "")
        id_expediente = data.get("id_expediente", "")

        if ruta_nueva and Path(ruta_nueva).is_absolute() and Path(ruta_nueva).is_file():
            if id_expediente:
                ok, _ = cls.validate_file(ruta_nueva)
                if not ok:
                    raise ValueError("Archivo no permitido o supera el tamano maximo de 5 MB.")
                ruta_abs, ruta_rel = _copy_file_to_repo(ruta_nueva, id_expediente)
                data["ruta_archivo"] = ruta_rel
                if not data.get("tamano_bytes"):
                    data["tamano_bytes"] = Path(ruta_abs).stat().st_size
                file_service.upload_file_async(Path(ruta_abs), ruta_rel)

        return super().update(_id, data)

    @classmethod
    def ensure_local_file(cls, doc_id: str) -> Path | None:
        """Resuelve el archivo local de un documento, descargandolo del VPS si es necesario."""
        doc = cls.get_by_id(doc_id)
        if not doc:
            return None
        ruta = doc.get("ruta_archivo", "")
        return file_service.resolve_local_path(ruta)

    @classmethod
    def validate_file(cls, file_path: str) -> tuple[bool, str]:
        """Valida extension y tamano permitido para documentos."""
        p = Path(file_path)
        if not p.is_file():
            return False, "El archivo no existe."
        if p.suffix.lower() not in cls.ALLOWED_EXTENSIONS:
            return False, "Extension no permitida."
        if p.stat().st_size > cls.MAX_FILE_SIZE_BYTES:
            return False, "El archivo supera el limite de 5 MB."
        return True, ""

    @classmethod
    def get_by_expediente(cls, id_expediente: str) -> list[dict]:
        return cls.get_all(where="id_expediente = ?", params=(id_expediente,),
                           order_by="categoria ASC, nombre ASC, version_doc DESC")

    @classmethod
    def get_versiones(cls, doc_id: str) -> list[dict]:
        """Obtiene todas las versiones de un documento (actual + anteriores)."""
        doc = cls.get_by_id(doc_id)
        if not doc:
            return []

        nombre = doc.get("nombre", "")
        id_exp = doc.get("id_expediente", "")

        # Buscar todas las versiones del mismo nombre y expediente
        versiones = cls.get_all(
            where="nombre = ? AND id_expediente = ?",
            params=(nombre, id_exp),
            order_by="version_doc DESC"
        )
        return versiones

    @classmethod
    def crear_nueva_version(cls, doc_id: str, ruta_archivo_nuevo: str,
                            notas: str = "", responsable: str = "") -> dict | None:
        """Crea una nueva version de un documento existente."""
        original = cls.get_by_id(doc_id)
        if not original:
            return None

        # Obtener version mas alta
        conn = db_local.get_connection()
        max_ver = conn.execute(
            "SELECT MAX(version_doc) FROM documentos WHERE nombre = ? AND id_expediente = ?",
            (original["nombre"], original["id_expediente"])
        ).fetchone()[0] or 1
        conn.close()

        nueva_ver = max_ver + 1

        ok, _ = cls.validate_file(ruta_archivo_nuevo)
        if not ok:
            raise ValueError("Archivo no permitido o supera el tamano maximo de 5 MB.")

        ruta_abs, ruta_rel = _copy_file_to_repo(ruta_archivo_nuevo, original["id_expediente"])

        tamano = 0
        if ruta_abs and Path(ruta_abs).is_file():
            tamano = Path(ruta_abs).stat().st_size

        file_service.upload_file_async(Path(ruta_abs), ruta_rel)

        nueva_data = {
            "id_expediente": original["id_expediente"],
            "categoria": original["categoria"],
            "subcategoria": original.get("subcategoria", ""),
            "nombre": original["nombre"],
            "descripcion": original.get("descripcion", ""),
            "ruta_archivo": ruta_rel,
            "tamano_bytes": tamano,
            "mime_type": original.get("mime_type", ""),
            "responsable": responsable or original.get("responsable", ""),
            "version_doc": nueva_ver,
            "version_padre": doc_id,
            "notas_version": notas,
        }

        return super().create(nueva_data)

    @classmethod
    def get_stats_by_expediente(cls, id_expediente: str) -> dict:
        """Retorna estadisticas de documentos de un expediente."""
        docs = cls.get_by_expediente(id_expediente)
        por_categoria = {}
        for d in docs:
            cat = d.get("categoria", "Otro")
            por_categoria[cat] = por_categoria.get(cat, 0) + 1

        tamano_total = sum(d.get("tamano_bytes", 0) or 0 for d in docs)
        return {
            "total": len(docs),
            "por_categoria": por_categoria,
            "tamano_total_mb": round(tamano_total / (1024 * 1024), 2) if tamano_total else 0,
        }

    @classmethod
    def search_documentos(cls, text: str) -> list[dict]:
        return cls.search(text, [
            "nombre", "categoria", "subcategoria", "descripcion", "responsable"
        ])


def _copy_file_to_repo(ruta_origen: str, id_expediente: str) -> tuple[str, str]:
    """Copia un archivo al repositorio local de documentos, organizado por expediente.

    Returns:
        Tupla (ruta_absoluta, ruta_relativa). La ruta_relativa es portable entre PCs.
    """
    if not ruta_origen or not Path(ruta_origen).exists():
        return ruta_origen, ruta_origen

    exp_dir = DOCS_DIR / id_expediente
    exp_dir.mkdir(exist_ok=True)

    nombre_destino = _build_tracked_filename(ruta_origen, id_expediente)
    destino = exp_dir / nombre_destino
    ruta_relativa = f"{id_expediente}/{nombre_destino}"

    try:
        shutil.copy2(ruta_origen, str(destino))
        return str(destino), ruta_relativa
    except Exception:
        logger.exception("Error al copiar archivo al repositorio: %s", ruta_origen)
        return ruta_origen, ruta_origen


def _slug(text: str, max_len: int = 30) -> str:
    """Normaliza texto para nombres de archivo seguros."""
    if not text:
        return "na"
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    if not cleaned:
        cleaned = "na"
    return cleaned[:max_len]


def _build_tracked_filename(ruta_origen: str, expediente_oid: str) -> str:
    """Genera nombre trazable: carpeta, cliente, expediente, fecha y sufijo unico."""
    ext = Path(ruta_origen).suffix.lower()
    if not ext:
        ext = ".bin"

    # Defaults seguros para cuando falte informacion
    numero_carpeta = "na"
    numero_cliente = "na"
    expediente_num = _slug(expediente_oid, max_len=16)

    try:
        from controllers.expediente_controller import ExpedienteController
        from controllers.cliente_controller import ClienteController

        exp = ExpedienteController.get_by_id(expediente_oid) or {}
        expediente_num = _slug(str(exp.get("id_expediente", expediente_oid)), max_len=16)
        cliente_oid = exp.get("id_cliente", "")
        if cliente_oid:
            cli = ClienteController.get_by_id(cliente_oid) or {}
            numero_carpeta = _slug(str(cli.get("numero_carpeta", "na")), max_len=12)
            numero_cliente = _slug(str(cli.get("id_cliente", "na")), max_len=12)
    except Exception:
        logger.exception("No se pudo obtener metadata para nombre trazable de archivo")

    fecha = datetime.now().strftime("%Y%m%d")
    sufijo = uuid.uuid4().hex[:6]
    # Ejemplo: carp_123_cli_45_exp_101_20260320_a1b2c3.pdf
    return f"carp_{numero_carpeta}_cli_{numero_cliente}_exp_{expediente_num}_{fecha}_{sufijo}{ext}"
