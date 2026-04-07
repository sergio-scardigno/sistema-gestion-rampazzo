"""Tests de integracion para core/db_local.py – esquema, CRUD y migraciones."""
import sqlite3
import pytest
from core import db_local


# =====================================================================
# Inicializacion y esquema
# =====================================================================

class TestInitDb:
    """Verificar que init_db() crea todas las tablas esperadas."""

    EXPECTED_TABLES = [
        "usuarios", "consultas", "clientes", "expedientes", "tareas",
        "comunicaciones", "movimientos", "documentos", "turnos",
        "audit_log", "session_signals", "sync_meta",
    ]

    def test_all_tables_exist(self):
        conn = db_local.get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        for table in self.EXPECTED_TABLES:
            assert table in tables, f"Tabla '{table}' no encontrada"

    def test_wal_mode_active(self):
        conn = db_local.get_connection()
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        assert mode == "wal"

    def test_foreign_keys_on(self):
        conn = db_local.get_connection()
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        conn.close()
        assert fk == 1

    def test_usuarios_has_eliminado_column(self):
        """Migracion: columna 'eliminado' debe existir."""
        conn = db_local.get_connection()
        cols = [c[1] for c in conn.execute("PRAGMA table_info(usuarios)").fetchall()]
        conn.close()
        assert "eliminado" in cols

    def test_audit_log_has_rol_column(self):
        """Migracion: columna 'rol' debe existir en audit_log."""
        conn = db_local.get_connection()
        cols = [c[1] for c in conn.execute("PRAGMA table_info(audit_log)").fetchall()]
        conn.close()
        assert "rol" in cols

    def test_documentos_has_versionado_columns(self):
        """Migracion: columnas de versionado deben existir."""
        conn = db_local.get_connection()
        cols = [c[1] for c in conn.execute("PRAGMA table_info(documentos)").fetchall()]
        conn.close()
        for col in ["subcategoria", "descripcion", "tamano_bytes", "mime_type",
                     "version_padre", "notas_version"]:
            assert col in cols, f"Columna '{col}' no encontrada en documentos"

    def test_responsable_username_columns(self):
        """Migracion: columna responsable_username en tablas operativas."""
        tables_with_ru = ["tareas", "turnos", "documentos", "comunicaciones", "movimientos"]
        for table in tables_with_ru:
            conn = db_local.get_connection()
            cols = [c[1] for c in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            conn.close()
            assert "responsable_username" in cols, f"Falta responsable_username en {table}"

    def test_movimientos_has_observaciones_column(self):
        """Migracion: columna observaciones en movimientos."""
        conn = db_local.get_connection()
        cols = [c[1] for c in conn.execute("PRAGMA table_info(movimientos)").fetchall()]
        conn.close()
        assert "observaciones" in cols

    def test_expedientes_double_responsable(self):
        """Expedientes debe tener ambas columnas de responsable username."""
        conn = db_local.get_connection()
        cols = [c[1] for c in conn.execute("PRAGMA table_info(expedientes)").fetchall()]
        conn.close()
        assert "responsable_username" in cols
        assert "responsable_secundario_username" in cols

    def test_notificaciones_resolution_columns(self):
        """Notificaciones debe soportar leida/resuelta por separado."""
        conn = db_local.get_connection()
        cols = [c[1] for c in conn.execute("PRAGMA table_info(notificaciones)").fetchall()]
        conn.close()
        for col in ["updated_at", "resuelta", "fecha_resolucion", "resuelta_por_estado"]:
            assert col in cols, f"Columna '{col}' no encontrada en notificaciones"


# =====================================================================
# CRUD helpers
# =====================================================================

class TestInsert:
    def test_insert_and_find(self):
        data = {"_id": "test-1", "nombre_completo": "Juan", "dni": "12345678",
                "sync_status": "pending", "version": 1}
        db_local.insert("clientes", data)
        result = db_local.find_by_id("clientes", "test-1")
        assert result is not None
        assert result["nombre_completo"] == "Juan"

    def test_insert_or_replace(self):
        """INSERT OR REPLACE debe sobreescribir por _id."""
        db_local.insert("clientes", {"_id": "dup-1", "nombre_completo": "V1",
                                      "version": 1, "sync_status": "pending"})
        db_local.insert("clientes", {"_id": "dup-1", "nombre_completo": "V2",
                                      "version": 2, "sync_status": "pending"})
        result = db_local.find_by_id("clientes", "dup-1")
        assert result["nombre_completo"] == "V2"


class TestUpdate:
    def test_update_changes_field(self):
        db_local.insert("clientes", {"_id": "u-1", "nombre_completo": "Before",
                                      "version": 1, "sync_status": "synced"})
        db_local.update("clientes", "u-1", {"nombre_completo": "After"})
        result = db_local.find_by_id("clientes", "u-1")
        assert result["nombre_completo"] == "After"

    def test_update_preserves_other_fields(self):
        db_local.insert("clientes", {"_id": "u-2", "nombre_completo": "Name",
                                      "dni": "11111111", "version": 1, "sync_status": "synced"})
        db_local.update("clientes", "u-2", {"nombre_completo": "Updated"})
        result = db_local.find_by_id("clientes", "u-2")
        assert result["dni"] == "11111111"


class TestDelete:
    def test_delete_removes_row(self):
        db_local.insert("clientes", {"_id": "d-1", "nombre_completo": "ToDelete",
                                      "version": 1, "sync_status": "synced"})
        db_local.delete("clientes", "d-1")
        assert db_local.find_by_id("clientes", "d-1") is None

    def test_delete_nonexistent_no_error(self):
        # No debe lanzar excepcion
        db_local.delete("clientes", "no-existe")


class TestFindAll:
    def _seed_clientes(self):
        for i in range(5):
            db_local.insert("clientes", {
                "_id": f"fa-{i}", "nombre_completo": f"Cliente {i}",
                "dni": f"1000000{i}", "version": 1, "sync_status": "synced",
            })

    def test_find_all_returns_all(self):
        self._seed_clientes()
        rows = db_local.find_all("clientes")
        assert len(rows) == 5

    def test_find_all_with_where(self):
        self._seed_clientes()
        rows = db_local.find_all("clientes", where="nombre_completo LIKE ?",
                                  params=("%Cliente 0%",))
        assert len(rows) == 1

    def test_find_all_with_limit(self):
        self._seed_clientes()
        rows = db_local.find_all("clientes", limit=3)
        assert len(rows) == 3

    def test_find_all_with_order_by(self):
        self._seed_clientes()
        rows = db_local.find_all("clientes", order_by="nombre_completo DESC")
        assert rows[0]["nombre_completo"] == "Cliente 4"


class TestCount:
    def test_count_all(self):
        for i in range(3):
            db_local.insert("clientes", {"_id": f"c-{i}", "nombre_completo": f"C{i}",
                                          "version": 1, "sync_status": "synced"})
        assert db_local.count("clientes") == 3

    def test_count_with_where(self):
        db_local.insert("clientes", {"_id": "cw-1", "nombre_completo": "A",
                                      "version": 1, "sync_status": "synced"})
        db_local.insert("clientes", {"_id": "cw-2", "nombre_completo": "B",
                                      "version": 1, "sync_status": "pending"})
        assert db_local.count("clientes", "sync_status = 'pending'") == 1

    def test_count_empty(self):
        assert db_local.count("clientes") == 0


class TestFindByIdNone:
    def test_returns_none_for_missing(self):
        assert db_local.find_by_id("clientes", "inexistente") is None


# =====================================================================
# Sync helpers
# =====================================================================

class TestSyncHelpers:
    def test_find_pending(self):
        db_local.insert("clientes", {"_id": "sp-1", "nombre_completo": "P",
                                      "version": 1, "sync_status": "pending"})
        db_local.insert("clientes", {"_id": "sp-2", "nombre_completo": "S",
                                      "version": 1, "sync_status": "synced"})
        pending = db_local.find_pending("clientes")
        assert len(pending) == 1
        assert pending[0]["_id"] == "sp-1"

    def test_mark_synced(self):
        db_local.insert("clientes", {"_id": "ms-1", "nombre_completo": "M",
                                      "version": 1, "sync_status": "pending"})
        db_local.mark_synced("clientes", "ms-1")
        row = db_local.find_by_id("clientes", "ms-1")
        assert row["sync_status"] == "synced"


class TestSyncMeta:
    def test_set_and_get(self):
        db_local.set_sync_meta("last_sync", "2025-01-01T00:00:00")
        assert db_local.get_sync_meta("last_sync") == "2025-01-01T00:00:00"

    def test_get_missing_returns_none(self):
        assert db_local.get_sync_meta("no_existe") is None

    def test_overwrite(self):
        db_local.set_sync_meta("key", "v1")
        db_local.set_sync_meta("key", "v2")
        assert db_local.get_sync_meta("key") == "v2"


# =====================================================================
# Context manager
# =====================================================================

class TestGetCursor:
    def test_commit_on_success(self):
        with db_local.get_cursor() as cur:
            cur.execute(
                "INSERT INTO clientes (_id, nombre_completo, version, sync_status) VALUES (?, ?, ?, ?)",
                ("gc-1", "Test", 1, "synced"),
            )
        assert db_local.find_by_id("clientes", "gc-1") is not None

    def test_rollback_on_error(self):
        with pytest.raises(Exception):
            with db_local.get_cursor() as cur:
                cur.execute(
                    "INSERT INTO clientes (_id, nombre_completo, version, sync_status) VALUES (?, ?, ?, ?)",
                    ("gc-2", "Test", 1, "synced"),
                )
                raise ValueError("Error forzado")
        # El insert debe haber sido revertido
        assert db_local.find_by_id("clientes", "gc-2") is None


# =====================================================================
# Helpers de conversion
# =====================================================================

class TestDictFromRow:
    def test_returns_dict(self):
        db_local.insert("clientes", {"_id": "dr-1", "nombre_completo": "Dict",
                                      "version": 1, "sync_status": "synced"})
        conn = db_local.get_connection()
        row = conn.execute("SELECT * FROM clientes WHERE _id = 'dr-1'").fetchone()
        conn.close()
        result = db_local.dict_from_row(row)
        assert isinstance(result, dict)
        assert result["_id"] == "dr-1"

    def test_none_returns_none(self):
        assert db_local.dict_from_row(None) is None
