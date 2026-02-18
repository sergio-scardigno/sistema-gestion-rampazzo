"""Tests de integracion para ComunicacionController."""
import pytest
from controllers.comunicacion_controller import ComunicacionController


class TestComunicacionCRUD:
    def test_create(self, session_superusuario, sample_comunicacion):
        r = ComunicacionController.create(sample_comunicacion)
        assert r["canal"] == "WhatsApp"
        assert r["id_comunicacion"] == 1

    def test_update(self, session_superusuario, sample_comunicacion):
        r = ComunicacionController.create(sample_comunicacion)
        updated = ComunicacionController.update(r["_id"], {"resultado": "Completado"})
        assert updated["resultado"] == "Completado"

    def test_delete(self, session_superusuario, sample_comunicacion):
        r = ComunicacionController.create(sample_comunicacion)
        assert ComunicacionController.delete(r["_id"]) is True


class TestGetByExpediente:
    def test_returns_expediente_comunicaciones(self, session_superusuario, sample_comunicacion):
        ComunicacionController.create(sample_comunicacion)
        ComunicacionController.create({**sample_comunicacion, "id_expediente": "otro"})
        results = ComunicacionController.get_by_expediente("exp-test-001")
        assert len(results) == 1

    def test_empty_for_unknown_expediente(self, session_superusuario):
        assert len(ComunicacionController.get_by_expediente("no-existe")) == 0


class TestConstants:
    def test_canales(self):
        assert "WhatsApp" in ComunicacionController.CANALES
        assert "Llamada" in ComunicacionController.CANALES
