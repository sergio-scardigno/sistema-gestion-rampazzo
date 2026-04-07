"""Encargado secundario por etapa de flujo (responsable principal sigue en expedientes)."""
from controllers.base_controller import BaseController
from models.base_model import now_iso


class ExpedienteEtapaResponsableController(BaseController):
    TABLE = "expediente_etapa_responsables"
    ID_FIELD = ""

    @classmethod
    def list_by_expediente(cls, id_expediente: str) -> list[dict]:
        return cls.get_all(
            where="id_expediente = ?",
            params=(id_expediente,),
            order_by="etapa_codigo ASC",
        )

    @classmethod
    def upsert_encargado(
        cls,
        id_expediente: str,
        etapa_codigo: str,
        responsable_secundario_username: str,
    ) -> dict | None:
        """Crea o actualiza el encargado para una etapa. Si username vacio, elimina override."""
        etapa = (etapa_codigo or "").strip()
        if not etapa or not id_expediente:
            return None
        uname = (responsable_secundario_username or "").strip()
        existing = cls.get_all(
            where="id_expediente = ? AND etapa_codigo = ?",
            params=(id_expediente, etapa),
            limit=1,
        )
        if not uname:
            if existing:
                cls.delete(existing[0]["_id"])
            return None
        payload = {
            "id_expediente": id_expediente,
            "etapa_codigo": etapa,
            "responsable_secundario_username": uname,
        }
        if existing:
            return cls.update(existing[0]["_id"], payload)
        payload["created_at"] = now_iso()
        return cls.create(payload)
