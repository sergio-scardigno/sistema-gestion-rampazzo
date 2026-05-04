"""CRUD de recordatorios / hitos por expediente."""
import re
from datetime import date, timedelta
from controllers.base_controller import BaseController
from models.base_model import now_iso


class ExpedienteRecordatorioController(BaseController):
    TABLE = "expediente_recordatorios"
    ID_FIELD = ""
    @classmethod
    def _tema_to_key(cls, tema: str) -> str:
        txt = (tema or "").strip().lower()
        txt = (
            txt.replace("á", "a")
            .replace("é", "e")
            .replace("í", "i")
            .replace("ó", "o")
            .replace("ú", "u")
            .replace("ü", "u")
            .replace("ñ", "n")
        )
        txt = re.sub(r"[^a-z0-9]+", "_", txt).strip("_")
        return txt or "tema_general"

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
            "origen": (data.get("origen") or "manual").strip() or "manual",
            "template_key": (data.get("template_key") or "").strip(),
            "estado_plazo": (data.get("estado_plazo") or "activo").strip() or "activo",
            "pospuesto_hasta": (data.get("pospuesto_hasta") or "").strip()[:10],
            "ultimo_aviso_nivel": "",
            "ultimo_aviso_fecha": "",
            "disparado_en": "",
            "creado_por_username": (data.get("creado_por_username") or "").strip(),
            "created_at": now_iso(),
        }
        return cls.create(payload)

    @classmethod
    def marcar_resuelto(cls, rec_id: str) -> dict | None:
        return cls.update(
            rec_id,
            {
                "estado_plazo": "resuelto",
                "disparado_en": now_iso(),
            },
        )

    @classmethod
    def posponer_dias(cls, rec_id: str, dias: int) -> dict | None:
        from datetime import date, timedelta

        rec = cls.get_by_id(rec_id)
        if not rec:
            return None
        base = (rec.get("fecha_disparo") or "")[:10]
        if len(base) != 10:
            return None
        ref = date.fromisoformat(base)
        nueva = (ref + timedelta(days=max(1, int(dias)))).isoformat()
        return cls.update(
            rec_id,
            {
                "fecha_disparo": nueva,
                "pospuesto_hasta": nueva,
                "estado_plazo": "pospuesto",
                "ultimo_aviso_nivel": "",
                "ultimo_aviso_fecha": "",
            },
        )

    @classmethod
    def generar_plantilla_req_migraciones(
        cls,
        id_expediente: str,
        tema: str,
        fecha_vencimiento: str,
        creado_por_username: str = "",
    ) -> dict:
        if not id_expediente:
            return {"creados": 0, "omitidos": 0, "tema_key": ""}
        tema_key = cls._tema_to_key(tema)
        fv = (fecha_vencimiento or "").strip()[:10]
        if len(fv) != 10:
            return {"creados": 0, "omitidos": 0, "tema_key": tema_key}
        venc = date.fromisoformat(fv)
        alarma_critica = (venc - timedelta(days=2)).isoformat()

        plan = [
            {
                "template_key": f"migraciones:{tema_key}:alarma_soft",
                "fecha_disparo": fv,
                "titulo": "Vencimiento",
                "mensaje": f"Vence tramite migratorio ({tema}).",
                "es_critico": 0,
            },
            {
                "template_key": f"migraciones:{tema_key}:alarma_critica_2dias",
                "fecha_disparo": alarma_critica,
                "titulo": "Alarma critica - 2 dias",
                "mensaje": f"Faltan 2 dias para el vencimiento ({tema}).",
                "es_critico": 1,
            },
        ]

        existentes = cls.get_all(
            where="id_expediente = ? AND origen = ? AND template_key IN (?, ?)",
            params=(
                id_expediente,
                "plantilla_migraciones",
                plan[0]["template_key"],
                plan[1]["template_key"],
            ),
            limit=20,
        )
        existing_by_key = {(r.get("template_key") or "").strip(): r for r in existentes}
        creados = 0
        omitidos = 0
        for item in plan:
            existing = existing_by_key.get(item["template_key"])
            if existing:
                cls.update(
                    existing["_id"],
                    {
                        "fecha_disparo": item["fecha_disparo"],
                        "titulo": item["titulo"],
                        "mensaje": item["mensaje"],
                        "es_critico": item["es_critico"],
                        "estado_plazo": "activo",
                        "disparado_en": "",
                        "ultimo_aviso_nivel": "",
                        "ultimo_aviso_fecha": "",
                    },
                )
                continue
            cls.create_for_expediente(
                id_expediente,
                {
                    "fecha_disparo": item["fecha_disparo"],
                    "titulo": item["titulo"],
                    "mensaje": item["mensaje"],
                    "notificar_a_username": "",
                    "etapa_codigo": "req_migraciones",
                    "es_critico": item["es_critico"],
                    "origen": "plantilla_migraciones",
                    "template_key": item["template_key"],
                    "estado_plazo": "activo",
                    "creado_por_username": creado_por_username,
                },
            )
            creados += 1
        omitidos = 2 - creados
        return {"creados": creados, "omitidos": max(0, omitidos), "tema_key": tema_key}
