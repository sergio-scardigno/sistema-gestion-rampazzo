"""
Sistema de logging avanzado para Sistema Rampazzo.

Proporciona:
  - Logging centralizado con RotatingFileHandler (archivo rotativo).
  - Contexto automatico: version, machine_id, usuario, modo frozen.
  - Captura global de excepciones (sys.excepthook, threading.excepthook).
  - Captura de crashes duros via faulthandler.
  - Redireccion de mensajes Qt a logging.

Uso:
  from core.logging_setup import init_logging
  init_logging()   # llamar UNA vez al inicio, antes de QApplication
"""
import sys
import os
import logging
import logging.config
import logging.handlers
import faulthandler
import threading
from pathlib import Path

_LOG_INITIALIZED = False

# ── Directorio de logs ──────────────────────────────────────────────

def get_log_dir() -> Path:
    """Retorna el directorio de logs, creandolo si no existe.

    En modo frozen (PyInstaller .exe) usa %LOCALAPPDATA%/Sistema Rampazzo/logs
    para garantizar permisos de escritura.
    En modo desarrollo usa BASE_DIR/logs.
    """
    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        log_dir = base / "Sistema Rampazzo" / "logs"
    else:
        from config import BASE_DIR
        log_dir = BASE_DIR / "logs"

    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


# ── Filtro de contexto ──────────────────────────────────────────────

class _AppContextFilter(logging.Filter):
    """Inyecta campos de contexto en cada LogRecord."""

    def filter(self, record):
        from config import APP_VERSION, MACHINE_ID

        record.app_version = APP_VERSION
        record.machine_id = MACHINE_ID
        record.frozen = getattr(sys, "frozen", False)

        # Usuario de sesion (puede no existir si falla antes del login)
        try:
            from core.auth import Session
            session = Session.get()
            record.session_user = session.username if session.logged_in else "-"
            record.session_rol = session.rol if session.logged_in else "-"
        except Exception:
            record.session_user = "-"
            record.session_rol = "-"

        return True


# ── Configuracion principal ─────────────────────────────────────────

def init_logging():
    """Configura el sistema de logging global.

    Debe llamarse una sola vez, lo mas temprano posible en main().
    """
    global _LOG_INITIALIZED
    if _LOG_INITIALIZED:
        return
    _LOG_INITIALIZED = True

    from config import (
        LOG_LEVEL, LOG_MAX_BYTES, LOG_BACKUP_COUNT, LOG_DIR_OVERRIDE,
    )

    if LOG_DIR_OVERRIDE:
        log_dir = Path(LOG_DIR_OVERRIDE)
        log_dir.mkdir(parents=True, exist_ok=True)
    else:
        log_dir = get_log_dir()

    log_file = str(log_dir / "app.log")
    crash_file = log_dir / "crash.log"

    # Formato detallado para archivo
    file_fmt = (
        "%(asctime)s | %(levelname)-8s | "
        "v%(app_version)s | %(machine_id)s | %(session_user)s | "
        "%(name)s:%(funcName)s:%(lineno)d | "
        "%(message)s"
    )

    # Formato compacto para consola (solo en modo dev)
    console_fmt = (
        "%(asctime)s %(levelname)-8s %(name)s:%(funcName)s:%(lineno)d  %(message)s"
    )

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "app_context": {
                "()": _AppContextFilter,
            },
        },
        "formatters": {
            "detailed": {
                "format": file_fmt,
                "datefmt": "%Y-%m-%dT%H:%M:%S",
            },
            "console": {
                "format": console_fmt,
                "datefmt": "%H:%M:%S",
            },
        },
        "handlers": {
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": log_file,
                "maxBytes": LOG_MAX_BYTES,
                "backupCount": LOG_BACKUP_COUNT,
                "encoding": "utf-8",
                "formatter": "detailed",
                "filters": ["app_context"],
                "level": "DEBUG",
            },
        },
        "root": {
            "level": LOG_LEVEL,
            "handlers": ["file"],
        },
    }

    # En modo dev agregar handler de consola
    if not getattr(sys, "frozen", False):
        config["handlers"]["console"] = {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
            "formatter": "console",
            "level": "DEBUG",
        }
        config["root"]["handlers"].append("console")

    logging.config.dictConfig(config)

    # Silenciar loggers ruidosos de terceros (pymongo emite heartbeats
    # cada ~10s en DEBUG, saturando consola y archivo de log).
    for noisy in ("pymongo", "pymongo.topology", "pymongo.connection",
                  "pymongo.command", "pymongo.serverSelection"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # Instalar captura global de excepciones
    _install_global_exception_handlers(crash_file)

    # Banner inicial
    logger = logging.getLogger("startup")
    logger.info(
        "=== Sistema Rampazzo iniciado === "
        "frozen=%s | log_dir=%s | pid=%d",
        getattr(sys, "frozen", False), log_dir, os.getpid(),
    )


# ── Hooks globales de excepciones ───────────────────────────────────

def _install_global_exception_handlers(crash_file: Path):
    """Instala interceptores para excepciones no capturadas."""

    _crash_logger = logging.getLogger("crash")

    # 1) sys.excepthook – excepciones no capturadas en el hilo principal
    _original_excepthook = sys.excepthook

    def _excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            _original_excepthook(exc_type, exc_value, exc_tb)
            return
        _crash_logger.critical(
            "Excepcion no capturada", exc_info=(exc_type, exc_value, exc_tb)
        )

    sys.excepthook = _excepthook

    # 2) threading.excepthook – excepciones no capturadas en threads secundarios
    def _thread_excepthook(args):
        if issubclass(args.exc_type, SystemExit):
            return
        _crash_logger.critical(
            "Excepcion no capturada en thread '%s'",
            args.thread.name if args.thread else "unknown",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = _thread_excepthook

    # 3) faulthandler – crashes duros (segfault, abort)
    try:
        fh = open(str(crash_file), "a", encoding="utf-8")
        faulthandler.enable(file=fh)
    except Exception:
        faulthandler.enable()

    # 4) Redireccion de mensajes internos de Qt a logging
    try:
        from PySide6.QtCore import qInstallMessageHandler, QtMsgType

        _qt_logger = logging.getLogger("qt")
        _qt_level_map = {
            QtMsgType.QtDebugMsg: logging.DEBUG,
            QtMsgType.QtInfoMsg: logging.INFO,
            QtMsgType.QtWarningMsg: logging.WARNING,
            QtMsgType.QtCriticalMsg: logging.ERROR,
            QtMsgType.QtFatalMsg: logging.CRITICAL,
        }

        def _qt_message_handler(mode, context, message):
            level = _qt_level_map.get(mode, logging.WARNING)
            _qt_logger.log(
                level,
                "%s (file=%s, line=%d, func=%s)",
                message,
                context.file or "?",
                context.line,
                context.function or "?",
            )

        qInstallMessageHandler(_qt_message_handler)
    except Exception:
        pass
