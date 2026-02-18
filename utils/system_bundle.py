"""
Exportacion/importacion completa del sistema en un unico archivo ZIP.

El bundle contiene:
  - rampazzo_export.csv: un CSV con columnas (table, row_json) para todas las tablas.
  - documentos/: carpeta con los archivos adjuntos, preservando estructura por expediente.

La primera fila del CSV es metadata (__meta__) con version, fecha y conteos.
"""
import csv
import io
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from config import (
    APP_VERSION, BASE_DIR, CONFIG_FILE, DATA_DIR, DOCS_DIR, SQLITE_PATH,
)
from core.db_local import _TABLES_SQL, get_connection, rows_to_list

logger = logging.getLogger(__name__)

EXPORT_TABLES = [
    "usuarios", "consultas", "clientes", "expedientes", "tareas",
    "turnos", "comunicaciones", "movimientos", "documentos", "audit_log",
    "notificaciones", "sync_meta", "app_meta",
]

CSV_FILENAME = "rampazzo_export.csv"
DOCS_FOLDER = "documentos"


def export_system_bundle(zip_path: str) -> dict:
    """Exporta toda la base de datos SQLite y documentos a un archivo ZIP.

    Args:
        zip_path: ruta destino del archivo .zip.

    Returns:
        dict con estadisticas: conteos por tabla, archivos copiados, etc.
    """
    stats: dict = {"tables": {}, "files_copied": 0, "total_rows": 0}
    bundle_id = uuid.uuid4().hex[:12]

    conn = get_connection()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(["table", "row_json"])

        table_counts: dict[str, int] = {}
        for table in EXPORT_TABLES:
            try:
                rows = conn.execute(f"SELECT * FROM {table}").fetchall()
                records = rows_to_list(rows)
            except Exception:
                logger.warning("Tabla '%s' no encontrada, se omite", table)
                records = []

            table_counts[table] = len(records)
            stats["total_rows"] += len(records)

            for rec in records:
                if table == "documentos":
                    rec = _relativize_doc_path(rec)
                writer.writerow([table, json.dumps(rec, ensure_ascii=False, default=str)])

        conn.close()

        meta = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "app_version": APP_VERSION,
            "bundle_id": bundle_id,
            "table_counts": table_counts,
        }
        meta_row = json.dumps(meta, ensure_ascii=False)
        lines = csv_buffer.getvalue().splitlines(True)
        csv_final = io.StringIO()
        csv_final.write(lines[0])
        csv_final.write(f"__meta__,{_csv_escape(meta_row)}\n")
        for line in lines[1:]:
            csv_final.write(line)

        zf.writestr(CSV_FILENAME, csv_final.getvalue().encode("utf-8").decode("utf-8"))

        files_copied = _add_docs_to_zip(zf)
        stats["files_copied"] = files_copied

    stats["tables"] = table_counts
    logger.info("Bundle exportado: %s (%d filas, %d archivos)", zip_path,
                stats["total_rows"], stats["files_copied"])
    return stats


def import_system_bundle(zip_path: str) -> dict:
    """Importa un bundle ZIP creando una nueva BD y directorio de documentos.

    Args:
        zip_path: ruta al archivo .zip exportado.

    Returns:
        dict con estadisticas y las rutas nuevas (new_db_path, new_docs_dir).
    """
    stats: dict = {"tables": {}, "total_rows": 0, "files_restored": 0,
                    "new_db_path": "", "new_docs_dir": ""}

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_db_name = f"local_imported_{timestamp}.db"
    new_db_path = str(DATA_DIR / new_db_name)
    new_docs_dir = str(DATA_DIR / f"documentos_imported_{timestamp}")

    os.makedirs(new_docs_dir, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmpdir)

        csv_path = os.path.join(tmpdir, CSV_FILENAME)
        if not os.path.isfile(csv_path):
            raise FileNotFoundError(
                f"El ZIP no contiene '{CSV_FILENAME}'. No es un bundle valido."
            )

        new_conn = _create_new_db(new_db_path)

        meta_info = {}
        table_rows: dict[str, list[dict]] = {}

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            if header != ["table", "row_json"]:
                raise ValueError("Formato de CSV invalido: cabecera incorrecta.")

            for row in reader:
                if len(row) < 2:
                    continue
                table_name, row_json_str = row[0], row[1]

                if table_name == "__meta__":
                    try:
                        meta_info = json.loads(row_json_str)
                    except json.JSONDecodeError:
                        pass
                    continue

                try:
                    record = json.loads(row_json_str)
                except json.JSONDecodeError:
                    logger.warning("JSON invalido en tabla '%s', se omite fila", table_name)
                    continue

                if table_name not in table_rows:
                    table_rows[table_name] = []
                table_rows[table_name].append(record)

        for table_name, records in table_rows.items():
            inserted = _insert_records(new_conn, table_name, records, new_docs_dir)
            stats["tables"][table_name] = inserted
            stats["total_rows"] += inserted

        # Marcar todos los registros como 'pending' para que se sincronicen
        # a MongoDB en el proximo ciclo de sync.
        _tables_with_sync = [
            "usuarios", "consultas", "clientes", "expedientes", "tareas",
            "turnos", "comunicaciones", "movimientos", "documentos",
            "notificaciones",
        ]
        for t in _tables_with_sync:
            if t in table_rows:
                try:
                    new_conn.execute(
                        f"UPDATE {t} SET sync_status = 'pending' WHERE sync_status = 'synced'"
                    )
                except Exception:
                    logger.warning("No se pudo marcar %s como pending", t)

        new_conn.commit()
        new_conn.close()

        docs_in_bundle = os.path.join(tmpdir, DOCS_FOLDER)
        if os.path.isdir(docs_in_bundle):
            files_restored = _copy_docs_from_bundle(docs_in_bundle, new_docs_dir)
            stats["files_restored"] = files_restored

    stats["new_db_path"] = new_db_path
    stats["new_docs_dir"] = new_docs_dir

    _update_config_ini(new_db_path, new_docs_dir)

    logger.info("Bundle importado: nueva BD=%s, docs=%s (%d filas, %d archivos)",
                new_db_path, new_docs_dir, stats["total_rows"], stats["files_restored"])
    return stats


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _csv_escape(value: str) -> str:
    """Escapa un valor para incluirlo como campo CSV."""
    if '"' in value or ',' in value or '\n' in value:
        return '"' + value.replace('"', '""') + '"'
    return value


