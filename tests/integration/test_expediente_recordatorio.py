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


class TestCheckRecordatoriosDispara:
    def test_marca_disparado_y_crea_notificacion(
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
        recs = ExpedienteRecordatorioController.list_by_expediente(exp["_id"])
        assert len(recs) == 1
        assert (recs[0].get("disparado_en") or "").strip()
        notifs = db_local.find_all(
            "notificaciones",
            where="target_username = ? AND tipo = ?",
            params=("testsuper", "recordatorio_expediente"),
        )
        assert len(notifs) >= 1
        assert (notifs[0].get("id_referencia") or "") == exp["_id"]
