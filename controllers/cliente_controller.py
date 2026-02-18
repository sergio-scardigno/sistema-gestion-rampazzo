"""Controlador de Clientes."""
import re

from core import db_local
from controllers.base_controller import BaseController
from utils.validators import validate_dni, validate_cuil, format_cuil


class ClienteController(BaseController):
    TABLE = "clientes"
    ID_FIELD = "id_cliente"

    # ------------------------------------------------------------------
    # Numero de carpeta: validacion y sugerencia
    # ------------------------------------------------------------------

    @classmethod
    def get_suggested_numero_carpeta(cls) -> str:
        """Devuelve el siguiente numero de carpeta correlativo disponible (MAX+1)."""
        conn = db_local.get_connection()
        row = conn.execute(
            "SELECT MAX(CAST(numero_carpeta AS INTEGER)) FROM clientes "
            "WHERE numero_carpeta IS NOT NULL AND numero_carpeta != '' "
            "AND numero_carpeta NOT GLOB '*[^0-9]*'"
        ).fetchone()
        conn.close()
        max_val = row[0] if row and row[0] is not None else 0
        return str(max_val + 1)

    @classmethod
    def _validate_numero_carpeta(cls, numero_carpeta: str, exclude_id: str = "") -> tuple[bool, str]:
        """Valida que numero_carpeta sea obligatorio, numerico y unico.

        Args:
            numero_carpeta: valor a validar.
            exclude_id: _id del cliente a excluir (para updates).

        Returns:
            (ok, mensaje_error)
        """
        if not numero_carpeta or not str(numero_carpeta).strip():
            return False, "El numero de carpeta es obligatorio."
        nc = str(numero_carpeta).strip()
        if not nc.isdigit():
            return False, "El numero de carpeta debe contener solo numeros."
        # Unicidad
        where = "numero_carpeta = ?"
        params: tuple = (nc,)
        if exclude_id:
            where += " AND _id != ?"
            params = (nc, exclude_id)
        if db_local.count(cls.TABLE, where, params) > 0:
            return False, f"Ya existe un cliente con el numero de carpeta {nc}."
        return True, ""

    @classmethod
    def create(cls, data: dict) -> dict:
        """Crear cliente con validacion de numero_carpeta, DNI y CUIL."""
        nc = str(data.get("numero_carpeta", "")).strip()
        ok, msg = cls._validate_numero_carpeta(nc)
        if not ok:
            raise ValueError(msg)
        data["numero_carpeta"] = nc
        # Validar DNI
        dni = str(data.get("dni", "")).strip()
        ok, msg = validate_dni(dni)
        if not ok:
            raise ValueError(msg)
        # Validar y formatear CUIL
        cuil = str(data.get("cuil", "")).strip()
        ok, msg = validate_cuil(cuil)
        if not ok:
            raise ValueError(msg)
        if cuil:
            data["cuil"] = format_cuil(cuil)
        return super().create(data)

    @classmethod
    def update(cls, _id: str, data: dict) -> dict | None:
        """Actualizar cliente con validacion de numero_carpeta, DNI y CUIL."""
        if "numero_carpeta" in data:
            nc = str(data["numero_carpeta"]).strip()
            ok, msg = cls._validate_numero_carpeta(nc, exclude_id=_id)
            if not ok:
                raise ValueError(msg)
            data["numero_carpeta"] = nc
        if "dni" in data:
            dni = str(data["dni"]).strip()
            ok, msg = validate_dni(dni)
            if not ok:
                raise ValueError(msg)
        if "cuil" in data:
            cuil = str(data["cuil"]).strip()
            ok, msg = validate_cuil(cuil)
            if not ok:
                raise ValueError(msg)
            if cuil:
                data["cuil"] = format_cuil(cuil)
        return super().update(_id, data)

    # ------------------------------------------------------------------
    # Busquedas
    # ------------------------------------------------------------------

    @classmethod
    def search_clientes(cls, text: str) -> list[dict]:
        return cls.search(text, ["nombre_completo", "dni", "cuil", "email", "telefonos", "numero_carpeta"])

    @classmethod
    def _normalize_dni(cls, dni: str) -> str:
        """Extrae solo digitos de un DNI (elimina puntos, guiones, espacios)."""
        return re.sub(r'[^\d]', '', str(dni).strip())

    @classmethod
    def get_by_dni(cls, dni: str) -> dict | None:
        """Buscar cliente por DNI (match exacto, normalizado a digitos).

        Compara solo los digitos del campo DNI almacenado contra los digitos
        de la entrada, de modo que '12.345.678' coincide con '12345678'.
        """
        digits = cls._normalize_dni(dni)
        if not digits:
            return None
        rows = cls._find_by_dni_digits(digits)
        return rows[0] if rows else None

    @classmethod
    def search_by_dni(cls, dni: str) -> list[dict]:
        """Buscar clientes cuyo DNI coincida (normalizado a digitos).

        Devuelve todos los resultados (puede haber mas de uno si hay datos
        duplicados en la base).
        """
        digits = cls._normalize_dni(dni)
        if not digits:
            return []
        return cls._find_by_dni_digits(digits)

    @classmethod
    def _find_by_dni_digits(cls, digits: str) -> list[dict]:
        """Busca clientes cuyo DNI (solo digitos) coincide con *digits*.

        Usa REPLACE encadenados en SQL para eliminar puntos, guiones y
        espacios del campo almacenado antes de comparar.
        """
        clean_expr = "REPLACE(REPLACE(REPLACE(dni, '.', ''), '-', ''), ' ', '')"
        return cls.get_all(
            where=f"{clean_expr} = ?",
            params=(digits,),
        )

    @classmethod
    def get_by_cuil(cls, cuil: str) -> dict | None:
        rows = cls.get_all(where="cuil = ?", params=(cuil,))
        return rows[0] if rows else None

    @classmethod
    def count_all(cls) -> int:
        """Cuenta el total de clientes registrados."""
        return cls.count()

    @classmethod
    def get_by_numero_carpeta(cls, numero_carpeta: str) -> dict | None:
        """Buscar cliente por numero de carpeta fisica (match exacto)."""
        nc = str(numero_carpeta).strip()
        if not nc:
            return None
        rows = cls.get_all(where="numero_carpeta = ?", params=(nc,))
        return rows[0] if rows else None
