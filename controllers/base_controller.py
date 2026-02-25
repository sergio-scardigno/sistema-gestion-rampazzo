"""
Controlador CRUD generico que opera sobre SQLite local.
Los cambios se marcan como 'pending' para que el SyncEngine los suba a Atlas.
"""
import json
from datetime import datetime, timezone

from core import db_local
from core.audit import log_action
from models.base_model import new_id, now_iso, base_fields
from config import MACHINE_ID


class BaseController:
    """Controlador base para CRUD sobre una tabla SQLite."""

    TABLE: str = ""  # Subclases definen esto
    ID_FIELD: str = ""  # Campo de ID legible (ej: id_cliente)

    @classmethod
    def _next_id(cls) -> int:
        """Auto-incremental para el campo ID legible."""
        if not cls.ID_FIELD:
            return 0
        rows = db_local.find_all(cls.TABLE, order_by=f"{cls.ID_FIELD} DESC", limit=1)
        if rows and rows[0].get(cls.ID_FIELD):
            return int(rows[0][cls.ID_FIELD]) + 1
        return 1

    @classmethod
    def create(cls, data: dict) -> dict:
        """Crear un registro nuevo."""
        record = base_fields()
        record.update(data)
        if cls.ID_FIELD and cls.ID_FIELD not in record:
            record[cls.ID_FIELD] = cls._next_id()
        # Serializar listas/dicts a JSON
        for k, v in record.items():
            if isinstance(v, (list, dict)):
                record[k] = json.dumps(v, ensure_ascii=False)
        db_local.insert(cls.TABLE, record)
        log_action("create", cls.TABLE, record["_id"], datos_nuevos=record)
        return record

    @classmethod
    def update(cls, _id: str, data: dict) -> dict | None:
        """Actualizar un registro existente."""
        existing = db_local.find_by_id(cls.TABLE, _id)
        if not existing:
            return None
        data["updated_at"] = now_iso()
        data["version"] = existing.get("version", 1) + 1
        data["sync_status"] = "pending"
        # Serializar listas/dicts a JSON
        for k, v in data.items():
            if isinstance(v, (list, dict)):
                data[k] = json.dumps(v, ensure_ascii=False)
        db_local.update(cls.TABLE, _id, data)
        log_action("update", cls.TABLE, _id, datos_anteriores=existing, datos_nuevos=data)
        return db_local.find_by_id(cls.TABLE, _id)

    @classmethod
    def delete(cls, _id: str) -> bool:
        """Eliminar un registro (soft-delete via sync, hard-delete local)."""
        existing = db_local.find_by_id(cls.TABLE, _id)
        if not existing:
            return False
        db_local.delete(cls.TABLE, _id)
        log_action("delete", cls.TABLE, _id, datos_anteriores=existing)
        return True

    @classmethod
    def get_by_id(cls, _id: str) -> dict | None:
        row = db_local.find_by_id(cls.TABLE, _id)
        if row:
            cls._deserialize(row)
        return row

    @classmethod
    def get_all(cls, where: str = "", params: tuple = (),
                order_by: str = "", limit: int = 0) -> list[dict]:
        rows = db_local.find_all(cls.TABLE, where=where, params=params,
                                 order_by=order_by, limit=limit)
        for r in rows:
            cls._deserialize(r)
        return rows

    @classmethod
    def count(cls, where: str = "", params: tuple = ()) -> int:
        return db_local.count(cls.TABLE, where=where, params=params)

    @classmethod
    def search(cls, text: str, fields: list[str], limit: int = 100) -> list[dict]:
        """Busqueda por texto en multiples campos."""
        if not text.strip():
            return cls.get_all(limit=limit)
        conditions = " OR ".join([f"{f} LIKE ?" for f in fields])
        params = tuple(f"%{text}%" for _ in fields)
        return cls.get_all(where=conditions, params=params, limit=limit)

    @classmethod
    def get_scoped(cls, where: str = "", params: tuple = (),
                   order_by: str = "", limit: int = 0,
                   campo_responsable: str = "responsable_username",
                   campo_secundario: str = "") -> list[dict]:
        """get_all con filtro automatico de visibilidad por sesion.

        Roles globales ven todo; roles restringidos ven solo asignado.
        """
        from core.auth import Session
        from core.permissions import scope_where
        session = Session.get()
        sw, sp = scope_where(session.rol, session.username,
                             campo_responsable, campo_secundario)
        if sw:
            if where:
                where = f"({where}) AND ({sw})"
                params = params + sp
            else:
                where = sw
                params = sp
        return cls.get_all(where=where, params=params,
                           order_by=order_by, limit=limit)

    @classmethod
    def _deserialize(cls, row: dict):
        """Deserializar campos JSON (telefonos, datos_rama, etc)."""
        for k, v in row.items():
            if isinstance(v, str) and v and v[0] in ("[", "{"):
                try:
                    row[k] = json.loads(v)
                except (json.JSONDecodeError, ValueError):
                    pass
