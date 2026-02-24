#!/bin/bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
APP_BIN="$DIR/SistemaRampazzo"

# Gatekeeper marca archivos descargados con cuarentena.
# Remover el atributo permite ejecutar la app sin advertencias bloqueantes.
if command -v xattr >/dev/null 2>&1; then
  xattr -cr "$DIR" || true
fi

chmod +x "$APP_BIN" || true
exec "$APP_BIN"
