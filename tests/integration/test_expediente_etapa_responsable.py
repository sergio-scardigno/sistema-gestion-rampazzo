"""Encargado secundario por etapa y visibilidad en get_scoped."""

import pytest

from controllers.expediente_controller import ExpedienteController
from controllers.expediente_etapa_responsable_controller import ExpedienteEtapaResponsableController
from core.auth import Session


@pytest.fixture
def session_abogado(monkeypatch):
    session = Session()
    session.usuario = {
        "_id": "u-abo",
        "username": "aboenc",
        "nombre_completo": "Abogado Enc",
        "rol": "abogado",
        "activo": 1,
        "eliminado": 0,
    }
    monkeypatch.setattr(Session, "_instance", session)
    return session


class TestEncargadoPorEtapa:
    def test_upsert_y_list(self, session_superusuario, sample_expediente):
        exp = ExpedienteController.create(
            {**sample_expediente, "responsable_username": "otro", "responsable_secundario_username": ""}
        )
        ExpedienteEtapaResponsableController.upsert_encargado(
            exp["_id"], "turno", "testsuper",
        )
        rows = ExpedienteEtapaResponsableController.list_by_expediente(exp["_id"])
        assert len(rows) == 1
        assert rows[0]["etapa_codigo"] == "turno"
        assert rows[0]["responsable_secundario_username"] == "testsuper"

    def test_abogado_ve_carpeta_si_es_encargado_en_etapa_actual(
        self, session_abogado, sample_expediente,
    ):
        exp = ExpedienteController.create({
            **sample_expediente,
            "responsable_username": "otro",
            "responsable_secundario_username": "",
            "etapa_codigo": "turno",
        })
        ExpedienteEtapaResponsableController.upsert_encargado(exp["_id"], "turno", "aboenc")
        rows = ExpedienteController.get_scoped()
        assert len(rows) == 1
        assert rows[0]["_id"] == exp["_id"]
