"""
Bloqueo pesimista de registros en MongoDB Atlas.
Cuando un usuario quiere editar, se solicita un bloqueo que expira en 15 min.
"""
import logging
from datetime import datetime, timezone, timedelta
from core.db_remote import is_connected, get_db
from core.auth import Session
from config import LOCK_EXPIRY_MINUTES

logger = logging.getLogger(__name__)


class LockManager:

    @staticmethod
    def acquire_lock(coleccion: str, documento_id: str) -> tuple[bool, str]:
        """
        Intentar bloquear un registro.
        Returns: (exito, mensaje)
        """
        if not is_connected():
            return False, "Sin conexion - no se puede bloquear para edicion"

        session = Session.get()
        username = session.username
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=LOCK_EXPIRY_MINUTES)

        db = get_db()
        locks = db.record_locks

        # Check existing lock
        existing = locks.find_one({
            "coleccion": coleccion,
            "documento_id": documento_id,
            "expires_at": {"$gt": now.isoformat()}
        })

        if existing:
            if existing.get("locked_by") == username:
                # Refresh own lock
                locks.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {"expires_at": expires.isoformat()}}
                )
                return True, "Bloqueo renovado"
            else:
                locked_by = existing.get("locked_by", "otro usuario")
                wait_msg = ""
                expires_at_raw = existing.get("expires_at", "")
                if expires_at_raw:
                    try:
                        expires_at = datetime.fromisoformat(expires_at_raw)
                        remaining = max(0, int((expires_at - now).total_seconds()))
                        mins = remaining // 60
                        secs = remaining % 60
                        if mins > 0:
                            wait_msg = f" Espere aproximadamente {mins} min {secs:02d} s."
                        else:
                            wait_msg = f" Espere aproximadamente {secs} s."
                    except Exception:
                        wait_msg = ""
                return (
                    False,
                    f'La carpeta esta bloqueada porque el usuario "{locked_by}" '
                    f"esta trabajando sobre ella.{wait_msg}"
                )

        # Create new lock
        try:
            locks.insert_one({
                "coleccion": coleccion,
                "documento_id": documento_id,
                "locked_by": username,
                "locked_at": now.isoformat(),
                "expires_at": expires.isoformat(),
            })
            return True, "Bloqueo adquirido"
        except Exception as e:
            logger.exception("Error al adquirir bloqueo: %s/%s", coleccion, documento_id)
            return False, f"Error al bloquear: {e}"

    @staticmethod
    def release_lock(coleccion: str, documento_id: str):
        """Liberar bloqueo de un registro."""
        if not is_connected():
            return
        try:
            db = get_db()
            session = Session.get()
            db.record_locks.delete_many({
                "coleccion": coleccion,
                "documento_id": documento_id,
                "locked_by": session.username,
            })
        except Exception:
            logger.warning("Error al liberar bloqueo: %s/%s", coleccion, documento_id, exc_info=True)

    @staticmethod
    def is_locked(coleccion: str, documento_id: str) -> tuple[bool, str]:
        """
        Verificar si un registro esta bloqueado.
        Returns: (esta_bloqueado, bloqueado_por)
        """
        if not is_connected():
            return False, ""
        try:
            db = get_db()
            now = datetime.now(timezone.utc).isoformat()
            lock = db.record_locks.find_one({
                "coleccion": coleccion,
                "documento_id": documento_id,
                "expires_at": {"$gt": now}
            })
            if lock:
                return True, lock.get("locked_by", "desconocido")
            return False, ""
        except Exception:
            logger.warning("Error al verificar bloqueo: %s/%s", coleccion, documento_id, exc_info=True)
            return False, ""

    @staticmethod
    def cleanup_expired():
        """Limpiar locks expirados (se llama periodicamente)."""
        if not is_connected():
            return
        try:
            db = get_db()
            now = datetime.now(timezone.utc).isoformat()
            db.record_locks.delete_many({"expires_at": {"$lt": now}})
        except Exception:
            logger.warning("Error al limpiar bloqueos expirados", exc_info=True)
