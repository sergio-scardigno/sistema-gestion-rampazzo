"""Tests de integracion para DocumentoController."""
import pytest
from pathlib import Path
from controllers.documento_controller import DocumentoController


class TestDocumentoCRUD:
    def test_create(self, session_superusuario, sample_documento):
        r = DocumentoController.create(sample_documento)
        assert r["nombre"] == "DNI_frente"
        assert r["categoria"] == "Identidad"

    def test_update(self, session_superusuario, sample_documento):
        r = DocumentoController.create(sample_documento)
        updated = DocumentoController.update(r["_id"], {"descripcion": "Actualizado"})
        assert updated["descripcion"] == "Actualizado"

    def test_delete(self, session_superusuario, sample_documento):
        r = DocumentoController.create(sample_documento)
        assert DocumentoController.delete(r["_id"]) is True


class TestGetByExpediente:
    def test_returns_docs_for_expediente(self, session_superusuario, sample_documento):
        DocumentoController.create(sample_documento)
        DocumentoController.create({**sample_documento, "id_expediente": "otro"})
        results = DocumentoController.get_by_expediente("exp-test-001")
        assert len(results) == 1


class TestGetVersiones:
    def test_returns_all_versions(self, session_superusuario, sample_documento):
        r1 = DocumentoController.create(sample_documento)
        # Crear otra version con el mismo nombre y expediente
        r2 = DocumentoController.create({
            **sample_documento,
            "version_doc": 2,
            "notas_version": "V2",
        })
        versions = DocumentoController.get_versiones(r1["_id"])
        assert len(versions) >= 1

    def test_nonexistent_returns_empty(self, session_superusuario):
        assert len(DocumentoController.get_versiones("no-existe")) == 0


class TestGetStatsByExpediente:
    def test_stats_structure(self, session_superusuario, sample_documento):
        DocumentoController.create(sample_documento)
        DocumentoController.create({
            **sample_documento,
            "categoria": "Laboral",
            "nombre": "Recibo",
        })
        stats = DocumentoController.get_stats_by_expediente("exp-test-001")
        assert stats["total"] == 2
        assert "Identidad" in stats["por_categoria"]
        assert "Laboral" in stats["por_categoria"]
        assert isinstance(stats["tamano_total_mb"], float)

    def test_empty_stats(self, session_superusuario):
        stats = DocumentoController.get_stats_by_expediente("no-existe")
        assert stats["total"] == 0


class TestSearchDocumentos:
    def test_search_by_nombre(self, session_superusuario, sample_documento):
        DocumentoController.create(sample_documento)
        results = DocumentoController.search_documentos("DNI")
        assert len(results) == 1

    def test_search_by_categoria(self, session_superusuario, sample_documento):
        DocumentoController.create(sample_documento)
        results = DocumentoController.search_documentos("Identidad")
        assert len(results) == 1


class TestConstants:
    def test_categorias(self):
        assert "Identidad" in DocumentoController.CATEGORIAS
        assert "Laboral" in DocumentoController.CATEGORIAS

    def test_subcategorias_structure(self):
        assert isinstance(DocumentoController.SUBCATEGORIAS, dict)
        assert "DNI" in DocumentoController.SUBCATEGORIAS["Identidad"]
