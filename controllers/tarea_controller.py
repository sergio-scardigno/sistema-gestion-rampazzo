"""Controlador de Tareas / Seguimiento."""
from controllers.base_controller import BaseController


class TareaController(BaseController):
    TABLE = "tareas"
    ID_FIELD = "id_tarea"

    ESTADOS = ["Pendiente", "En curso", "En espera", "Cumplida", "Cancelada"]
    TIPOS_ACCION = [
        "Turno ANSES", "Inicio virtual", "Presentacion documental",
        "Seguimiento expediente", "Notificacion", "Reclamo",
        "Audiencia", "Pericia", "Otro"
    ]

    @classmethod
    def get_by_expediente(cls, id_expediente: str) -> list[dict]:
        return cls.get_all(where="id_expediente = ?", params=(id_expediente,),
                           order_by="fecha_vencimiento ASC")

    @classmethod
    def get_by_migracion_requerimiento(cls, id_migracion_requerimiento: str) -> list[dict]:
        mid = (id_migracion_requerimiento or "").strip()
        if not mid:
            return []
        return cls.get_all(
            where="id_migracion_requerimiento = ?",
            params=(mid,),
            order_by="fecha_vencimiento ASC",
        )

    @classmethod
    def get_pendientes(cls, responsable: str = "") -> list[dict]:
        if responsable:
            return cls.get_all(
                where="estado IN ('Pendiente','En curso','En espera') AND responsable = ?",
                params=(responsable,), order_by="fecha_vencimiento ASC"
            )
        return cls.get_all(
            where="estado IN ('Pendiente','En curso','En espera')",
            order_by="fecha_vencimiento ASC"
        )

    @classmethod
    def get_vencidas(cls) -> list[dict]:
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        return cls.get_all(
            where="estado IN ('Pendiente','En curso') AND fecha_vencimiento < ?",
            params=(today,), order_by="fecha_vencimiento ASC"
        )

    @classmethod
    def get_proximas_a_vencer(cls, dias: int = 3, responsable_username: str = "") -> list[dict]:
        from datetime import datetime, timedelta

        hoy = datetime.now().strftime("%Y-%m-%d")
        limite = (datetime.now() + timedelta(days=max(1, dias))).strftime("%Y-%m-%d")
        where = (
            "estado IN ('Pendiente','En curso','En espera') "
            "AND fecha_vencimiento >= ? AND fecha_vencimiento <= ?"
        )
        params: tuple = (hoy, limite)
        if responsable_username:
            where += " AND responsable_username = ?"
            params = (hoy, limite, responsable_username)
        return cls.get_all(where=where, params=params, order_by="fecha_vencimiento ASC")

    @classmethod
    def update(cls, _id: str, data: dict) -> dict | None:
        """Actualizar tarea y resolver alertas cuando pasa a estado cerrado."""
        existing = cls.get_by_id(_id)
        updated = super().update(_id, data)
        if not updated:
            return None

        estado_old = (existing or {}).get("estado", "")
        estado_new = updated.get("estado", "")
        if estado_new in ("Cumplida", "Completada", "Cancelada") and estado_old != estado_new:
            from controllers.notificacion_controller import NotificacionController
            NotificacionController.resolve_for_tarea(_id, resolved_by_status=True)
        return updated
