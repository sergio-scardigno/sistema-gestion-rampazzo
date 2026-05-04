"""Controlador de Notificaciones internas."""
from datetime import datetime, timedelta, timezone

from core import db_local
from models.base_model import new_id
from config import MACHINE_ID

OPEN_STATES = ("Pendiente", "En curso", "En espera")
CLOSED_STATES = ("Cumplida", "Completada", "Cancelada")
TASK_ALERT_TYPES = ("tarea_asignada", "tarea_proxima_vencer")
POPUP_ALERT_TYPES = (
    "tarea_asignada",
    "tarea_proxima_vencer",
    "expediente_asignado",
    "expediente_etapa_encargado",
    "recordatorio_expediente",
    "expediente_observacion_equipo",
    "expediente_estado_cambiado",
)

DISMISSIBLE_TYPES = (
    "expediente_asignado",
    "turno_asignado",
    "expediente_etapa_encargado",
    "recordatorio_expediente",
    "expediente_observacion_equipo",
    "expediente_estado_cambiado",
    "tarea_asignada",
    "tarea_proxima_vencer",
)

# Solo estos dejan de contar en el badge al abrir el popup (sin tocar la BD).
BADGE_HIDE_ON_VIEW_TYPES = ("expediente_asignado", "turno_asignado")

BADGE_PERSIST_WHEN_READ_TYPES = TASK_ALERT_TYPES

