"""Tests unitarios para models/base_model.py"""
import re
from datetime import datetime, timezone

from models.base_model import new_id, now_iso, base_fields


class TestNewId:
    def test_returns_uuid_string(self):
        _id = new_id()
        assert isinstance(_id, str)
        # Patron UUID v4
        pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
        assert re.match(pattern, _id)

    def test_unique_per_call(self):
        ids = {new_id() for _ in range(100)}
        assert len(ids) == 100


class TestNowIso:
    def test_returns_iso_string(self):
        result = now_iso()
        # Debe poder parsearse como ISO
        dt = datetime.fromisoformat(result)
        assert dt.tzinfo is not None  # debe tener timezone

    def test_is_utc(self):
        result = now_iso()
        dt = datetime.fromisoformat(result)
        assert dt.tzinfo == timezone.utc


class TestBaseFields:
    def test_contains_required_keys(self):
        fields = base_fields()
        assert "_id" in fields
        assert "updated_at" in fields
        assert "version" in fields
        assert "sync_status" in fields
        assert "created_by_machine" in fields

    def test_version_starts_at_one(self):
        assert base_fields()["version"] == 1

    def test_sync_status_is_pending(self):
        assert base_fields()["sync_status"] == "pending"

    def test_machine_id_is_patched(self):
        # El conftest pone MACHINE_ID = "test-machine"
        assert base_fields()["created_by_machine"] == "test-machine"

    def test_unique_ids(self):
        f1 = base_fields()
        f2 = base_fields()
        assert f1["_id"] != f2["_id"]
