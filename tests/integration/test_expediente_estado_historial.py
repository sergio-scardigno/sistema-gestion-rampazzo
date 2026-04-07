"""Tests de integracion para el historial de estados de expedientes y auto-archivado."""
import time
import pytest

from controllers.expediente_controller import ExpedienteController
from controllers import expediente_estado_controller as eec
from controllers.reporte_controller import ReporteController
from core import db_local


# ── Helpers ──

def _create_expediente(session, **overrides):
    """Crea un expediente de prueba y retorna el registro."""
    data = {
        "id_cliente": "cli-test-001",
        "tipo_tramite": "Jubilacion",
        "fecha_apertura": "2025-01-10",
        "responsable": "Test Superusuario",
        "responsable_username": "testsuper",
        "estado": "Activo",
        "prioridad": "Normal",
    }
    data.update(overrides)
    return ExpedienteController.create(data)


# ══════════════════════════════════════════════════════════
#  Tests de creacion de segmentos
# ══════════════════════════════════════════════════════════

class TestSegmentoAlCrear:
    def test_create_expediente_opens_segment(self, session_superusuario):
        exp = _create_expediente(session_superusuario)
        hist = eec.get_historial(exp["_id"])
        assert len(hist) == 1
        seg = hist[0]
        assert seg["estado"] == "para_citar_o_videollamada"
        assert seg["responsable_username"] == "testsuper"
        assert seg["inicio_ts"] is not None
        assert seg["fin_ts"] is None
        assert seg["origen"] == "manual"

    def test_create_with_custom_etapa(self, session_superusuario):
        exp = _create_expediente(session_superusuario, etapa_codigo="para_analizar")
        hist = eec.get_historial(exp["_id"])
        assert hist[0]["estado"] == "para_analizar"


# ══════════════════════════════════════════════════════════
#  Tests de rotacion de segmentos
# ══════════════════════════════════════════════════════════

class TestRotacionSegmentos:
    def test_change_etapa_rotates_segment(self, session_superusuario):
        exp = _create_expediente(session_superusuario)
        ExpedienteController.update(exp["_id"], {"etapa_codigo": "para_analizar"})
        hist = eec.get_historial(exp["_id"])
        assert len(hist) == 2
        assert hist[0]["estado"] == "para_citar_o_videollamada"
        assert hist[0]["fin_ts"] is not None
        assert hist[1]["estado"] == "para_analizar"
        assert hist[1]["fin_ts"] is None

    def test_observacion_transicion_guardada_en_segmento(self, session_superusuario):
        exp = _create_expediente(session_superusuario)
        ExpedienteController.update(exp["_id"], {
            "etapa_codigo": "para_analizar",
            "observacion_transicion": "Llamar al cliente el martes.",
        })
        hist = eec.get_historial(exp["_id"])
        assert len(hist) == 2
        assert (hist[1].get("observacion_transicion") or "") == "Llamar al cliente el martes."

    def test_change_responsable_rotates_segment(self, session_superusuario):
        exp = _create_expediente(session_superusuario)
        ExpedienteController.update(exp["_id"], {"responsable_username": "otrouser"})
        hist = eec.get_historial(exp["_id"])
        assert len(hist) == 2
        assert hist[0]["responsable_username"] == "testsuper"
        assert hist[0]["fin_ts"] is not None
        assert hist[1]["responsable_username"] == "otrouser"
        assert hist[1]["fin_ts"] is None

    def test_no_rotation_when_nothing_changes(self, session_superusuario):
        exp = _create_expediente(session_superusuario)
        ExpedienteController.update(exp["_id"], {"observaciones": "actualizado"})
        hist = eec.get_historial(exp["_id"])
        assert len(hist) == 1

    def test_multiple_etapa_changes(self, session_superusuario):
        exp = _create_expediente(session_superusuario)
        ExpedienteController.update(exp["_id"], {"etapa_codigo": "para_analizar"})
        ExpedienteController.update(exp["_id"], {"etapa_codigo": "para_citar"})
        ExpedienteController.update(exp["_id"], {
            "etapa_codigo": "enviar_notificarse",
            "estado": "Cerrado",
            "resultado": "Favorable",
            "fecha_cierre": "2025-06-01",
        })
        hist = eec.get_historial(exp["_id"])
        assert len(hist) == 4
        estados = [h["estado"] for h in hist]
        assert estados == [
            "para_citar_o_videollamada",
            "para_analizar",
            "para_citar",
            "enviar_notificarse",
        ]
        for h in hist[:-1]:
            assert h["fin_ts"] is not None
        assert hist[-1]["fin_ts"] is None


# ══════════════════════════════════════════════════════════
#  Tests de auto-archivado
# ══════════════════════════════════════════════════════════

