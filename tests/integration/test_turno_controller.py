"""Tests de integracion para TurnoController."""
import pytest
from datetime import datetime, timedelta
from controllers.turno_controller import TurnoController
from controllers.expediente_controller import ExpedienteController
from controllers.documento_controller import DocumentoController


class TestTurnoCRUD:
    def test_create(self, session_superusuario, sample_turno):
        r = TurnoController.create(sample_turno)
        assert r["oficina_anses"] == "UDAI Resistencia"
        assert r["id_turno"] == 1
        assert r["estado"] == "Pendiente"

    def test_update(self, session_superusuario, sample_turno):
        r = TurnoController.create(sample_turno)
        updated = TurnoController.update(r["_id"], {"estado": "Confirmado"})
        assert updated["estado"] == "Confirmado"

    def test_delete(self, session_superusuario, sample_turno):
        r = TurnoController.create(sample_turno)
        assert TurnoController.delete(r["_id"]) is True


class TestGetByCliente:
    def test_returns_client_turnos(self, session_superusuario, sample_turno):
        TurnoController.create(sample_turno)
        TurnoController.create({**sample_turno, "id_cliente": "otro"})
        assert len(TurnoController.get_by_cliente("cli-test-001")) == 1


class TestGetByExpediente:
    def test_returns_expediente_turnos(self, session_superusuario, sample_turno):
        TurnoController.create(sample_turno)
        assert len(TurnoController.get_by_expediente("exp-test-001")) == 1


class TestGetHoy:
    def test_returns_today_turnos(self, session_superusuario, sample_turno):
        today = datetime.now().strftime("%Y-%m-%d")
        TurnoController.create({**sample_turno, "fecha_turno": today})
        TurnoController.create({**sample_turno, "fecha_turno": "2020-01-01"})
        results = TurnoController.get_hoy()
        assert len(results) == 1

    def test_empty_if_no_today_turnos(self, session_superusuario):
        assert len(TurnoController.get_hoy()) == 0


class TestGetProximos:
    def test_returns_upcoming_turnos(self, session_superusuario, sample_turno):
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        TurnoController.create({**sample_turno, "fecha_turno": tomorrow})
        # Turno pasado
        TurnoController.create({**sample_turno, "fecha_turno": "2020-01-01"})
        results = TurnoController.get_proximos(dias=7)
        assert len(results) == 1

    def test_includes_today(self, session_superusuario, sample_turno):
        today = datetime.now().strftime("%Y-%m-%d")
        TurnoController.create({**sample_turno, "fecha_turno": today})
        results = TurnoController.get_proximos(dias=7)
        assert len(results) == 1


class TestGetSinDocumentacion:
    def test_returns_unprepared(self, session_superusuario, sample_turno):
        future = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        TurnoController.create({
            **sample_turno, "fecha_turno": future,
            "documentacion_lista": 0, "estado": "Pendiente",
        })
        TurnoController.create({
            **sample_turno, "fecha_turno": future,
            "documentacion_lista": 1, "estado": "Pendiente",
        })
        results = TurnoController.get_sin_documentacion()
        assert len(results) == 1


class TestGetPendientesResultado:
    def test_returns_attended_without_result(self, session_superusuario, sample_turno):
        TurnoController.create({**sample_turno, "estado": "Asistido", "resultado": ""})
        TurnoController.create({**sample_turno, "estado": "Asistido", "resultado": "Aprobado"})
        results = TurnoController.get_pendientes_resultado()
        assert len(results) == 1


class TestMarcarAsistido:
    def test_changes_state(self, session_superusuario, sample_turno):
        r = TurnoController.create(sample_turno)
        updated = TurnoController.marcar_asistido(r["_id"])
        assert updated["estado"] == "Asistido"


class TestReprogramar:
    def test_creates_new_turno(self, session_superusuario, sample_turno):
        r = TurnoController.create(sample_turno)
        nuevo = TurnoController.reprogramar(r["_id"], "2025-05-20", "10:00")
        assert nuevo is not None
        assert nuevo["fecha_turno"] == "2025-05-20"
        assert nuevo["hora_turno"] == "10:00"
        assert (nuevo.get("id_constancia_doc") or "") == ""
        # Original debe estar reprogramado
        original = TurnoController.get_by_id(r["_id"])
        assert original["estado"] == "Reprogramado"

    def test_reprogramar_nonexistent(self, session_superusuario):
        assert TurnoController.reprogramar("no-existe", "2025-01-01", "09:00") is None


class TestTurnoConstanciaDoc:
    def test_turno_puede_enlazar_id_constancia_doc(
        self, session_superusuario, sample_expediente, tmp_path,
    ):
        exp = ExpedienteController.create(sample_expediente)
        pdf = tmp_path / "constancia.pdf"
        pdf.write_bytes(b"%PDF-1.4\n%test")
        doc = DocumentoController.create({
            "id_expediente": exp["_id"],
            "categoria": "Turnos ANSES",
            "subcategoria": "Constancia",
            "nombre": "Constancia test",
            "ruta_archivo": str(pdf),
            "fecha": "2025-01-01",
            "mime_type": "application/pdf",
        })
        t = TurnoController.create({
            "id_cliente": exp["id_cliente"],
            "id_expediente": exp["_id"],
            "fecha_turno": "2025-04-10",
            "hora_turno": "09:30",
            "oficina_anses": "UDAI Resistencia",
            "tipo_tramite": "Jubilacion",
            "estado": "Pendiente",
            "responsable": "Test",
            "responsable_username": "testsuper",
        })
        u = TurnoController.update(t["_id"], {"id_constancia_doc": doc["_id"]})
        assert u.get("id_constancia_doc") == doc["_id"]
        loaded = TurnoController.get_by_id(t["_id"])
        assert loaded.get("id_constancia_doc") == doc["_id"]


class TestConstants:
    def test_estados(self):
        assert "Pendiente" in TurnoController.ESTADOS
        assert "Asistido" in TurnoController.ESTADOS

    def test_tipos_tramite(self):
        assert "Jubilacion" in TurnoController.TIPOS_TRAMITE

    def test_oficinas(self):
        assert "UDAI Resistencia" in TurnoController.OFICINAS_ANSES
