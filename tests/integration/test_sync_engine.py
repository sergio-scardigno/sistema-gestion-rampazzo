"""Tests de integracion para core/sync_engine.py

Estrategia hibrida:
- Mayoria de tests usan mocks de MongoDB (rapidos, estables)
- Tests criticos (marcados con @pytest.mark.slow) pueden usar Mongo real si esta disponible
"""
import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from core import db_local
from core.sync_engine import SyncEngine, SYNC_TABLES, LOCAL_ONLY_FIELDS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_local_pending(table, _id, extra=None):
    """Inserta un registro pendiente en SQLite local."""
    data = {
        "_id": _id,
        "sync_status": "pending",
        "version": 1,
        "updated_at": "2025-01-01T00:00:00+00:00",
        "created_by_machine": "test-machine",
    }
    if table == "usuarios":
        data.update({"username": f"user_{_id}", "password_hash": "xxx",
                      "nombre_completo": "Test", "rol": "agente", "activo": 1,
                      "eliminado": 0})
    elif table == "clientes":
        data.update({"nombre_completo": f"Cliente {_id}"})
    elif table == "expedientes":
        data.update({"tipo_tramite": "Jubilacion", "estado": "Activo"})
    if extra:
        data.update(extra)
    db_local.insert(table, data)
    return data


def _make_mock_db():
    """Crea un mock de la base de datos MongoDB."""
    mock_db = MagicMock()
    # Cada coleccion es un MagicMock con metodos find/replace_one
    for table in SYNC_TABLES:
        collection = MagicMock()
        collection.find.return_value = []  # Sin documentos remotos por defecto
        collection.replace_one.return_value = MagicMock(modified_count=1)
        mock_db.__getitem__ = MagicMock(side_effect=lambda t: getattr(mock_db, t, MagicMock()))
        setattr(mock_db, table, collection)
    return mock_db


# ---------------------------------------------------------------------------
# Tests con Mongo mockeado
# ---------------------------------------------------------------------------

class TestSyncConstants:
    def test_sync_tables_covers_all_entities(self):
        expected = {"usuarios", "consultas", "clientes", "expedientes",
                    "tareas", "turnos", "comunicaciones", "movimientos",
                    "documentos", "expediente_estado_historial", "audit_log"}
        assert expected == set(SYNC_TABLES)

    def test_local_only_fields(self):
        assert "sync_status" in LOCAL_ONLY_FIELDS


class TestSyncNoConnection:
    def test_sync_emits_failure_when_disconnected(self, qtbot):
        """Sin conexion a Mongo, sync debe emitir sync_finished(False, ...)."""
        engine = SyncEngine()
        with qtbot.waitSignal(engine.sync_finished, timeout=5000) as blocker:
            engine.sync()
        success, msg = blocker.args
        assert success is False
        assert "conexion" in msg.lower()


class TestPushPending:
    def test_pushes_pending_to_mongo(self, monkeypatch):
        """Registros pendientes locales se suben a Atlas via replace_one."""
        _insert_local_pending("clientes", "push-1")

        mock_db = _make_mock_db()
        engine = SyncEngine()
        engine._push_pending(mock_db, "clientes")

        mock_db.clientes.replace_one.assert_called_once()
        call_args = mock_db.clientes.replace_one.call_args
        assert call_args[0][0] == {"_id": "push-1"}  # filtro
        doc = call_args[0][1]
        assert "sync_status" not in doc  # campo local excluido

    def test_marks_synced_after_push(self, monkeypatch):
        _insert_local_pending("clientes", "push-2")

        mock_db = _make_mock_db()
        engine = SyncEngine()
        engine._push_pending(mock_db, "clientes")

        row = db_local.find_by_id("clientes", "push-2")
        assert row["sync_status"] == "synced"

    def test_multiple_pending_pushed(self, monkeypatch):
        _insert_local_pending("clientes", "mp-1")
        _insert_local_pending("clientes", "mp-2")

        mock_db = _make_mock_db()
        engine = SyncEngine()
        engine._push_pending(mock_db, "clientes")

        assert mock_db.clientes.replace_one.call_count == 2

    def test_push_converts_usuario_activo_to_bool(self, monkeypatch):
        _insert_local_pending("usuarios", "usr-1", {"activo": 1})

        mock_db = _make_mock_db()
        engine = SyncEngine()
        engine._push_pending(mock_db, "usuarios")

        doc = mock_db.usuarios.replace_one.call_args[0][1]
        assert doc["activo"] is True  # debe ser bool, no int

    def test_push_error_continues_to_next(self, monkeypatch):
        """Si falla un replace_one, el siguiente se intenta igual."""
        _insert_local_pending("clientes", "err-1")
        _insert_local_pending("clientes", "err-2")

        mock_db = _make_mock_db()
        mock_db.clientes.replace_one.side_effect = [Exception("network"), MagicMock()]
        engine = SyncEngine()
        engine._push_pending(mock_db, "clientes")

        assert mock_db.clientes.replace_one.call_count == 2
        # err-1 no se marco como synced (fallo), err-2 si
        assert db_local.find_by_id("clientes", "err-1")["sync_status"] == "pending"
        assert db_local.find_by_id("clientes", "err-2")["sync_status"] == "synced"

    def test_push_upsert_flag(self, monkeypatch):
        _insert_local_pending("clientes", "ups-1")

        mock_db = _make_mock_db()
        engine = SyncEngine()
        engine._push_pending(mock_db, "clientes")

        call_kwargs = mock_db.clientes.replace_one.call_args
        assert call_kwargs[1].get("upsert") is True or call_kwargs[0][2] is True


