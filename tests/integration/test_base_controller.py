"""Tests de integracion para controllers/base_controller.py"""
import json
import pytest

from controllers.base_controller import BaseController
from core import db_local


# Controlador concreto de prueba que hereda BaseController
class _TestController(BaseController):
    TABLE = "clientes"
    ID_FIELD = "id_cliente"


class TestCreate:
    def test_create_returns_record(self, session_superusuario):
        record = _TestController.create({"nombre_completo": "Nuevo"})
        assert "_id" in record
        assert record["nombre_completo"] == "Nuevo"
        assert record["version"] == 1
        assert record["sync_status"] == "pending"

    def test_create_auto_id(self, session_superusuario):
        r1 = _TestController.create({"nombre_completo": "Primero"})
        r2 = _TestController.create({"nombre_completo": "Segundo"})
        assert r1["id_cliente"] == 1
        assert r2["id_cliente"] == 2

    def test_create_persists_in_db(self, session_superusuario):
        record = _TestController.create({"nombre_completo": "Persistido"})
        found = db_local.find_by_id("clientes", record["_id"])
        assert found is not None
        assert found["nombre_completo"] == "Persistido"

    def test_create_serializes_list(self, session_superusuario):
        record = _TestController.create({
            "nombre_completo": "ConTel",
            "telefonos": ["123", "456"],
        })
        # En la BD debe estar como JSON string
        raw = db_local.find_by_id("clientes", record["_id"])
        assert isinstance(raw["telefonos"], str)
        assert json.loads(raw["telefonos"]) == ["123", "456"]

    def test_create_generates_audit_log(self, session_superusuario):
        _TestController.create({"nombre_completo": "Auditado"})
        logs = db_local.find_all("audit_log", where="accion = 'create' AND coleccion = 'clientes'")
        assert len(logs) >= 1


class TestUpdate:
    def test_update_changes_field(self, session_superusuario):
        record = _TestController.create({"nombre_completo": "Original"})
        updated = _TestController.update(record["_id"], {"nombre_completo": "Editado"})
        assert updated["nombre_completo"] == "Editado"

    def test_update_increments_version(self, session_superusuario):
        record = _TestController.create({"nombre_completo": "V1"})
        updated = _TestController.update(record["_id"], {"nombre_completo": "V2"})
        assert updated["version"] == 2

    def test_update_sets_pending(self, session_superusuario):
        record = _TestController.create({"nombre_completo": "S"})
        db_local.mark_synced("clientes", record["_id"])
        updated = _TestController.update(record["_id"], {"nombre_completo": "S2"})
        assert updated["sync_status"] == "pending"

    def test_update_nonexistent_returns_none(self, session_superusuario):
        result = _TestController.update("no-existe", {"nombre_completo": "X"})
        assert result is None

    def test_update_updates_timestamp(self, session_superusuario):
        record = _TestController.create({"nombre_completo": "Ts"})
        old_ts = record["updated_at"]
        updated = _TestController.update(record["_id"], {"nombre_completo": "Ts2"})
        assert updated["updated_at"] >= old_ts

    def test_update_generates_audit_log(self, session_superusuario):
        record = _TestController.create({"nombre_completo": "AudUp"})
        _TestController.update(record["_id"], {"nombre_completo": "AudUp2"})
        logs = db_local.find_all("audit_log", where="accion = 'update' AND coleccion = 'clientes'")
        assert len(logs) >= 1


class TestDelete:
    def test_delete_removes_record(self, session_superusuario):
        record = _TestController.create({"nombre_completo": "Borrar"})
        result = _TestController.delete(record["_id"])
        assert result is True
        assert _TestController.get_by_id(record["_id"]) is None
        raw = db_local.find_by_id("clientes", record["_id"])
        assert int(raw.get("is_deleted", 0)) == 1
        assert raw.get("sync_status") == "pending"

    def test_delete_nonexistent_returns_false(self, session_superusuario):
        assert _TestController.delete("no-existe") is False

    def test_delete_generates_audit_log(self, session_superusuario):
        record = _TestController.create({"nombre_completo": "AudDel"})
        _TestController.delete(record["_id"])
        logs = db_local.find_all("audit_log", where="accion = 'delete' AND coleccion = 'clientes'")
        assert len(logs) >= 1


