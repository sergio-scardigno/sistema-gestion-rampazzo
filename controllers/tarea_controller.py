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
