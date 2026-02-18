"""Tests unitarios para core/permissions.py"""
import pytest
from core.permissions import (
    ROLES, PERMISOS, tiene_permiso, modulos_permitidos,
    es_rol_global, scope_where, ROLES_GLOBALES,
)


class TestTienePermiso:
    """Verificar que cada rol tiene los permisos esperados."""

    def test_superusuario_tiene_todo(self):
        assert tiene_permiso("superusuario", "cualquier.cosa")
        assert tiene_permiso("superusuario", "consultas.read")
        assert tiene_permiso("superusuario", "migracion.execute")

    def test_administrador_tiene_usuarios(self):
        assert tiene_permiso("administrador", "usuarios.create")
        assert tiene_permiso("administrador", "usuarios.delete")
        assert tiene_permiso("administrador", "auditoria.read")

    def test_abogado_tiene_expedientes_no_usuarios(self):
        assert tiene_permiso("abogado", "expedientes.create")
        assert tiene_permiso("abogado", "documentos.create")
        assert not tiene_permiso("abogado", "usuarios.create")
        assert not tiene_permiso("abogado", "movimientos.create")
        assert not tiene_permiso("abogado", "reportes.read")

    def test_agente_tiene_clientes_no_movimientos(self):
        assert tiene_permiso("agente", "clientes.create")
        assert tiene_permiso("agente", "expedientes.read")
        assert not tiene_permiso("agente", "movimientos.create")
        assert not tiene_permiso("agente", "auditoria.read")

    def test_secretaria_solo_lectura_mayormente(self):
        assert tiene_permiso("secretaria", "clientes.read")
        assert not tiene_permiso("secretaria", "clientes.create")
        assert not tiene_permiso("secretaria", "expedientes.create")
        assert tiene_permiso("secretaria", "expedientes.read")

    def test_wildcard_modulo_cubre_subpermisos(self):
        # "clientes.*" debe cubrir "clientes.read", "clientes.create", etc.
        assert tiene_permiso("agente", "clientes.read")
        assert tiene_permiso("agente", "clientes.create")
        assert tiene_permiso("agente", "clientes.delete")

    def test_rol_inexistente_no_tiene_permisos(self):
        assert not tiene_permiso("inexistente", "clientes.read")

    def test_permiso_exacto_vs_wildcard(self):
        # Secretaria tiene "clientes.read" explicitamente
        assert tiene_permiso("secretaria", "clientes.read")
        # Pero no tiene "clientes.*" ni "clientes.delete"
        assert not tiene_permiso("secretaria", "clientes.delete")


class TestRestriccionEconomicaYAdmin:
    """Verificar que agente, abogado y secretaria NO tienen acceso a
    modulos economicos, reportes, auditoria, empleados ni configuracion."""

    MODULOS_RESTRINGIDOS = [
        "movimientos.read", "movimientos.create",
        "reportes.read", "reportes.*",
        "auditoria.read", "auditoria.*",
        "usuarios.read", "usuarios.*",
        "configuracion.read", "configuracion.*",
    ]

    @pytest.mark.parametrize("rol", ["secretaria", "agente", "abogado"])
    def test_roles_sin_acceso_economico_ni_admin(self, rol):
        for permiso in self.MODULOS_RESTRINGIDOS:
            assert not tiene_permiso(rol, permiso), (
                f"{rol} no deberia tener permiso '{permiso}'"
            )

    def test_administrador_tiene_acceso_economico(self):
        assert tiene_permiso("administrador", "movimientos.read")
        assert tiene_permiso("administrador", "reportes.read")
        assert tiene_permiso("administrador", "auditoria.read")
        assert tiene_permiso("administrador", "usuarios.read")

    def test_superusuario_tiene_acceso_total(self):
        assert tiene_permiso("superusuario", "movimientos.read")
        assert tiene_permiso("superusuario", "reportes.read")
        assert tiene_permiso("superusuario", "configuracion.read")


class TestModulosPermitidos:
    def test_superusuario_ve_todo(self):
        modulos = modulos_permitidos("superusuario")
        assert "dashboard" in modulos
        assert "usuarios" in modulos
        assert "auditoria" in modulos
        assert "migracion" in modulos

    def test_secretaria_ve_limitado(self):
        modulos = modulos_permitidos("secretaria")
        assert "dashboard" in modulos
        assert "consultas" not in modulos
        assert "clientes" in modulos
        assert "usuarios" not in modulos
        assert "auditoria" not in modulos

    def test_administrador_ve_administracion(self):
        modulos = modulos_permitidos("administrador")
        assert "administracion" in modulos
        assert "auditoria" in modulos
        assert "usuarios" in modulos

    @pytest.mark.parametrize("rol", ["secretaria", "agente", "abogado"])
    def test_roles_restringidos_no_ven_modulos_economicos(self, rol):
        modulos = modulos_permitidos(rol)
        for mod in ["administracion", "reportes", "auditoria", "usuarios", "configuracion"]:
            assert mod not in modulos, (
                f"{rol} no deberia ver modulo '{mod}' en sidebar"
            )


class TestEsRolGlobal:
    def test_administrador_es_global(self):
        assert es_rol_global("administrador") is True

    def test_superusuario_es_global(self):
        assert es_rol_global("superusuario") is True

    def test_abogado_no_es_global(self):
        assert es_rol_global("abogado") is False

    def test_secretaria_no_es_global(self):
        assert es_rol_global("secretaria") is False


class TestScopeWhere:
    def test_rol_global_sin_filtro(self):
        where, params = scope_where("administrador", "admin")
        assert where == ""
        assert params == ()

    def test_rol_restringido_filtra_por_username(self):
        where, params = scope_where("abogado", "abogado1")
        assert "responsable_username = ?" in where
        assert params == ("abogado1",)

    def test_campo_secundario(self):
        where, params = scope_where(
            "agente", "agente1",
            campo="responsable_username",
            campo_secundario="responsable_secundario_username"
        )
        assert "responsable_username = ?" in where
        assert "responsable_secundario_username = ?" in where
        assert params == ("agente1", "agente1")

    def test_superusuario_sin_filtro(self):
        where, params = scope_where("superusuario", "super1")
        assert where == ""
        assert params == ()
