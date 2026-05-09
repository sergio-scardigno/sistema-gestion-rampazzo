"""Requerimientos de migracion por carpeta (expediente padre), con etapas internas y trazabilidad."""
from __future__ import annotations

import json
import logging
import re
from datetime import date

from controllers.base_controller import BaseController
from controllers.expediente_controller import ExpedienteController
from controllers.expediente_recordatorio_controller import ExpedienteRecordatorioController
from core import db_local
from core.auth import Session
from models.base_model import now_iso

logger = logging.getLogger(__name__)

ESTADOS_CICLO = frozenset({"iniciado", "finalizado"})
ESTADOS_AVANCE_ETAPA = frozenset({"pendiente", "en_curso", "hecho"})


def _slug_codigo(texto: str) -> str:
    t = (texto or "").strip().lower()
    for a, b in (
        ("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n"),
    ):
        t = t.replace(a, b)
    t = re.sub(r"[^a-z0-9]+", "_", t).strip("_")
    return t or "etapa"


def _fmt_fecha_chequeo(fecha_iso: str | None, hoy: date) -> str:
    """Etiqueta para listados operativos (vencimiento etapa o alarma recordatorio)."""
    s = (fecha_iso or "").strip()[:10]
    if len(s) != 10:
        return ""
    try:
        d = date.fromisoformat(s)
    except ValueError:
        return s
    if d < hoy:
        return f"{s} (vencido)"
    if d == hoy:
        return f"{s} (hoy)"
    return s


def _sort_key_fecha_label(label: str) -> str:
    if not (label or "").strip():
        return "9999-99-99"
    t = label.replace(" (vencido)", "").replace(" (hoy)", "")[:10]
    return t if len(t) == 10 else "9999-99-99"


class MigracionRequerimientoHistorialController(BaseController):
    TABLE = "migracion_requerimiento_historial"
    ID_FIELD = ""

    @classmethod
    def registrar(
        cls,
        id_requerimiento: str,
        evento_tipo: str,
        *,
        id_etapa: str = "",
        detalle: str | dict = "",
        usuario: str = "",
    ) -> dict:
        if isinstance(detalle, dict):
            detalle = json.dumps(detalle, ensure_ascii=False)
        payload = {
            "id_requerimiento": id_requerimiento,
            "evento_tipo": (evento_tipo or "").strip(),
            "id_etapa": (id_etapa or "").strip(),
            "detalle": (detalle or "").strip(),
            "usuario": (usuario or "").strip(),
            "created_at": now_iso(),
        }
        return cls.create(payload)


