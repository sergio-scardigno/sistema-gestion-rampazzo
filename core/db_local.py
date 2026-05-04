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

SYNCED_ENTITY_TABLES = [
    "usuarios", "consultas", "clientes", "expedientes",
    "tareas", "turnos", "comunicaciones", "movimientos", "documentos",
    "modelos_escrito", "escritos", "expediente_estado_historial", "notificaciones",
    "expediente_recordatorios", "expediente_etapa_responsables", "citas",
]

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
    is_deleted INTEGER DEFAULT 0,
    deleted_at TEXT,
    deleted_by TEXT DEFAULT '',
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
    is_deleted INTEGER DEFAULT 0,
    deleted_at TEXT,
    deleted_by TEXT DEFAULT '',
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
    nro_tramite_dni TEXT,
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
    created_by_username TEXT DEFAULT '',
    procedencia_contacto TEXT,
    observaciones TEXT,
    is_deleted INTEGER DEFAULT 0,
    deleted_at TEXT,
    deleted_by TEXT DEFAULT '',
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
    etapa_codigo TEXT DEFAULT 'para_citar_o_videollamada',
    prioridad TEXT DEFAULT 'Normal',
    modalidad TEXT,
    ubicacion_fisica TEXT,
    link_drive TEXT,
    fecha_cierre TEXT,
    resultado TEXT,
    numero_expediente_anses TEXT,
    calculo_derecho_nota TEXT DEFAULT '',
    clave_mi_anses TEXT,
    clave_fiscal TEXT,
    observaciones TEXT,
    is_deleted INTEGER DEFAULT 0,
    deleted_at TEXT,
    deleted_by TEXT DEFAULT '',
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
    is_deleted INTEGER DEFAULT 0,
    deleted_at TEXT,
    deleted_by TEXT DEFAULT '',
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
    is_deleted INTEGER DEFAULT 0,
    deleted_at TEXT,
    deleted_by TEXT DEFAULT '',
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
    observaciones TEXT DEFAULT '',
    responsable_username TEXT DEFAULT '',
    is_deleted INTEGER DEFAULT 0,
    deleted_at TEXT,
    deleted_by TEXT DEFAULT '',
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
    is_deleted INTEGER DEFAULT 0,
    deleted_at TEXT,
    deleted_by TEXT DEFAULT '',
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
    is_deleted INTEGER DEFAULT 0,
    deleted_at TEXT,
    deleted_by TEXT DEFAULT '',
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
    is_deleted INTEGER DEFAULT 0,
    deleted_at TEXT,
    deleted_by TEXT DEFAULT '',
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
    is_deleted INTEGER DEFAULT 0,
    deleted_at TEXT,
    deleted_by TEXT DEFAULT '',
    updated_at TEXT,
    version INTEGER DEFAULT 1,
    sync_status TEXT DEFAULT 'synced',
    created_by_machine TEXT,
    id_constancia_doc TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS citas (
    _id TEXT PRIMARY KEY,
    id_cita INTEGER,
    id_cliente TEXT,
    id_expediente TEXT,
    fecha_cita TEXT,
    hora_cita TEXT,
    motivo TEXT,
    estado TEXT DEFAULT 'Pendiente',
    observaciones TEXT,
    citado_por TEXT,
    citado_por_username TEXT DEFAULT '',
    responsable TEXT,
    responsable_username TEXT DEFAULT '',
    is_deleted INTEGER DEFAULT 0,
    deleted_at TEXT,
    deleted_by TEXT DEFAULT '',
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
    updated_at TEXT,
    leida INTEGER DEFAULT 0,
    resuelta INTEGER DEFAULT 0,
    fecha_resolucion TEXT,
    resuelta_por_estado INTEGER DEFAULT 0,
    is_deleted INTEGER DEFAULT 0,
    deleted_at TEXT,
    deleted_by TEXT DEFAULT '',
    sync_status TEXT DEFAULT 'synced',
    created_by_machine TEXT
);

