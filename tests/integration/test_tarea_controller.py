"""Tests de integracion para TareaController."""
import pytest
from controllers.tarea_controller import TareaController


class TestTareaCRUD:
    def test_create(self, session_superusuario, sample_tarea):
        r = TareaController.create(sample_tarea)
        assert r["descripcion"] == "Sacar turno en UDAI"
        assert r["id_tarea"] == 1
        assert r["estado"] == "Pendiente"

    def test_update(self, session_superusuario, sample_tarea):
        r = TareaController.create(sample_tarea)
        updated = TareaController.update(r["_id"], {"estado": "En curso"})
        assert updated["estado"] == "En curso"

    def test_delete(self, session_superusuario, sample_tarea):
        r = TareaController.create(sample_tarea)
        assert TareaController.delete(r["_id"]) is True

    def test_auto_id_increment(self, session_superusuario, sample_tarea):
        r1 = TareaController.create(sample_tarea)
        r2 = TareaController.create({**sample_tarea})
        assert r2["id_tarea"] == r1["id_tarea"] + 1


class TestGetByExpediente:
    def test_returns_tasks_for_expediente(self, session_superusuario, sample_tarea):
        TareaController.create(sample_tarea)
        TareaController.create({**sample_tarea, "id_expediente": "otro-exp"})
        results = TareaController.get_by_expediente("exp-test-001")
        assert len(results) == 1


class TestGetPendientes:
    def test_returns_pending_tasks(self, session_superusuario, sample_tarea):
        TareaController.create(sample_tarea)  # estado = Pendiente
        TareaController.create({**sample_tarea, "estado": "Cumplida"})
        results = TareaController.get_pendientes()
        assert len(results) == 1

    def test_filter_by_responsable(self, session_superusuario, sample_tarea):
        TareaController.create(sample_tarea)
        TareaController.create({**sample_tarea, "responsable": "Otro"})
        results = TareaController.get_pendientes(responsable="Test Abogado")
        assert len(results) == 1


class TestGetVencidas:
    def test_returns_overdue_tasks(self, session_superusuario):
        TareaController.create({
            "id_expediente": "exp-1",
            "tipo_accion": "Turno ANSES",
            "estado": "Pendiente",
            "fecha_vencimiento": "2020-01-01",  # pasado
        })
        TareaController.create({
            "id_expediente": "exp-2",
            "tipo_accion": "Otro",
            "estado": "Pendiente",
            "fecha_vencimiento": "2099-12-31",  # futuro
        })
        vencidas = TareaController.get_vencidas()
        assert len(vencidas) == 1

    def test_cumplidas_not_included(self, session_superusuario):
        TareaController.create({
            "id_expediente": "exp-1",
            "tipo_accion": "Otro",
            "estado": "Cumplida",
            "fecha_vencimiento": "2020-01-01",
        })
        assert len(TareaController.get_vencidas()) == 0


class TestConstants:
    def test_estados(self):
        assert "Pendiente" in TareaController.ESTADOS
        assert "Cumplida" in TareaController.ESTADOS

    def test_tipos_accion(self):
        assert "Turno ANSES" in TareaController.TIPOS_ACCION
