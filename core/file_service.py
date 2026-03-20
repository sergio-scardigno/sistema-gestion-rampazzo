"""
Servicio cliente para comunicarse con el servidor de archivos (VPS).
Maneja upload y download de documentos de forma transparente.
"""
import logging
from pathlib import Path
from threading import Thread

import requests

from config import FILE_SERVER_URL, FILE_SERVER_API_KEY, DOCS_DIR

logger = logging.getLogger(__name__)

_TIMEOUT_UPLOAD = 120
_TIMEOUT_DOWNLOAD = 120


def is_configured() -> bool:
    return bool(FILE_SERVER_URL and FILE_SERVER_API_KEY)


def _headers() -> dict:
    return {"X-API-Key": FILE_SERVER_API_KEY}


def upload_file(ruta_local: Path, ruta_relativa: str) -> bool:
    """Sube un archivo al servidor de archivos.

    Args:
        ruta_local: Path absoluto del archivo en disco.
        ruta_relativa: Ruta relativa dentro del repo (ej: 'exp123/abc_foto.jpg').

    Returns:
        True si se subio correctamente.
    """
    if not is_configured():
        return False

    if not ruta_local.is_file():
        logger.warning("upload_file: archivo local no existe: %s", ruta_local)
        return False

    url = f"{FILE_SERVER_URL}/upload/{ruta_relativa}"
    try:
        with open(ruta_local, "rb") as f:
            resp = requests.post(
                url,
                files={"file": (ruta_local.name, f, "application/octet-stream")},
                headers=_headers(),
                timeout=_TIMEOUT_UPLOAD,
            )
        if resp.status_code == 200:
            logger.info("Archivo subido al servidor: %s", ruta_relativa)
            return True
        logger.error("Error al subir archivo (%s): %s", resp.status_code, resp.text)
        return False
    except Exception:
        logger.exception("Error de conexion al subir archivo: %s", ruta_relativa)
        return False


def upload_file_async(ruta_local: Path, ruta_relativa: str):
    """Sube un archivo al servidor en un thread separado (no bloquea la UI)."""
    if not is_configured():
        return
    t = Thread(target=upload_file, args=(ruta_local, ruta_relativa), daemon=True)
    t.start()


def download_file(ruta_relativa: str, destino_local: Path | None = None) -> Path | None:
    """Descarga un archivo del servidor al repositorio local.

    Args:
        ruta_relativa: Ruta relativa del archivo en el servidor.
        destino_local: Path destino. Si es None, usa DOCS_DIR / ruta_relativa.

    Returns:
        Path al archivo descargado, o None si fallo.
    """
    if not is_configured():
        return None

    if destino_local is None:
        destino_local = DOCS_DIR / ruta_relativa

    if destino_local.is_file():
        return destino_local

    url = f"{FILE_SERVER_URL}/download/{ruta_relativa}"
    try:
        resp = requests.get(url, headers=_headers(), timeout=_TIMEOUT_DOWNLOAD, stream=True)
        if resp.status_code == 200:
            destino_local.parent.mkdir(parents=True, exist_ok=True)
            with open(destino_local, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 256):
                    f.write(chunk)
            logger.info("Archivo descargado del servidor: %s", ruta_relativa)
            return destino_local
        if resp.status_code == 404:
            logger.warning("Archivo no encontrado en el servidor: %s", ruta_relativa)
        else:
            logger.error("Error al descargar (%s): %s", resp.status_code, resp.text)
        return None
    except Exception:
        logger.exception("Error de conexion al descargar archivo: %s", ruta_relativa)
        return None


def resolve_local_path(ruta_archivo: str) -> Path | None:
    """Resuelve la ruta de un archivo: busca local, si no existe descarga del VPS.

    Soporta tanto rutas absolutas (legacy) como relativas (nuevas).

    Returns:
        Path al archivo local, o None si no se pudo resolver.
    """
    if not ruta_archivo:
        return None

    p = Path(ruta_archivo)

    # Ruta absoluta (legacy): si existe, usarla directamente
    if p.is_absolute():
        if p.is_file():
            return p
        # Intentar como relativa respecto a DOCS_DIR (por si se migro)
        try:
            rel = p.relative_to(DOCS_DIR)
            ruta_rel_str = rel.as_posix()
        except ValueError:
            # No es relativa a DOCS_DIR, no se puede resolver
            return None
    else:
        ruta_rel_str = p.as_posix()

    # Buscar en repo local
    local_path = DOCS_DIR / ruta_rel_str
    if local_path.is_file():
        return local_path

    # Intentar descargar del VPS
    return download_file(ruta_rel_str, local_path)
