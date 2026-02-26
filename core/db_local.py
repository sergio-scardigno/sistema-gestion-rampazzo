"""
SQLite local – cache/espejo de MongoDB Atlas.
Crea las tablas automaticamente al iniciar.
"""
import re
import sqlite3
import json
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from config import SQLITE_PATH

logger = logging.getLogger(__name__)

_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS usuarios (
    _id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    nombre_completo TEXT,
    email TEXT,
    rol TEXT NOT NULL DEFAULT 'secretaria',
    activo INTEGER DEFAULT 1,
    eliminado INTEGER DEFAULT 0,
    ultimo_acceso TEXT,
    updated_at TEXT,
    version INTEGER DEFAULT 1,
    sync_status TEXT DEFAULT 'synced',
    created_by_machine TEXT
);

CREATE TABLE IF NOT EXISTS consultas (
    _id TEXT PRIMARY KEY,
    id_consulta INTEGER,
    fecha_ingreso TEXT,
    canal TEXT,
    nombre TEXT,
    dni TEXT,
    edad INTEGER,
    telefono TEXT,
    email TEXT,
    localidad TEXT,
    motivo TEXT,
    estado TEXT DEFAULT 'Nuevo',
    operador TEXT,
    observaciones TEXT,
    id_cliente TEXT,
    updated_at TEXT,
    version INTEGER DEFAULT 1,
    sync_status TEXT DEFAULT 'synced',
    created_by_machine TEXT
);

CREATE TABLE IF NOT EXISTS clientes (
    _id TEXT PRIMARY KEY,
    id_cliente INTEGER,
    numero_carpeta TEXT,
    nombre_completo TEXT NOT NULL,
    dni TEXT,
    cuil TEXT,
    fecha_nacimiento TEXT,
    direccion TEXT,
    localidad TEXT,
    telefonos TEXT,
    email TEXT,
    obra_social TEXT,
    actividad TEXT,
    clave_mi_anses TEXT,
    clave_fiscal TEXT,
    procedencia_contacto TEXT,
    observaciones TEXT,
    updated_at TEXT,
    version INTEGER DEFAULT 1,
    sync_status TEXT DEFAULT 'synced',
    created_by_machine TEXT
);

CREATE TABLE IF NOT EXISTS expedientes (
    _id TEXT PRIMARY KEY,
    id_expediente INTEGER,
    id_cliente TEXT,
    tipo_tramite TEXT,
    area TEXT,
    rama TEXT,
    subtipo TEXT,
    datos_rama TEXT,
    datos_judicial TEXT,
    fecha_apertura TEXT,
    responsable TEXT,
    responsable_secundario TEXT,
    responsable_username TEXT DEFAULT '',
    responsable_secundario_username TEXT DEFAULT '',
    estado TEXT DEFAULT 'Activo',
    prioridad TEXT DEFAULT 'Normal',
    ubicacion_fisica TEXT,
    link_drive TEXT,
    fecha_cierre TEXT,
    resultado TEXT,
    numero_expediente_anses TEXT,
    clave_mi_anses TEXT,
    clave_fiscal TEXT,
    observaciones TEXT,
    updated_at TEXT,
    version INTEGER DEFAULT 1,
    sync_status TEXT DEFAULT 'synced',
    created_by_machine TEXT
);

CREATE TABLE IF NOT EXISTS tareas (
    _id TEXT PRIMARY KEY,
    id_tarea INTEGER,
    id_expediente TEXT,
    tipo_accion TEXT,
    descripcion TEXT,
    responsable TEXT,
    responsable_username TEXT DEFAULT '',
    creado_por_username TEXT DEFAULT '',
    creado_por_nombre TEXT DEFAULT '',
    fecha_inicio TEXT,
    fecha_vencimiento TEXT,
    estado TEXT DEFAULT 'Pendiente',
    resultado TEXT,
    archivo_adjunto TEXT,
    updated_at TEXT,
    version INTEGER DEFAULT 1,
    sync_status TEXT DEFAULT 'synced',
    created_by_machine TEXT
);

