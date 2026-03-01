"""Tests de integracion para ExpedienteController."""
import pytest
from controllers.expediente_controller import ExpedienteController
from controllers.notificacion_controller import NotificacionController
from core import db_local
from core.auth import Session


class TestExpedienteCRUD:
    def test_create(self, session_superusuario, sample_expediente):
        r = ExpedienteController.create(sample_expediente)
        assert r["tipo_tramite"] == "Jubilacion"
        assert r["id_expediente"] == 1
        assert r["estado"] == "Activo"

    def test_update(self, session_superusuario, sample_expediente):
        r = ExpedienteController.create(sample_expediente)
        updated = ExpedienteController.update(r["_id"], {"estado": "En tramite"})
        assert updated["estado"] == "En tramite"

    def test_delete(self, session_superusuario, sample_expediente):
        r = ExpedienteController.create(sample_expediente)
        assert ExpedienteController.delete(r["_id"]) is True

    def test_auto_id(self, session_superusuario, sample_expediente):
        r1 = ExpedienteController.create(sample_expediente)
        r2 = ExpedienteController.create({**sample_expediente})
        assert r2["id_expediente"] == r1["id_expediente"] + 1


class TestGetByCliente:
    def test_returns_client_expedientes(self, session_superusuario, sample_expediente):
        ExpedienteController.create(sample_expediente)
        ExpedienteController.create({**sample_expediente, "id_cliente": "otro-cli"})
        results = ExpedienteController.get_by_cliente("cli-test-001")
        assert len(results) == 1

    def test_empty_for_unknown_client(self, session_superusuario):
        assert len(ExpedienteController.get_by_cliente("no-existe")) == 0


class TestSearch:
    def test_search_by_tipo(self, session_superusuario, sample_expediente):
        ExpedienteController.create(sample_expediente)
        results = ExpedienteController.search_expedientes("Jubilacion")
        assert len(results) == 1


class TestCerrar:
    def test_cerrar_expediente(self, session_superusuario, sample_expediente):
        r = ExpedienteController.create(sample_expediente)
        closed = ExpedienteController.cerrar(r["_id"], "Favorable", "2025-06-01")
        assert closed["estado"] == "Cerrado"
        assert closed["resultado"] == "Favorable"
        assert closed["fecha_cierre"] == "2025-06-01"

    def test_cerrar_nonexistent(self, session_superusuario):
        assert ExpedienteController.cerrar("no-existe", "X", "2025-01-01") is None


class TestTieneTareaActiva:
    def test_sin_tareas(self, session_superusuario, sample_expediente):
        r = ExpedienteController.create(sample_expediente)
        assert ExpedienteController.tiene_tarea_activa(r["_id"]) is False

    def test_con_tarea_pendiente(self, session_superusuario, sample_expediente):
        r = ExpedienteController.create(sample_expediente)
        from controllers.tarea_controller import TareaController
        TareaController.create({
            "id_expediente": r["_id"],
            "tipo_accion": "Seguimiento expediente",
            "estado": "Pendiente",
        })
        assert ExpedienteController.tiene_tarea_activa(r["_id"]) is True


class TestGetSinTareaActiva:
    def test_returns_expedientes_without_active_tasks(self, session_superusuario, sample_expediente):
        r = ExpedienteController.create(sample_expediente)
        results = ExpedienteController.get_sin_tarea_activa()
        ids = [e["_id"] for e in results]
        assert r["_id"] in ids

    def test_excludes_expedientes_with_active_tasks(self, session_superusuario, sample_expediente):
        r = ExpedienteController.create(sample_expediente)
        from controllers.tarea_controller import TareaController
        TareaController.create({
            "id_expediente": r["_id"],
            "tipo_accion": "Seguimiento expediente",
            "estado": "Pendiente",
        })
        results = ExpedienteController.get_sin_tarea_activa()
        ids = [e["_id"] for e in results]
        assert r["_id"] not in ids


