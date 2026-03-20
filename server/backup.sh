#!/usr/bin/env bash
# Backup semanal comprimido (zstd) de documentos Rampazzo.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

# Defaults (si no hay .env o faltan variables).
RAMPAZZO_STORAGE_DIR_DEFAULT="/opt/rampazzo/documentos"
RAMPAZZO_BACKUP_DIR_DEFAULT="/opt/rampazzo/backups"
RAMPAZZO_BACKUP_RETENTION_WEEKS_DEFAULT="4"

if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    source "$ENV_FILE"
fi

STORAGE_DIR="${RAMPAZZO_STORAGE_DIR:-$RAMPAZZO_STORAGE_DIR_DEFAULT}"
BACKUP_DIR="${RAMPAZZO_BACKUP_DIR:-$RAMPAZZO_BACKUP_DIR_DEFAULT}"
RETENTION_WEEKS="${RAMPAZZO_BACKUP_RETENTION_WEEKS:-$RAMPAZZO_BACKUP_RETENTION_WEEKS_DEFAULT}"

if [ ! -d "$STORAGE_DIR" ]; then
    logger -t rampazzo-backup "[ERROR] STORAGE_DIR no existe: $STORAGE_DIR"
    echo "ERROR: STORAGE_DIR no existe: $STORAGE_DIR" >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"

DATE_TAG="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/docs_backup_${DATE_TAG}.tar.zst"

STORAGE_PARENT="$(dirname "$STORAGE_DIR")"
STORAGE_BASENAME="$(basename "$STORAGE_DIR")"

# Compresion fuerte: muy buen ratio para lotes de PDFs/imagenes.
tar --zstd -cf "$BACKUP_FILE" -C "$STORAGE_PARENT" "$STORAGE_BASENAME"

SIZE_BYTES="$(stat -c%s "$BACKUP_FILE" 2>/dev/null || echo 0)"
SIZE_MB="$(awk "BEGIN {printf \"%.2f\", ${SIZE_BYTES}/1024/1024}")"

if ! [[ "$RETENTION_WEEKS" =~ ^[0-9]+$ ]]; then
    RETENTION_WEEKS="$RAMPAZZO_BACKUP_RETENTION_WEEKS_DEFAULT"
fi
RETENTION_DAYS="$((RETENTION_WEEKS * 7))"

# Borra backups antiguos segun retencion.
find "$BACKUP_DIR" -maxdepth 1 -type f -name "docs_backup_*.tar.zst" -mtime +"$RETENTION_DAYS" -delete

logger -t rampazzo-backup "[OK] Backup generado: ${BACKUP_FILE} (${SIZE_MB} MB), retencion=${RETENTION_WEEKS} semanas"
echo "Backup OK: ${BACKUP_FILE} (${SIZE_MB} MB)"
