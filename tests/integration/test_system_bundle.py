"""
Tests de exportacion/importacion completa del sistema (system_bundle).

Verifica el round-trip: export -> import a nueva BD y que los datos coincidan.
"""
import json
import os
import uuid
import zipfile

import pytest

from core import db_local
from models.base_model import now_iso


@pytest.fixture
def populated_db(tmp_path, monkeypatch):
    """Inserta datos de ejemplo en varias tablas y configura DOCS_DIR."""
    docs_dir = tmp_path / "documentos"
    docs_dir.mkdir()
    monkeypatch.setattr("config.DOCS_DIR", docs_dir)
    monkeypatch.setattr("utils.system_bundle.DOCS_DIR", docs_dir)

    _ts = now_iso()

    # Usuarios
    for i in range(3):
        db_local.insert("usuarios", {
            "_id": str(uuid.uuid4()),
            "username": f"user{i}",
            "password_hash": "fakehash",
            "nombre_completo": f"Usuario {i}",
            "email": f"u{i}@test.com",
            "rol": "abogado",
            "activo": 1,
            "eliminado": 0,
            "updated_at": _ts,
            "version": 1,
            "sync_status": "synced",
            "created_by_machine": "test",
        })

    # Clientes
    client_ids = []
    for i in range(5):
        cid = str(uuid.uuid4())
        client_ids.append(cid)
        db_local.insert("clientes", {
            "_id": cid,
            "numero_carpeta": str(100 + i),
            "nombre_completo": f"Cliente {i}",
            "dni": f"1234567{i}",
            "cuil": f"20-1234567{i}-9",
            "clave_mi_anses": f"clave_anses_{i}",
            "clave_fiscal": f"clave_fiscal_{i}",
            "telefonos": json.dumps([f"362400{i:04d}"]),
            "updated_at": _ts,
            "version": 1,
            "sync_status": "synced",
            "created_by_machine": "test",
        })

    # Expedientes
    exp_ids = []
    for i in range(3):
        eid = str(uuid.uuid4())
        exp_ids.append(eid)
        db_local.insert("expedientes", {
            "_id": eid,
            "id_cliente": client_ids[i],
            "tipo_tramite": "Jubilacion",
            "estado": "Activo",
            "responsable": "Usuario 0",
            "responsable_username": "user0",
            "fecha_apertura": "2025-01-01",
            "updated_at": _ts,
            "version": 1,
            "sync_status": "synced",
            "created_by_machine": "test",
        })

    # Tareas
    for i in range(4):
        db_local.insert("tareas", {
            "_id": str(uuid.uuid4()),
            "id_expediente": exp_ids[i % len(exp_ids)],
            "tipo_accion": "Seguimiento",
            "descripcion": f"Tarea {i}",
            "responsable": "Usuario 0",
            "responsable_username": "user0",
            "estado": "Pendiente",
            "updated_at": _ts,
            "version": 1,
            "sync_status": "synced",
            "created_by_machine": "test",
        })

    # Documentos con archivos fisicos
    exp_doc_dir = docs_dir / exp_ids[0]
    exp_doc_dir.mkdir()
    fake_file = exp_doc_dir / "test_doc.pdf"
    fake_file.write_text("contenido de prueba", encoding="utf-8")

    db_local.insert("documentos", {
        "_id": str(uuid.uuid4()),
        "id_expediente": exp_ids[0],
        "categoria": "Identidad",
        "nombre": "DNI_frente",
        "ruta_archivo": str(fake_file),
        "tamano_bytes": fake_file.stat().st_size,
        "updated_at": _ts,
        "version": 1,
        "sync_status": "synced",
        "created_by_machine": "test",
    })

    # Turnos
    db_local.insert("turnos", {
        "_id": str(uuid.uuid4()),
        "id_cliente": client_ids[0],
        "id_expediente": exp_ids[0],
        "fecha_turno": "2025-04-10",
        "hora_turno": "09:30",
        "oficina_anses": "UDAI Test",
        "estado": "Pendiente",
        "responsable_username": "user0",
        "updated_at": _ts,
        "version": 1,
        "sync_status": "synced",
        "created_by_machine": "test",
    })

    return {
        "docs_dir": docs_dir,
        "client_ids": client_ids,
        "exp_ids": exp_ids,
    }


