"""Controlador de Comunicaciones."""
from controllers.base_controller import BaseController


class ComunicacionController(BaseController):
    TABLE = "comunicaciones"
    ID_FIELD = "id_comunicacion"

    CANALES = ["WhatsApp", "Llamada", "Mail", "Presencial", "Videollamada"]

    @classmethod
    def get_by_expediente(cls, id_expediente: str) -> list[dict]:
        return cls.get_all(where="id_expediente = ?", params=(id_expediente,),
                           order_by="fecha DESC")