class MigracionRequerimientoEtapaController(BaseController):
    TABLE = "migracion_requerimiento_etapa"
    ID_FIELD = "id_migracion_etapa"

    @classmethod
    def list_by_requerimiento(cls, id_requerimiento: str) -> list[dict]:
        return cls.get_all(
            where="id_requerimiento = ?",
            params=(id_requerimiento,),
            order_by="orden ASC, titulo ASC",
        )

    @classmethod
    def _requerimiento_editable(cls, id_requerimiento: str) -> dict | None:
        req = MigracionRequerimientoController.get_by_id(id_requerimiento)
        if not req:
            return None
        if (req.get("estado_ciclo") or "").strip() == "finalizado":
            return None
        return req

    @classmethod
    def create(cls, data: dict) -> dict | None:
        id_req = (data.get("id_requerimiento") or "").strip()
        if not cls._requerimiento_editable(id_req):
            return None
        titulo = (data.get("titulo") or "").strip() or "Etapa"
        codigo = (data.get("codigo") or "").strip() or _slug_codigo(titulo)
        orden = data.get("orden", 0)
        try:
            orden_i = int(orden)
        except (TypeError, ValueError):
            orden_i = 0
        avance = (data.get("estado_avance") or "pendiente").strip() or "pendiente"
        if avance not in ESTADOS_AVANCE_ETAPA:
            avance = "pendiente"
        payload = {
            "id_requerimiento": id_req,
            "codigo": codigo,
            "titulo": titulo,
            "orden": orden_i,
            "fecha_vencimiento": (data.get("fecha_vencimiento") or "").strip()[:10],
            "estado_avance": avance,
            "notas": (data.get("notas") or "").strip(),
            "created_at": now_iso(),
        }
        record = super().create(payload)
        session = Session.get()
        MigracionRequerimientoHistorialController.registrar(
            id_req,
            "etapa_alta",
            id_etapa=record.get("_id", ""),
            detalle={"titulo": titulo, "codigo": codigo},
            usuario=session.username if session.logged_in else "",
        )
        MigracionRequerimientoController.sincronizar_recordatorio_vencimiento_etapa(record.get("_id", ""))
        return record

    @classmethod
    def update(cls, _id: str, data: dict) -> dict | None:
        existing = cls.get_by_id(_id)
        if not existing:
            return None
        id_req = (existing.get("id_requerimiento") or "").strip()
        if not cls._requerimiento_editable(id_req):
            return None
        if "estado_avance" in data:
            av = (data.get("estado_avance") or "").strip() or "pendiente"
            if av not in ESTADOS_AVANCE_ETAPA:
                data = {**data, "estado_avance": "pendiente"}
        before = {
            "titulo": existing.get("titulo"),
            "fecha_vencimiento": existing.get("fecha_vencimiento"),
            "estado_avance": existing.get("estado_avance"),
        }
        result = super().update(_id, data)
        if result:
            session = Session.get()
            MigracionRequerimientoHistorialController.registrar(
                id_req,
                "etapa_actualizada",
                id_etapa=_id,
                detalle={"antes": before, "despues": {k: result.get(k) for k in before}},
                usuario=session.username if session.logged_in else "",
            )
            MigracionRequerimientoController.sincronizar_recordatorio_vencimiento_etapa(_id)
        return result

    @classmethod
    def delete(cls, _id: str) -> bool:
        existing = cls.get_by_id(_id)
        if not existing:
            return False
        id_req = (existing.get("id_requerimiento") or "").strip()
        if not cls._requerimiento_editable(id_req):
            return False
        MigracionRequerimientoController._eliminar_recordatorios_de_etapa(_id, id_req)
        ok = super().delete(_id)
        if ok:
            session = Session.get()
            MigracionRequerimientoHistorialController.registrar(
                id_req,
                "etapa_baja",
                id_etapa=_id,
                detalle={"titulo": existing.get("titulo")},
                usuario=session.username if session.logged_in else "",
            )
        return ok


