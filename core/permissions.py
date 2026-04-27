"""
Sistema RBAC – Roles y permisos.

Mapeo con el pliego tecnico:
  Pliego            -> Sistema
  Recepcion         -> secretaria
  Juridico          -> abogado
  Administracion    -> administrador
  Direccion         -> superusuario
  (adicional)       -> agente
"""
import logging

logger = logging.getLogger(__name__)

ROLES = ["secretaria", "agente", "abogado", "analisis", "administrador", "admin_visor", "superusuario"]

# Alias formales del pliego para mostrar en UI
ROL_ALIAS = {
    "secretaria": "Recepcion",
    "agente": "Agente",
    "abogado": "Juridico",
    "analisis": "Analisis",
    "administrador": "Administracion",
    "admin_visor": "Admin Visor",
    "superusuario": "Direccion",
}

ROL_DESCRIPCION = {
    "secretaria": "Lectura de clientes, carpetas, tareas, turnos y comunicaciones",
    "agente": "Operacion completa de consultas, clientes, carpetas y tareas",
    "abogado": "Juridico: carpetas, documentos y tareas",
    "analisis": "Analisis: carpetas, documentos y tareas",
    "administrador": "Control total operativo, economico, auditoria y gestion de empleados",
    "admin_visor": "Control administrativo con movimientos economicos en solo lectura",
    "superusuario": "Acceso total, configuracion, migracion y auditoria",
}

PERMISOS: dict[str, list[str]] = {
    "secretaria": [
        "clientes.read",
        "expedientes.read",
        "tareas.read",
        "turnos.read",
        "comunicaciones.read",
        "citas.read",
    ],
    "agente": [
        "clientes.*",
        "expedientes.*",
        "tareas.*",
        "turnos.*",
        "comunicaciones.*",
        "citas.*",
        "documentos.read",
        "escritos.read",
    ],
    "abogado": [
        "clientes.*",
        "expedientes.*",
        "tareas.*",
        "turnos.*",
        "comunicaciones.*",
        "citas.*",
        "documentos.*",
        "escritos.*",
    ],
    "analisis": [
        "clientes.*",
        "expedientes.*",
        "tareas.*",
        "turnos.*",
        "comunicaciones.*",
        "citas.*",
        "documentos.*",
        "escritos.*",
    ],
    "administrador": [
        "clientes.*",
        "expedientes.*",
        "tareas.*",
        "turnos.*",
        "comunicaciones.*",
        "citas.*",
        "documentos.*",
        "escritos.*",
        "movimientos.*",
        "reportes.*",
        "auditoria.*",
        "usuarios.*",
    ],
    "admin_visor": [
        "clientes.*",
        "expedientes.*",
        "tareas.*",
        "turnos.*",
        "comunicaciones.*",
        "citas.*",
        "documentos.*",
        "escritos.*",
        "movimientos.read",
        "reportes.*",
        "auditoria.*",
        "usuarios.*",
    ],
    "superusuario": [
        "*",
    ],
}

# Mapeo modulo -> permisos necesarios para ver la seccion en el sidebar
MODULO_PERMISOS = {
    "dashboard": "clientes.read",
    "clientes": "clientes.read",
    "expedientes": "expedientes.read",
    "carpetas_iniciadas": "expedientes.read",
    "tareas": "tareas.read",
    "turnos": "turnos.read",
    "citas": "citas.read",
    "comunicaciones": "comunicaciones.read",
    "documentos": "documentos.read",
    "administracion": "movimientos.read",
    "reportes": "reportes.*",
    "auditoria": "auditoria.*",
    "usuarios": "usuarios.*",
    "configuracion": "configuracion.*",
    "migracion": "migracion.*",
}


def tiene_permiso(rol: str, permiso_requerido: str) -> bool:
    """Verifica si un rol tiene un permiso especifico."""
    permisos_rol = PERMISOS.get(rol, [])
    if "*" in permisos_rol:
        return True
    for p in permisos_rol:
        if p == permiso_requerido:
            return True
        # Wildcard por modulo: "consultas.*" cubre "consultas.read", "consultas.create", etc.
        if p.endswith(".*"):
            modulo = p[:-2]
            if permiso_requerido.startswith(modulo + "."):
                return True
            if permiso_requerido == modulo:
                return True
    return False


def modulos_permitidos(rol: str) -> list[str]:
    """Retorna la lista de modulos que un rol puede ver en el sidebar."""
    permitidos = []
    for modulo, permiso in MODULO_PERMISOS.items():
        if tiene_permiso(rol, permiso):
            permitidos.append(modulo)
    # Modulo dedicado: requiere ver carpetas y el calendario de citas
    if (
        tiene_permiso(rol, "expedientes.read")
        and tiene_permiso(rol, "citas.read")
        and "pendientes_citar" not in permitidos
    ):
        permitidos.append("pendientes_citar")
    return permitidos


# ── Visibilidad por asignacion ──

ROLES_GLOBALES = {"administrador", "admin_visor", "superusuario"}


def es_rol_global(rol: str) -> bool:
    """Retorna True si el rol tiene visibilidad global (ve todos los registros)."""
    return rol in ROLES_GLOBALES


def es_scope_global_por_modulo(rol: str, modulo: str = "") -> bool:
    """Define excepciones de visibilidad global por modulo."""
    if es_rol_global(rol):
        return True
    # Regla solicitada por cliente:
    # secretaria ve todos los clientes y carpetas.
    if rol == "secretaria" and modulo in {"clientes", "expedientes", "citas"}:
        return True
    return False


def scope_where(rol: str, username: str, campo: str = "responsable_username",
                campo_secundario: str = "", modulo: str = "") -> tuple[str, tuple]:
    """Genera una clausula WHERE + params para filtrar por asignacion.

    Si el rol es global, retorna condicion vacia (ve todo).
    Si el rol es restringido, filtra por username en el campo indicado.

    Args:
        rol: rol del usuario en sesion
        username: username del usuario en sesion
        campo: nombre de la columna de responsable_username
        campo_secundario: campo adicional (ej. responsable_secundario_username en expedientes)

    Returns:
        (where_clause, params) para usar en queries
    """
    if es_scope_global_por_modulo(rol, modulo):
        return "", ()

    if campo_secundario:
        return (
            f"({campo} = ? OR {campo_secundario} = ?)",
            (username, username)
        )
    return (f"{campo} = ?", (username,))


def get_active_users() -> list[dict]:
    """Retorna la lista de usuarios activos y no eliminados del sistema."""
    from core import db_local
    return db_local.find_all(
        "usuarios",
        where="(activo = 1) AND (eliminado = 0 OR eliminado IS NULL)",
        order_by="nombre_completo ASC",
    )


def get_active_users_fresh() -> list[dict]:
    """Como get_active_users, pero intenta traer usuarios nuevos desde Atlas antes.

    Evita que en formularios (tareas, carpetas, etc.) no figuren personas dadas
    de alta en otro equipo hasta una sincronizacion manual completa.
    """
    try:
        from core.db_remote import is_connected
        from core.sync_engine import pull_usuarios_from_remote
        if is_connected():
            pull_usuarios_from_remote()
    except Exception:
        logger.exception("get_active_users_fresh: pull opcional fallo; se usa cache local")
    return get_active_users()
