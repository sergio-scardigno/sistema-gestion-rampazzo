"""Integracion: modulo requerimientos de migracion."""
import pytest

from controllers.cliente_controller import ClienteController
from controllers.expediente_controller import ExpedienteController
from controllers.expediente_recordatorio_controller import ExpedienteRecordatorioController
from controllers.migracion_requerimiento_controller import (
    MigracionRequerimientoController,
    MigracionRequerimientoEtapaController,
)
from core import db_local
from core.scheduler import check_recordatorios_expedientes


@pytest.fixture
def exp_migracion(session_superusuario, sample_expediente):
    data = dict(sample_expediente)
    data["rama"] = "Migraciones"
    data["responsable_username"] = "testsuper"
    data["responsable_secundario_username"] = ""
    return ExpedienteController.create(data)


class TestMigracionSchema:
    def test_tablas_existen(self):
        conn = db_local.get_connection()
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'migracion_%'"
        )
        names = {r[0] for r in cur.fetchall()}
        conn.close()
        assert "migracion_requerimiento" in names
        assert "migracion_requerimiento_etapa" in names
        assert "migracion_requerimiento_historial" in names

    def test_tareas_tiene_id_migracion(self):
        conn = db_local.get_connection()
        cols = [c[1] for c in conn.execute("PRAGMA table_info(tareas)").fetchall()]
        conn.close()
        assert "id_migracion_requerimiento" in cols

    def test_recordatorios_tiene_migracion_cols(self):
        conn = db_local.get_connection()
        cols = [c[1] for c in conn.execute("PRAGMA table_info(expediente_recordatorios)").fetchall()]
        conn.close()
        assert "id_migracion_requerimiento" in cols
        assert "id_migracion_etapa" in cols