def _relativize_doc_path(record: dict) -> dict:
    """Convierte ruta_archivo absoluta a relativa al bundle (documentos/...)."""
    ruta = record.get("ruta_archivo", "")
    if not ruta:
        return record

    docs_dir_str = str(DOCS_DIR)
    if ruta.startswith(docs_dir_str):
        rel = ruta[len(docs_dir_str):].lstrip(os.sep).lstrip("/")
        record = dict(record)
        record["ruta_archivo"] = f"{DOCS_FOLDER}/{rel}".replace("\\", "/")
    return record


def _absolutize_doc_path(record: dict, new_docs_dir: str) -> dict:
    """Convierte ruta relativa del bundle a ruta absoluta en el nuevo docs dir."""
    ruta = record.get("ruta_archivo", "")
    if not ruta:
        return record

    prefix = f"{DOCS_FOLDER}/"
    if ruta.startswith(prefix):
        rel = ruta[len(prefix):]
        record = dict(record)
        record["ruta_archivo"] = str(Path(new_docs_dir) / rel)
    return record


def _add_docs_to_zip(zf: zipfile.ZipFile) -> int:
    """Agrega los archivos de documentos al ZIP."""
    count = 0
    docs_path = Path(DOCS_DIR)
    if not docs_path.exists():
        return count

    for root, _dirs, files in os.walk(docs_path):
        for fname in files:
            abs_path = os.path.join(root, fname)
            rel_to_docs = os.path.relpath(abs_path, str(docs_path))
            arc_name = f"{DOCS_FOLDER}/{rel_to_docs}".replace("\\", "/")
            try:
                zf.write(abs_path, arc_name)
                count += 1
            except Exception:
                logger.warning("No se pudo agregar archivo al ZIP: %s", abs_path)
    return count


def _create_new_db(db_path: str) -> sqlite3.Connection:
    """Crea una nueva base de datos SQLite con el esquema completo."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA encoding='UTF-8'")
    conn.executescript(_TABLES_SQL)
    conn.commit()
    return conn


def _insert_records(conn: sqlite3.Connection, table: str,
                    records: list[dict], new_docs_dir: str) -> int:
    """Inserta registros en una tabla de la nueva BD."""
    inserted = 0
    for rec in records:
        if table == "documentos":
            rec = _absolutize_doc_path(rec, new_docs_dir)
        try:
            cols = list(rec.keys())
            vals = []
            for v in rec.values():
                if isinstance(v, (list, dict)):
                    vals.append(json.dumps(v, ensure_ascii=False, default=str))
                elif v is None:
                    vals.append(None)
                else:
                    vals.append(str(v))

            placeholders = ", ".join(["?"] * len(cols))
            col_names = ", ".join(cols)
            sql = f"INSERT OR REPLACE INTO {table} ({col_names}) VALUES ({placeholders})"
            conn.execute(sql, vals)
            inserted += 1
        except Exception:
            logger.warning("Error insertando registro en '%s': %s",
                           table, rec.get("_id", "?"), exc_info=True)
    return inserted


def _copy_docs_from_bundle(src_dir: str, dest_dir: str) -> int:
    """Copia los archivos de documentos del bundle al nuevo directorio."""
    count = 0
    for root, _dirs, files in os.walk(src_dir):
        for fname in files:
            src_file = os.path.join(root, fname)
            rel = os.path.relpath(src_file, src_dir)
            dest_file = os.path.join(dest_dir, rel)
            os.makedirs(os.path.dirname(dest_file), exist_ok=True)
            try:
                shutil.copy2(src_file, dest_file)
                count += 1
            except Exception:
                logger.warning("Error copiando documento: %s", src_file)
    return count


def _update_config_ini(new_db_path: str, new_docs_dir: str):
    """Actualiza config.ini para apuntar a la nueva BD y docs."""
    import configparser

    cfg = configparser.ConfigParser()
    if CONFIG_FILE.exists():
        cfg.read(str(CONFIG_FILE), encoding="utf-8")

    if not cfg.has_section("sqlite"):
        cfg.add_section("sqlite")
    cfg.set("sqlite", "path", new_db_path)

    if not cfg.has_section("paths"):
        cfg.add_section("paths")
    cfg.set("paths", "docs_dir", new_docs_dir)

    with open(str(CONFIG_FILE), "w", encoding="utf-8") as f:
        cfg.write(f)

    logger.info("config.ini actualizado: sqlite.path=%s, paths.docs_dir=%s",
                new_db_path, new_docs_dir)
