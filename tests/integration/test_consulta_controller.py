"""Tests de integracion para ConsultaController."""
import pytest
from controllers.consulta_controller import ConsultaController


class TestConsultaCRUD:
    def test_create(self, session_superusuario, sample_consulta):
        r = ConsultaController.create(sample_consulta)
        assert r["nombre"] == "Maria Lopez"
        assert r["id_consulta"] == 1
        assert r["estado"] == "Nuevo"

    def test_update(self, session_superusuario, sample_consulta):
        r = ConsultaController.create(sample_consulta)
        updated = ConsultaController.update(r["_id"], {"estado": "En evaluacion"})
        assert updated["estado"] == "En evaluacion"

    def test_delete(self, session_superusuario, sample_consulta):
        r = ConsultaController.create(sample_consulta)
        assert ConsultaController.delete(r["_id"]) is True
        assert ConsultaController.get_by_id(r["_id"]) is None

    def test_get_all(self, session_superusuario, sample_consulta):
        ConsultaController.create(sample_consulta)
        ConsultaController.create({**sample_consulta, "nombre": "Otro"})
        assert len(ConsultaController.get_all()) == 2


class TestConsultaSearch:
    def test_search_by_nombre(self, session_superusuario, sample_consulta):
        ConsultaController.create(sample_consulta)
        assert len(ConsultaController.search_consultas("Maria")) == 1

    def test_search_by_motivo(self, session_superusuario, sample_consulta):
        ConsultaController.create(sample_consulta)
        assert len(ConsultaController.search_consultas("jubilacion")) == 1

    def test_search_no_results(self, session_superusuario, sample_consulta):
        ConsultaController.create(sample_consulta)
        assert len(ConsultaController.search_consultas("xyz")) == 0


class TestConsultaConvertirACliente:
    """Tests para el flujo de asociar consulta a cliente."""

    def test_update_estado_convertido_en_cliente(self, session_superusuario, sample_consulta):
        r = ConsultaController.create(sample_consulta)
        updated = ConsultaController.update(r["_id"], {
            "estado": "Convertido en cliente",
            "id_cliente": "cli-fake-001",
        })
        assert updated["estado"] == "Convertido en cliente"
        assert updated["id_cliente"] == "cli-fake-001"

    def test_update_estado_convertido_en_expediente(self, session_superusuario, sample_consulta):
        r = ConsultaController.create(sample_consulta)
        updated = ConsultaController.update(r["_id"], {
            "estado": "Convertido en expediente",
            "id_cliente": "cli-fake-002",
        })
        assert updated["estado"] == "Convertido en expediente"
        assert updated["id_cliente"] == "cli-fake-002"

    def test_id_cliente_persists(self, session_superusuario, sample_consulta):
        """Verificar que id_cliente se guarda y se recupera correctamente."""
        r = ConsultaController.create(sample_consulta)
        ConsultaController.update(r["_id"], {"id_cliente": "cli-test-123"})
        reloaded = ConsultaController.get_by_id(r["_id"])
        assert reloaded["id_cliente"] == "cli-test-123"


class TestConsultaConstants:
    def test_canales_defined(self):
        assert len(ConsultaController.CANALES) > 0
        assert "Telefono" in ConsultaController.CANALES

    def test_estados_defined(self):
        assert len(ConsultaController.ESTADOS) > 0
        assert "Nuevo" in ConsultaController.ESTADOS
        assert "Convertido en cliente" in ConsultaController.ESTADOS
        assert "Convertido en expediente" in ConsultaController.ESTADOS
