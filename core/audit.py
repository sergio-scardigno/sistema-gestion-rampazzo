"""
Log de auditoria inalterable.
Solo inserciones, nunca updates ni deletes.

Inmutabilidad garantizada:
  - El modulo NO expone funciones de update/delete sobre audit_log.
  - Se aplica un trigger SQLite que bloquea DELETE y UPDATE en init.
"""
import uuid
import json
from datetime import datetime, timezone

from core import db_local
from core.auth import Session
from config import MACHINE_ID


# Triggers SQL de proteccion – se crean en init_audit_protection()
_AUDIT_PROTECTION_SQL = [
    """
    CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
    BEFORE DELETE ON audit_log
    BEGIN
        SELECT RAISE(ABORT, 'audit_log es inmutable: no se permite DELETE');
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS audit_log_no_update
    BEFORE UPDATE ON audit_log
    BEGIN
        SELECT RAISE(ABORT, 'audit_log es inmutable: no se permite UPDATE');
    END;
    """,
]


def init_audit_protection():
    """Aplica triggers de inmutabilidad sobre audit_log.
    Debe llamarse despues de init_db()."""
    conn = db_local.get_connection()
    for sql in _AUDIT_PROTECTION_SQL:
        conn.execute(sql)
    conn.commit()
    conn.close()


def log_action(accion: str, coleccion: str, documento_id: str,
               datos_anteriores: dict | None = None,
               datos_nuevos: dict | None = None,
               usuario_override: str | None = None):
    """Registrar una accion en el audit log.
    
    Args:
        accion: tipo de accion (crear, actualizar, eliminar, login, logout, etc.)
        coleccion: tabla/coleccion afectada
        documento_id: ID del registro afectado
        datos_anteriores: snapshot antes del cambio
        datos_nuevos: snapshot despues del cambio
        usuario_override: si se especifica, se usa en vez del usuario de sesion
    """
    session = Session.get()
    entry = {
        "_id": str(uuid.uuid4()),
        "usuario": usuario_override or (session.username if session.logged_in else "sistema"),
        "rol": session.rol if session.logged_in else "",
        "accion": accion,
        "coleccion": coleccion,
        "documento_id": documento_id,
        "datos_anteriores": json.dumps(datos_anteriores, default=str, ensure_ascii=False) if datos_anteriores else None,
        "datos_nuevos": json.dumps(datos_nuevos, default=str, ensure_ascii=False) if datos_nuevos else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sync_status": "pending",
        "created_by_machine": MACHINE_ID,
    }
    db_local.insert("audit_log", entry)


def log_user_action(accion: str, target_user_id: str,
                    datos_anteriores: dict | None = None,
                    datos_nuevos: dict | None = None):
    """Registrar una accion sobre usuarios (crear, pausar, reactivar, eliminar, reset_password, cambio_rol)."""
    log_action(accion, "usuarios", target_user_id, datos_anteriores, datos_nuevos)


def log_login(username: str, exito: bool, detalle: str = ""):
    """Registrar intento de login."""
    log_action(
        accion="login_ok" if exito else "login_fallido",
        coleccion="sesiones",
        documento_id=username,
        datos_nuevos={"exito": exito, "detalle": detalle},
        usuario_override=username,
    )


def log_logout(username: str):
    """Registrar cierre de sesion."""
    log_action(
        accion="logout",
        coleccion="sesiones",
        documento_id=username,
        usuario_override=username,
    )
