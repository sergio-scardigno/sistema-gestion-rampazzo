"""
Conexion a MongoDB Atlas (fuente de verdad central).
"""
import logging

import pymongo
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from config import MONGO_URI, MONGO_DB_NAME

logger = logging.getLogger(__name__)

_client: MongoClient | None = None
_db = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=120000,
        )
    return _client


def get_db():
    global _db
    if _db is None:
        _db = get_client()[MONGO_DB_NAME]
    return _db


def is_connected() -> bool:
    try:
        get_client().admin.command("ping")
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError, Exception):
        return False


def ensure_indexes():
    """Crear indices necesarios en Atlas."""
    db = get_db()
    db.usuarios.create_index("username", unique=True)
    db.clientes.create_index("cuil")
    db.clientes.create_index("nombre_completo")
    db.expedientes.create_index("id_cliente")
    db.tareas.create_index("id_expediente")
    db.comunicaciones.create_index("id_expediente")
    db.movimientos.create_index("id_expediente")
    db.movimientos.create_index("id_cliente")
    db.documentos.create_index("id_expediente")
    db.record_locks.create_index("expires_at", expireAfterSeconds=0)
    # updated_at indexes for sync
    for col_name in ["usuarios", "consultas", "clientes", "expedientes",
                     "tareas", "comunicaciones", "movimientos", "documentos", "audit_log"]:
        db[col_name].create_index("updated_at")


def update_remote_app_version():
    """Registra la version actual del programa en MongoDB Atlas.

    Crea o actualiza el documento version_config en la coleccion app_meta.
    Solo actualiza si la version actual es mayor que la almacenada.
    """
    from datetime import datetime, timezone
    from config import APP_VERSION, APP_VERSION_TUPLE, MIN_COMPATIBLE_VERSION

    try:
        if not is_connected():
            return

        db = get_db()
        meta = db.app_meta.find_one({"_id": "version_config"})

        if meta is None:
            # Primera vez: crear documento
            db.app_meta.insert_one({
                "_id": "version_config",
                "app_version": APP_VERSION,
                "min_compatible_version": MIN_COMPATIBLE_VERSION,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            return

        # Solo actualizar si la version actual es mayor
        stored_version = meta.get("app_version", "0.0.0")
        stored_tuple = tuple(
            int(x) for x in stored_version.split(".")
        ) if stored_version else (0, 0, 0)

        if APP_VERSION_TUPLE >= stored_tuple:
            db.app_meta.update_one(
                {"_id": "version_config"},
                {"$set": {
                    "app_version": APP_VERSION,
                    "min_compatible_version": MIN_COMPATIBLE_VERSION,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }}
            )
    except Exception:
        logger.warning("No se pudo actualizar version remota en Atlas", exc_info=True)


def close():
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