class TestGetScoped:
    def test_superusuario_sees_all(self, session_superusuario, sample_expediente):
        ExpedienteController.create(sample_expediente)
        ExpedienteController.create({**sample_expediente, "responsable_username": "otro"})
        results = ExpedienteController.get_scoped()
        assert len(results) == 2

    def test_secretaria_sees_all_expedientes(self, session_secretaria, sample_expediente):
        ExpedienteController.create({**sample_expediente, "responsable_username": "testsec"})
        ExpedienteController.create({**sample_expediente, "responsable_username": "otro"})
        results = ExpedienteController.get_scoped()
        assert len(results) == 2

    def test_restricted_role_abogado_sees_own(self, monkeypatch, sample_expediente):
        session = Session()
        session.usuario = {
            "_id": "test-abo-id",
            "username": "testabo",
            "nombre_completo": "Test Abogado",
            "rol": "abogado",
            "activo": 1,
            "eliminado": 0,
        }
        monkeypatch.setattr(Session, "_instance", session)

        ExpedienteController.create({**sample_expediente, "responsable_username": "testabo"})
        ExpedienteController.create({**sample_expediente, "responsable_username": "otro"})
        results = ExpedienteController.get_scoped()
        assert len(results) == 1
        assert results[0]["responsable_username"] == "testabo"

    def test_scoped_includes_secondary_responsable(self, session_secretaria, sample_expediente):
        """Secretaria ve expedientes donde es responsable_secundario."""
        ExpedienteController.create({
            **sample_expediente,
            "responsable_username": "otro",
            "responsable_secundario_username": "testsec",
        })
        results = ExpedienteController.get_scoped()
        assert len(results) == 1


class TestConstants:
    def test_tipos_tramite(self):
        assert "Jubilacion" in ExpedienteController.TIPOS_TRAMITE

    def test_estados(self):
        assert "Activo" in ExpedienteController.ESTADOS
        assert "Cerrado" in ExpedienteController.ESTADOS

    def test_prioridades(self):
        assert "Normal" in ExpedienteController.PRIORIDADES


def _seed_user(username: str, rol: str):
    db_local.insert(
        "usuarios",
        {
            "_id": f"user-{username}",
            "username": username,
            "password_hash": "x",
            "nombre_completo": username.upper(),
            "email": f"{username}@test.com",
            "rol": rol,
            "activo": 1,
            "eliminado": 0,
            "sync_status": "synced",
            "version": 1,
            "created_by_machine": "test-machine",
        },
    )


class TestExpedienteNotifications:
    def test_create_notifies_abogado_destino(self, session_superusuario, sample_expediente):
        _seed_user("abogado_dest", "abogado")
        data = {**sample_expediente, "responsable_username": "abogado_dest"}
        exp = ExpedienteController.create(data)
        active = NotificacionController.get_active_for_user("abogado_dest", limit=10)
        assert any(
            n.get("tipo") == "expediente_asignado" and n.get("id_referencia") == exp["_id"]
            for n in active
        )

    def test_update_notifies_new_responsable(self, session_superusuario, sample_expediente):
        _seed_user("abogado_old", "abogado")
        _seed_user("admin_new", "administrador")
        exp = ExpedienteController.create({**sample_expediente, "responsable_username": "abogado_old"})
        before_old = NotificacionController.get_active_for_user("abogado_old", limit=20)
        ExpedienteController.update(exp["_id"], {"responsable_username": "admin_new"})
        active_new = NotificacionController.get_active_for_user("admin_new", limit=10)
        active_old = NotificacionController.get_active_for_user("abogado_old", limit=10)
        assert any(n.get("tipo") == "expediente_asignado" for n in active_new)
        assert len(active_old) == len(before_old)

    def test_create_does_not_notify_secretaria(self, session_superusuario, sample_expediente):
        _seed_user("sec_dest", "secretaria")
        ExpedienteController.create({**sample_expediente, "responsable_username": "sec_dest"})
        active = NotificacionController.get_active_for_user("sec_dest", limit=10)
        assert all(n.get("tipo") != "expediente_asignado" for n in active)
