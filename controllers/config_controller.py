"""Controlador de configuracion global – logos y branding."""
import os
import shutil
import uuid
import logging
from pathlib import Path

from core import db_local
from core.auth import Session
from config import DATA_DIR

logger = logging.getLogger(__name__)


# Directorio de almacenamiento de logos
LOGOS_DIR = DATA_DIR / "logos"
LOGOS_DIR.mkdir(exist_ok=True)

# Claves en sync_meta
KEY_LOGO_PRINCIPAL = "logo_principal_path"
KEY_LOGO_EXPEDIENTES = "logo_expedientes_path"

# Extensiones permitidas
EXTENSIONES_VALIDAS = {".png", ".jpg", ".jpeg", ".bmp", ".ico"}


class ConfigController:
    """Manejo de logos configurables. Solo superusuario puede escribir."""

    @staticmethod
    def _es_superusuario() -> bool:
        session = Session.get()
        return session.logged_in and session.rol == "superusuario"

    @staticmethod
    def get_logo_principal() -> str | None:
        """Retorna la ruta absoluta del logo principal si existe y es valida."""
        path = db_local.get_sync_meta(KEY_LOGO_PRINCIPAL)
        if path and os.path.isfile(path):
            return path
        return None

    @staticmethod
    def get_logo_expedientes() -> str | None:
        """Retorna la ruta absoluta del logo de expedientes si existe y es valida."""
        path = db_local.get_sync_meta(KEY_LOGO_EXPEDIENTES)
        if path and os.path.isfile(path):
            return path
        return None

    @staticmethod
    def set_logo_principal(source_path: str) -> tuple[bool, str]:
        """Copia la imagen a data/logos/ y guarda la ruta. Solo superusuario."""
        if not ConfigController._es_superusuario():
            return False, "Solo el superusuario puede cambiar logos."
        return ConfigController._save_logo(source_path, KEY_LOGO_PRINCIPAL, "logo_principal")

    @staticmethod
    def set_logo_expedientes(source_path: str) -> tuple[bool, str]:
        """Copia la imagen a data/logos/ y guarda la ruta. Solo superusuario."""
        if not ConfigController._es_superusuario():
            return False, "Solo el superusuario puede cambiar logos."
        return ConfigController._save_logo(source_path, KEY_LOGO_EXPEDIENTES, "logo_expedientes")

    @staticmethod
    def remove_logo_principal() -> tuple[bool, str]:
        """Elimina el logo principal. Solo superusuario."""
        if not ConfigController._es_superusuario():
            return False, "Solo el superusuario puede cambiar logos."
        return ConfigController._remove_logo(KEY_LOGO_PRINCIPAL)

    @staticmethod
    def remove_logo_expedientes() -> tuple[bool, str]:
        """Elimina el logo de expedientes. Solo superusuario."""
        if not ConfigController._es_superusuario():
            return False, "Solo el superusuario puede cambiar logos."
        return ConfigController._remove_logo(KEY_LOGO_EXPEDIENTES)

    @staticmethod
    def _save_logo(source_path: str, meta_key: str, prefix: str) -> tuple[bool, str]:
        """Copia un archivo de imagen a LOGOS_DIR y persiste la ruta."""
        src = Path(source_path)
        if not src.is_file():
            return False, "El archivo seleccionado no existe."

        ext = src.suffix.lower()
        if ext not in EXTENSIONES_VALIDAS:
            return False, f"Formato no soportado ({ext}). Use: {', '.join(EXTENSIONES_VALIDAS)}"

        # Nombre unico para evitar colisiones
        dest_name = f"{prefix}_{uuid.uuid4().hex[:8]}{ext}"
        dest = LOGOS_DIR / dest_name

        try:
            # Eliminar logo anterior si existe
            old_path = db_local.get_sync_meta(meta_key)
            if old_path and os.path.isfile(old_path):
                try:
                    os.remove(old_path)
                except OSError:
                    pass

            shutil.copy2(str(src), str(dest))
            db_local.set_sync_meta(meta_key, str(dest))
            return True, "Logo actualizado correctamente."
        except Exception as e:
            logger.exception("Error al guardar logo")
            return False, f"Error al guardar logo: {e}"

    @staticmethod
    def _remove_logo(meta_key: str) -> tuple[bool, str]:
        """Elimina el archivo fisico y borra la clave de sync_meta."""
        path = db_local.get_sync_meta(meta_key)
        if path and os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass
        db_local.set_sync_meta(meta_key, "")
        return True, "Logo eliminado."
