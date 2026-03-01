"""Controlador de Notificaciones internas."""
from datetime import datetime, timedelta, timezone

from core import db_local
from models.base_model import new_id
from config import MACHINE_ID

OPEN_STATES = ("Pendiente", "En curso", "En espera")
CLOSED_STATES = ("Cumplida", "Completada", "Cancelada")
TASK_ALERT_TYPES = ("tarea_asignada", "tarea_proxima_vencer")
POPUP_ALERT_TYPES = ("tarea_asignada", "tarea_proxima_vencer", "expediente_asignado")


class NotificacionController:
    """Gestiona notificaciones persistentes dirigidas a usuarios."""

    @classmethod
    def _supports_resolution_fields(cls) -> bool:
        return db_local.table_has_column("notificaciones", "resuelta")

    @classmethod
    def _supports_updated_at(cls) -> bool:
        return db_local.table_has_column("notificaciones", "updated_at")

    @classmethod
    def _now_iso(cls) -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def _base_record(
        cls,
        target_username: str,
        tipo: str,
        mensaje: str,
        id_referencia: str = "",
    ) -> dict:
        now = cls._now_iso()
        record = {
            "_id": new_id(),
            "target_username": target_username,
            "tipo": tipo,
            "mensaje": mensaje,
            "id_referencia": id_referencia,
            "created_at": now,
            "leida": 0,
            "sync_status": "pending",
            "created_by_machine": MACHINE_ID,
        }
        if cls._supports_resolution_fields():
            record["resuelta"] = 0
            record["fecha_resolucion"] = ""
            record["resuelta_por_estado"] = 0
        if cls._supports_updated_at():
            record["updated_at"] = now
        return record

    @classmethod
    def _upsert_task_notification(
        cls,
        target_username: str,
        tipo: str,
        mensaje: str,
        id_referencia: str,
    ) -> dict:
        where = "target_username = ? AND tipo = ? AND id_referencia = ?"
        params = [target_username, tipo, id_referencia]
        if cls._supports_resolution_fields():
            where += " AND (resuelta = 0 OR resuelta IS NULL)"
        existing = db_local.find_all(
            "notificaciones",
            where=where,
            params=tuple(params),
            order_by="created_at DESC",
            limit=1,
        )
        now = cls._now_iso()
        if existing:
            current = existing[0]
            was_read = int(current.get("leida", 0) or 0) == 1
            payload = {"mensaje": mensaje, "sync_status": "pending"}
            if cls._supports_resolution_fields():
                payload["resuelta"] = 0
                payload["fecha_resolucion"] = ""
                payload["resuelta_por_estado"] = 0
            # Si ya estaba leida, preservamos la lectura y su marca temporal.
            if not was_read:
                payload["leida"] = 0
            if cls._supports_updated_at() and not was_read:
                payload["updated_at"] = now
            db_local.update("notificaciones", current["_id"], payload)
            return db_local.find_by_id("notificaciones", current["_id"]) or current
        record = cls._base_record(target_username, tipo, mensaje, id_referencia=id_referencia)
        db_local.insert("notificaciones", record)
        return record

    @classmethod
    def create_for_tarea_asignada(
        cls, target_username: str, mensaje: str, id_referencia: str = ""
    ) -> dict:
        """Crear o refrescar una notificacion de tarea asignada."""
        if id_referencia:
            return cls._upsert_task_notification(
                target_username=target_username,
                tipo="tarea_asignada",
                mensaje=mensaje,
                id_referencia=id_referencia,
            )
        record = cls._base_record(target_username, "tarea_asignada", mensaje, id_referencia)
        db_local.insert("notificaciones", record)
        return record

    @classmethod
    def create_for_tarea_proxima_vencer(
        cls, target_username: str, mensaje: str, id_referencia: str
    ) -> dict:
        """Crear o refrescar una notificacion de tarea proxima a vencer."""
        return cls._upsert_task_notification(
            target_username=target_username,
            tipo="tarea_proxima_vencer",
            mensaje=mensaje,
            id_referencia=id_referencia,
        )

    @classmethod
    def create_for_turno_asignado(
        cls, target_username: str, mensaje: str, id_referencia: str = ""
    ) -> dict:
        """Crear una notificacion de turno asignado para un usuario."""
        record = cls._base_record(target_username, "turno_asignado", mensaje, id_referencia)
        db_local.insert("notificaciones", record)
        return record

    @classmethod
    def create_for_expediente_asignado(
        cls, target_username: str, mensaje: str, id_referencia: str
    ) -> dict:
        """Crear o refrescar una notificacion de expediente asignado."""
        return cls._upsert_task_notification(
            target_username=target_username,
            tipo="expediente_asignado",
            mensaje=mensaje,
            id_referencia=id_referencia,
        )

    @classmethod
    def get_unread_for_user(cls, username: str, limit: int = 20) -> list[dict]:
        """Obtener notificaciones activas y no leidas para un usuario."""
        where = "target_username = ? AND leida = 0"
        if cls._supports_resolution_fields():
            where += " AND (resuelta = 0 OR resuelta IS NULL)"
        return db_local.find_all(
            "notificaciones",
            where=where,
            params=(username,),
            order_by="created_at DESC",
            limit=limit,
        )

    @classmethod
    def get_active_for_user(cls, username: str, limit: int = 20) -> list[dict]:
        """Obtener notificaciones activas (leidas o no) para campana."""
        where = "target_username = ?"
        if cls._supports_resolution_fields():
            where += " AND (resuelta = 0 OR resuelta IS NULL)"
        return db_local.find_all(
            "notificaciones",
            where=where,
            params=(username,),
            order_by="created_at DESC",
            limit=limit,
        )

    @classmethod
    def mark_read(cls, _id: str):
        """Marcar una notificacion como leida."""
        payload = {"leida": 1, "sync_status": "pending"}
        if cls._supports_updated_at():
            payload["updated_at"] = cls._now_iso()
        db_local.update("notificaciones", _id, payload)

    @classmethod
    def mark_all_read(cls, username: str):
        """Marcar todas las notificaciones activas de un usuario como leidas."""
        active = cls.get_active_for_user(username, limit=200)
        for n in active:
            cls.mark_read(n["_id"])

    @classmethod
    def resolve_for_tarea(cls, tarea_id: str, resolved_by_status: bool = True):
        """Resolver alertas de una tarea cuando pasa a estado cerrado."""
        if not tarea_id:
            return
        if not cls._supports_resolution_fields():
            # Compatibilidad con esquemas viejos: al menos la marca como leida.
            with db_local.get_cursor() as cur:
                cur.execute(
                    "UPDATE notificaciones SET leida = 1, sync_status = 'pending' "
                    "WHERE id_referencia = ? AND tipo IN (?, ?)",
                    (tarea_id, TASK_ALERT_TYPES[0], TASK_ALERT_TYPES[1]),
                )
            return
        now = cls._now_iso()
        with db_local.get_cursor() as cur:
            set_parts = [
                "resuelta = 1",
                "fecha_resolucion = ?",
                "resuelta_por_estado = ?",
                "sync_status = 'pending'",
            ]
            params = [now, 1 if resolved_by_status else 0]
            if cls._supports_updated_at():
                set_parts.append("updated_at = ?")
                params.append(now)
            params.extend([tarea_id, TASK_ALERT_TYPES[0], TASK_ALERT_TYPES[1]])
            cur.execute(
                "UPDATE notificaciones SET "
                + ", ".join(set_parts)
                + " WHERE id_referencia = ? AND tipo IN (?, ?) AND (resuelta = 0 OR resuelta IS NULL)",
                tuple(params),
            )

    @classmethod
    def sync_task_alerts_for_user(cls, username: str, due_days: int = 3):
        """Sincroniza alertas de tareas asignadas y proximas a vencer para login/campana."""
        from controllers.tarea_controller import TareaController

        if not username:
            return
        today = datetime.now().strftime("%Y-%m-%d")
        limit_day = (datetime.now() + timedelta(days=max(1, due_days))).strftime("%Y-%m-%d")
        assigned = TareaController.get_all(
            where="responsable_username = ? AND estado IN ('Pendiente','En curso','En espera')",
            params=(username,),
            order_by="fecha_vencimiento ASC",
        )
        due_soon = TareaController.get_all(
            where=(
                "responsable_username = ? AND estado IN ('Pendiente','En curso','En espera') "
                "AND fecha_vencimiento >= ? AND fecha_vencimiento <= ?"
            ),
            params=(username, today, limit_day),
            order_by="fecha_vencimiento ASC",
        )
        for t in assigned:
            desc = (t.get("descripcion", "") or "").strip()
            desc_short = desc[:70] + ("..." if len(desc) > 70 else "")
            msg = f"Tarea asignada pendiente: {desc_short}"
            cls.create_for_tarea_asignada(username, msg, id_referencia=t.get("_id", ""))
        for t in due_soon:
            desc = (t.get("descripcion", "") or "").strip()
            desc_short = desc[:70] + ("..." if len(desc) > 70 else "")
            venc = t.get("fecha_vencimiento", "")
            msg = f"Tarea proxima a vencer ({venc}): {desc_short}"
            cls.create_for_tarea_proxima_vencer(username, msg, id_referencia=t.get("_id", ""))

        cls.resolve_closed_task_alerts(username)

    @classmethod
    def resolve_closed_task_alerts(cls, username: str):
        """Resuelve notificaciones activas de tareas cerradas o inexistentes."""
        from controllers.tarea_controller import TareaController

        active = cls.get_active_for_user(username, limit=300)
        for notif in active:
            if notif.get("tipo") not in TASK_ALERT_TYPES:
                continue
            task_id = notif.get("id_referencia", "")
            if not task_id:
                continue
            tarea = TareaController.get_by_id(task_id)
            if not tarea or tarea.get("estado") in CLOSED_STATES:
                cls.resolve_for_tarea(task_id, resolved_by_status=True)

    @classmethod
    def get_login_popup_notifications(cls, username: str, due_days: int = 3, limit: int = 20) -> list[dict]:
        """Devuelve alertas activas para mostrar en popup de inicio de sesion."""
        cls.sync_task_alerts_for_user(username, due_days=due_days)
        active = cls.get_active_for_user(username, limit=limit)
        return [n for n in active if n.get("tipo") in POPUP_ALERT_TYPES]
