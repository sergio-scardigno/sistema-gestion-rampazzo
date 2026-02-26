"""
Motor de sincronizacion bidireccional SQLite <-> MongoDB Atlas.
Corre en un hilo separado para no bloquear la UI.
"""
import json
import logging
import sqlite3
from datetime import datetime, timezone

from PySide6.QtCore import QObject, Signal, QThread, QMutex

from core import db_local, db_remote
from core.db_remote import is_connected
from config import MACHINE_ID, SQLITE_PATH

logger = logging.getLogger(__name__)

SYNC_TABLES = [
    "usuarios", "consultas", "clientes", "expedientes",
    "tareas", "turnos", "comunicaciones", "movimientos", "documentos",
    "modelos_escrito", "escritos",
    "expediente_estado_historial", "audit_log"
]

# Campos que no van a Atlas
LOCAL_ONLY_FIELDS = {"sync_status"}


class _SyncWorker(QObject):
    """Worker que ejecuta la sincronizacion en un hilo secundario."""
    finished = Signal(bool, str)
    progress = Signal(str)

    def run(self):
        if not is_connected():
            self.finished.emit(False, "Sin conexion")
            return

        total_pulled = 0
        try:
            db = db_remote.get_db()
            for i, table in enumerate(SYNC_TABLES, 1):
                self.progress.emit(f"Sincronizando {table} ({i}/{len(SYNC_TABLES)})...")
                _push_pending(db, table)
                count = _pull_remote(db, table)
                total_pulled += count
                if count:
                    self.progress.emit(f"{table}: {count} registros descargados")

            db_remote.update_remote_app_version()

            now = datetime.now(timezone.utc).isoformat()
            db_local.set_sync_meta("last_sync", now)
            self.finished.emit(True, f"Sync OK – {total_pulled} registros descargados")
        except Exception:
            logger.exception("Error en ciclo de sincronizacion")
            self.finished.emit(False, "Error de sincronizacion (ver logs)")


class SyncEngine(QObject):
    sync_started = Signal()
    sync_finished = Signal(bool, str)  # (success, message)
    sync_progress = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mutex = QMutex()
        self._running = False
        self._thread: QThread | None = None
        self._worker: _SyncWorker | None = None

    def _is_running(self) -> bool:
        self._mutex.lock()
        running = self._running
        self._mutex.unlock()
        return running

    def _set_running(self, value: bool):
        self._mutex.lock()
        self._running = value
        self._mutex.unlock()

    def sync(self):
        """Ejecutar ciclo de sincronizacion en un hilo separado (no bloqueante)."""
        if self._is_running():
            logger.debug("Sync ya en curso, se omite llamada duplicada")
            return

        self._set_running(True)
        self.sync_started.emit()

        self._thread = QThread()
        self._worker = _SyncWorker()
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.sync_progress.emit)
        self._worker.finished.connect(self._on_worker_finished)

        self._thread.start()

    def _on_worker_finished(self, success: bool, message: str):
        """Callback cuando el worker termina (se ejecuta en el hilo principal)."""
        self.sync_finished.emit(success, message)
        self._set_running(False)

        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(5000)
            self._thread.deleteLater()
            self._thread = None
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    def force_sync(self):
        """Forzar sync inmediato (no bloqueante)."""
        self.sync()


# ---------------------------------------------------------------------------
# Funciones de sync (ejecutadas en el hilo del worker)
# ---------------------------------------------------------------------------

def _get_thread_connection() -> sqlite3.Connection:
    """Crea una conexion SQLite propia para el hilo de sync."""
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _get_table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Obtiene el set de columnas que existen en una tabla SQLite."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


def _push_pending(db, table: str):
    """Subir cambios locales pendientes a Atlas."""
    pending = db_local.find_pending(table)
    collection = db[table]

    now_iso = datetime.now(timezone.utc).isoformat()

    for row in pending:
        doc = {k: v for k, v in row.items() if k not in LOCAL_ONLY_FIELDS}
        if table == "usuarios" and "activo" in doc:
            doc["activo"] = bool(doc["activo"])

        # Actualizar updated_at para que otros clientes detecten el cambio
        # en su sync incremental (query por updated_at > last_pull).
        if "updated_at" in doc:
            doc["updated_at"] = now_iso

        try:
            collection.replace_one({"_id": doc["_id"]}, doc, upsert=True)
            db_local.mark_synced(table, row["_id"])
        except Exception:
            logger.exception(
                "Error al subir registro a Atlas: table=%s, _id=%s",
                table, row.get("_id", "?"),
            )


