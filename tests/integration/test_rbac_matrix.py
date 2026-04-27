"""Matriz RBAC: permisos y alcance por rol."""

import pytest

from controllers.cliente_controller import ClienteController
from controllers.expediente_controller import ExpedienteController
from controllers.tarea_controller import TareaController
from core.auth import Session
from core.permissions import modulos_permitidos, scope_where, tiene_permiso


def _set_session(monkeypatch, username: str, rol: str):
    session = Session()
    session.usuario = {
        "_id": f"id-{username}",
        "username": username,
        "nombre_completo": username,
        "rol": rol,
        "activo": 1,
        "eliminado": 0,
    }
    monkeypatch.setattr(Session, "_instance", session)
    return session


class TestRBACMatrixPermisos:
    @pytest.mark.parametrize(
        "rol,permiso,esperado",
        [
            ("secretaria", "clientes.read", True),
            ("secretaria", "clientes.create", False),
            ("agente", "expedientes.update", True),
            ("agente", "documentos.create", False),
            ("abogado", "documentos.update", True),
            ("analisis", "tareas.delete", True),
            ("administrador", "movimientos.delete", True),
            ("admin_visor", "movimientos.read", True),
            ("admin_visor", "movimientos.create", False),
            ("superusuario", "migracion.create", True),
        ],
    )
    def test_permisos_por_rol(self, rol, permiso, esperado):
        assert tiene_permiso(rol, permiso) is esperado

    @pytest.mark.parametrize(
        "rol,modulo",
        [
            ("secretaria", "clientes"),
            ("agente", "expedientes"),
            ("abogado", "documentos"),
            ("analisis", "tareas"),
            ("administrador", "usuarios"),
            ("admin_visor", "reportes"),
            ("superusuario", "migracion"),
        ],
    )
    def test_modulos_visibles_clave(self, rol, modulo):
        assert modulo in modulos_permitidos(rol)


class TestRBACMatrixScope:
    def test_scope_sql_por_rol(self):
        where_sec, params_sec = scope_where("secretaria", "sec", modulo="expedientes")
        where_abo, params_abo = scope_where("abogado", "abo", modulo="expedientes")
        where_admin, params_admin = scope_where("administrador", "adm", modulo="expedientes")

        assert where_sec == ""
        assert params_sec == ()
        assert "responsable_username" in where_abo
        assert params_abo == ("abo",)
        assert where_admin == ""
        assert params_admin == ()

    def test_scope_expedientes_por_rol(self, monkeypatch, session_superusuario):
        cli = ClienteController.create({"nombre_completo": "Cli Scope", "dni": "37777777", "numero_carpeta": "9801"})
        ExpedienteController.create({"id_cliente": cli["_id"], "tipo_tramite": "Jubilacion", "responsable_username": "abogado_a"})
        ExpedienteController.create({"id_cliente": cli["_id"], "tipo_tramite": "Pension", "responsable_username": "abogado_b"})

        _set_session(monkeypatch, "abogado_a", "abogado")
        abo_rows = ExpedienteController.get_scoped()

        _set_session(monkeypatch, "sec", "secretaria")
        sec_rows = ExpedienteController.get_scoped()

        _set_session(monkeypatch, "adm", "administrador")
        adm_rows = ExpedienteController.get_scoped()

        assert len(abo_rows) == 1
        assert len(sec_rows) == 2
        assert len(adm_rows) == 2

    def test_scope_tareas_por_rol(self, monkeypatch, session_superusuario):
        TareaController.create({"id_expediente": "exp-rbac", "tipo_accion": "Otro", "estado": "Pendiente", "responsable_username": "abogado_x"})
        TareaController.create({"id_expediente": "exp-rbac", "tipo_accion": "Otro", "estado": "Pendiente", "responsable_username": "abogado_y"})

        _set_session(monkeypatch, "abogado_x", "abogado")
        abo_rows = TareaController.get_scoped()
        _set_session(monkeypatch, "admin", "administrador")
        adm_rows = TareaController.get_scoped()

        assert len(abo_rows) == 1
        assert len(adm_rows) == 2

    def test_scope_clientes_secretaria_vs_abogado(self, monkeypatch, session_superusuario):
        c1 = ClienteController.create({"nombre_completo": "Cli A", "dni": "38888881", "numero_carpeta": "9802"})
        c2 = ClienteController.create({"nombre_completo": "Cli B", "dni": "38888882", "numero_carpeta": "9803"})
        ExpedienteController.create({"id_cliente": c1["_id"], "tipo_tramite": "Jubilacion", "responsable_username": "abogado_x"})
        ExpedienteController.create({"id_cliente": c2["_id"], "tipo_tramite": "Jubilacion", "responsable_username": "otro"})

        _set_session(monkeypatch, "abogado_x", "abogado")
        abo_rows = ClienteController.get_scoped()
        _set_session(monkeypatch, "sec", "secretaria")
        sec_rows = ClienteController.get_scoped()

        assert len(abo_rows) == 1
        assert len(sec_rows) == 2
