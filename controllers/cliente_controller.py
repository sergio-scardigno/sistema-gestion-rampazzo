"""Controlador de Clientes."""
import re

from core import db_local
from core.auth import Session
from core.permissions import es_scope_global_por_modulo
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
        session = Session.get()
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
        if session.logged_in and not data.get("created_by_username"):
            data["created_by_username"] = session.username
        return super().create(data)

    @classmethod
    def _scope_clause_for_user(cls, rol: str, username: str, alias: str = "") -> tuple[str, tuple]:
        """Define visibilidad de clientes por rol."""
        if es_scope_global_por_modulo(rol, "clientes"):
            return "", ()
        # Regla requerida: abogado solo ve clientes creados por el o
        # clientes que tengan carpeta asignada al abogado.
        if rol == "abogado":
            table_prefix = alias or "clientes."
            id_col = f"{table_prefix}_id"
            created_col = f"{table_prefix}created_by_username"
            has_created_col = db_local.table_has_column("clientes", "created_by_username")
            exists_clause = (
                f"EXISTS (SELECT 1 FROM expedientes e "
                f"WHERE e.id_cliente = {id_col} "
                "AND (e.responsable_username = ? OR e.responsable_secundario_username = ?) "
                "AND (e.is_deleted IS NULL OR e.is_deleted = 0))"
            )
            if has_created_col:
                return (
                    f"({created_col} = ? OR {exists_clause})",
                    (username, username, username),
                )
            return (exists_clause, (username, username))
        return "", ()

    @classmethod
    def get_scoped(cls, where: str = "", params: tuple = (),
                   order_by: str = "", limit: int = 0) -> list[dict]:
        session = Session.get()
        sw, sp = cls._scope_clause_for_user(session.rol, session.username)
        if sw:
            if where:
                where = f"({where}) AND ({sw})"
                params = params + sp
            else:
                where = sw
                params = sp
        return cls.get_all(where=where, params=params, order_by=order_by, limit=limit)

    @classmethod
    def get_by_id_scoped(cls, _id: str) -> dict | None:
        rows = cls.get_scoped(where="_id = ?", params=(_id,), limit=1)
        return rows[0] if rows else None

    @classmethod
    def update(cls, _id: str, data: dict) -> dict | None:
        """Actualizar cliente con validacion de numero_carpeta, DNI y CUIL."""
        session = Session.get()
        if session.logged_in and session.rol == "abogado":
            if not cls.get_by_id_scoped(_id):
                return None
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

    @classmethod
    def delete(cls, _id: str) -> bool:
        session = Session.get()
        if session.logged_in and session.rol == "abogado":
            if not cls.get_by_id_scoped(_id):
                return False
        return super().delete(_id)

    # ------------------------------------------------------------------
    # Busquedas
    # ------------------------------------------------------------------

    @classmethod
    def search_clientes(cls, text: str) -> list[dict]:
        if not text.strip():
            return cls.get_scoped(order_by="nombre_completo ASC", limit=200)
        fields = ["nombre_completo", "dni", "cuil", "email", "telefonos", "numero_carpeta"]
        conditions = " OR ".join([f"{f} LIKE ?" for f in fields])
        params = tuple(f"%{text}%" for _ in fields)
        return cls.get_scoped(where=conditions, params=params, order_by="nombre_completo ASC", limit=200)

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
        return cls.get_scoped(
            where=f"{clean_expr} = ?",
            params=(digits,),
        )

    @classmethod
    def get_by_cuil(cls, cuil: str) -> dict | None:
        rows = cls.get_scoped(where="cuil = ?", params=(cuil,))
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
        rows = cls.get_scoped(where="numero_carpeta = ?", params=(nc,))
        return rows[0] if rows else None
