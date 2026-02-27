"""Tests de exportaciones separadas de análisis (clientes y carpetas)."""
from pathlib import Path
import uuid

import pandas as pd

from core import db_local


def _seed_clientes_y_carpetas():
    ts = "2026-01-01T00:00:00+00:00"
    c_id = str(uuid.uuid4())
    e_id = str(uuid.uuid4())
    db_local.insert("clientes", {
        "_id": c_id,
        "id_cliente": 1001,
        "numero_carpeta": "1001",
        "nombre_completo": "Cliente Analisis",
        "dni": "12345678",
        "cuil": "20-12345678-9",
        "procedencia_contacto": "Web",
        "telefonos": '["3624000000"]',
        "updated_at": ts,
        "version": 1,
        "sync_status": "synced",
        "created_by_machine": "test-machine",
    })
    db_local.insert("expedientes", {
        "_id": e_id,
        "id_expediente": 9001,
        "id_cliente": c_id,
        "tipo_tramite": "Jubilacion",
        "rama": "Previsional",
        "subtipo": "Ordinaria",
        "estado": "Activo",
        "responsable": "Test",
        "responsable_username": "testsuper",
        "fecha_apertura": "2026-01-05",
        "updated_at": ts,
        "version": 1,
        "sync_status": "synced",
        "created_by_machine": "test-machine",
    })


class TestExportesAnalisis:
    def test_export_clientes_csv(self, tmp_path):
        from utils.export import export_clientes_csv, CLIENTES_ANALISIS_COLUMNS
        _seed_clientes_y_carpetas()
        path = tmp_path / "clientes.csv"
        export_clientes_csv(str(path))
        assert path.exists()
        df = pd.read_csv(path)
        assert list(df.columns) == CLIENTES_ANALISIS_COLUMNS
        assert len(df) >= 1
        assert "Cliente Analisis" in set(df["nombre_completo"].astype(str))

    def test_export_clientes_excel(self, tmp_path):
        from utils.export import export_clientes_excel, CLIENTES_ANALISIS_COLUMNS
        _seed_clientes_y_carpetas()
        path = tmp_path / "clientes.xlsx"
        export_clientes_excel(str(path))
        assert path.exists()
        df = pd.read_excel(path)
        assert list(df.columns) == CLIENTES_ANALISIS_COLUMNS
        assert len(df) >= 1

    def test_export_carpetas_csv(self, tmp_path):
        from utils.export import export_carpetas_csv, CARPETAS_ANALISIS_COLUMNS
        _seed_clientes_y_carpetas()
        path = tmp_path / "carpetas.csv"
        export_carpetas_csv(str(path))
        assert path.exists()
        df = pd.read_csv(path)
        assert list(df.columns) == CARPETAS_ANALISIS_COLUMNS
        assert len(df) >= 1
        assert "Jubilacion" in set(df["tipo_tramite"].astype(str))

    def test_export_carpetas_excel(self, tmp_path):
        from utils.export import export_carpetas_excel, CARPETAS_ANALISIS_COLUMNS
        _seed_clientes_y_carpetas()
        path = tmp_path / "carpetas.xlsx"
        export_carpetas_excel(str(path))
        assert path.exists()
        df = pd.read_excel(path)
        assert list(df.columns) == CARPETAS_ANALISIS_COLUMNS
        assert len(df) >= 1