class TestAutoArchivado:
    def test_auto_archivar_cerrados_old(self, session_superusuario):
        """Expediente cerrado hace mas de 30 dias se archiva."""
        exp = _create_expediente(session_superusuario,
                                 estado="Cerrado",
                                 resultado="Favorable",
                                 fecha_cierre="2024-01-01")
        count = ExpedienteController.auto_archivar_cerrados(dias=30)
        assert count == 1
        updated = ExpedienteController.get_by_id(exp["_id"])
        assert updated["estado"] == "Archivado"

    def test_auto_archivar_does_not_touch_recent(self, session_superusuario):
        """Expediente cerrado hace menos de 30 dias NO se archiva."""
        from datetime import date, timedelta
        recent_date = (date.today() - timedelta(days=5)).isoformat()
        exp = _create_expediente(session_superusuario,
                                 estado="Cerrado",
                                 resultado="Favorable",
                                 fecha_cierre=recent_date)
        count = ExpedienteController.auto_archivar_cerrados(dias=30)
        assert count == 0
        updated = ExpedienteController.get_by_id(exp["_id"])
        assert updated["estado"] == "Cerrado"

    def test_auto_archivar_updates_expediente_sin_rotar_por_solo_estado(self, session_superusuario):
        """Auto-archivado cambia estado del expediente; el historial sigue por etapa (sin rotar)."""
        exp = _create_expediente(session_superusuario,
                                 estado="Cerrado",
                                 resultado="Favorable",
                                 fecha_cierre="2024-01-01")
        ExpedienteController.auto_archivar_cerrados(dias=30)
        updated = ExpedienteController.get_by_id(exp["_id"])
        assert updated["estado"] == "Archivado"
        hist = eec.get_historial(exp["_id"])
        assert len(hist) == 1

    def test_auto_archivar_ignores_activos(self, session_superusuario):
        """Expedientes activos no se tocan."""
        _create_expediente(session_superusuario, estado="Activo")
        count = ExpedienteController.auto_archivar_cerrados(dias=30)
        assert count == 0


# ══════════════════════════════════════════════════════════
#  Tests de seed
# ══════════════════════════════════════════════════════════

class TestSeed:
    def test_seed_creates_segments_for_existing(self, session_superusuario):
        """Seed crea segmentos para expedientes activos sin historial."""
        # Crear expediente directamente en BD (sin pasar por controller override)
        from models.base_model import base_fields
        record = base_fields()
        record.update({
            "id_expediente": 999,
            "id_cliente": "cli-x",
            "tipo_tramite": "Jubilacion",
            "estado": "Activo",
            "responsable_username": "testsuper",
            "fecha_apertura": "2025-01-01",
        })
        db_local.insert("expedientes", record)
        # Verificar que no tiene historial
        hist = eec.get_historial(record["_id"])
        assert len(hist) == 0
        # Ejecutar seed
        count = eec.seed_expedientes_sin_segmento()
        assert count == 1
        hist = eec.get_historial(record["_id"])
        assert len(hist) == 1
        assert hist[0]["origen"] == "seed"

    def test_seed_idempotent(self, session_superusuario):
        """Ejecutar seed dos veces no duplica segmentos."""
        exp = _create_expediente(session_superusuario)
        # Ya tiene 1 segmento del create
        count = eec.seed_expedientes_sin_segmento()
        assert count == 0
        hist = eec.get_historial(exp["_id"])
        assert len(hist) == 1


# ══════════════════════════════════════════════════════════
#  Tests de funciones de reporte
# ══════════════════════════════════════════════════════════

class TestReporteTiempos:
    def test_tiempos_por_estado_expediente(self, session_superusuario):
        exp = _create_expediente(session_superusuario)
        result = ReporteController.tiempos_por_estado_expediente(exp["_id"])
        assert "estados" in result
        assert "total_dias" in result
        assert len(result["estados"]) >= 1
        assert result["estados"][0]["estado"] == "para_citar_o_videollamada"

    def test_tiempos_por_estado_expediente_multiple(self, session_superusuario):
        exp = _create_expediente(session_superusuario)
        ExpedienteController.update(exp["_id"], {"etapa_codigo": "para_analizar"})
        result = ReporteController.tiempos_por_estado_expediente(exp["_id"])
        estados = [e["estado"] for e in result["estados"]]
        assert "para_citar_o_videollamada" in estados
        assert "para_analizar" in estados

    def test_tiempos_por_estado_responsable_empty(self, session_superusuario):
        result = ReporteController.tiempos_por_estado_responsable()
        assert isinstance(result, list)

    def test_tiempos_por_estado_responsable_with_data(self, session_superusuario):
        exp = _create_expediente(session_superusuario)
        ExpedienteController.update(exp["_id"], {"etapa_codigo": "para_analizar"})
        time.sleep(0.02)
        ExpedienteController.update(exp["_id"], {"etapa_codigo": "para_citar"})
        result = ReporteController.tiempos_por_estado_responsable()
        assert len(result) >= 1
        assert "responsable" in result[0]
        assert "estado" in result[0]
        assert "promedio_dias" in result[0]

    def test_aperturas_y_cierres_por_responsable(self, session_superusuario):
        _create_expediente(session_superusuario)
        result = ReporteController.aperturas_y_cierres_por_responsable()
        assert len(result) >= 1
        assert "iniciadas" in result[0]
        assert "cerradas" in result[0]

    def test_aperturas_cierres_con_cerradas(self, session_superusuario):
        exp = _create_expediente(session_superusuario)
        ExpedienteController.update(exp["_id"], {
            "estado": "Cerrado",
            "resultado": "Favorable",
            "fecha_cierre": "2025-06-01",
        })
        result = ReporteController.aperturas_y_cierres_por_responsable()
        totales = sum(r["cerradas"] for r in result)
        assert totales >= 1
