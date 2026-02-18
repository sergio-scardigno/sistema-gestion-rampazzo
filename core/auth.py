"""
Autenticacion y sesion de usuario.
Login contra Atlas si hay conexion, sino contra cache local.
"""
import uuid
import logging
from datetime import datetime, timezone

import bcrypt

from core import db_local, db_remote
from core.db_remote import is_connected
from config import MACHINE_ID

logger = logging.getLogger(__name__)


class Session:
    """Sesion del usuario activo."""
    _instance = None

    def __init__(self):
        self.usuario: dict | None = None

    @classmethod
    def get(cls) -> "Session":
        if cls._instance is None:
            cls._instance = Session()
        return cls._instance

    @property
    def logged_in(self) -> bool:
        return self.usuario is not None

    @property
    def username(self) -> str:
        return self.usuario.get("username", "") if self.usuario else ""

    @property
    def rol(self) -> str:
        return self.usuario.get("rol", "") if self.usuario else ""

    @property
    def nombre(self) -> str:
        return self.usuario.get("nombre_completo", "") if self.usuario else ""

    def logout(self):
        self.usuario = None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def login(username: str, password: str) -> tuple[bool, str]:
    """
    Intentar login. Retorna (exito, mensaje).
    Prioriza Atlas; si no hay conexion, usa cache local.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Intentar contra Atlas primero
    if is_connected():
        try:
            db = db_remote.get_db()
            user_doc = db.usuarios.find_one({"username": username})
            if user_doc is None:
                return False, "Usuario no encontrado"
            if user_doc.get("eliminado"):
                return False, "Usuario dado de baja"
            if not user_doc.get("activo", True):
                return False, "Usuario desactivado"
            if not check_password(password, user_doc["password_hash"]):
                return False, "Contrasena incorrecta"

            # Actualizar ultimo acceso en Atlas
            db.usuarios.update_one(
                {"_id": user_doc["_id"]},
                {"$set": {"ultimo_acceso": now, "updated_at": now}}
            )
            # Cachear en local
            user_doc["ultimo_acceso"] = now
            user_doc["updated_at"] = now
            user_doc["sync_status"] = "synced"
            local_data = {k: str(v) if v is not None else None for k, v in user_doc.items()}
            local_data["activo"] = 1 if user_doc.get("activo", True) else 0
            db_local.insert("usuarios", local_data)

            Session.get().usuario = user_doc
            return True, "Login exitoso"
        except Exception:
            logger.warning("Login contra Atlas fallo, cayendo a cache local", exc_info=True)

    # Login contra cache local
    user_row = db_local.find_all("usuarios", where="username = ?", params=(username,))
    if not user_row:
        return False, "Usuario no encontrado (modo offline)"
    user = user_row[0]
    if user.get("eliminado"):
        return False, "Usuario dado de baja"
    if not user.get("activo", 1):
        return False, "Usuario desactivado"
    if not check_password(password, user["password_hash"]):
        return False, "Contrasena incorrecta"

    Session.get().usuario = user
    return True, "Login exitoso (modo offline)"


def create_user(username: str, password: str, nombre_completo: str,
                email: str, rol: str) -> tuple[bool, str]:
    """Crear usuario nuevo. Requiere conexion a Atlas."""
    if not is_connected():
        return False, "Se requiere conexion para crear usuarios"

    now = datetime.now(timezone.utc).isoformat()
    _id = str(uuid.uuid4())

    doc = {
        "_id": _id,
        "username": username,
        "password_hash": hash_password(password),
        "nombre_completo": nombre_completo,
        "email": email,
        "rol": rol,
        "activo": True,
        "ultimo_acceso": None,
        "updated_at": now,
        "version": 1,
        "created_by_machine": MACHINE_ID,
    }

    try:
        db = db_remote.get_db()
        db.usuarios.insert_one(doc)
        # Cachear en local
        local_data = {k: str(v) if v is not None else None for k, v in doc.items()}
        local_data["activo"] = 1
        local_data["sync_status"] = "synced"
        db_local.insert("usuarios", local_data)
        return True, "Usuario creado exitosamente"
    except Exception as e:
        if "duplicate key" in str(e).lower():
            return False, "El nombre de usuario ya existe"
        logger.exception("Error al crear usuario '%s'", username)
        return False, f"Error al crear usuario: {e}"


def ensure_admin_exists():
    """Crear usuarios por defecto si no existe ningun usuario en la BD."""
    if db_local.count("usuarios") > 0:
        return

    now = datetime.now(timezone.utc).isoformat()

    default_users = [
        ("secretaria", "sec123",   "Secretaria Rampazzo",    "secretaria"),
        ("agente",     "age123",   "Agente Rampazzo",        "agente"),
        ("abogado",    "abo123",   "Abogado Rampazzo",       "abogado"),
        ("admin",      "admin123", "Administrador Rampazzo", "administrador"),
        ("super",      "super123", "Super Usuario",          "superusuario"),
    ]

    for username, password, nombre, rol in default_users:
        _id = str(uuid.uuid4())
        doc = {
            "_id": _id,
            "username": username,
            "password_hash": hash_password(password),
            "nombre_completo": nombre,
            "email": "",
            "rol": rol,
            "activo": 1,
            "ultimo_acceso": None,
            "updated_at": now,
            "version": 1,
            "sync_status": "pending",
            "created_by_machine": MACHINE_ID,
        }
        db_local.insert("usuarios", doc)

        # Si hay conexion, crear tambien en Atlas
        if is_connected():
            try:
                atlas_doc = dict(doc)
                atlas_doc["activo"] = True
                del atlas_doc["sync_status"]
                db_remote.get_db().usuarios.insert_one(atlas_doc)
                db_local.mark_synced("usuarios", _id)
            except Exception:
                logger.warning("No se pudo crear usuario seed '%s' en Atlas", username, exc_info=True)
