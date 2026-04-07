"""CRUD de recordatorios / hitos por expediente."""
from controllers.base_controller import BaseController
from models.base_model import now_iso


class ExpedienteRecordatorioController(BaseController):
    TABLE = "expediente_recordatorios"
    ID_FIELD = ""

    @classmethod
    def list_by_expediente(cls, id_expediente: str) -> list[dict]:
        return cls.get_all(
            where="id_expediente = ?",
            params=(id_expediente,),
            order_by="fecha_disparo ASC",
        )

    @classmethod
    def create_for_expediente(cls, id_expediente: str, data: dict) -> dict:
        crit = data.get("es_critico", 0)
        try:
            crit_i = 1 if int(crit) else 0
        except (TypeError, ValueError):
            crit_i = 0
        payload = {
            "id_expediente": id_expediente,
            "fecha_disparo": (data.get("fecha_disparo") or "").strip()[:10],
            "titulo": (data.get("titulo") or "").strip(),
            "mensaje": (data.get("mensaje") or "").strip(),
            "notificar_a_username": (data.get("notificar_a_username") or "").strip(),
            "etapa_codigo": (data.get("etapa_codigo") or "").strip(),
            "es_critico": crit_i,
            "disparado_en": "",
            "creado_por_username": (data.get("creado_por_username") or "").strip(),
            "created_at": now_iso(),
        }
        return cls.create(payload)