class TestGetById:
    def test_existing(self, session_superusuario):
        record = _TestController.create({"nombre_completo": "Existe"})
        found = _TestController.get_by_id(record["_id"])
        assert found["nombre_completo"] == "Existe"

    def test_nonexistent(self):
        assert _TestController.get_by_id("no-existe") is None

    def test_deserializes_json_list(self, session_superusuario):
        _TestController.create({
            "nombre_completo": "Tel",
            "telefonos": ["111", "222"],
        })
        rows = _TestController.get_all()
        row = rows[0]
        assert isinstance(row["telefonos"], list)
        assert row["telefonos"] == ["111", "222"]


class TestGetAll:
    def test_returns_all(self, session_superusuario):
        for i in range(3):
            _TestController.create({"nombre_completo": f"All{i}"})
        assert len(_TestController.get_all()) == 3

    def test_with_where_filter(self, session_superusuario):
        _TestController.create({"nombre_completo": "Alpha"})
        _TestController.create({"nombre_completo": "Beta"})
        rows = _TestController.get_all(where="nombre_completo = ?", params=("Alpha",))
        assert len(rows) == 1
        assert rows[0]["nombre_completo"] == "Alpha"

    def test_with_limit(self, session_superusuario):
        for i in range(5):
            _TestController.create({"nombre_completo": f"Lim{i}"})
        assert len(_TestController.get_all(limit=2)) == 2


class TestCount:
    def test_count(self, session_superusuario):
        for i in range(4):
            _TestController.create({"nombre_completo": f"Cnt{i}"})
        assert _TestController.count() == 4

    def test_count_with_filter(self, session_superusuario):
        _TestController.create({"nombre_completo": "A"})
        _TestController.create({"nombre_completo": "B"})
        assert _TestController.count(where="nombre_completo = ?", params=("A",)) == 1


class TestSearch:
    def test_search_finds_match(self, session_superusuario):
        _TestController.create({"nombre_completo": "Carlos Garcia"})
        _TestController.create({"nombre_completo": "Ana Lopez"})
        results = _TestController.search("Carlos", ["nombre_completo"])
        assert len(results) == 1
        assert results[0]["nombre_completo"] == "Carlos Garcia"

    def test_search_empty_text_returns_all(self, session_superusuario):
        _TestController.create({"nombre_completo": "A"})
        _TestController.create({"nombre_completo": "B"})
        results = _TestController.search("", ["nombre_completo"])
        assert len(results) == 2

    def test_search_case_insensitive_via_like(self, session_superusuario):
        _TestController.create({"nombre_completo": "CARLOS"})
        results = _TestController.search("carlos", ["nombre_completo"])
        assert len(results) == 1


class TestNextId:
    def test_auto_increments(self, session_superusuario):
        r1 = _TestController.create({"nombre_completo": "Uno"})
        r2 = _TestController.create({"nombre_completo": "Dos"})
        r3 = _TestController.create({"nombre_completo": "Tres"})
        assert r1["id_cliente"] == 1
        assert r2["id_cliente"] == 2
        assert r3["id_cliente"] == 3

    def test_starts_at_one_empty_table(self, session_superusuario):
        r = _TestController.create({"nombre_completo": "First"})
        assert r["id_cliente"] == 1


class TestDeserialize:
    def test_deserialize_json_array(self, session_superusuario):
        _TestController.create({
            "nombre_completo": "Des",
            "telefonos": ["a", "b"],
        })
        row = _TestController.get_all()[0]
        assert isinstance(row["telefonos"], list)

    def test_non_json_string_unchanged(self, session_superusuario):
        _TestController.create({"nombre_completo": "Plain", "email": "x@y.com"})
        row = _TestController.get_all()[0]
        assert row["email"] == "x@y.com"
