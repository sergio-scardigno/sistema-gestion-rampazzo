"""Tests de integracion para core/audit.py y controllers/audit_controller.py"""
import json
import pytest
from core.audit import (
    log_action, log_user_action, log_login, log_logout, init_audit_protection,
)
from controllers.audit_controller import AuditController
from core import db_local


# =====================================================================
# core/audit.py – funciones de log
# =====================================================================

class TestLogAction:
    def test_creates_audit_entry(self, session_superusuario):
        log_action("create", "clientes", "doc-1",
                   datos_nuevos={"nombre_completo": "Test"})
        logs = db_local.find_all("audit_log")
        assert len(logs) == 1
        assert logs[0]["accion"] == "create"
        assert logs[0]["coleccion"] == "clientes"
        assert logs[0]["usuario"] == "testsuper"

    def test_stores_datos_as_json(self, session_superusuario):
        log_action("update", "clientes", "doc-1",
                   datos_anteriores={"nombre": "A"},
                   datos_nuevos={"nombre": "B"})
        log = db_local.find_all("audit_log")[0]
        ant = json.loads(log["datos_anteriores"])
        assert ant["nombre"] == "A"

    def test_without_session_uses_sistema(self):
        log_action("create", "clientes", "doc-1")
        log = db_local.find_all("audit_log")[0]
        assert log["usuario"] == "sistema"

    def test_usuario_override(self):
        log_action("create", "clientes", "doc-1", usuario_override="custom_user")
        log = db_local.find_all("audit_log")[0]
        assert log["usuario"] == "custom_user"


class TestLogLogin:
    def test_login_ok(self):
        log_login("admin", True, "Login exitoso")
        log = db_local.find_all("audit_log")[0]
        assert log["accion"] == "login_ok"
        assert log["usuario"] == "admin"

    def test_login_failed(self):
        log_login("hacker", False, "Password incorrecta")
        log = db_local.find_all("audit_log")[0]
        assert log["accion"] == "login_fallido"


class TestLogLogout:
    def test_logout(self):
        log_logout("admin")
        log = db_local.find_all("audit_log")[0]
        assert log["accion"] == "logout"
        assert log["usuario"] == "admin"


class TestLogUserAction:
    def test_user_action(self, session_superusuario):
        log_user_action("crear_usuario", "user-123",
                        datos_nuevos={"username": "nuevo"})
        log = db_local.find_all("audit_log")[0]
        assert log["accion"] == "crear_usuario"
        assert log["coleccion"] == "usuarios"


class TestAuditProtection:
    def test_triggers_prevent_delete(self):
        """Los triggers deben bloquear DELETE en audit_log."""
        init_audit_protection()
        log_action("create", "test", "x")
        log = db_local.find_all("audit_log")[0]
        with pytest.raises(Exception, match="inmutable"):
            with db_local.get_cursor() as cur:
                cur.execute("DELETE FROM audit_log WHERE _id = ?", (log["_id"],))

    def test_triggers_prevent_update(self):
        """Los triggers deben bloquear UPDATE en audit_log."""
        init_audit_protection()
        log_action("create", "test", "x")
        log = db_local.find_all("audit_log")[0]
        with pytest.raises(Exception, match="inmutable"):
            with db_local.get_cursor() as cur:
                cur.execute("UPDATE audit_log SET accion = 'hack' WHERE _id = ?", (log["_id"],))


# =====================================================================
# AuditController – consultas y estadisticas
# =====================================================================

class TestAuditControllerGetAll:
    def _seed_logs(self):
        log_action("create", "clientes", "c1", usuario_override="user1")
        log_action("update", "expedientes", "e1", usuario_override="user2")
        log_action("delete", "tareas", "t1", usuario_override="user1")

    def test_returns_all(self):
        self._seed_logs()
        logs = AuditController.get_all()
        assert len(logs) == 3

    def test_filter_by_usuario(self):
        self._seed_logs()
        logs = AuditController.get_all(usuario="user1")
        assert len(logs) == 2

    def test_filter_by_coleccion(self):
        self._seed_logs()
        logs = AuditController.get_all(coleccion="clientes")
        assert len(logs) == 1

    def test_filter_by_accion(self):
        self._seed_logs()
        logs = AuditController.get_all(accion="delete")
        assert len(logs) == 1

    def test_enriches_with_labels(self):
        self._seed_logs()
        logs = AuditController.get_all()
        for log in logs:
            assert "accion_label" in log
            assert "coleccion_label" in log
            assert "resumen" in log


class TestAuditControllerGetByDocument:
    def test_returns_history(self):
        log_action("create", "clientes", "c-x", usuario_override="u1")
        log_action("update", "clientes", "c-x", usuario_override="u1")
        logs = AuditController.get_by_document("clientes", "c-x")
        assert len(logs) == 2

    def test_filters_by_document(self):
        log_action("create", "clientes", "c-1", usuario_override="u1")
        log_action("create", "clientes", "c-2", usuario_override="u1")
        logs = AuditController.get_by_document("clientes", "c-1")
        assert len(logs) == 1


class TestAuditControllerStats:
    def _seed_data(self):
        for _ in range(3):
            log_action("create", "clientes", "x", usuario_override="user1")
        log_action("update", "clientes", "x", usuario_override="user2")

    def test_stats_por_usuario(self):
        self._seed_data()
        stats = AuditController.get_stats_por_usuario()
        assert len(stats) >= 2
        user1_stat = [s for s in stats if s["usuario"] == "user1"][0]
        assert user1_stat["total"] == 3
        assert user1_stat["creates"] == 3

    def test_acciones_hoy(self):
        self._seed_data()
        count = AuditController.get_acciones_hoy()
        assert count >= 4

    def test_actividad_diaria(self):
        self._seed_data()
        days = AuditController.get_actividad_diaria(dias=1)
        assert len(days) >= 1

    def test_actividad_por_usuario(self):
        self._seed_data()
        results = AuditController.get_actividad_por_usuario(dias=1)
        assert len(results) >= 2

    def test_actividad_por_modulo(self):
        self._seed_data()
        results = AuditController.get_actividad_por_modulo(dias=1)
        assert len(results) >= 1

    def test_usuarios_activos(self):
        self._seed_data()
        users = AuditController.get_usuarios_activos()
        assert "user1" in users
        assert "user2" in users

    def test_colecciones_activas(self):
        self._seed_data()
        cols = AuditController.get_colecciones_activas()
        assert "clientes" in cols


class TestGetCamposModificados:
    def test_create_shows_new_fields(self):
        log_action("create", "clientes", "c1",
                   datos_nuevos={"nombre_completo": "Juan", "dni": "123"})
        log = db_local.find_all("audit_log")[0]
        cambios = AuditController.get_campos_modificados(log["_id"])
        campos = [c["campo"] for c in cambios]
        assert "nombre_completo" in campos

    def test_update_shows_changed_fields(self):
        log_action("update", "clientes", "c1",
                   datos_anteriores={"nombre_completo": "A"},
                   datos_nuevos={"nombre_completo": "B"})
        log = db_local.find_all("audit_log")[0]
        cambios = AuditController.get_campos_modificados(log["_id"])
        assert len(cambios) >= 1
        assert cambios[0]["anterior"] == "A"
        assert cambios[0]["nuevo"] == "B"

    def test_nonexistent_returns_empty(self):
        assert AuditController.get_campos_modificados("no-existe") == []
