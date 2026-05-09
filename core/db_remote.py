"""
Conexion a MongoDB Atlas (fuente de verdad central).
"""
import logging
import json
from pathlib import Path

import pymongo
from bson import json_util
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from config import MONGO_URI, MONGO_DB_NAME

logger = logging.getLogger(__name__)

_client: MongoClient | None = None
_db = None
SYNC_COLLECTIONS = [
    "usuarios", "consultas", "clientes", "expedientes",
    "tareas", "turnos", "comunicaciones", "movimientos", "documentos",
    "modelos_escrito", "escritos", "expediente_estado_historial", "audit_log",
    "notificaciones", "expediente_recordatorios", "expediente_etapa_responsables",
    "session_signals", "sync_conflicts", "citas",
    "migracion_requerimiento", "migracion_requerimiento_etapa", "migracion_requerimiento_historial",
]


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
    db.turnos.create_index("id_expediente")
    db.turnos.create_index("id_cliente")
    db.escritos.create_index("id_expediente")
    db.modelos_escrito.create_index("rama")
    db.expediente_estado_historial.create_index("id_expediente")
    db.expediente_estado_historial.create_index("responsable_username")
    db.expediente_estado_historial.create_index("encargado_username")
    db.notificaciones.create_index("target_username")
    db.notificaciones.create_index([("target_username", pymongo.ASCENDING), ("resuelta", pymongo.ASCENDING)])
    db.expediente_recordatorios.create_index([("notificar_a_username", pymongo.ASCENDING), ("fecha_disparo", pymongo.ASCENDING)])
    db.expediente_etapa_responsables.create_index([("id_expediente", pymongo.ASCENDING), ("etapa_codigo", pymongo.ASCENDING)], unique=True)
    db.citas.create_index("fecha_cita")
    db.citas.create_index("id_cliente")
    db.citas.create_index("id_expediente")
    db.migracion_requerimiento.create_index("id_expediente")
    db.migracion_requerimiento_etapa.create_index("id_requerimiento")
    db.migracion_requerimiento_historial.create_index("id_requerimiento")
    db.sync_conflicts.create_index("status")
    db.sync_conflicts.create_index([("table_name", pymongo.ASCENDING), ("record_id", pymongo.ASCENDING)])
    db.record_locks.create_index("expires_at", expireAfterSeconds=0)
    # updated_at indexes for sync
    for col_name in [
        "usuarios", "consultas", "clientes", "expedientes",
        "tareas", "turnos", "comunicaciones", "movimientos", "documentos",
        "modelos_escrito", "escritos", "expediente_estado_historial", "expediente_recordatorios",
        "expediente_etapa_responsables",
        "audit_log", "notificaciones", "sync_conflicts", "citas",
        "migracion_requerimiento", "migracion_requerimiento_etapa", "migracion_requerimiento_historial",
    ]:
        db[col_name].create_index("updated_at")


def get_remote_counts(collections: list[str] | None = None) -> dict[str, int]:
    db = get_db()
    result: dict[str, int] = {}
    for name in (collections or SYNC_COLLECTIONS):
        try:
            result[name] = db[name].count_documents({})
        except Exception:
            result[name] = -1
    return result


def export_sync_collections(export_dir: str, collections: list[str] | None = None) -> dict[str, int]:
    """Exporta colecciones Mongo a JSONL (una por archivo)."""
    db = get_db()
    out = Path(export_dir)
    out.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for name in (collections or SYNC_COLLECTIONS):
        file_path = out / f"{name}.jsonl"
        written = 0
        with file_path.open("w", encoding="utf-8") as fh:
            for doc in db[name].find({}):
                fh.write(json.dumps(doc, default=json_util.default, ensure_ascii=False) + "\n")
                written += 1
        counts[name] = written
    return counts


def import_sync_collections(import_dir: str, dry_run: bool = False, collections: list[str] | None = None) -> dict[str, int]:
    """Importa colecciones Mongo desde JSONL (replace por _id)."""
    db = get_db()
    base = Path(import_dir)
    counts: dict[str, int] = {}
    for name in (collections or SYNC_COLLECTIONS):
        file_path = base / f"{name}.jsonl"
        if not file_path.exists():
            counts[name] = 0
            continue
        applied = 0
        with file_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                doc = json.loads(line, object_hook=json_util.object_hook)
                if "_id" not in doc:
                    continue
                if not dry_run:
                    db[name].replace_one({"_id": doc["_id"]}, doc, upsert=True)
                applied += 1
        counts[name] = applied
    return counts


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
