"""Tests de integracion para ReporteController."""
import pytest
from controllers.reporte_controller import ReporteController
from controllers.expediente_controller import ExpedienteController
from controllers.cliente_controller import ClienteController
from controllers.tarea_controller import TareaController
from controllers.movimiento_controller import MovimientoController
from controllers.turno_controller import TurnoController


def _seed_data(session_fixture):
    """Crear datos semilla para reportes."""
    # Clientes
    ClienteController.create({
        "numero_carpeta": "9001", "nombre_completo": "Ana Test",
        "procedencia_contacto": "Telefono",
    })
    ClienteController.create({
        "numero_carpeta": "9002", "nombre_completo": "Pedro Test",
        "procedencia_contacto": "Instagram",
    })

    # Expedientes
    ExpedienteController.create({
        "id_cliente": "c1", "tipo_tramite": "Jubilacion",
        "estado": "Activo", "responsable_username": "testsuper",
        "fecha_apertura": "2025-01-01",
    })
    ExpedienteController.create({
        "id_cliente": "c2", "tipo_tramite": "Amparo",
        "estado": "Cerrado", "responsable_username": "testsuper",
        "fecha_apertura": "2024-06-01", "fecha_cierre": "2025-01-15",
        "resultado": "Favorable",
    })

    # Tareas
    TareaController.create({
        "id_expediente": "e1", "tipo_accion": "Turno ANSES",
        "estado": "Pendiente", "fecha_vencimiento": "2020-01-01",
    })
    TareaController.create({
        "id_expediente": "e1", "tipo_accion": "Otro",
        "estado": "Cumplida", "fecha_vencimiento": "2025-12-31",
    })

    # Movimientos
    MovimientoController.create({
        "id_cliente": "c1", "id_expediente": "e1",
        "tipo": "Honorario", "monto": 100000, "saldo": 100000,
        "fecha": "2025-01-01", "estado": "Pendiente",
    })
    MovimientoController.create({
        "id_cliente": "c2", "id_expediente": "e2",
        "tipo": "Honorario", "monto": 50000, "saldo": 0,
        "fecha": "2025-02-01", "estado": "Cancelado",
    })


class TestKpisOperativos:
    def test_structure(self, session_superusuario):
        _seed_data(session_superusuario)
        kpis = ReporteController.kpis_operativos()
        assert "total_expedientes" in kpis
        assert "expedientes_activos" in kpis
        assert "expedientes_cerrados" in kpis
        assert "tareas_pendientes" in kpis
        assert "tareas_vencidas" in kpis

    def test_values(self, session_superusuario):
        _seed_data(session_superusuario)
        kpis = ReporteController.kpis_operativos()
        assert kpis["total_expedientes"] == 2
        assert kpis["expedientes_activos"] == 1
        assert kpis["expedientes_cerrados"] == 1
        assert kpis["tareas_pendientes"] >= 1
        assert kpis["tareas_vencidas"] >= 1

    def test_empty_db(self, session_superusuario):
        kpis = ReporteController.kpis_operativos()
        assert kpis["total_expedientes"] == 0


class TestKpisComerciales:
    def test_structure(self, session_superusuario):
        _seed_data(session_superusuario)
        kpis = ReporteController.kpis_comerciales()
        assert "total_clientes" in kpis

    def test_total_clientes(self, session_superusuario):
        _seed_data(session_superusuario)
        kpis = ReporteController.kpis_comerciales()
        assert kpis["total_clientes"] >= 2

    def test_empty_db(self, session_superusuario):
        kpis = ReporteController.kpis_comerciales()
        assert kpis["total_clientes"] == 0


class TestKpisEconomicos:
    def test_structure(self, session_superusuario):
        _seed_data(session_superusuario)
        kpis = ReporteController.kpis_economicos()
        assert "ingresos_cobrados" in kpis
        assert "pendientes_cobro" in kpis

    def test_values(self, session_superusuario):
        _seed_data(session_superusuario)
        kpis = ReporteController.kpis_economicos()
        assert kpis["ingresos_cobrados"] == 50000.0
        assert kpis["pendientes_cobro"] == 100000.0


class TestExpedientesPorTipo:
    def test_returns_breakdown(self, session_superusuario):
        _seed_data(session_superusuario)
        result = ReporteController.expedientes_por_tipo()
        tipos = [r["tipo"] for r in result]
        assert "Jubilacion" in tipos
        assert "Amparo" in tipos


class TestClientesPorProcedencia:
    def test_returns_breakdown(self, session_superusuario):
        _seed_data(session_superusuario)
        result = ReporteController.clientes_por_procedencia()
        procedencias = [r["procedencia"] for r in result]
        assert "Telefono" in procedencias
        assert "Instagram" in procedencias


class TestTiempoPromedioResolucion:
    def test_with_closed_expedientes(self, session_superusuario):
        _seed_data(session_superusuario)
        result = ReporteController.tiempo_promedio_resolucion()
        assert result["total_cerrados"] >= 1
        assert result["promedio_dias"] > 0

    def test_without_closed_expedientes(self, session_superusuario):
        result = ReporteController.tiempo_promedio_resolucion()
        assert result["total_cerrados"] == 0
        assert result["promedio_dias"] == 0


class TestTurnosVsCasos:
    def test_structure(self, session_superusuario):
        _seed_data(session_superusuario)
        result = ReporteController.turnos_vs_casos()
        assert "total_turnos" in result
        assert "total_expedientes" in result
        assert "ratio" in result


class TestAnalisisClientesSinCarpeta:
    def test_structure(self, session_superusuario):
        _seed_data(session_superusuario)
        result = ReporteController.analisis_clientes_sin_carpeta()
        assert "total_clientes" in result
        assert "con_carpeta" in result
        assert "sin_carpeta" in result
        assert "tasa_sin_carpeta" in result


class TestKpisEconomicosPeriodo:
    def test_without_filters(self, session_superusuario):
        _seed_data(session_superusuario)
        result = ReporteController.kpis_economicos_periodo()
        assert "ingresos_cobrados" in result
        assert "total_movimientos" in result

    def test_with_date_range(self, session_superusuario):
        _seed_data(session_superusuario)
        result = ReporteController.kpis_economicos_periodo(
            desde="2025-01-01", hasta="2025-01-31"
        )
        assert result["total_movimientos"] >= 1
