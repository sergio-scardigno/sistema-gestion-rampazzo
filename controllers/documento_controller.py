"""Controlador de Documentos – gestion documental con categorias y versionado."""
import os
import shutil
import uuid
import logging
from pathlib import Path

from controllers.base_controller import BaseController
from core import db_local
from config import DOCS_DIR

logger = logging.getLogger(__name__)


class DocumentoController(BaseController):
    TABLE = "documentos"
    ID_FIELD = ""

    # Categorias del pliego tecnico
    CATEGORIAS = [
        "Identidad", "Laboral", "Medicos", "Judiciales",
        "Administrativos", "Resoluciones", "Escritos",
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
        "Notificaciones": ["Cedula", "Carta documento", "Telegrama", "Otro"],
        "Comunicaciones": ["Email", "Nota", "Informe", "Otro"],
        "Otro": ["General"],
    }

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

        # Copiar archivo al repositorio
        ruta_destino = _copy_file_to_repo(ruta_archivo_nuevo, original["id_expediente"])

        # Obtener tamano del archivo
        tamano = 0
        if ruta_destino and Path(ruta_destino).exists():
            tamano = Path(ruta_destino).stat().st_size

        nueva_data = {
            "id_expediente": original["id_expediente"],
            "categoria": original["categoria"],
            "subcategoria": original.get("subcategoria", ""),
            "nombre": original["nombre"],
            "descripcion": original.get("descripcion", ""),
            "ruta_archivo": ruta_destino,
            "tamano_bytes": tamano,
            "mime_type": original.get("mime_type", ""),
            "responsable": responsable or original.get("responsable", ""),
            "version_doc": nueva_ver,
            "version_padre": doc_id,
            "notas_version": notas,
        }

        return cls.create(nueva_data)

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


def _copy_file_to_repo(ruta_origen: str, id_expediente: str) -> str:
    """Copia un archivo al repositorio local de documentos, organizado por expediente."""
    if not ruta_origen or not Path(ruta_origen).exists():
        return ruta_origen  # Mantener ruta original si no se puede copiar

    exp_dir = DOCS_DIR / id_expediente
    exp_dir.mkdir(exist_ok=True)

    nombre_archivo = Path(ruta_origen).name
    destino = exp_dir / f"{uuid.uuid4().hex[:8]}_{nombre_archivo}"

    try:
        shutil.copy2(ruta_origen, str(destino))
        return str(destino)
    except Exception:
        logger.exception("Error al copiar archivo al repositorio: %s", ruta_origen)
        return ruta_origen