CREATE TABLE IF NOT EXISTS comunicaciones (
    _id TEXT PRIMARY KEY,
    id_comunicacion INTEGER,
    id_expediente TEXT,
    fecha TEXT,
    canal TEXT,
    emisor TEXT,
    receptor TEXT,
    responsable_username TEXT DEFAULT '',
    motivo TEXT,
    mensaje TEXT,
    resultado TEXT,
    updated_at TEXT,
    version INTEGER DEFAULT 1,
    sync_status TEXT DEFAULT 'synced',
    created_by_machine TEXT
);

CREATE TABLE IF NOT EXISTS movimientos (
    _id TEXT PRIMARY KEY,
    id_movimiento INTEGER,
    id_cliente TEXT,
    id_expediente TEXT,
    tipo TEXT,
    monto REAL,
    fecha TEXT,
    forma_pago TEXT,
    estado TEXT DEFAULT 'Pendiente',
    comprobante TEXT,
    saldo REAL,
    responsable_username TEXT DEFAULT '',
    updated_at TEXT,
    version INTEGER DEFAULT 1,
    sync_status TEXT DEFAULT 'synced',
    created_by_machine TEXT
);

CREATE TABLE IF NOT EXISTS documentos (
    _id TEXT PRIMARY KEY,
    id_expediente TEXT,
    categoria TEXT,
    subcategoria TEXT DEFAULT '',
    nombre TEXT,
    descripcion TEXT DEFAULT '',
    ruta_archivo TEXT,
    tamano_bytes INTEGER DEFAULT 0,
    mime_type TEXT DEFAULT '',
    fecha TEXT,
    responsable TEXT,
    responsable_username TEXT DEFAULT '',
    version_doc INTEGER DEFAULT 1,
    version_padre TEXT DEFAULT '',
    notas_version TEXT DEFAULT '',
    updated_at TEXT,
    version INTEGER DEFAULT 1,
    sync_status TEXT DEFAULT 'synced',
    created_by_machine TEXT
);

CREATE TABLE IF NOT EXISTS modelos_escrito (
    _id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    descripcion TEXT DEFAULT '',
    rama TEXT DEFAULT '',
    contenido_html TEXT NOT NULL,
    activo INTEGER DEFAULT 1,
    updated_at TEXT,
    version INTEGER DEFAULT 1,
    sync_status TEXT DEFAULT 'synced',
    created_by_machine TEXT
);

CREATE TABLE IF NOT EXISTS escritos (
    _id TEXT PRIMARY KEY,
    id_expediente TEXT NOT NULL,
    id_modelo TEXT DEFAULT '',
    titulo TEXT NOT NULL,
    contenido_html TEXT NOT NULL,
    fecha_creacion TEXT,
    responsable TEXT DEFAULT '',
    responsable_username TEXT DEFAULT '',
    updated_at TEXT,
    version INTEGER DEFAULT 1,
    sync_status TEXT DEFAULT 'synced',
    created_by_machine TEXT
);

CREATE TABLE IF NOT EXISTS turnos (
    _id TEXT PRIMARY KEY,
    id_turno INTEGER,
    id_cliente TEXT,
    id_expediente TEXT,
    fecha_turno TEXT,
    hora_turno TEXT,
    oficina_anses TEXT,
    tipo_tramite TEXT,
    codigo_turno TEXT,
    estado TEXT DEFAULT 'Pendiente',
    responsable TEXT,
    responsable_username TEXT DEFAULT '',
    documentacion_lista INTEGER DEFAULT 0,
    notas_preparacion TEXT,
    resultado TEXT,
    requiere_nuevo_turno INTEGER DEFAULT 0,
    observaciones TEXT,
    updated_at TEXT,
    version INTEGER DEFAULT 1,
    sync_status TEXT DEFAULT 'synced',
    created_by_machine TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    _id TEXT PRIMARY KEY,
    usuario TEXT,
    rol TEXT DEFAULT '',
    accion TEXT,
    coleccion TEXT,
    documento_id TEXT,
    datos_anteriores TEXT,
    datos_nuevos TEXT,
    timestamp TEXT,
    sync_status TEXT DEFAULT 'synced',
    created_by_machine TEXT
);