class TestMigracionCrud:
    def test_list_tabla_presencial_virtual(self, session_superusuario, exp_migracion):
        ExpedienteController.update(
            exp_migracion["_id"],
            {"modalidad": "Presencial", "etapa_codigo": "iniciada_presencial"},
        )
        rec = MigracionRequerimientoController.create(
            {"id_expediente": exp_migracion["_id"], "titulo": "Tabla test", "tipo": ""}
        )
        assert rec
        pres = MigracionRequerimientoController.list_iniciados_tabla_por_modalidad_scoped("Presencial")
        row_p = next((r for r in pres if (r.get("_id") or "") == rec["_id"]), None)
        assert row_p is not None
        vir = MigracionRequerimientoController.list_iniciados_tabla_por_modalidad_scoped("Virtual")
        assert not any((r.get("_id") or "") == rec["_id"] for r in vir)

    def test_list_tabla_incluye_anses_y_prox_alarma(self, session_superusuario, sample_expediente):
        cli = ClienteController.create(
            {
                "numero_carpeta": "88001",
                "nombre_completo": "Cliente Migr Tabla",
                "dni": "31234567",
                "cuil": "20312345679",
                "nro_tramite_dni": "DNI-TRAM-99",
                "clave_mi_anses": "CLAVE_CLI_ANSES",
                "clave_fiscal": "CLAVE_CLI_FISC",
            }
        )
        data = dict(sample_expediente)
        data["id_cliente"] = cli["_id"]
        data["rama"] = "Migraciones"
        data["tipo_tramite"] = "Ciudadania"
        data["modalidad"] = "Presencial"
        data["etapa_codigo"] = "iniciada_presencial"
        data["numero_expediente_anses"] = "024-888777"
        data["clave_mi_anses"] = ""
        data["clave_fiscal"] = ""
        exp = ExpedienteController.create(data)
        rec = MigracionRequerimientoController.create(
            {"id_expediente": exp["_id"], "titulo": "Req listado ANSES", "tipo": "test"}
        )
        assert rec
        ExpedienteRecordatorioController.create_for_expediente(
            exp["_id"],
            {
                "fecha_disparo": "2030-03-20",
                "titulo": "Revision ANSES",
                "mensaje": "",
                "id_migracion_requerimiento": rec["_id"],
                "creado_por_username": "testsuper",
            },
        )
        rows = MigracionRequerimientoController.list_iniciados_tabla_por_modalidad_scoped("Presencial")
        row = next((r for r in rows if r.get("_id") == rec["_id"]), None)
        assert row is not None
        assert row.get("cli_dni") == "31234567"
        assert row.get("cli_nro_tramite_dni") == "DNI-TRAM-99"
        assert row.get("clave_mi_anses") == "CLAVE_CLI_ANSES"
        assert row.get("nro_tramite_anses") == "024-888777"
        assert "2030-03-20" in (row.get("prox_alarma") or "")

    def test_list_tabla_incluye_etapa_req_migraciones(self, session_superusuario, sample_expediente):
        """req_migraciones: cada listado filtra por modalidad de la carpeta (no duplica en P y V)."""
        data_p = dict(sample_expediente)
        data_p["rama"] = "Migraciones"
        data_p["etapa_codigo"] = "req_migraciones"
        data_p["modalidad"] = "Presencial"
        exp_p = ExpedienteController.create(data_p)
        rec_p = MigracionRequerimientoController.create(
            {"id_expediente": exp_p["_id"], "titulo": "Tramite req migr pres", "tipo": ""}
        )
        data_v = dict(sample_expediente)
        data_v["rama"] = "Migraciones"
        data_v["etapa_codigo"] = "req_migraciones"
        data_v["modalidad"] = "Virtual"
        exp_v = ExpedienteController.create(data_v)
        rec_v = MigracionRequerimientoController.create(
            {"id_expediente": exp_v["_id"], "titulo": "Tramite req migr virt", "tipo": ""}
        )
        assert rec_p and rec_v
        pres = MigracionRequerimientoController.list_iniciados_tabla_por_modalidad_scoped("Presencial")
        vir = MigracionRequerimientoController.list_iniciados_tabla_por_modalidad_scoped("Virtual")
        ids_p = {r.get("_id") for r in pres}
        ids_v = {r.get("_id") for r in vir}
        assert rec_p["_id"] in ids_p
        assert rec_p["_id"] not in ids_v
        assert rec_v["_id"] in ids_v
        assert rec_v["_id"] not in ids_p

    def test_list_tabla_incluye_previsional_req_migraciones(self, session_superusuario, sample_expediente):
        """Área Previsional + req_migraciones: el listado no debe exigir rama Migraciones."""
        data = dict(sample_expediente)
        data["rama"] = "Previsional"
        data["etapa_codigo"] = "req_migraciones"
        data["modalidad"] = "Presencial"
        exp = ExpedienteController.create(data)
        rec = MigracionRequerimientoController.create(
            {"id_expediente": exp["_id"], "titulo": "Tramite previsional req migr", "tipo": ""}
        )
        assert rec
        pres = MigracionRequerimientoController.list_iniciados_tabla_por_modalidad_scoped("Presencial")
        assert any((r.get("_id") or "") == rec["_id"] for r in pres)

    def test_crea_requerimiento_y_etapa_default(self, session_superusuario, exp_migracion):
        rec = MigracionRequerimientoController.create(
            {"id_expediente": exp_migracion["_id"], "titulo": "Ciudadania", "tipo": "Ciudadania argentina"}
        )
        assert rec
        etapas = MigracionRequerimientoEtapaController.list_by_requerimiento(rec["_id"])
        assert len(etapas) >= 1

    def test_prox_venc_listado_cuando_etapa_hecha_tiene_fecha(self, session_superusuario, exp_migracion):
        """La columna prox_venc no debe quedar vacía si la única etapa con fecha está en hecho."""
        ExpedienteController.update(
            exp_migracion["_id"],
            {"modalidad": "Presencial", "etapa_codigo": "iniciada_presencial"},
        )
        rec = MigracionRequerimientoController.create(
            {"id_expediente": exp_migracion["_id"], "titulo": "Tabla prox venc", "tipo": ""}
        )
        assert rec
        etapas = MigracionRequerimientoEtapaController.list_by_requerimiento(rec["_id"])
        et = etapas[0]
        MigracionRequerimientoEtapaController.update(
            et["_id"],
            {"fecha_vencimiento": "2026-05-09", "estado_avance": "hecho"},
        )
        assert MigracionRequerimientoController.proxima_fecha_vencimiento_req(rec["_id"]) == "2026-05-09"
        rows = MigracionRequerimientoController.list_iniciados_tabla_por_modalidad_scoped("Presencial")
        row = next((r for r in rows if r.get("_id") == rec["_id"]), None)
        assert row is not None
        assert "2026-05-09" in (row.get("prox_venc") or "")

    def test_finalizado_bloquea_edicion_etapa(self, session_superusuario, exp_migracion):
        rec = MigracionRequerimientoController.create(
            {"id_expediente": exp_migracion["_id"], "titulo": "Residencia", "tipo": ""}
        )
        assert rec
        MigracionRequerimientoController.update(rec["_id"], {"estado_ciclo": "finalizado"})
        nuevo = MigracionRequerimientoEtapaController.create(
            {"id_requerimiento": rec["_id"], "titulo": "Nueva", "orden": 9}
        )
        assert nuevo is None

    def test_recordatorio_migracion_dispara_notificacion(
        self, session_superusuario, exp_migracion,
    ):
        rec = MigracionRequerimientoController.create(
            {"id_expediente": exp_migracion["_id"], "titulo": "Tramite X", "tipo": ""}
        )
        etapas = MigracionRequerimientoEtapaController.list_by_requerimiento(rec["_id"])
        et = etapas[0]
        MigracionRequerimientoEtapaController.update(
            et["_id"],
            {"fecha_vencimiento": "2020-01-01", "estado_avance": "en_curso"},
        )
        check_recordatorios_expedientes()
        rows = db_local.find_all(
            "expediente_recordatorios",
            where="id_migracion_etapa = ?",
            params=(et["_id"],),
            limit=5,
        )
        assert rows
        assert (rows[0].get("disparado_en") or "").strip()
        notifs = db_local.find_all(
            "notificaciones",
            where="tipo = ? AND id_referencia = ?",
            params=("recordatorio_migracion_etapa", exp_migracion["_id"]),
            limit=10,
        )
        assert len(notifs) >= 1

    def test_recordatorio_migracion_dispara_sin_scheduler_manual(
        self, session_superusuario, exp_migracion,
    ):
        """Tras guardar vencimiento, debe correr check de recordatorios (campana morada)."""
        rec = MigracionRequerimientoController.create(
            {"id_expediente": exp_migracion["_id"], "titulo": "Tramite Y", "tipo": ""}
        )
        et = MigracionRequerimientoEtapaController.list_by_requerimiento(rec["_id"])[0]
        MigracionRequerimientoEtapaController.update(
            et["_id"],
            {"fecha_vencimiento": "2020-05-01", "estado_avance": "en_curso"},
        )
        notifs = db_local.find_all(
            "notificaciones",
            where="tipo = ? AND id_referencia = ?",
            params=("recordatorio_migracion_etapa", exp_migracion["_id"]),
            limit=10,
        )
        assert len(notifs) >= 1
