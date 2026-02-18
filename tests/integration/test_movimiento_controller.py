"""Tests de integracion para MovimientoController."""
import pytest
from controllers.movimiento_controller import MovimientoController


class TestMovimientoCRUD:
    def test_create(self, session_superusuario, sample_movimiento):
        r = MovimientoController.create(sample_movimiento)
        assert r["monto"] == 50000.0
        assert r["id_movimiento"] == 1

    def test_update(self, session_superusuario, sample_movimiento):
        r = MovimientoController.create(sample_movimiento)
        updated = MovimientoController.update(r["_id"], {"estado": "Cancelado"})
        assert updated["estado"] == "Cancelado"

    def test_delete(self, session_superusuario, sample_movimiento):
        r = MovimientoController.create(sample_movimiento)
        assert MovimientoController.delete(r["_id"]) is True


class TestGetByExpediente:
    def test_returns_expediente_movimientos(self, session_superusuario, sample_movimiento):
        MovimientoController.create(sample_movimiento)
        MovimientoController.create({**sample_movimiento, "id_expediente": "otro"})
        results = MovimientoController.get_by_expediente("exp-test-001")
        assert len(results) == 1


class TestGetByCliente:
    def test_returns_client_movimientos(self, session_superusuario, sample_movimiento):
        MovimientoController.create(sample_movimiento)
        MovimientoController.create({**sample_movimiento, "id_cliente": "otro"})
        results = MovimientoController.get_by_cliente("cli-test-001")
        assert len(results) == 1


class TestSaldoCliente:
    def test_sum_saldos(self, session_superusuario):
        MovimientoController.create({
            "id_cliente": "cli-1", "id_expediente": "exp-1",
            "tipo": "Honorario", "monto": 100000, "fecha": "2025-01-01",
            "estado": "Pendiente", "saldo": 100000,
        })
        MovimientoController.create({
            "id_cliente": "cli-1", "id_expediente": "exp-1",
            "tipo": "Honorario", "monto": 50000, "fecha": "2025-02-01",
            "estado": "Pendiente", "saldo": 50000,
        })
        assert MovimientoController.saldo_cliente("cli-1") == 150000.0

    def test_zero_for_unknown(self, session_superusuario):
        assert MovimientoController.saldo_cliente("no-existe") == 0.0


class TestConstants:
    def test_tipos(self):
        assert "Honorario" in MovimientoController.TIPOS
        assert "Gasto" in MovimientoController.TIPOS

    def test_formas_pago(self):
        assert "Transferencia" in MovimientoController.FORMAS_PAGO