class TestPullRemote:
    def test_pulls_remote_docs_into_local(self, monkeypatch):
        """Documentos remotos se bajan a SQLite local."""
        remote_doc = {
            "_id": "remote-1",
            "nombre_completo": "Remoto",
            "updated_at": "2025-06-01T00:00:00",
            "version": 1,
        }

        mock_db = _make_mock_db()
        mock_db.clientes.find.return_value = [remote_doc]

        engine = SyncEngine()
        engine._pull_remote(mock_db, "clientes")

        local = db_local.find_by_id("clientes", "remote-1")
        assert local is not None
        assert local["nombre_completo"] == "Remoto"
        assert local["sync_status"] == "synced"

    def test_pull_skips_locally_pending(self, monkeypatch):
        """No sobreescribir registros locales pendientes."""
        _insert_local_pending("clientes", "conflict-1",
                              {"nombre_completo": "Local Pending"})

        remote_doc = {
            "_id": "conflict-1",
            "nombre_completo": "Remote Override",
            "updated_at": "2025-07-01T00:00:00",
            "version": 2,
        }

        mock_db = _make_mock_db()
        mock_db.clientes.find.return_value = [remote_doc]

        engine = SyncEngine()
        engine._pull_remote(mock_db, "clientes")

        local = db_local.find_by_id("clientes", "conflict-1")
        assert local["nombre_completo"] == "Local Pending"  # no sobreescrito

    def test_pull_converts_bools_to_int(self, monkeypatch):
        """Booleans de Mongo se convierten a int para SQLite."""
        remote_doc = {
            "_id": "bool-1",
            "username": "u1",
            "password_hash": "h",
            "nombre_completo": "Bool Test",
            "rol": "agente",
            "activo": True,
            "eliminado": False,
            "updated_at": "2025-01-01T00:00:00",
            "version": 1,
        }
        mock_db = _make_mock_db()
        mock_db.usuarios.find.return_value = [remote_doc]

        engine = SyncEngine()
        engine._pull_remote(mock_db, "usuarios")

        local = db_local.find_by_id("usuarios", "bool-1")
        assert local["activo"] in (1, "1")  # SQLite puede devolver int o str

    def test_pull_converts_lists_to_json(self, monkeypatch):
        """Listas de Mongo se serializan a JSON para SQLite."""
        remote_doc = {
            "_id": "list-1",
            "nombre_completo": "List Test",
            "telefonos": ["123", "456"],
            "updated_at": "2025-01-01T00:00:00",
            "version": 1,
        }
        mock_db = _make_mock_db()
        mock_db.clientes.find.return_value = [remote_doc]

        engine = SyncEngine()
        engine._pull_remote(mock_db, "clientes")

        local = db_local.find_by_id("clientes", "list-1")
        parsed = json.loads(local["telefonos"])
        assert parsed == ["123", "456"]

    def test_pull_uses_incremental_query(self, monkeypatch):
        """Si hay last_pull guardado, solo trae documentos mas recientes."""
        db_local.set_sync_meta("last_pull_clientes", "2025-06-01T00:00:00")

        mock_db = _make_mock_db()
        mock_db.clientes.find.return_value = []

        engine = SyncEngine()
        engine._pull_remote(mock_db, "clientes")

        # Verificar que el query tiene filtro de updated_at
        call_args = mock_db.clientes.find.call_args[0][0]
        assert "updated_at" in call_args
        assert call_args["updated_at"]["$gt"] == "2025-06-01T00:00:00"

    def test_pull_sets_sync_meta(self, monkeypatch):
        """Despues de pull, actualiza last_pull_<table>."""
        mock_db = _make_mock_db()
        mock_db.clientes.find.return_value = []

        engine = SyncEngine()
        engine._pull_remote(mock_db, "clientes")

        assert db_local.get_sync_meta("last_pull_clientes") is not None


