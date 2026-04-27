"""Controlador de Citas del estudio."""
from datetime import datetime, timedelta

from controllers.base_controller import BaseController


class CitaController(BaseController):
    TABLE = "citas"
    ID_FIELD = "id_cita"

    ESTADOS = [
        "Pendiente", "Confirmada", "Asistio",
        "No asistio", "Cancelada",
    ]

    @classmethod
    def get_by_fecha(cls, fecha: str) -> list[dict]:
        """Obtener todas las citas de una fecha (YYYY-MM-DD)."""
        return cls.get_all(
            where="fecha_cita = ?", params=(fecha,),
            order_by="hora_cita ASC"
        )

    @classmethod
    def get_hoy(cls) -> list[dict]:
        """Obtener citas del dia actual."""
        today = datetime.now().strftime("%Y-%m-%d")
        return cls.get_by_fecha(today)

    @classmethod
    def get_by_cliente(cls, id_cliente: str) -> list[dict]:
        """Obtener todas las citas de un cliente."""
        return cls.get_all(
            where="id_cliente = ?", params=(id_cliente,),
            order_by="fecha_cita DESC, hora_cita DESC"
        )

    @classmethod
    def get_by_expediente(cls, id_expediente: str) -> list[dict]:
        """Obtener todas las citas de un expediente/carpeta."""
        return cls.get_all(
            where="id_expediente = ?", params=(id_expediente,),
            order_by="fecha_cita DESC, hora_cita DESC"
        )

    @classmethod
    def tiene_cita_pendiente(cls, id_expediente: str) -> bool:
        """True si hay al menos una cita Pendiente o Confirmada vinculada a la carpeta."""
        if not (id_expediente or "").strip():
            return False
        rows = cls.get_all(
            where="id_expediente = ? AND estado IN ('Pendiente','Confirmada')",
            params=(id_expediente.strip(),),
            limit=1,
        )
        return bool(rows)

    @classmethod
    def get_proximas(cls, dias: int = 7) -> list[dict]:
        """Obtener citas futuras dentro de los proximos N dias."""
        today = datetime.now().strftime("%Y-%m-%d")
        limit_date = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
        return cls.get_all(
            where="fecha_cita >= ? AND fecha_cita <= ? AND estado IN ('Pendiente','Confirmada')",
            params=(today, limit_date),
            order_by="fecha_cita ASC, hora_cita ASC"
        )

    @classmethod
    def marcar_asistio(cls, _id: str) -> dict | None:
        """Cambiar estado a Asistio."""
        return cls.update(_id, {"estado": "Asistio"})

    @classmethod
    def marcar_no_asistio(cls, _id: str) -> dict | None:
        """Cambiar estado a No asistio."""
        return cls.update(_id, {"estado": "No asistio"})

    @classmethod
    def cancelar(cls, _id: str) -> dict | None:
        """Cambiar estado a Cancelada."""
        return cls.update(_id, {"estado": "Cancelada"})