CREATE TABLE IF NOT EXISTS session_signals (
    _id TEXT PRIMARY KEY,
    target_user TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    created_at TEXT,
    processed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS notificaciones (
    _id TEXT PRIMARY KEY,
    target_username TEXT NOT NULL,
    tipo TEXT NOT NULL,
    mensaje TEXT,
    id_referencia TEXT DEFAULT '',
    created_at TEXT,
    leida INTEGER DEFAULT 0,
    sync_status TEXT DEFAULT 'synced',
    created_by_machine TEXT
);

CREATE TABLE IF NOT EXISTS expediente_estado_historial (
    _id TEXT PRIMARY KEY,
    id_expediente TEXT NOT NULL,
    estado TEXT NOT NULL,
    responsable_username TEXT DEFAULT '',
    usuario TEXT DEFAULT 'sistema',
    inicio_ts TEXT NOT NULL,
    fin_ts TEXT,
    origen TEXT DEFAULT 'manual',
    updated_at TEXT,
    version INTEGER DEFAULT 1,
    sync_status TEXT DEFAULT 'synced',
    created_by_machine TEXT
);

CREATE TABLE IF NOT EXISTS sync_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA encoding='UTF-8'")
    return conn


@contextmanager
def get_cursor():
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Crear todas las tablas si no existen."""
    conn = get_connection()
    conn.executescript(_TABLES_SQL)
    # Migracion: agregar columna eliminado si no existe (para BD existentes)
    try:
        conn.execute("SELECT eliminado FROM usuarios LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE usuarios ADD COLUMN eliminado INTEGER DEFAULT 0")
        conn.commit()
    # Migracion: agregar columna rol a audit_log si no existe
    try:
        conn.execute("SELECT rol FROM audit_log LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE audit_log ADD COLUMN rol TEXT DEFAULT ''")
        conn.commit()
    # Migracion: agregar columnas de versionado a documentos si no existen
    for col, default in [
        ("subcategoria", "''"), ("descripcion", "''"), ("tamano_bytes", "0"),
        ("mime_type", "''"), ("version_padre", "''"), ("notas_version", "''"),
    ]:
        try:
            conn.execute(f"SELECT {col} FROM documentos LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute(f"ALTER TABLE documentos ADD COLUMN {col} TEXT DEFAULT {default}")
            conn.commit()
    # Migracion: agregar columna numero_carpeta a clientes si no existe
    try:
        conn.execute("SELECT numero_carpeta FROM clientes LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE clientes ADD COLUMN numero_carpeta TEXT")
        conn.commit()
    # Migracion: agregar columna localidad a clientes si no existe
    try:
        conn.execute("SELECT localidad FROM clientes LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE clientes ADD COLUMN localidad TEXT")
        conn.commit()
    # Migracion: agregar columnas clave_mi_anses y clave_fiscal a clientes
    for col in ["clave_mi_anses", "clave_fiscal"]:
        try:
            conn.execute(f"SELECT {col} FROM clientes LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute(f"ALTER TABLE clientes ADD COLUMN {col} TEXT")
            conn.commit()
    # Migracion: agregar columna procedencia_contacto a clientes
    try:
        conn.execute("SELECT procedencia_contacto FROM clientes LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE clientes ADD COLUMN procedencia_contacto TEXT")
        conn.commit()
    # Migracion: agregar columnas clave_mi_anses y clave_fiscal a expedientes
    for col in ["clave_mi_anses", "clave_fiscal"]:
        try:
            conn.execute(f"SELECT {col} FROM expedientes LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute(f"ALTER TABLE expedientes ADD COLUMN {col} TEXT")
            conn.commit()
    # Migracion: agregar columnas de ramas y modulo judicial a expedientes
    for col in ["rama", "subtipo", "datos_rama", "datos_judicial"]:
        try:
            conn.execute(f"SELECT {col} FROM expedientes LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute(f"ALTER TABLE expedientes ADD COLUMN {col} TEXT")
            conn.commit()
    # Indice unico para evitar carpetas duplicadas
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_clientes_numero_carpeta "
        "ON clientes(numero_carpeta) WHERE numero_carpeta IS NOT NULL AND numero_carpeta != ''"
    )
    conn.commit()
    # Migracion: agregar columnas de creador en tareas si no existen
    for col in ["creado_por_username", "creado_por_nombre"]:
        try:
            conn.execute(f"SELECT {col} FROM tareas LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute(f"ALTER TABLE tareas ADD COLUMN {col} TEXT DEFAULT ''")
            conn.commit()
    # Migracion: agregar columnas responsable_username en tablas operativas
    _migrate_responsable_username(conn)

    # ── Reparar caracteres corruptos (U+FFFD) de importaciones previas ──
    _fix_replacement_characters(conn)

    # ── Indices de rendimiento en columnas de relacion y busqueda ──
    _indices = [
        "CREATE INDEX IF NOT EXISTS idx_expedientes_id_cliente ON expedientes(id_cliente)",
        "CREATE INDEX IF NOT EXISTS idx_tareas_id_expediente ON tareas(id_expediente)",
        "CREATE INDEX IF NOT EXISTS idx_turnos_id_expediente ON turnos(id_expediente)",
        "CREATE INDEX IF NOT EXISTS idx_documentos_id_expediente ON documentos(id_expediente)",
        "CREATE INDEX IF NOT EXISTS idx_escritos_id_expediente ON escritos(id_expediente)",
        "CREATE INDEX IF NOT EXISTS idx_modelos_escrito_rama ON modelos_escrito(rama)",
        "CREATE INDEX IF NOT EXISTS idx_comunicaciones_id_expediente ON comunicaciones(id_expediente)",
        "CREATE INDEX IF NOT EXISTS idx_movimientos_id_expediente ON movimientos(id_expediente)",
        "CREATE INDEX IF NOT EXISTS idx_movimientos_id_cliente ON movimientos(id_cliente)",
        "CREATE INDEX IF NOT EXISTS idx_turnos_id_cliente ON turnos(id_cliente)",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_coleccion_doc ON audit_log(coleccion, documento_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_usuario_timestamp ON audit_log(usuario, timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_coleccion_accion_timestamp ON audit_log(coleccion, accion, timestamp)",
        # Indices para busqueda rapida de clientes por DNI, nombre y CUIL
        "CREATE INDEX IF NOT EXISTS idx_clientes_dni ON clientes(dni)",
        "CREATE INDEX IF NOT EXISTS idx_clientes_nombre ON clientes(nombre_completo)",
        "CREATE INDEX IF NOT EXISTS idx_clientes_cuil ON clientes(cuil)",
        # Indices para historial de estados de expedientes
        "CREATE INDEX IF NOT EXISTS idx_eeh_expediente_inicio ON expediente_estado_historial(id_expediente, inicio_ts)",
        "CREATE INDEX IF NOT EXISTS idx_eeh_expediente_fin ON expediente_estado_historial(id_expediente, fin_ts)",
        "CREATE INDEX IF NOT EXISTS idx_eeh_responsable_inicio ON expediente_estado_historial(responsable_username, inicio_ts)",
    ]
    for idx_sql in _indices:
        conn.execute(idx_sql)
    conn.commit()

    conn.close()


def _fix_replacement_characters(conn):
    """Repara caracteres U+FFFD introducidos por importaciones CSV con encoding incorrecto.

    Los caracteres mas comunes perdidos en nombres/observaciones en espanol son:
    - N + FFFD + espacio/digito  ->  N°  (signo numero)
    - G + FFFD + E              ->  GUE  (dieresis: AGUERO, GUEMES)
    - Resto                     ->  N~   (ene en espanol, >90% de los casos)

    Se ejecuta una sola vez; al terminar marca en app_meta que ya corrio.
    """
    FFFD = "\ufffd"

    # Verificar si ya se ejecuto
    row = conn.execute(
        "SELECT value FROM app_meta WHERE key = 'fffd_fix_done'"
    ).fetchone()
    if row:
        return

    # Columnas de texto a reparar por tabla
    targets = [
        ("clientes", ["nombre_completo", "direccion", "observaciones",
                       "clave_mi_anses", "clave_fiscal"]),
        ("expedientes", ["observaciones", "clave_mi_anses", "clave_fiscal",
                         "resultado"]),
        ("tareas", ["descripcion", "resultado"]),
        ("comunicaciones", ["motivo", "mensaje", "resultado"]),
        ("turnos", ["observaciones", "notas_preparacion", "resultado"]),
    ]

    import re
    total_fixed = 0

    for table, columns in targets:
        for col in columns:
            try:
                conn.execute(f"SELECT {col} FROM {table} LIMIT 1")
            except Exception:
                continue

            affected = conn.execute(
                f"SELECT _id, {col} FROM {table} WHERE {col} LIKE ?",
                (f"%{FFFD}%",)
            ).fetchall()

            for _id, value in affected:
                if not value:
                    continue
                fixed = value
                # Patron N° (numero): N + FFFD seguido de espacio o digito
                fixed = re.sub(f"N{FFFD}(?=[ 0-9])", "N\u00b0", fixed)
                fixed = re.sub(f"n{FFFD}(?=[ 0-9])", "n\u00b0", fixed)
                # Patron GUE con dieresis: G + FFFD + E
                fixed = re.sub(f"G{FFFD}E", "G\u00dcE", fixed)
                fixed = re.sub(f"g{FFFD}e", "g\u00fce", fixed)
                # Todo lo demas -> Ñ (o ñ segun contexto)
                fixed = fixed.replace(FFFD, "\u00d1")

                if fixed != value:
                    conn.execute(
                        f"UPDATE {table} SET {col} = ? WHERE _id = ?",
                        (fixed, _id)
                    )
                    total_fixed += 1

    # Marcar como ejecutado
    conn.execute(
        "INSERT OR REPLACE INTO app_meta (key, value, updated_at) VALUES (?, ?, ?)",
        ("fffd_fix_done", str(total_fixed),
         datetime.now(timezone.utc).isoformat())
    )
    conn.commit()


def _migrate_responsable_username(conn):
    """Agrega columnas responsable_username y hace backfill desde usuarios existentes."""
    # Tablas con columna responsable_username a migrar
    tables_single = ["tareas", "turnos", "documentos", "comunicaciones", "movimientos"]
    for table in tables_single:
        try:
            conn.execute(f"SELECT responsable_username FROM {table} LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN responsable_username TEXT DEFAULT ''")
            conn.commit()

    # Expedientes: dos columnas
    for col in ["responsable_username", "responsable_secundario_username"]:
        try:
            conn.execute(f"SELECT {col} FROM expedientes LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute(f"ALTER TABLE expedientes ADD COLUMN {col} TEXT DEFAULT ''")
            conn.commit()

    # Backfill: mapear valores de texto libre a username
    # Construir mapa de nombre/username -> username
    users = conn.execute(
        "SELECT username, nombre_completo FROM usuarios WHERE eliminado = 0 OR eliminado IS NULL"
    ).fetchall()
    if not users:
        return

    user_map = {}  # normalizado -> username
    for u in users:
        uname = u[0] or ""
        nombre = u[1] or ""
        # Mapear por username exacto y por nombre completo normalizado
        user_map[uname.strip().upper()] = uname
        if nombre:
            user_map[nombre.strip().upper()] = uname

    def _resolve(text: str) -> str:
        if not text:
            return ""
        normalized = text.strip().upper()
        return user_map.get(normalized, "")

    # Detectar que tablas tienen columna 'responsable' (texto legacy)
    def _has_column(tbl, col):
        info = conn.execute(f"PRAGMA table_info({tbl})").fetchall()
        return any(c[1] == col for c in info)

    # Backfill tablas con responsable (solo las que tienen columna responsable legacy)
    for table in tables_single:
        if not _has_column(table, "responsable"):
            continue
        rows = conn.execute(
            f"SELECT _id, responsable FROM {table} WHERE (responsable_username IS NULL OR responsable_username = '')"
        ).fetchall()
        for r in rows:
            resolved = _resolve(r[1])
            if resolved:
                conn.execute(
                    f"UPDATE {table} SET responsable_username = ? WHERE _id = ?",
                    (resolved, r[0])
                )
        conn.commit()

    # Backfill expedientes
    rows = conn.execute(
        "SELECT _id, responsable, responsable_secundario FROM expedientes "
        "WHERE (responsable_username IS NULL OR responsable_username = '')"
    ).fetchall()
    for r in rows:
        r1 = _resolve(r[1])
        r2 = _resolve(r[2])
        if r1 or r2:
            conn.execute(
                "UPDATE expedientes SET responsable_username = ?, responsable_secundario_username = ? WHERE _id = ?",
                (r1, r2, r[0])
            )
    conn.commit()


def dict_from_row(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows) -> list[dict]:
    return [dict(r) for r in rows]


# ----- Generic CRUD helpers -----

def insert(table: str, data: dict):
    cols = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    sql = f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})"
    with get_cursor() as cur:
        cur.execute(sql, list(data.values()))


def update(table: str, _id: str, data: dict):
    sets = ", ".join([f"{k} = ?" for k in data.keys()])
    sql = f"UPDATE {table} SET {sets} WHERE _id = ?"
    with get_cursor() as cur:
        cur.execute(sql, list(data.values()) + [_id])


def delete(table: str, _id: str):
    with get_cursor() as cur:
        cur.execute(f"DELETE FROM {table} WHERE _id = ?", (_id,))


def find_by_id(table: str, _id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(f"SELECT * FROM {table} WHERE _id = ?", (_id,)).fetchone()
    conn.close()
    return dict_from_row(row)


def find_all(table: str, where: str = "", params: tuple = (), order_by: str = "",
             limit: int = 0) -> list[dict]:
    sql = f"SELECT * FROM {table}"
    if where:
        sql += f" WHERE {where}"
    if order_by:
        sql += f" ORDER BY {order_by}"
    if limit:
        sql += f" LIMIT {limit}"
    conn = get_connection()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows_to_list(rows)


def count(table: str, where: str = "", params: tuple = ()) -> int:
    sql = f"SELECT COUNT(*) FROM {table}"
    if where:
        sql += f" WHERE {where}"
    conn = get_connection()
    result = conn.execute(sql, params).fetchone()[0]
    conn.close()
    return result


def find_pending(table: str) -> list[dict]:
    return find_all(table, where="sync_status = 'pending'")


def mark_synced(table: str, _id: str):
    if table == "audit_log":
        _mark_audit_log_synced(_id)
    else:
        update(table, _id, {"sync_status": "synced"})


def _mark_audit_log_synced(_id: str):
    """Marca un registro de audit_log como synced esquivando los triggers de inmutabilidad.

    Los triggers bloquean UPDATE/DELETE genéricos, pero aquí necesitamos
    actualizar solo el campo sync_status después de subir a Atlas.
    Se desactiva el trigger temporalmente dentro de la misma conexión.
    """
    conn = get_connection()
    try:
        conn.execute("DROP TRIGGER IF EXISTS audit_log_no_update")
        conn.execute(
            "UPDATE audit_log SET sync_status = 'synced' WHERE _id = ?",
            (_id,)
        )
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS audit_log_no_update
            BEFORE UPDATE ON audit_log
            BEGIN
                SELECT RAISE(ABORT, 'audit_log es inmutable: no se permite UPDATE');
            END
        """)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_sync_meta(key: str) -> str | None:
    conn = get_connection()
    row = conn.execute("SELECT value FROM sync_meta WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row[0] if row else None


def set_sync_meta(key: str, value: str):
    with get_cursor() as cur:
        cur.execute("INSERT OR REPLACE INTO sync_meta (key, value) VALUES (?, ?)", (key, value))


# ----- App version helpers -----

def get_app_meta(key: str) -> str | None:
    """Lee un valor de la tabla app_meta."""
    conn = get_connection()
    row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row[0] if row else None


def set_app_meta(key: str, value: str):
    """Inserta o actualiza un valor en app_meta."""
    now = datetime.now(timezone.utc).isoformat()
    with get_cursor() as cur:
        cur.execute(
            "INSERT OR REPLACE INTO app_meta (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, now)
        )


def check_and_update_app_version():
    """Registra la version actual de la app en la BD local.

    Retorna (version_anterior, version_actual) para que el caller pueda
    decidir si hay incompatibilidad.  version_anterior es None en la
    primera ejecucion.
    """
    from config import APP_VERSION

    stored_version = get_app_meta("app_version")

    if stored_version is None:
        # Primera ejecucion: guardar version actual
        set_app_meta("app_version", APP_VERSION)
        set_app_meta("app_version_date", datetime.now(timezone.utc).isoformat())
        return None, APP_VERSION

    if stored_version != APP_VERSION:
        # Version cambio: guardar la anterior y actualizar
        set_app_meta("previous_app_version", stored_version)
        set_app_meta("app_version", APP_VERSION)
        set_app_meta("app_version_date", datetime.now(timezone.utc).isoformat())
        return stored_version, APP_VERSION

    return stored_version, APP_VERSION


def _parse_version(version_str: str) -> tuple:
    """Convierte '1.2.3' en (1, 2, 3)."""
    try:
        return tuple(int(x) for x in version_str.split("."))
    except (ValueError, AttributeError):
        return (0, 0, 0)


def validate_version_compatibility() -> tuple[bool, str]:
    """Valida que la version del programa sea compatible con la BD local.

    Retorna (compatible: bool, mensaje: str).
    - Si la BD tiene una version mayor al programa, advierte pero permite
      continuar (el usuario decide).
    - Si la version del programa es menor que la min_compatible remota,
      bloquea.
    """
    from config import APP_VERSION, APP_VERSION_TUPLE

    previous_version, current_version = check_and_update_app_version()

    if previous_version is None:
        # Primera ejecucion
        return True, ""

    stored_tuple = _parse_version(previous_version)

    if stored_tuple > APP_VERSION_TUPLE:
        return False, (
            f"La base de datos fue utilizada con una version mas reciente "
            f"del programa (v{previous_version}).\n\n"
            f"Usted esta ejecutando v{APP_VERSION}.\n\n"
            f"Usar una version anterior podria corromper los datos.\n"
            f"Por favor actualice el programa o contacte al administrador."
        )

    # Version igual o menor en BD -> actualizacion normal
    return True, ""


def validate_remote_version_compatibility() -> tuple[bool, str]:
    """Valida la version contra la configuracion remota de MongoDB.

    Retorna (compatible: bool, mensaje: str).
    Debe llamarse solo cuando hay conexion.
    """
    from config import APP_VERSION, APP_VERSION_TUPLE

    try:
        from core.db_remote import get_db, is_connected
        if not is_connected():
            return True, ""  # Sin conexion, no se puede validar

        db = get_db()
        meta = db.app_meta.find_one({"_id": "version_config"})
        if not meta:
            return True, ""  # No hay config remota aun

        min_version_str = meta.get("min_compatible_version", "")
        if not min_version_str:
            return True, ""

        min_version_tuple = _parse_version(min_version_str)
        if APP_VERSION_TUPLE < min_version_tuple:
            return False, (
                f"Esta version del programa (v{APP_VERSION}) ya no es compatible.\n\n"
                f"La version minima requerida es v{min_version_str}.\n\n"
                f"Por favor actualice el programa para poder continuar."
            )

        return True, ""
    except Exception:
        logger.warning("Error al validar version remota (se permite continuar)", exc_info=True)
        return True, ""