class MigracionRequerimientoController(BaseController):
    TABLE = "migracion_requerimiento"
    ID_FIELD = "id_migracion_requerimiento"

    @classmethod
    def puede_operar_expediente(cls, id_expediente: str) -> bool:
        if not (id_expediente or "").strip():
            return False
        rows = ExpedienteController.get_scoped(
            where="e._id = ?",
            params=(id_expediente,),
            limit=1,
        )
        return bool(rows)

    @classmethod
    def list_by_expediente(cls, id_expediente: str) -> list[dict]:
        return cls.get_all(
            where="id_expediente = ?",
            params=(id_expediente,),
            order_by="orden ASC, titulo ASC",
        )

    @classmethod
    def _eliminar_recordatorios_de_etapa(cls, id_etapa: str, id_requerimiento: str) -> None:
        req = cls.get_by_id(id_requerimiento)
        if not req:
            return
        id_exp = (req.get("id_expediente") or "").strip()
        template_key = f"migracion_etapa:{id_etapa}:vencimiento"
        rows = ExpedienteRecordatorioController.get_all(
            where="id_expediente = ? AND template_key = ? AND origen = ?",
            params=(id_exp, template_key, "migracion_modulo"),
            limit=20,
        )
        for r in rows:
            ExpedienteRecordatorioController.delete(r.get("_id", ""))

    @classmethod
    def _resolver_recordatorios_vencimiento_etapa(cls, id_etapa: str, id_requerimiento: str) -> None:
        """Marca como resueltos los recordatorios de venc. de esta etapa (no borrar: historial en carpeta)."""
        req = cls.get_by_id(id_requerimiento)
        if not req:
            return
        id_exp = (req.get("id_expediente") or "").strip()
        template_key = f"migracion_etapa:{id_etapa}:vencimiento"
        rows = ExpedienteRecordatorioController.get_all(
            where="id_expediente = ? AND template_key = ? AND origen = ?",
            params=(id_exp, template_key, "migracion_modulo"),
            limit=20,
        )
        for r in rows:
            rid = (r.get("_id") or "").strip()
            if rid and (r.get("estado_plazo") or "") != "resuelto":
                ExpedienteRecordatorioController.marcar_resuelto(rid)

    @classmethod
    def _disparar_recordatorios_migracion_si_aplica(cls) -> None:
        """Ejecuta el job de recordatorios en caliente (no esperar al intervalo de 45 min)."""
        try:
            from core.scheduler import check_recordatorios_expedientes

            check_recordatorios_expedientes()
        except Exception:
            logger.debug("check_recordatorios_expedientes tras etapa migracion", exc_info=True)

    @classmethod
    def sincronizar_recordatorio_vencimiento_etapa(cls, id_etapa: str) -> None:
        et = MigracionRequerimientoEtapaController.get_by_id(id_etapa)
        if not et:
            return
        id_req = (et.get("id_requerimiento") or "").strip()
        req = cls.get_by_id(id_req)
        if not req:
            return
        if (et.get("estado_avance") or "").strip() == "hecho":
            # Disparar avisos mientras el recordatorio sigue activo; luego cerrarlo.
            cls._disparar_recordatorios_migracion_si_aplica()
            cls._resolver_recordatorios_vencimiento_etapa(id_etapa, id_req)
            return
        id_exp = (req.get("id_expediente") or "").strip()
        template_key = f"migracion_etapa:{id_etapa}:vencimiento"
        fv = (et.get("fecha_vencimiento") or "").strip()[:10]
        existentes = ExpedienteRecordatorioController.get_all(
            where="id_expediente = ? AND template_key = ? AND origen = ?",
            params=(id_exp, template_key, "migracion_modulo"),
            limit=10,
        )
        if len(fv) != 10:
            for ex in existentes:
                ExpedienteRecordatorioController.delete(ex.get("_id", ""))
            return
        session = Session.get()
        creado_por = session.username if session.logged_in else ""
        titulo = f"Venc. migr. — {et.get('titulo', 'Etapa')}"
        mensaje = (
            f"Requerimiento migracion: {req.get('titulo', '')}. "
            f"Etapa: {et.get('titulo', '')}."
        )
        if existentes:
            ExpedienteRecordatorioController.update(
                existentes[0]["_id"],
                {
                    "fecha_disparo": fv,
                    "titulo": titulo,
                    "mensaje": mensaje,
                    "id_migracion_requerimiento": id_req,
                    "id_migracion_etapa": id_etapa,
                    "etapa_codigo": "",
                    "estado_plazo": "activo",
                    "disparado_en": "",
                    "ultimo_aviso_nivel": "",
                    "ultimo_aviso_fecha": "",
                },
            )
            cls._disparar_recordatorios_migracion_si_aplica()
            return
        ExpedienteRecordatorioController.create_for_expediente(
            id_exp,
            {
                "fecha_disparo": fv,
                "titulo": titulo,
                "mensaje": mensaje,
                "notificar_a_username": "",
                "etapa_codigo": "",
                "es_critico": 0,
                "origen": "migracion_modulo",
                "template_key": template_key,
                "estado_plazo": "activo",
                "creado_por_username": creado_por,
                "id_migracion_requerimiento": id_req,
                "id_migracion_etapa": id_etapa,
            },
        )
        cls._disparar_recordatorios_migracion_si_aplica()

    @classmethod
    def list_historial(cls, id_requerimiento: str) -> list[dict]:
        return MigracionRequerimientoHistorialController.get_all(
            where="id_requerimiento = ?",
            params=(id_requerimiento,),
            order_by="created_at DESC",
            limit=200,
        )

    @classmethod
    def create(cls, data: dict) -> dict | None:
        id_exp = (data.get("id_expediente") or "").strip()
        if not cls.puede_operar_expediente(id_exp):
            return None
        titulo = (data.get("titulo") or "").strip()
        if not titulo:
            return None
        session = Session.get()
        orden = data.get("orden", 0)
        try:
            orden_i = int(orden)
        except (TypeError, ValueError):
            orden_i = 0
        payload = {
            "id_expediente": id_exp,
            "titulo": titulo,
            "tipo": (data.get("tipo") or "").strip(),
            "estado_ciclo": "iniciado",
            "notas": (data.get("notas") or "").strip(),
            "orden": orden_i,
            "created_by_username": session.username if session.logged_in else "",
            "created_at": now_iso(),
        }
        record = super().create(payload)
        MigracionRequerimientoHistorialController.registrar(
            record["_id"],
            "requerimiento_alta",
            detalle={"titulo": titulo},
            usuario=session.username if session.logged_in else "",
        )
        MigracionRequerimientoEtapaController.create(
            {
                "id_requerimiento": record["_id"],
                "titulo": "Gestion general",
                "codigo": "gestion_general",
                "orden": 0,
            }
        )
        return record

    @classmethod
    def update(cls, _id: str, data: dict) -> dict | None:
        existing = cls.get_by_id(_id)
        if not existing:
            return None
        id_exp = (existing.get("id_expediente") or "").strip()
        if not cls.puede_operar_expediente(id_exp):
            return None
        payload = dict(data)
        nuevo_ciclo = (payload.get("estado_ciclo") or existing.get("estado_ciclo") or "").strip()
        if nuevo_ciclo and nuevo_ciclo not in ESTADOS_CICLO:
            payload.pop("estado_ciclo", None)
        elif nuevo_ciclo == "finalizado" and (existing.get("estado_ciclo") or "") != "finalizado":
            payload["finalizado_en"] = now_iso()
        elif nuevo_ciclo == "iniciado":
            payload["finalizado_en"] = ""
        old_ciclo = existing.get("estado_ciclo", "")
        result = super().update(_id, payload)
        if result and payload.get("estado_ciclo") is not None and result.get("estado_ciclo") != old_ciclo:
            session = Session.get()
            MigracionRequerimientoHistorialController.registrar(
                _id,
                "ciclo_cambio",
                detalle={"anterior": old_ciclo, "nuevo": result.get("estado_ciclo")},
                usuario=session.username if session.logged_in else "",
            )
        return result

    @classmethod
    def delete(cls, _id: str) -> bool:
        ex = cls.get_by_id(_id)
        if not ex or not cls.puede_operar_expediente(ex.get("id_expediente", "")):
            return False
        session = Session.get()
        deleted_by = session.username if session.logged_in else "system"
        conn = db_local.get_connection()
        try:
            rows = conn.execute(
                "SELECT _id FROM migracion_requerimiento_etapa WHERE id_requerimiento = ? "
                "AND (is_deleted IS NULL OR is_deleted = 0)",
                (_id,),
            ).fetchall()
            for r in rows:
                db_local.soft_delete("migracion_requerimiento_etapa", r[0], deleted_by=deleted_by)
        finally:
            conn.close()
        return super().delete(_id)

    @classmethod
    def list_iniciados_con_expediente_scoped(cls, *, limit: int = 500) -> list[dict]:
        session = Session.get()
        conditions = [
            "(m.is_deleted IS NULL OR m.is_deleted = 0)",
            "(e.is_deleted IS NULL OR e.is_deleted = 0)",
            "m.estado_ciclo = 'iniciado'",
            "e.estado NOT IN ('Cerrado','Archivado')",
        ]
        params: list = []
        sw, sp = ExpedienteController._scope_expediente_efectivo_sql(session)
        if sw:
            conditions.append(f"({sw})")
            params.extend(sp)
        sql = (
            "SELECT m.*, e.id_expediente AS exp_id_expediente, e.etapa_codigo AS exp_etapa_codigo, "
            "e.responsable_username AS exp_responsable_username, "
            "c.nombre_completo AS cli_nombre, c.dni AS cli_dni, "
            "c.numero_carpeta AS numero_carpeta_cliente "
            "FROM migracion_requerimiento m "
            "JOIN expedientes e ON e._id = m.id_expediente "
            "LEFT JOIN clientes c ON c._id = e.id_cliente "
            + ExpedienteController._JOIN_ETAPA_ENCARGADO
            + " WHERE " + " AND ".join(conditions)
            + " ORDER BY e.id_expediente ASC, m.orden ASC, m.titulo ASC"
        )
        if limit:
            sql += f" LIMIT {int(limit)}"
        conn = db_local.get_connection()
        rows = conn.execute(sql, tuple(params)).fetchall()
        conn.close()
        return db_local.rows_to_list(rows)

    @classmethod
    def _cond_modalidad_expediente(cls, modalidad: str) -> str:
        """Una pestaña por modalidad real: INICIADA P/V por etapa global; req_* por campo modalidad del expediente.

        Las carpetas en req_migraciones / req_analizar / req_citar sin modalidad definida no entran a ningún listado
        hasta fijar Presencial o Virtual en la ficha.
        """
        m = (modalidad or "").strip()
        if m == "Presencial":
            return "(e.etapa_codigo = 'iniciada_presencial' OR e.modalidad = 'Presencial')"
        return "(e.etapa_codigo = 'iniciada_virtual' OR e.modalidad = 'Virtual')"

    @classmethod
    def list_iniciados_tabla_por_modalidad_scoped(cls, modalidad: str) -> list[dict]:
        """Filas para tabla en Carpetas Iniciadas: requisitos con ciclo iniciado, por modalidad / etapa global."""
        session = Session.get()
        mod_ex = cls._cond_modalidad_expediente(modalidad)
        conditions = [
            "(m.is_deleted IS NULL OR m.is_deleted = 0)",
            "(e.is_deleted IS NULL OR e.is_deleted = 0)",
            "m.estado_ciclo = 'iniciado'",
            "e.estado NOT IN ('Cerrado','Archivado')",
            mod_ex,
        ]
        params: list = []
        sw, sp = ExpedienteController._scope_expediente_efectivo_sql(session)
        if sw:
            conditions.append(f"({sw})")
            params.extend(sp)
        subq_alarma = (
            "(SELECT MIN(r.fecha_disparo) FROM expediente_recordatorios r "
            "WHERE r.id_expediente = e._id AND r.id_migracion_requerimiento = m._id "
            "AND (r.is_deleted IS NULL OR r.is_deleted = 0) "
            "AND COALESCE(r.estado_plazo, 'activo') NOT IN ('resuelto'))"
        )
        sql = (
            "SELECT m.*, e.id_expediente AS exp_id_expediente, e.etapa_codigo AS exp_etapa_codigo, "
            "e.modalidad AS exp_modalidad, e.responsable_username AS exp_responsable_username, "
            "e.numero_expediente_anses AS nro_tramite_anses_exp, "
            "COALESCE(NULLIF(TRIM(e.clave_mi_anses), ''), c.clave_mi_anses, '') AS clave_mi_anses_efectiva, "
            "COALESCE(NULLIF(TRIM(e.clave_fiscal), ''), c.clave_fiscal, '') AS clave_fiscal_efectiva, "
            "c.nombre_completo AS cli_nombre, c.dni AS cli_dni, c.cuil AS cli_cuil, "
            "c.nro_tramite_dni AS cli_nro_tramite_dni, "
            "c.numero_carpeta AS numero_carpeta_cliente, "
            f"{subq_alarma} AS prox_alarma_fecha_raw "
            "FROM migracion_requerimiento m "
            "JOIN expedientes e ON e._id = m.id_expediente "
            "LEFT JOIN clientes c ON c._id = e.id_cliente "
            + ExpedienteController._JOIN_ETAPA_ENCARGADO
            + " WHERE " + " AND ".join(conditions)
            + " ORDER BY e.id_expediente ASC, m.orden ASC, m.titulo ASC"
        )
        conn = db_local.get_connection()
        rows = conn.execute(sql, tuple(params)).fetchall()
        conn.close()
        raw = db_local.rows_to_list(rows)
        out: list[dict] = []
        hoy = date.today()
        for r in raw:
            mid = (r.get("_id") or "").strip()
            pv = cls.proxima_fecha_vencimiento_req(mid)
            prox_label = _fmt_fecha_chequeo(pv, hoy) if pv else ""
            pa_raw = (r.get("prox_alarma_fecha_raw") or "").strip()
            prox_alarma_label = _fmt_fecha_chequeo(pa_raw, hoy) if pa_raw else ""

            out.append({
                "_id": mid,
                "id_expediente": (r.get("id_expediente") or "").strip(),
                "carpeta_id": r.get("exp_id_expediente", "") or "",
                "numero_carpeta_cliente": r.get("numero_carpeta_cliente", "") or "",
                "cli_nombre": r.get("cli_nombre", "") or "",
                "cli_dni": r.get("cli_dni", "") or "",
                "cli_cuil": r.get("cli_cuil", "") or "",
                "cli_nro_tramite_dni": r.get("cli_nro_tramite_dni", "") or "",
                "clave_mi_anses": r.get("clave_mi_anses_efectiva", "") or "",
                "clave_fiscal": r.get("clave_fiscal_efectiva", "") or "",
                "nro_tramite_anses": r.get("nro_tramite_anses_exp", "") or "",
                "req_titulo": r.get("titulo", "") or "",
                "tipo": r.get("tipo", "") or "",
                "estado_ciclo": r.get("estado_ciclo", "") or "",
                "prox_venc": prox_label,
                "prox_alarma": prox_alarma_label,
            })
        out.sort(key=lambda x: (
            min(_sort_key_fecha_label(x.get("prox_venc", "")), _sort_key_fecha_label(x.get("prox_alarma", ""))),
            int(x.get("carpeta_id") or 0) if str(x.get("carpeta_id") or "").isdigit() else 0,
        ))
        return out

    @classmethod
    def count_por_ciclo_scoped(cls) -> dict[str, int]:
        session = Session.get()
        sw, sp = ExpedienteController._scope_expediente_efectivo_sql(session)
        scope_sql = f" AND ({sw})" if sw else ""

        def _one(where_extra: str) -> int:
            conn = db_local.get_connection()
            q = (
                "SELECT COUNT(*) FROM migracion_requerimiento m "
                "JOIN expedientes e ON e._id = m.id_expediente "
                + ExpedienteController._JOIN_ETAPA_ENCARGADO
                + " WHERE (m.is_deleted IS NULL OR m.is_deleted = 0) "
                "AND (e.is_deleted IS NULL OR e.is_deleted = 0) "
                f"AND e.estado NOT IN ('Cerrado','Archivado') "
                f"{where_extra}{scope_sql}"
            )
            row = conn.execute(q, sp).fetchone()
            conn.close()
            return int(row[0]) if row else 0

        return {
            "iniciados": _one("AND m.estado_ciclo = 'iniciado'"),
            "finalizados": _one("AND m.estado_ciclo = 'finalizado'"),
        }

    @classmethod
    def proxima_fecha_vencimiento_req(cls, id_requerimiento: str) -> str:
        """Próxima fecha de vencimiento de etapa interna para listados.

        Prioriza etapas aún no marcadas como hechas. Si todas las que tienen fecha
        están hechas (p. ej. una sola etapa cerrada con vencimiento), devuelve igual
        la fecha para que el listado no quede en blanco.
        """
        etapas = MigracionRequerimientoEtapaController.list_by_requerimiento(id_requerimiento)
        fechas_pend: list[str] = []
        fechas_cualquiera: list[str] = []
        for et in etapas:
            fv = (et.get("fecha_vencimiento") or "").strip()[:10]
            if len(fv) != 10:
                continue
            fechas_cualquiera.append(fv)
            if (et.get("estado_avance") or "").strip() != "hecho":
                fechas_pend.append(fv)
        if fechas_pend:
            fechas_pend.sort()
            return fechas_pend[0]
        if fechas_cualquiera:
            fechas_cualquiera.sort()
            return fechas_cualquiera[0]
        return ""

    @classmethod
    def list_etapas_con_vencimiento_proximo_scoped(cls, dias: int = 14) -> list[dict]:
        """Etapas internas con vencimiento en ventana (scope expediente)."""
        from datetime import timedelta

        session = Session.get()
        hoy = date.today()
        limite = (hoy + timedelta(days=max(1, int(dias)))).isoformat()[:10]
        hoy_s = hoy.isoformat()[:10]
        conditions = [
            "(m.is_deleted IS NULL OR m.is_deleted = 0)",
            "(me.is_deleted IS NULL OR me.is_deleted = 0)",
            "(e.is_deleted IS NULL OR e.is_deleted = 0)",
            "m.estado_ciclo = 'iniciado'",
            "me.estado_avance != 'hecho'",
            "LENGTH(TRIM(me.fecha_vencimiento)) = 10",
            "me.fecha_vencimiento >= ?",
            "me.fecha_vencimiento <= ?",
            "e.estado NOT IN ('Cerrado','Archivado')",
        ]
        params: list = [hoy_s, limite]
        sw, sp = ExpedienteController._scope_expediente_efectivo_sql(session)
        if sw:
            conditions.append(f"({sw})")
            params.extend(sp)
        sql = (
            "SELECT me.*, m.titulo AS req_titulo, m.id_expediente, "
            "e.id_expediente AS exp_id_expediente, c.nombre_completo AS cli_nombre "
            "FROM migracion_requerimiento_etapa me "
            "JOIN migracion_requerimiento m ON m._id = me.id_requerimiento "
            "JOIN expedientes e ON e._id = m.id_expediente "
            "LEFT JOIN clientes c ON c._id = e.id_cliente "
            + ExpedienteController._JOIN_ETAPA_ENCARGADO
            + " WHERE " + " AND ".join(conditions)
            + " ORDER BY me.fecha_vencimiento ASC"
        )
        conn = db_local.get_connection()
        rows = conn.execute(sql, tuple(params)).fetchall()
        conn.close()
        return db_local.rows_to_list(rows)
