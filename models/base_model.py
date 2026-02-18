"""
Clase base para todos los modelos.
Provee campos de sincronizacion y helpers comunes.
"""
import uuid
from datetime import datetime, timezone
from config import MACHINE_ID


def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def base_fields() -> dict:
    """Campos comunes para todo registro nuevo."""
    return {
        "_id": new_id(),
        "updated_at": now_iso(),
        "version": 1,
        "sync_status": "pending",
        "created_by_machine": MACHINE_ID,
    }
