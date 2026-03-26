"""
Servidor de archivos para Sistema Rampazzo.
Permite subir y descargar documentos entre multiples PCs via HTTP.
Corre en el VPS con FastAPI + Uvicorn.
"""
import os
import secrets
import logging
from datetime import datetime
from pathlib import Path
from collections import defaultdict

from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------
STORAGE_DIR = Path(os.environ.get("RAMPAZZO_STORAGE_DIR", "/opt/rampazzo/documentos"))
API_KEY = os.environ.get("RAMPAZZO_API_KEY", "")
HOST = os.environ.get("RAMPAZZO_HOST", "0.0.0.0")
PORT = int(os.environ.get("RAMPAZZO_PORT", "8443"))
MAX_FILE_SIZE_MB = int(os.environ.get("RAMPAZZO_MAX_FILE_SIZE_MB", "5"))
BACKUP_DIR = Path(os.environ.get("RAMPAZZO_BACKUP_DIR", "/opt/rampazzo/backups"))
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".doc", ".docx"}

STORAGE_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("rampazzo_files")

app = FastAPI(
    title="Rampazzo File Server",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def _verify_key(x_api_key: str = Header(...)):
    if not API_KEY:
        raise HTTPException(500, "API key no configurada en el servidor")
    if not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(403, "API key invalida")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    free_bytes = 0
    try:
        stat = os.statvfs(str(STORAGE_DIR))
        free_bytes = stat.f_bavail * stat.f_frsize
    except (OSError, AttributeError):
        pass
    return {
        "status": "ok",
        "storage_dir": str(STORAGE_DIR),
        "free_space_mb": round(free_bytes / (1024 * 1024), 1) if free_bytes else None,
    }


@app.post("/upload/{file_path:path}")
async def upload_file(
    file_path: str,
    file: UploadFile = File(...),
    x_api_key: str = Header(...),
):
    _verify_key(x_api_key)

    safe_path = Path(file_path)
    if ".." in safe_path.parts:
        raise HTTPException(400, "Ruta invalida")
    if safe_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, "Tipo de archivo no permitido")

    dest = STORAGE_DIR / safe_path
    dest.parent.mkdir(parents=True, exist_ok=True)

    size = 0
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    try:
        with open(dest, "wb") as f:
            while chunk := await file.read(1024 * 256):
                size += len(chunk)
                if size > max_bytes:
                    f.close()
                    dest.unlink(missing_ok=True)
                    raise HTTPException(
                        413, f"Archivo excede el limite de {MAX_FILE_SIZE_MB} MB"
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error al guardar archivo: %s", file_path)
        raise HTTPException(500, f"Error al guardar: {exc}")

    logger.info("Archivo subido: %s (%s KB)", file_path, round(size / 1024, 1))
    return {"status": "ok", "path": file_path, "size_bytes": size}


@app.get("/stats")
async def stats(x_api_key: str = Header(...)):
    _verify_key(x_api_key)

    total_files = 0
    total_size = 0
    by_expediente = defaultdict(lambda: {"files": 0, "size_bytes": 0})

    for file in STORAGE_DIR.rglob("*"):
        if not file.is_file():
            continue
        total_files += 1
        size = file.stat().st_size
        total_size += size
        parts = file.relative_to(STORAGE_DIR).parts
        exp_id = parts[0] if parts else "sin_carpeta"
        by_expediente[exp_id]["files"] += 1
        by_expediente[exp_id]["size_bytes"] += size

    por_expediente = [
        {
            "id_expediente": exp_id,
            "files": info["files"],
            "size_mb": round(info["size_bytes"] / (1024 * 1024), 2),
        }
        for exp_id, info in sorted(by_expediente.items(), key=lambda item: item[1]["files"], reverse=True)
    ]

    return {
        "total_files": total_files,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "por_expediente": por_expediente,
    }


@app.get("/backups")
async def backups(x_api_key: str = Header(...)):
    _verify_key(x_api_key)

    if not BACKUP_DIR.exists():
        return {"backup_dir": str(BACKUP_DIR), "backups": [], "total_size_mb": 0.0}

    entries = []
    total_size_bytes = 0

    for file in sorted(BACKUP_DIR.glob("docs_backup_*.tar.zst"), key=lambda p: p.name, reverse=True):
        if not file.is_file():
            continue
        size = file.stat().st_size
        total_size_bytes += size

        date_str = None
        stem_name = file.name.removesuffix(".tar.zst")
        raw_ts = stem_name.replace("docs_backup_", "", 1)
        try:
            dt = datetime.strptime(raw_ts, "%Y%m%d_%H%M%S")
            date_str = dt.strftime("%Y-%m-%d")
        except ValueError:
            date_str = None

        entries.append(
            {
                "name": file.name,
                "size_mb": round(size / (1024 * 1024), 2),
                "date": date_str,
            }
        )

    return {
        "backup_dir": str(BACKUP_DIR),
        "backups": entries,
        "total_size_mb": round(total_size_bytes / (1024 * 1024), 2),
    }


@app.get("/download/{file_path:path}")
async def download_file(
    file_path: str,
    x_api_key: str = Header(...),
):
    _verify_key(x_api_key)

    safe_path = Path(file_path)
    if ".." in safe_path.parts:
        raise HTTPException(400, "Ruta invalida")

    dest = STORAGE_DIR / safe_path
    if not dest.is_file():
        raise HTTPException(404, "Archivo no encontrado")

    return FileResponse(
        path=str(dest),
        filename=dest.name,
        media_type="application/octet-stream",
    )


@app.delete("/delete/{file_path:path}")
async def delete_file(
    file_path: str,
    x_api_key: str = Header(...),
):
    _verify_key(x_api_key)

    safe_path = Path(file_path)
    if ".." in safe_path.parts:
        raise HTTPException(400, "Ruta invalida")

    dest = STORAGE_DIR / safe_path
    if not dest.is_file():
        raise HTTPException(404, "Archivo no encontrado")

    dest.unlink()
    logger.info("Archivo eliminado: %s", file_path)
    return {"status": "ok", "path": file_path}


# ---------------------------------------------------------------------------
# Manejo de errores global
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Error no manejado: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if not API_KEY:
        generated = secrets.token_urlsafe(32)
        print("=" * 60)
        print("  ATENCION: No se configuro RAMPAZZO_API_KEY")
        print(f"  Generando key temporal: {generated}")
        print("  Configura RAMPAZZO_API_KEY en el .env o como variable")
        print("=" * 60)
        API_KEY = generated

    logger.info("Iniciando servidor en %s:%s", HOST, PORT)
    logger.info("Directorio de almacenamiento: %s", STORAGE_DIR)

    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
    )
