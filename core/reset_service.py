"""
Servicio de reset total de base de datos.

Borra todos los datos de SQLite local y MongoDB Atlas,
preservando unicamente los usuarios seed originales.
"""
import logging

from core import db_local, db_remote
from core.db_remote import is_connected
from core.sync_engine import SYNC_TABLES

logger = logging.getLogger("reset_service")

# Todas las tablas locales que se deben vaciar (usuarios al final, se repuebla con seed)
ALL_LOCAL_TABLES = [
    "consultas", "clientes", "expedientes", "tareas", "turnos",
    "comunicaciones", "movimientos", "documentos", "audit_log",
    "session_signals", "notificaciones", "sync_meta", "app_meta",
    "usuarios",
]

# Colecciones remotas a vaciar (SYNC_TABLES + extras presentes en Atlas)
ALL_REMOTE_COLLECTIONS = list(dict.fromkeys(
    list(SYNC_TABLES) + ["app_meta", "record_locks", "notificaciones", "session_signals"]
))


def reset_all_data_keep_seed_users() -> tuple[bool, str]:
    """Ejecuta el reset total de la base de datos.

    Pasos:
      1. Verificar conexion a Atlas.
      2. Crear backup local.
      3. Detener el scheduler.
      4. Vaciar todas las colecciones en MongoDB Atlas.
      5. Vaciar todas las tablas en SQLite local
         (desactivando triggers de audit_log temporalmente).
      6. Re-inicializar la BD y crear los usuarios seed.

    Returns:
        (exito: bool, mensaje: str)
    """
    # 1. Verificar conexion
    if not is_connected():
        return False, "Se requiere conexion a MongoDB Atlas para ejecutar el reset."

    # 2. Backup local antes de borrar
    try:
        from core.scheduler import backup_database
        backup_database()
        logger.info("Backup creado antes del reset")
    except Exception:
        logger.warning("No se pudo crear backup pre-reset", exc_info=True)

    # 3. Detener scheduler para evitar que el sync reponga datos
    try:
        from core.scheduler import stop_scheduler
        stop_scheduler()
        logger.info("Scheduler detenido")
    except Exception:
        logger.warning("Error al detener scheduler", exc_info=True)

    # 4. Vaciar MongoDB Atlas
    try:
        db = db_remote.get_db()
        for col_name in ALL_REMOTE_COLLECTIONS:
            try:
                db[col_name].delete_many({})
                logger.info(f"MongoDB: coleccion '{col_name}' vaciada")
            except Exception:
                logger.warning("MongoDB: error al vaciar '%s'", col_name, exc_info=True)
    except Exception as e:
        return False, f"Error al conectar con MongoDB Atlas: {e}"

    # 5. Vaciar SQLite local
    try:
        conn = db_local.get_connection()
        # Desactivar triggers de inmutabilidad de audit_log
        conn.execute("DROP TRIGGER IF EXISTS audit_log_no_delete")
        conn.execute("DROP TRIGGER IF EXISTS audit_log_no_update")
        conn.commit()

        for table in ALL_LOCAL_TABLES:
            try:
                conn.execute(f"DELETE FROM {table}")
                logger.info(f"SQLite: tabla '{table}' vaciada")
            except Exception:
                logger.warning("SQLite: error al vaciar '%s'", table, exc_info=True)
        conn.commit()
        conn.close()
    except Exception as e:
        return False, f"Error al vaciar la base de datos local: {e}"

    # 6. Re-inicializar BD, triggers y usuarios seed
    try:
        from core.db_local import init_db
        from core.audit import init_audit_protection
        from core.auth import ensure_admin_exists

        init_db()
        init_audit_protection()
        ensure_admin_exists()
        logger.info("Base de datos re-inicializada con usuarios seed")
    except Exception as e:
        return False, f"Error al re-inicializar la base de datos: {e}"

    return True, "Base de datos reseteada exitosamente. Se crearon los usuarios por defecto."
