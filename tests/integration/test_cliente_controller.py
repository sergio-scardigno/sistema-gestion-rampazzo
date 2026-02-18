"""Tests de integracion para ClienteController."""
import pytest
from controllers.cliente_controller import ClienteController


class TestClienteCRUD:
    def test_create_cliente(self, session_superusuario, sample_cliente):
        r = ClienteController.create(sample_cliente)
        assert r["nombre_completo"] == "Juan Perez"
        assert r["id_cliente"] == 1
        assert r["numero_carpeta"] == "1001"

    def test_update_cliente(self, session_superusuario, sample_cliente):
        r = ClienteController.create(sample_cliente)
        updated = ClienteController.update(r["_id"], {"nombre_completo": "Juan P. Modificado"})
        assert updated["nombre_completo"] == "Juan P. Modificado"
        assert updated["version"] == 2

    def test_delete_cliente(self, session_superusuario, sample_cliente):
        r = ClienteController.create(sample_cliente)
        assert ClienteController.delete(r["_id"]) is True
        assert ClienteController.get_by_id(r["_id"]) is None

    def test_get_by_id(self, session_superusuario, sample_cliente):
        r = ClienteController.create(sample_cliente)
        found = ClienteController.get_by_id(r["_id"])
        assert found["dni"] == "12345678"

    def test_get_all(self, session_superusuario):
        ClienteController.create({"nombre_completo": "A", "numero_carpeta": "5001"})
        ClienteController.create({"nombre_completo": "B", "numero_carpeta": "5002"})
        assert len(ClienteController.get_all()) == 2


class TestClienteSearch:
    def test_search_by_name(self, session_superusuario, sample_cliente):
        ClienteController.create(sample_cliente)
        results = ClienteController.search_clientes("Juan")
        assert len(results) == 1

    def test_search_by_dni(self, session_superusuario, sample_cliente):
        ClienteController.create(sample_cliente)
        results = ClienteController.search_clientes("12345678")
        assert len(results) == 1

    def test_search_by_email(self, session_superusuario, sample_cliente):
        ClienteController.create(sample_cliente)
        results = ClienteController.search_clientes("juan@test.com")
        assert len(results) == 1

    def test_search_by_numero_carpeta(self, session_superusuario, sample_cliente):
        ClienteController.create(sample_cliente)
        results = ClienteController.search_clientes("1001")
        assert len(results) == 1

    def test_search_no_match(self, session_superusuario, sample_cliente):
        ClienteController.create(sample_cliente)
        results = ClienteController.search_clientes("inexistente")
        assert len(results) == 0


class TestGetByDni:
    def test_found(self, session_superusuario, sample_cliente):
        ClienteController.create(sample_cliente)
        found = ClienteController.get_by_dni("12345678")
        assert found is not None
        assert found["nombre_completo"] == "Juan Perez"

    def test_not_found(self, session_superusuario):
        assert ClienteController.get_by_dni("99999999") is None

    def test_empty_returns_none(self, session_superusuario):
        assert ClienteController.get_by_dni("") is None

    def test_strips_whitespace(self, session_superusuario, sample_cliente):
        ClienteController.create(sample_cliente)
        found = ClienteController.get_by_dni("  12345678  ")
        assert found is not None


class TestGetByCuil:
    def test_found(self, session_superusuario, sample_cliente):
        ClienteController.create(sample_cliente)
        found = ClienteController.get_by_cuil("20-12345678-9")
        assert found is not None
        assert found["nombre_completo"] == "Juan Perez"

    def test_not_found(self, session_superusuario):
        assert ClienteController.get_by_cuil("99-99999999-9") is None


class TestGetByNumeroCarpeta:
    def test_found(self, session_superusuario, sample_cliente):
        ClienteController.create(sample_cliente)
        found = ClienteController.get_by_numero_carpeta("1001")
        assert found is not None
        assert found["nombre_completo"] == "Juan Perez"
        assert found["numero_carpeta"] == "1001"

    def test_not_found(self, session_superusuario):
        assert ClienteController.get_by_numero_carpeta("9999") is None

    def test_empty_returns_none(self, session_superusuario):
        assert ClienteController.get_by_numero_carpeta("") is None


class TestNumeroCarpetaValidation:
    """Validaciones de numero_carpeta: obligatorio, numerico, unico."""

    def test_create_sin_carpeta_falla(self, session_superusuario):
        with pytest.raises(ValueError, match="obligatorio"):
            ClienteController.create({"nombre_completo": "Sin Carpeta"})

    def test_create_carpeta_vacia_falla(self, session_superusuario):
        with pytest.raises(ValueError, match="obligatorio"):
            ClienteController.create({"nombre_completo": "Vacio", "numero_carpeta": ""})

    def test_create_carpeta_no_numerica_falla(self, session_superusuario):
        with pytest.raises(ValueError, match="solo numeros"):
            ClienteController.create({"nombre_completo": "Letras", "numero_carpeta": "ABC"})

    def test_create_carpeta_alfanumerica_falla(self, session_superusuario):
        with pytest.raises(ValueError, match="solo numeros"):
            ClienteController.create({"nombre_completo": "Mix", "numero_carpeta": "123A"})

    def test_create_carpeta_duplicada_falla(self, session_superusuario, sample_cliente):
        ClienteController.create(sample_cliente)  # carpeta 1001
        with pytest.raises(ValueError, match="Ya existe"):
            ClienteController.create({
                "nombre_completo": "Otro Cliente",
                "numero_carpeta": "1001",
            })

    def test_update_carpeta_duplicada_falla(self, session_superusuario):
        c1 = ClienteController.create({"nombre_completo": "C1", "numero_carpeta": "2001"})
        c2 = ClienteController.create({"nombre_completo": "C2", "numero_carpeta": "2002"})
        with pytest.raises(ValueError, match="Ya existe"):
            ClienteController.update(c2["_id"], {"numero_carpeta": "2001"})

    def test_update_misma_carpeta_ok(self, session_superusuario, sample_cliente):
        """Actualizar un cliente manteniendo su misma carpeta no debe fallar."""
        r = ClienteController.create(sample_cliente)
        updated = ClienteController.update(r["_id"], {"numero_carpeta": "1001"})
        assert updated["numero_carpeta"] == "1001"

    def test_update_sin_carpeta_en_data_ok(self, session_superusuario, sample_cliente):
        """Update que no toca numero_carpeta no debe validar."""
        r = ClienteController.create(sample_cliente)
        updated = ClienteController.update(r["_id"], {"nombre_completo": "Nuevo Nombre"})
        assert updated["nombre_completo"] == "Nuevo Nombre"
        assert updated["numero_carpeta"] == "1001"

    def test_create_carpeta_numerica_ok(self, session_superusuario):
        r = ClienteController.create({"nombre_completo": "Ok", "numero_carpeta": "42"})
        assert r["numero_carpeta"] == "42"

    def test_carpetas_diferentes_ok(self, session_superusuario):
        ClienteController.create({"nombre_completo": "A", "numero_carpeta": "3001"})
        ClienteController.create({"nombre_completo": "B", "numero_carpeta": "3002"})
        assert ClienteController.count() == 2