NOTIF_STYLES = {
    "tarea_asignada": {
        "bg": "#e8f0fe",
        "border": "#2d6bcf",
        "icon": "\u2611",
        "icon_color": "#2d6bcf",
        "label": "TAREA",
    },
    "tarea_proxima_vencer": {
        "bg": "#fdecea",
        "border": "#d32f2f",
        "icon": "\u23F1",
        "icon_color": "#d32f2f",
        "label": "VENCE",
    },
    "expediente_etapa_encargado": {
        "bg": "#e6f5f3",
        "border": "#0d9488",
        "icon": "\u2699",
        "icon_color": "#0d9488",
        "label": "ETAPA",
    },
    "recordatorio_expediente": {
        "bg": "#fee2e2",
        "border": "#991b1b",
        "icon": "\u26A0",
        "icon_color": "#991b1b",
        "label": "RECORD.",
    },
    "expediente_asignado": {
        "bg": "#f0ebfa",
        "border": "#7b5cd6",
        "icon": "\u2630",
        "icon_color": "#7b5cd6",
        "label": "CARPETA",
    },
    "turno_asignado": {
        "bg": "#fef7e0",
        "border": "#c9a84c",
        "icon": "\u23F0",
        "icon_color": "#c9a84c",
        "label": "TURNO",
    },
    "expediente_observacion_equipo": {
        "bg": "#eef6ff",
        "border": "#2563eb",
        "icon": "\u270D",
        "icon_color": "#2563eb",
        "label": "OBS.",
    },
    "expediente_estado_cambiado": {
        "bg": "#f0fdf4",
        "border": "#15803d",
        "icon": "\u21BB",
        "icon_color": "#15803d",
        "label": "ESTADO",
    },
}
_DEFAULT_NOTIF_STYLE = {
    "bg": "#eef2f7",
    "border": "#374151",
    "icon": "\u2139",
    "icon_color": "#374151",
    "label": "ALERTA",
}


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
        # No reactivar filas descartadas manualmente (resuelta=1, resuelta_por_estado=0).
        if cls._supports_resolution_fields() and id_referencia:
            dismissed = db_local.find_all(
                "notificaciones",
                where=(
                    "target_username = ? AND tipo = ? AND id_referencia = ? "
                    "AND resuelta = 1 AND (resuelta_por_estado = 0 OR resuelta_por_estado IS NULL)"
                ),
                params=(target_username, tipo, id_referencia),
                order_by="created_at DESC",
                limit=1,
            )
            if dismissed:
                return dismissed[0]
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
    def create_for_expediente_etapa_encargado(
        cls, target_username: str, mensaje: str, id_referencia: str
    ) -> dict:
        """Crear o refrescar notificacion al encargado por cambio de etapa."""
        return cls._upsert_task_notification(
            target_username=target_username,
            tipo="expediente_etapa_encargado",
            mensaje=mensaje,
            id_referencia=id_referencia,
        )

    @classmethod
    def create_for_recordatorio_expediente(
        cls,
        target_username: str,
        mensaje: str,
        id_referencia: str,
        *,
        force_new: bool = False,
    ) -> dict:
        """Crear o refrescar recordatorio programado de expediente."""
        if force_new:
            record = cls._base_record(
                target_username,
                "recordatorio_expediente",
                mensaje,
                id_referencia,
            )
            db_local.insert("notificaciones", record)
            return record
        return cls._upsert_task_notification(
            target_username=target_username,
            tipo="recordatorio_expediente",
            mensaje=mensaje,
            id_referencia=id_referencia,
        )

    @classmethod
    def create_for_expediente_observacion_equipo(
        cls, target_username: str, mensaje: str, id_referencia: str
    ) -> dict:
        """Crear o refrescar notificacion por observacion al equipo en carpeta."""
        return cls._upsert_task_notification(
            target_username=target_username,
            tipo="expediente_observacion_equipo",
            mensaje=mensaje,
            id_referencia=id_referencia,
        )

    @classmethod
    def create_for_expediente_estado_cambiado(
        cls, target_username: str, mensaje: str, id_referencia: str
    ) -> dict:
        """Crear o refrescar notificacion por cambio de estado/etapa en carpeta."""
        return cls._upsert_task_notification(
            target_username=target_username,
            tipo="expediente_estado_cambiado",
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
    def get_recent_for_user(cls, username: str, limit: int = 100) -> list[dict]:
        """Obtener historial reciente (activas + resueltas) para un usuario."""
        if not username:
            return []
        return db_local.find_all(
            "notificaciones",
            where="target_username = ?",
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
    def dismiss_notification(cls, _id: str, username: str) -> bool:
        """Marca una notificacion como resuelta por el usuario (no vuelve a mostrarse).

        Usa resuelta=1 y resuelta_por_estado=0 para distinguir del cierre automatico
        por estado de tarea (resuelta_por_estado=1).
        """
        if not _id or not username:
            return False
        row = db_local.find_by_id("notificaciones", _id)
        if not row or (row.get("target_username") or "") != username:
            return False
        tipo = row.get("tipo", "")
        if tipo not in DISMISSIBLE_TYPES:
            return False
        now = cls._now_iso()
        if cls._supports_resolution_fields():
            payload = {
                "resuelta": 1,
                "fecha_resolucion": now,
                "resuelta_por_estado": 0,
                "leida": 1,
                "sync_status": "pending",
            }
            if cls._supports_updated_at():
                payload["updated_at"] = now
            db_local.update("notificaciones", _id, payload)
        else:
            cls.mark_read(_id)
        return True

    @classmethod
    def dismiss_by_type_and_ref(
        cls, username: str, tipo: str, id_referencia: str
    ) -> int:
        """Descarta todas las notificaciones activas que coincidan con tipo y referencia."""
        if not username or tipo not in DISMISSIBLE_TYPES:
            return 0
        where = "target_username = ? AND tipo = ? AND id_referencia = ?"
        params: list = [username, tipo, id_referencia or ""]
        if cls._supports_resolution_fields():
            where += " AND (resuelta = 0 OR resuelta IS NULL)"
        rows = db_local.find_all(
            "notificaciones",
            where=where,
            params=tuple(params),
            limit=50,
        )
        count = 0
        for n in rows:
            if cls.dismiss_notification(n.get("_id", ""), username):
                count += 1
        return count

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
    def sync_task_alerts_for_user(cls, username: str, due_days: int = 30):
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
    def get_login_popup_notifications(cls, username: str, due_days: int = 30, limit: int = 20) -> list[dict]:
        """Devuelve alertas activas para mostrar en popup de inicio de sesion.

        Se usa un pool amplio en BD: si solo se pidieran las ultimas 20 notificaciones,
        las de tarea (muy frecuentes tras sync) dejaban fuera designaciones de carpeta.
        """
        cls.sync_task_alerts_for_user(username, due_days=due_days)
        pool_limit = max(limit * 25, 200)
        active = cls.get_active_for_user(username, limit=pool_limit)
        popup = [n for n in active if n.get("tipo") in POPUP_ALERT_TYPES]
        carpeta_tipos = {
            "expediente_asignado",
            "expediente_etapa_encargado",
            "recordatorio_expediente",
        }
        carpeta = [n for n in popup if n.get("tipo") in carpeta_tipos]
        tareas = [n for n in popup if n.get("tipo") not in carpeta_tipos]
        carpeta.sort(key=lambda n: n.get("created_at", "") or "", reverse=True)
        tareas.sort(key=lambda n: n.get("created_at", "") or "", reverse=True)
        merged = carpeta + tareas
        return merged[:limit]
