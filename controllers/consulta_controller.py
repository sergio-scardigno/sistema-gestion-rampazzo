"""Controlador de Consultas (CRM)."""
from controllers.base_controller import BaseController


class ConsultaController(BaseController):
    TABLE = "consultas"
    ID_FIELD = "id_consulta"

    CANALES = ["Instagram", "TikTok", "Facebook", "Web", "Telefono", "Presencial", "Referido"]
    ESTADOS = [
        "Nuevo", "En evaluacion", "Apto", "No viable",
        "Turno asignado", "Cerrado sin caso",
        "Convertido en cliente", "Convertido en expediente"
    ]

    @classmethod
    def search_consultas(cls, text: str) -> list[dict]:
        return cls.search(text, ["nombre", "dni", "telefono", "email", "motivo", "operador"])