CREATE TABLE IF NOT EXISTS expediente_estado_historial (
    _id TEXT PRIMARY KEY,
    id_expediente TEXT NOT NULL,
    estado TEXT NOT NULL,
    etapa_anterior TEXT DEFAULT '',
    responsable_username TEXT DEFAULT '',
    encargado_username TEXT DEFAULT '',
    observacion_transicion TEXT DEFAULT '',
    usuario TEXT DEFAULT 'sistema',
    inicio_ts TEXT NOT NULL,
    fin_ts TEXT,
    origen TEXT DEFAULT 'manual',
    is_deleted INTEGER DEFAULT 0,
    deleted_at TEXT,
    deleted_by TEXT DEFAULT '',
    updated_at TEXT,
    version INTEGER DEFAULT 1,
    sync_status TEXT DEFAULT 'synced',
    created_by_machine TEXT
);

CREATE TABLE IF NOT EXISTS expediente_recordatorios (
    _id TEXT PRIMARY KEY,
    id_expediente TEXT NOT NULL,
    fecha_disparo TEXT NOT NULL,
    titulo TEXT DEFAULT '',
    mensaje TEXT DEFAULT '',
    notificar_a_username TEXT DEFAULT '',
    disparado_en TEXT DEFAULT '',
    creado_por_username TEXT DEFAULT '',
    etapa_codigo TEXT DEFAULT '',
    es_critico INTEGER DEFAULT 0,
    origen TEXT DEFAULT 'manual',
    template_key TEXT DEFAULT '',
    estado_plazo TEXT DEFAULT 'activo',
    pospuesto_hasta TEXT DEFAULT '',
    ultimo_aviso_nivel TEXT DEFAULT '',
    ultimo_aviso_fecha TEXT DEFAULT '',
    created_at TEXT,
    updated_at TEXT,
    version INTEGER DEFAULT 1,
    sync_status TEXT DEFAULT 'synced',
    created_by_machine TEXT,
    is_deleted INTEGER DEFAULT 0,
    deleted_at TEXT,
    deleted_by TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS expediente_etapa_responsables (
    _id TEXT PRIMARY KEY,
    id_expediente TEXT NOT NULL,
    etapa_codigo TEXT NOT NULL,
    responsable_secundario_username TEXT DEFAULT '',
    created_at TEXT,
    updated_at TEXT,
    version INTEGER DEFAULT 1,
    sync_status TEXT DEFAULT 'synced',
    created_by_machine TEXT,
    is_deleted INTEGER DEFAULT 0,
    deleted_at TEXT,
    deleted_by TEXT DEFAULT ''
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

CREATE TABLE IF NOT EXISTS sync_conflicts (
    _id TEXT PRIMARY KEY,
    table_name TEXT NOT NULL,
    record_id TEXT NOT NULL,
    conflict_type TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    local_version INTEGER DEFAULT 0,
    remote_version INTEGER DEFAULT 0,
    local_snapshot TEXT,
    remote_snapshot TEXT,
    status TEXT DEFAULT 'open',
    sync_status TEXT DEFAULT 'pending',
    created_by_machine TEXT
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
    # Migracion: agregar nro_tramite_dni a clientes si no existe
    try:
        conn.execute("SELECT nro_tramite_dni FROM clientes LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE clientes ADD COLUMN nro_tramite_dni TEXT")
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
    # Migracion: agregar creador en clientes
    try:
        conn.execute("SELECT created_by_username FROM clientes LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE clientes ADD COLUMN created_by_username TEXT DEFAULT ''")
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
    # Migracion: agregar columna modalidad a expedientes
    try:
        conn.execute("SELECT modalidad FROM expedientes LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE expedientes ADD COLUMN modalidad TEXT")
        conn.commit()
    # Migracion: agregar etapa_codigo a expedientes
    try:
        conn.execute("SELECT etapa_codigo FROM expedientes LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute(
            "ALTER TABLE expedientes ADD COLUMN etapa_codigo TEXT DEFAULT 'para_citar_o_videollamada'"
        )
        conn.commit()
    # Backfill etapa_codigo para registros legacy
    conn.execute("""
        UPDATE expedientes
        SET etapa_codigo = CASE
            WHEN LOWER(COALESCE(estado, '')) = 'favorable' THEN 'favorable'
            WHEN LOWER(COALESCE(estado, '')) = 'desfavorable' THEN 'desfavorable'
            WHEN LOWER(COALESCE(estado, '')) IN ('cerrado', 'archivado') THEN 'enviar_notificarse'
            WHEN LOWER(COALESCE(estado, '')) = 'en tramite' THEN 'para_analizar'
            WHEN LOWER(COALESCE(estado, '')) = 'en espera' THEN 'pendiente_turno'
            ELSE 'para_citar_o_videollamada'
        END
        WHERE COALESCE(TRIM(etapa_codigo), '') = ''
    """)
    conn.commit()
    # Migracion: agregar nota de calculo derecho a expedientes
    try:
        conn.execute("SELECT calculo_derecho_nota FROM expedientes LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE expedientes ADD COLUMN calculo_derecho_nota TEXT DEFAULT ''")
        conn.commit()
    # Indice unico para evitar carpetas duplicadas
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_clientes_numero_carpeta "
        "ON clientes(numero_carpeta) WHERE numero_carpeta IS NOT NULL AND numero_carpeta != ''"
    )
    conn.commit()
    # Migracion: id documento de constancia PDF del turno ANSES
    try:
        conn.execute("SELECT id_constancia_doc FROM turnos LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE turnos ADD COLUMN id_constancia_doc TEXT DEFAULT ''")
        conn.commit()
    # Migracion: agregar columnas de creador en tareas si no existen
    for col in ["creado_por_username", "creado_por_nombre"]:
        try:
            conn.execute(f"SELECT {col} FROM tareas LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute(f"ALTER TABLE tareas ADD COLUMN {col} TEXT DEFAULT ''")
            conn.commit()
    # Migracion: observaciones en movimientos economicos
    try:
        conn.execute("SELECT observaciones FROM movimientos LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE movimientos ADD COLUMN observaciones TEXT DEFAULT ''")
        conn.commit()
    # Migracion: agregar columnas responsable_username en tablas operativas
    _migrate_responsable_username(conn)
    _migrate_soft_delete_columns(conn)
    _migrate_notificaciones_resolution(conn)
    _migrate_expediente_historial_etapas(conn)
    _migrate_expediente_etapa_y_recordatorio_plazos(conn)

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
        "CREATE INDEX IF NOT EXISTS idx_clientes_created_by_username ON clientes(created_by_username)",
        # Indices para historial de estados de expedientes
        "CREATE INDEX IF NOT EXISTS idx_eeh_expediente_inicio ON expediente_estado_historial(id_expediente, inicio_ts)",
        "CREATE INDEX IF NOT EXISTS idx_eeh_expediente_fin ON expediente_estado_historial(id_expediente, fin_ts)",
        "CREATE INDEX IF NOT EXISTS idx_eeh_responsable_inicio ON expediente_estado_historial(responsable_username, inicio_ts)",
        "CREATE INDEX IF NOT EXISTS idx_eeh_encargado_inicio ON expediente_estado_historial(encargado_username, inicio_ts)",
        "CREATE INDEX IF NOT EXISTS idx_expedientes_etapa_codigo ON expedientes(etapa_codigo)",
        "CREATE INDEX IF NOT EXISTS idx_recordatorios_fecha_disparo ON expediente_recordatorios(fecha_disparo)",
        "CREATE INDEX IF NOT EXISTS idx_recordatorios_usuario_fecha ON expediente_recordatorios(notificar_a_username, fecha_disparo)",
        "CREATE INDEX IF NOT EXISTS idx_recordatorios_etapa_fecha ON expediente_recordatorios(etapa_codigo, fecha_disparo)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_ee_resp_exp_etapa ON expediente_etapa_responsables(id_expediente, etapa_codigo) WHERE (is_deleted IS NULL OR is_deleted = 0)",
        "CREATE INDEX IF NOT EXISTS idx_ee_resp_expediente ON expediente_etapa_responsables(id_expediente)",
        "CREATE INDEX IF NOT EXISTS idx_sync_conflicts_status_detected ON sync_conflicts(status, detected_at)",
        "CREATE INDEX IF NOT EXISTS idx_sync_conflicts_table_record ON sync_conflicts(table_name, record_id)",
        "CREATE INDEX IF NOT EXISTS idx_notificaciones_target_created ON notificaciones(target_username, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_notificaciones_target_resuelta ON notificaciones(target_username, resuelta)",
        # Indices para citas
        "CREATE INDEX IF NOT EXISTS idx_citas_fecha ON citas(fecha_cita)",
        "CREATE INDEX IF NOT EXISTS idx_citas_id_cliente ON citas(id_cliente)",
        "CREATE INDEX IF NOT EXISTS idx_citas_id_expediente ON citas(id_expediente)",
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


def _migrate_soft_delete_columns(conn):
    """Agrega columnas de tombstone en tablas sincronizadas existentes."""
    for table in SYNCED_ENTITY_TABLES:
        for col, col_def in [
            ("is_deleted", "INTEGER DEFAULT 0"),
            ("deleted_at", "TEXT"),
            ("deleted_by", "TEXT DEFAULT ''"),
        ]:
            try:
                conn.execute(f"SELECT {col} FROM {table} LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
                conn.commit()


def _migrate_notificaciones_resolution(conn):
    """Agrega campos de estado/resolucion para notificaciones persistentes."""
    for col, col_def in [
        ("updated_at", "TEXT"),
        ("resuelta", "INTEGER DEFAULT 0"),
        ("fecha_resolucion", "TEXT"),
        ("resuelta_por_estado", "INTEGER DEFAULT 0"),
    ]:
        try:
            conn.execute(f"SELECT {col} FROM notificaciones LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute(f"ALTER TABLE notificaciones ADD COLUMN {col} {col_def}")
            conn.commit()


def _migrate_expediente_historial_etapas(conn):
    """Agrega columnas para trazabilidad de etapas en historial."""
    for col, col_def in [
        ("etapa_anterior", "TEXT DEFAULT ''"),
        ("encargado_username", "TEXT DEFAULT ''"),
        ("observacion_transicion", "TEXT DEFAULT ''"),
    ]:
        try:
            conn.execute(f"SELECT {col} FROM expediente_estado_historial LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute(f"ALTER TABLE expediente_estado_historial ADD COLUMN {col} {col_def}")
            conn.commit()


def _migrate_expediente_etapa_y_recordatorio_plazos(conn):
    """Encargado secundario por etapa; recordatorios con etapa y critico."""
    for col, col_def in [
        ("etapa_codigo", "TEXT DEFAULT ''"),
        ("es_critico", "INTEGER DEFAULT 0"),
        ("origen", "TEXT DEFAULT 'manual'"),
        ("template_key", "TEXT DEFAULT ''"),
        ("estado_plazo", "TEXT DEFAULT 'activo'"),
        ("pospuesto_hasta", "TEXT DEFAULT ''"),
        ("ultimo_aviso_nivel", "TEXT DEFAULT ''"),
        ("ultimo_aviso_fecha", "TEXT DEFAULT ''"),
    ]:
        try:
            conn.execute(f"SELECT {col} FROM expediente_recordatorios LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute(f"ALTER TABLE expediente_recordatorios ADD COLUMN {col} {col_def}")
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


def table_has_column(table: str, column: str) -> bool:
    conn = get_connection()
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return any(r[1] == column for r in rows)
    finally:
        conn.close()


def soft_delete(table: str, _id: str, deleted_by: str = "system") -> bool:
    if not find_by_id(table, _id):
        return False
    now = datetime.now(timezone.utc).isoformat()
    payload = {"sync_status": "pending", "updated_at": now}
    if table_has_column(table, "is_deleted"):
        payload["is_deleted"] = 1
    if table_has_column(table, "deleted_at"):
        payload["deleted_at"] = now
    if table_has_column(table, "deleted_by"):
        payload["deleted_by"] = deleted_by
    update(table, _id, payload)
    return True


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


def get_table_counts(tables: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    conn = get_connection()
    try:
        for table in tables:
            try:
                counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except Exception:
                counts[table] = 0
    finally:
        conn.close()
    return counts


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
