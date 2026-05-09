"""
Configuracion central del sistema Rampazzo.
Lee config.ini si existe, sino usa valores por defecto.
"""
import os
import sys
import socket
import shutil
import configparser
from pathlib import Path

def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _dir_is_writable(path: Path) -> bool:
    """Devuelve True si se puede crear/escribir dentro del directorio."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        test = path / ".write_test"
        test.write_text("ok", encoding="utf-8")
        try:
            test.unlink()
        except OSError:
            pass
        return True
    except Exception:
        return False


if _is_frozen():
    # En ejecutables (PyInstaller), los recursos viven en _MEIPASS (onefile)
    # o al lado del exe (onedir). Usamos BASE_DIR para recursos.
    BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    APP_DIR = Path(sys.executable).resolve().parent

    # Data/config persistentes: preferir modo portable (./data) si es escribible;
    # sino usar LocalAppData/AppData del usuario.
    _portable_data = APP_DIR / "data"
    if _dir_is_writable(_portable_data):
        DATA_DIR = _portable_data
    else:
        if sys.platform == "darwin":
            _user_data_root = str(Path.home() / "Library" / "Application Support")
        elif sys.platform.startswith("linux"):
            _user_data_root = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        else:
            _user_data_root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(APP_DIR)
        DATA_DIR = Path(_user_data_root) / "SistemaRampazzo" / "data"
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Config editable por el usuario (persistente).
    CONFIG_FILE = DATA_DIR / "config.ini"

    # Si viene un config.ini junto al exe, copiarlo una vez a DATA_DIR
    # (asi el sistema funciona igual en instalaciones sin permisos de escritura).
    _distributed_cfg = APP_DIR / "config.ini"
    if not CONFIG_FILE.exists() and _distributed_cfg.exists():
        try:
            shutil.copy2(str(_distributed_cfg), str(CONFIG_FILE))
        except Exception:
            # Si no se pudo copiar, al menos leer el distribuido.
            CONFIG_FILE = _distributed_cfg
else:
    # En modo desarrollo, mantener comportamiento tradicional:
    # config.ini en raiz del proyecto y data/ dentro del repo.
    BASE_DIR = Path(__file__).resolve().parent
    APP_DIR = BASE_DIR
    DATA_DIR = BASE_DIR / "data"
    DATA_DIR.mkdir(exist_ok=True)
    CONFIG_FILE = BASE_DIR / "config.ini"

_cfg = configparser.ConfigParser()
if CONFIG_FILE.exists():
    _cfg.read(str(CONFIG_FILE), encoding="utf-8")


def _get(section: str, key: str, fallback: str = "") -> str:
    return _cfg.get(section, key, fallback=fallback)


# --- MongoDB Atlas ---
MONGO_URI = _get("mongo", "uri", "mongodb://localhost:27017")
MONGO_DB_NAME = _get("mongo", "database", "rampazzo")

# --- SQLite local ---
_configured_sqlite = _get("sqlite", "path", "")
if _configured_sqlite and _is_frozen():
    # En modo frozen, ignorar rutas absolutas que apunten a directorios inexistentes
    # (evita fallos al llevar el exe a otra PC con un config.ini viejo).
    _sql_parent = Path(_configured_sqlite).parent
    if not _sql_parent.exists():
        _configured_sqlite = ""
SQLITE_PATH = _configured_sqlite or str(DATA_DIR / "local.db")

# --- Documentos (archivos adjuntos) ---
_configured_docs = _get("paths", "docs_dir", "")
if _configured_docs and _is_frozen():
    _docs_parent = Path(_configured_docs).parent
    if not _docs_parent.exists():
        _configured_docs = ""
DOCS_DIR = Path(_configured_docs or str(DATA_DIR / "documentos"))
DOCS_DIR.mkdir(parents=True, exist_ok=True)

# --- Sync ---
SYNC_INTERVAL_SECONDS = int(_get("sync", "interval_seconds", "300"))  # 5 min
# Bloqueo pesimista de registros en Mongo (expedientes/clientes al editar), en segundos.
# Solo lock_expiry_seconds (default 30). lock_expiry_minutes en ini antiguos se ignora.
LOCK_EXPIRY_SECONDS = max(1, int(_get("sync", "lock_expiry_seconds", "30")))

# --- Machine ---
MACHINE_ID = _get("machine", "id", os.environ.get("COMPUTERNAME", socket.gethostname()) or "unknown")

# --- Backup ---
BACKUP_DIR = DATA_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)
BACKUP_RETENTION_DAYS = int(_get("backup", "retention_days", "30"))

# --- App ---
APP_NAME = "Sistema Rampazzo"
APP_VERSION = "1.9.2"
APP_VERSION_TUPLE = tuple(int(x) for x in APP_VERSION.split("."))
MIN_COMPATIBLE_VERSION = "1.0.0"
MIN_COMPATIBLE_VERSION_TUPLE = tuple(int(x) for x in MIN_COMPATIBLE_VERSION.split("."))

try:
    from build_info import BUILD_NUMBER, BUILD_TIMESTAMP
except ImportError:
    BUILD_NUMBER = "dev"
    BUILD_TIMESTAMP = ""

APP_FULL_VERSION = f"{APP_VERSION} (build {BUILD_NUMBER})"

# --- Logging ---
LOG_LEVEL = _get("logging", "level", "DEBUG").upper()
LOG_MAX_BYTES = int(_get("logging", "max_mb", "10")) * 1024 * 1024  # default 10 MB
LOG_BACKUP_COUNT = int(_get("logging", "backup_count", "5"))
LOG_DIR_OVERRIDE = _get("logging", "dir", "")

# --- Encryption key for sensitive fields ---
ENCRYPTION_KEY = _get("security", "encryption_key", "")

# --- File Server (VPS) ---
FILE_SERVER_URL = _get("file_server", "url", "").rstrip("/")
FILE_SERVER_API_KEY = _get("file_server", "api_key", "")

# --- ANSES ---
ANSES_PROVINCIA_DEFECTO = _get("anses", "provincia_defecto", "Buenos Aires")