class TestExportSystemBundle:
    """Tests de exportacion."""

    def test_export_creates_zip(self, tmp_path, populated_db):
        from utils.system_bundle import export_system_bundle

        zip_path = str(tmp_path / "export.zip")
        stats = export_system_bundle(zip_path)

        assert os.path.isfile(zip_path)
        assert stats["total_rows"] > 0
        assert stats["tables"]["clientes"] == 5
        assert stats["tables"]["expedientes"] == 3
        assert stats["tables"]["tareas"] == 4
        assert stats["tables"]["usuarios"] == 3
        assert stats["tables"]["documentos"] == 1
        assert stats["tables"]["turnos"] == 1

    def test_export_zip_contains_csv(self, tmp_path, populated_db):
        from utils.system_bundle import export_system_bundle

        zip_path = str(tmp_path / "export.zip")
        export_system_bundle(zip_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            assert "rampazzo_export.csv" in names

    def test_export_zip_contains_docs(self, tmp_path, populated_db):
        from utils.system_bundle import export_system_bundle

        zip_path = str(tmp_path / "export.zip")
        stats = export_system_bundle(zip_path)

        assert stats["files_copied"] == 1
        with zipfile.ZipFile(zip_path, "r") as zf:
            doc_files = [n for n in zf.namelist() if n.startswith("documentos/")]
            assert len(doc_files) == 1

    def test_export_csv_has_meta_row(self, tmp_path, populated_db):
        from utils.system_bundle import export_system_bundle
        import csv
        import io

        zip_path = str(tmp_path / "export.zip")
        export_system_bundle(zip_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            csv_content = zf.read("rampazzo_export.csv").decode("utf-8")

        reader = csv.reader(io.StringIO(csv_content))
        header = next(reader)
        assert header == ["table", "row_json"]

        first_data = next(reader)
        assert first_data[0] == "__meta__"
        meta = json.loads(first_data[1])
        assert "exported_at" in meta
        assert "app_version" in meta
        assert "table_counts" in meta

    def test_export_doc_paths_are_relative(self, tmp_path, populated_db):
        from utils.system_bundle import export_system_bundle
        import csv
        import io

        zip_path = str(tmp_path / "export.zip")
        export_system_bundle(zip_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            csv_content = zf.read("rampazzo_export.csv").decode("utf-8")

        reader = csv.reader(io.StringIO(csv_content))
        next(reader)  # header
        for row in reader:
            if row[0] == "documentos":
                rec = json.loads(row[1])
                ruta = rec.get("ruta_archivo", "")
                assert ruta.startswith("documentos/"), f"Ruta deberia ser relativa: {ruta}"
                assert "\\" not in ruta


class TestImportSystemBundle:
    """Tests de importacion."""

    def test_import_creates_new_db(self, tmp_path, populated_db, monkeypatch):
        from utils.system_bundle import export_system_bundle, import_system_bundle

        zip_path = str(tmp_path / "export.zip")
        export_system_bundle(zip_path)

        monkeypatch.setattr("config.DATA_DIR", tmp_path / "import_target")
        monkeypatch.setattr("utils.system_bundle.DATA_DIR", tmp_path / "import_target")
        (tmp_path / "import_target").mkdir()

        monkeypatch.setattr("config.CONFIG_FILE", tmp_path / "import_target" / "config.ini")
        monkeypatch.setattr("utils.system_bundle.CONFIG_FILE", tmp_path / "import_target" / "config.ini")

        stats = import_system_bundle(zip_path)

        assert stats["new_db_path"] != ""
        assert os.path.isfile(stats["new_db_path"])
        assert stats["total_rows"] > 0

    def test_round_trip_counts_match(self, tmp_path, populated_db, monkeypatch):
        from utils.system_bundle import export_system_bundle, import_system_bundle

        zip_path = str(tmp_path / "export.zip")
        export_stats = export_system_bundle(zip_path)

        monkeypatch.setattr("config.DATA_DIR", tmp_path / "import_target")
        monkeypatch.setattr("utils.system_bundle.DATA_DIR", tmp_path / "import_target")
        (tmp_path / "import_target").mkdir()

        monkeypatch.setattr("config.CONFIG_FILE", tmp_path / "import_target" / "config.ini")
        monkeypatch.setattr("utils.system_bundle.CONFIG_FILE", tmp_path / "import_target" / "config.ini")

        import_stats = import_system_bundle(zip_path)

        for table in ["clientes", "expedientes", "tareas", "usuarios", "documentos", "turnos"]:
            assert import_stats["tables"].get(table, 0) == export_stats["tables"].get(table, 0), \
                f"Conteo de {table} no coincide: export={export_stats['tables'].get(table)} import={import_stats['tables'].get(table)}"

    def test_round_trip_data_integrity(self, tmp_path, populated_db, monkeypatch):
        from utils.system_bundle import export_system_bundle, import_system_bundle
        import sqlite3

        zip_path = str(tmp_path / "export.zip")
        export_system_bundle(zip_path)

        monkeypatch.setattr("config.DATA_DIR", tmp_path / "import_target")
        monkeypatch.setattr("utils.system_bundle.DATA_DIR", tmp_path / "import_target")
        (tmp_path / "import_target").mkdir()

        monkeypatch.setattr("config.CONFIG_FILE", tmp_path / "import_target" / "config.ini")
        monkeypatch.setattr("utils.system_bundle.CONFIG_FILE", tmp_path / "import_target" / "config.ini")

        stats = import_system_bundle(zip_path)

        new_conn = sqlite3.connect(stats["new_db_path"])
        new_conn.row_factory = sqlite3.Row

        clientes = [dict(r) for r in new_conn.execute("SELECT * FROM clientes").fetchall()]
        assert len(clientes) == 5
        nombres = {c["nombre_completo"] for c in clientes}
        for i in range(5):
            assert f"Cliente {i}" in nombres

        claves = [c for c in clientes if c.get("clave_mi_anses")]
        assert len(claves) == 5

        new_conn.close()

    def test_round_trip_docs_copied(self, tmp_path, populated_db, monkeypatch):
        from utils.system_bundle import export_system_bundle, import_system_bundle
        import sqlite3

        zip_path = str(tmp_path / "export.zip")
        export_system_bundle(zip_path)

        monkeypatch.setattr("config.DATA_DIR", tmp_path / "import_target")
        monkeypatch.setattr("utils.system_bundle.DATA_DIR", tmp_path / "import_target")
        (tmp_path / "import_target").mkdir()

        monkeypatch.setattr("config.CONFIG_FILE", tmp_path / "import_target" / "config.ini")
        monkeypatch.setattr("utils.system_bundle.CONFIG_FILE", tmp_path / "import_target" / "config.ini")

        stats = import_system_bundle(zip_path)

        assert stats["files_restored"] == 1
        assert os.path.isdir(stats["new_docs_dir"])

        new_conn = sqlite3.connect(stats["new_db_path"])
        new_conn.row_factory = sqlite3.Row
        doc = dict(new_conn.execute("SELECT * FROM documentos LIMIT 1").fetchone())
        new_conn.close()

        ruta = doc.get("ruta_archivo", "")
        assert ruta.startswith(stats["new_docs_dir"])
        assert os.path.isfile(ruta), f"El archivo deberia existir: {ruta}"

    def test_import_invalid_zip_raises(self, tmp_path, monkeypatch):
        from utils.system_bundle import import_system_bundle

        monkeypatch.setattr("config.DATA_DIR", tmp_path)
        monkeypatch.setattr("utils.system_bundle.DATA_DIR", tmp_path)
        monkeypatch.setattr("config.CONFIG_FILE", tmp_path / "config.ini")
        monkeypatch.setattr("utils.system_bundle.CONFIG_FILE", tmp_path / "config.ini")

        bad_zip = tmp_path / "bad.zip"
        with zipfile.ZipFile(str(bad_zip), "w") as zf:
            zf.writestr("random.txt", "no csv here")

        with pytest.raises(FileNotFoundError, match="No es un bundle valido"):
            import_system_bundle(str(bad_zip))

    def test_import_updates_config_ini(self, tmp_path, populated_db, monkeypatch):
        from utils.system_bundle import export_system_bundle, import_system_bundle
        import configparser

        zip_path = str(tmp_path / "export.zip")
        export_system_bundle(zip_path)

        target_dir = tmp_path / "import_target"
        target_dir.mkdir()
        config_file = target_dir / "config.ini"

        monkeypatch.setattr("config.DATA_DIR", target_dir)
        monkeypatch.setattr("utils.system_bundle.DATA_DIR", target_dir)
        monkeypatch.setattr("config.CONFIG_FILE", config_file)
        monkeypatch.setattr("utils.system_bundle.CONFIG_FILE", config_file)

        stats = import_system_bundle(zip_path)

        assert config_file.exists()
        cfg = configparser.ConfigParser()
        cfg.read(str(config_file), encoding="utf-8")
        assert cfg.get("sqlite", "path") == stats["new_db_path"]
        assert cfg.get("paths", "docs_dir") == stats["new_docs_dir"]