def _pull_remote(db, table: str) -> int:
    """Bajar TODOS los cambios remotos a SQLite local (batch insert).

    Retorna la cantidad de registros descargados.
    """
    last_sync = db_local.get_sync_meta(f"last_pull_{table}")
    collection = db[table]

    # Si hay timestamp pero la tabla local esta vacia, forzar descarga completa
    if last_sync:
        local_count = db_local.count(table)
        if local_count == 0:
            logger.info(
                "pull %s: tabla local vacia pero last_sync=%s, se fuerza descarga completa",
                table, last_sync,
            )
            last_sync = None

    query = {}
    if last_sync:
        query["updated_at"] = {"$gt": last_sync}

    inserted = 0
    try:
        remote_docs = list(collection.find(query, batch_size=5000))
        if not remote_docs:
            db_local.set_sync_meta(f"last_pull_{table}",
                                   datetime.now(timezone.utc).isoformat())
            return 0

        logger.info("pull %s: %d documentos descargados de MongoDB", table, len(remote_docs))

        conn = _get_thread_connection()
        try:
            # Obtener las columnas reales de la tabla SQLite
            valid_cols = _get_table_columns(conn, table)
            if not valid_cols:
                logger.warning("pull %s: tabla no encontrada en SQLite, se omite", table)
                return 0

            # IDs locales con cambios pendientes (para no pisarlos)
            pending_ids: set[str] = set()
            try:
                rows = conn.execute(
                    f"SELECT _id FROM {table} WHERE sync_status = 'pending'"
                ).fetchall()
                pending_ids = {r[0] for r in rows}
            except Exception:
                pass

            # Convertir docs de Mongo a formato SQLite
            batch: list[dict] = []
            skipped_cols: set[str] = set()
            for doc in remote_docs:
                doc_id = str(doc["_id"])
                if doc_id in pending_ids:
                    continue

                local_doc: dict[str, object] = {}
                for k, v in doc.items():
                    if k not in valid_cols:
                        skipped_cols.add(k)
                        continue
                    if isinstance(v, (list, dict)):
                        local_doc[k] = json.dumps(v, ensure_ascii=False, default=str)
                    elif isinstance(v, bool):
                        local_doc[k] = 1 if v else 0
                    elif v is None:
                        local_doc[k] = None
                    else:
                        local_doc[k] = str(v)
                local_doc["sync_status"] = "synced"
                batch.append(local_doc)

            if skipped_cols:
                logger.info(
                    "pull %s: campos de MongoDB ignorados (no existen en SQLite): %s",
                    table, ", ".join(sorted(skipped_cols))
                )

            # Usar exactamente las columnas de la tabla SQLite que aparecen en los docs
            if batch:
                used_cols = sorted(valid_cols & {k for rec in batch for k in rec})
                if "_id" in used_cols:
                    used_cols.remove("_id")
                    used_cols.insert(0, "_id")
                placeholders = ", ".join(["?"] * len(used_cols))
                col_names = ", ".join(used_cols)
                sql = f"INSERT OR REPLACE INTO {table} ({col_names}) VALUES ({placeholders})"

                conn.execute("BEGIN")
                for rec in batch:
                    vals = [rec.get(c) for c in used_cols]
                    try:
                        conn.execute(sql, vals)
                        inserted += 1
                    except Exception:
                        logger.warning("Error insertando en %s _id=%s",
                                       table, rec.get("_id", "?"), exc_info=True)
                conn.commit()

            conn.execute(
                "INSERT OR REPLACE INTO sync_meta (key, value) VALUES (?, ?)",
                (f"last_pull_{table}", datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

            logger.info("pull %s: %d registros insertados en SQLite", table, inserted)
        finally:
            conn.close()

    except Exception:
        logger.exception("Error al descargar cambios remotos: table=%s", table)

    return inserted
