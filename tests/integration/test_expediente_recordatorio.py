"""Tests de recordatorios de expediente y disparo vía scheduler."""

from controllers.expediente_controller import ExpedienteController
from controllers.expediente_recordatorio_controller import ExpedienteRecordatorioController
from core import db_local
from core.scheduler import check_recordatorios_expedientes


class TestExpedienteRecordatorioList:
    def test_list_vacio(self, session_superusuario, sample_expediente):
        exp = ExpedienteController.create(sample_expediente)
        assert ExpedienteRecordatorioController.list_by_expediente(exp["_id"]) == []

    def test_create_y_list(self, session_superusuario, sample_expediente):
        exp = ExpedienteController.create(sample_expediente)
        ExpedienteRecordatorioController.create_for_expediente(exp["_id"], {
            "fecha_disparo": "2099-12-31",
            "titulo": "Revisar",
            "mensaje": "Texto",
            "notificar_a_username": "testsuper",
            "creado_por_username": "testsuper",
        })
        rows = ExpedienteRecordatorioController.list_by_expediente(exp["_id"])
        assert len(rows) == 1
        assert rows[0]["titulo"] == "Revisar"
        assert rows[0]["fecha_disparo"] == "2099-12-31"

    def test_generar_plantilla_req_migraciones(self, session_superusuario, sample_expediente):
        exp = ExpedienteController.create(sample_expediente)
        result = ExpedienteRecordatorioController.generar_plantilla_req_migraciones(
            exp["_id"],
            tema="Requerimiento",
            fecha_vencimiento="2030-12-20",
            creado_por_username="testsuper",
        )
        assert result["creados"] == 2
        rows = ExpedienteRecordatorioController.list_by_expediente(exp["_id"])
        by_title = {r.get("titulo", ""): r for r in rows}
        assert "Vencimiento" in by_title
        assert "Alarma critica - 2 dias" in by_title
        assert by_title["Alarma critica - 2 dias"].get("es_critico", 0) == 1
        result2 = ExpedienteRecordatorioController.generar_plantilla_req_migraciones(
            exp["_id"],
            tema="Requerimiento",
            fecha_vencimiento="2031-01-10",
            creado_por_username="testsuper",
        )
        assert result2["creados"] == 0
        rows2 = ExpedienteRecordatorioController.list_by_expediente(exp["_id"])
        by_title2 = {r.get("titulo", ""): r for r in rows2}
        assert by_title2["Vencimiento"]["fecha_disparo"] == "2031-01-10"

    def test_generar_plantilla_titulos_custom(self, session_superusuario, sample_expediente):
        exp = ExpedienteController.create(sample_expediente)
        result = ExpedienteRecordatorioController.generar_plantilla_req_migraciones(
            exp["_id"],
            tema="Requerimiento",
            fecha_vencimiento="2030-12-20",
            creado_por_username="testsuper",
            titulo_soft="Tramite nuevo — vence",
            titulo_critico="Tramite nuevo — 2 dias",
        )
        assert result["creados"] == 2
        rows = ExpedienteRecordatorioController.list_by_expediente(exp["_id"])
        by_title = {r.get("titulo", ""): r for r in rows}
        assert "Tramite nuevo — vence" in by_title
        assert "Tramite nuevo — 2 dias" in by_title

    def test_generar_plantilla_preserva_titulos_en_update(
        self, session_superusuario, sample_expediente,
    ):
        exp = ExpedienteController.create(sample_expediente)
        ExpedienteRecordatorioController.generar_plantilla_req_migraciones(
            exp["_id"],
            tema="Requerimiento",
            fecha_vencimiento="2030-12-20",
            creado_por_username="testsuper",
        )
        rows = ExpedienteRecordatorioController.list_by_expediente(exp["_id"])
        soft = next(
            r for r in rows
            if (r.get("template_key") or "").endswith(":alarma_soft")
        )
        ExpedienteRecordatorioController.update(soft["_id"], {"titulo": "Titulo personalizado soft"})
        crit = next(
            r for r in rows
            if (r.get("template_key") or "").endswith(":alarma_critica_2dias")
        )
        ExpedienteRecordatorioController.update(crit["_id"], {"titulo": "Titulo personalizado critico"})
        ExpedienteRecordatorioController.generar_plantilla_req_migraciones(
            exp["_id"],
            tema="Requerimiento",
            fecha_vencimiento="2031-06-15",
            creado_por_username="testsuper",
            titulo_soft="Deberia ignorarse",
            titulo_critico="Deberia ignorarse crit",
            preservar_titulos_en_update=True,
        )
        rows2 = ExpedienteRecordatorioController.list_by_expediente(exp["_id"])
        by_key = {(r.get("template_key") or "").strip(): r for r in rows2}
        k0 = "migraciones:requerimiento:alarma_soft"
        k1 = "migraciones:requerimiento:alarma_critica_2dias"
        assert by_key[k0]["titulo"] == "Titulo personalizado soft"
        assert by_key[k1]["titulo"] == "Titulo personalizado critico"
        assert by_key[k0]["fecha_disparo"] == "2031-06-15"
        assert by_key[k1]["fecha_disparo"] == "2031-06-13"


class TestCheckRecordatoriosDispara:
    def test_marca_disparado_y_crea_notificacion(
        self, session_superusuario, sample_expediente,
    ):
        exp = ExpedienteController.create(sample_expediente)
        ExpedienteController.update(exp["_id"], {"responsable_secundario_username": "secuser"})
        ExpedienteRecordatorioController.create_for_expediente(exp["_id"], {
            "fecha_disparo": "2020-01-01",
            "titulo": "Plazo vencido",
            "mensaje": "Accion",
            "notificar_a_username": "testsuper",
            "creado_por_username": "testsuper",
        })
        check_recordatorios_expedientes()
        recs = ExpedienteRecordatorioController.list_by_expediente(exp["_id"])
        assert len(recs) == 1
        assert (recs[0].get("disparado_en") or "").strip()
        assert recs[0].get("ultimo_aviso_nivel") in {"vencido", "hoy", "previo"}
        notifs = db_local.find_all(
            "notificaciones",
            where="target_username = ? AND tipo = ?",
            params=("testsuper", "recordatorio_expediente"),
        )
        assert len(notifs) >= 1
        assert (notifs[0].get("id_referencia") or "") == exp["_id"]
        notifs_sec = db_local.find_all(
            "notificaciones",
            where="target_username = ? AND tipo = ?",
            params=("secuser", "recordatorio_expediente"),
        )
        assert len(notifs_sec) >= 1

    def test_no_duplica_mismo_nivel_mismo_dia(
        self, session_superusuario, sample_expediente,
    ):
        exp = ExpedienteController.create(sample_expediente)
        ExpedienteRecordatorioController.create_for_expediente(exp["_id"], {
            "fecha_disparo": "2020-01-01",
            "titulo": "Plazo vencido",
            "mensaje": "Accion",
            "notificar_a_username": "testsuper",
            "creado_por_username": "testsuper",
        })
        check_recordatorios_expedientes()
        first = db_local.count(
            "notificaciones",
            "target_username = ? AND tipo = ?",
            ("testsuper", "recordatorio_expediente"),
        )
        check_recordatorios_expedientes()
        second = db_local.count(
            "notificaciones",
            "target_username = ? AND tipo = ?",
            ("testsuper", "recordatorio_expediente"),
        )
        assert second == first
