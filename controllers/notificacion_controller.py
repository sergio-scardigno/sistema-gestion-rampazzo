"""Controlador de Notificaciones internas."""
from datetime import datetime, timezone

from core import db_local
from models.base_model import new_id
from config import MACHINE_ID


class NotificacionController:
    """Gestiona notificaciones persistentes dirigidas a usuarios."""

    @classmethod
    def create_for_tarea_asignada(cls, target_username: str, mensaje: str,
                                  id_referencia: str = "") -> dict:
        """Crear una notificacion de tarea asignada para un usuario."""
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "_id": new_id(),
            "target_username": target_username,
            "tipo": "tarea_asignada",
            "mensaje": mensaje,
            "id_referencia": id_referencia,
            "created_at": now,
            "leida": 0,
            "sync_status": "pending",
            "created_by_machine": MACHINE_ID,
        }
        db_local.insert("notificaciones", record)
        return record

    @classmethod
    def create_for_turno_asignado(cls, target_username: str, mensaje: str,
                                  id_referencia: str = "") -> dict:
        """Crear una notificacion de turno asignado para un usuario."""
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "_id": new_id(),
            "target_username": target_username,
            "tipo": "turno_asignado",
            "mensaje": mensaje,
            "id_referencia": id_referencia,
            "created_at": now,
            "leida": 0,
            "sync_status": "pending",
            "created_by_machine": MACHINE_ID,
        }
        db_local.insert("notificaciones", record)
        return record

    @classmethod
    def get_unread_for_user(cls, username: str, limit: int = 20) -> list[dict]:
        """Obtener notificaciones no leidas para un usuario."""
        return db_local.find_all(
            "notificaciones",
            where="target_username = ? AND leida = 0",
            params=(username,),
            order_by="created_at DESC",
            limit=limit,
        )

    @classmethod
    def mark_read(cls, _id: str):
        """Marcar una notificacion como leida."""
        db_local.update("notificaciones", _id, {"leida": 1})

    @classmethod
    def mark_all_read(cls, username: str):
        """Marcar todas las notificaciones de un usuario como leidas."""
        unread = cls.get_unread_for_user(username, limit=100)
        for n in unread:
            db_local.update("notificaciones", n["_id"], {"leida": 1})