class TestFullSync:
    def test_full_sync_cycle(self, monkeypatch, qtbot):
        """Ciclo completo: conectar, push, pull, emitir exito."""
        _insert_local_pending("clientes", "full-1")

        mock_db = _make_mock_db()
        for table in SYNC_TABLES:
            getattr(mock_db, table).find.return_value = []

        monkeypatch.setattr("core.sync_engine.is_connected", lambda: True)
        monkeypatch.setattr("core.db_remote.get_db", lambda: mock_db)

        engine = SyncEngine()
        with qtbot.waitSignal(engine.sync_finished, timeout=5000) as blocker:
            engine.sync()

        success, msg = blocker.args
        assert success is True
        assert "OK" in msg

        # Verificar que se actualizo last_sync
        assert db_local.get_sync_meta("last_sync") is not None

    def test_sync_emits_start_signal(self, monkeypatch, qtbot):
        mock_db = _make_mock_db()
        for table in SYNC_TABLES:
            getattr(mock_db, table).find.return_value = []

        monkeypatch.setattr("core.sync_engine.is_connected", lambda: True)
        monkeypatch.setattr("core.db_remote.get_db", lambda: mock_db)

        engine = SyncEngine()
        with qtbot.waitSignal(engine.sync_started, timeout=5000):
            engine.sync()

    def test_sync_handles_error(self, monkeypatch, qtbot):
        """Si ocurre un error durante sync, emite finished(False, error)."""
        monkeypatch.setattr("core.sync_engine.is_connected", lambda: True)
        monkeypatch.setattr("core.db_remote.get_db",
                            MagicMock(side_effect=Exception("DB crash")))

        engine = SyncEngine()
        with qtbot.waitSignal(engine.sync_finished, timeout=5000) as blocker:
            engine.sync()

        success, msg = blocker.args
        assert success is False
        assert "Error" in msg

    def test_force_sync_calls_sync(self, monkeypatch, qtbot):
        """force_sync es un alias de sync."""
        mock_db = _make_mock_db()
        for table in SYNC_TABLES:
            getattr(mock_db, table).find.return_value = []

        monkeypatch.setattr("core.sync_engine.is_connected", lambda: True)
        monkeypatch.setattr("core.db_remote.get_db", lambda: mock_db)

        engine = SyncEngine()
        with qtbot.waitSignal(engine.sync_finished, timeout=5000) as blocker:
            engine.force_sync()

        success, _ = blocker.args
        assert success is True


class TestSyncAllTables:
    def test_push_iterates_all_tables(self, monkeypatch, qtbot):
        """Sync debe iterar sobre todas las SYNC_TABLES."""
        # Insertar un pending en clientes y uno en tareas
        _insert_local_pending("clientes", "at-1")
        _insert_local_pending("tareas", "at-2", {
            "id_expediente": "e1", "tipo_accion": "Otro", "estado": "Pendiente",
        })

        mock_db = _make_mock_db()
        for table in SYNC_TABLES:
            getattr(mock_db, table).find.return_value = []

        monkeypatch.setattr("core.sync_engine.is_connected", lambda: True)
        monkeypatch.setattr("core.db_remote.get_db", lambda: mock_db)

        engine = SyncEngine()
        with qtbot.waitSignal(engine.sync_finished, timeout=5000):
            engine.sync()

        # Verificar que se hizo push para clientes y tareas
        assert mock_db.clientes.replace_one.call_count == 1
        assert mock_db.tareas.replace_one.call_count == 1
