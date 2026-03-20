#!/usr/bin/env bash
# =============================================================================
# Setup completo del servidor de archivos Rampazzo para Ubuntu VPS.
#
# Uso:
#   chmod +x setup.sh
#   sudo ./setup.sh
#
# Lo que hace:
#   1. Instala Python 3.11+ si no esta disponible
#   2. Crea usuario de sistema 'rampazzo'
#   3. Crea estructura de directorios en /opt/rampazzo/
#   4. Copia archivos del servidor
#   5. Crea virtualenv e instala dependencias
#   6. Genera API key segura (si no existe)
#   7. Configura firewall (ufw)
#   8. Instala servicio systemd
#   9. Arranca el servicio
# =============================================================================
set -euo pipefail

# --- Colores ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# --- Verificar root ---
if [ "$EUID" -ne 0 ]; then
    error "Este script debe ejecutarse como root (sudo ./setup.sh)"
fi

INSTALL_DIR="/opt/rampazzo/server"
STORAGE_DIR="/opt/rampazzo/documentos"
BACKUP_DIR="/opt/rampazzo/backups"
SERVICE_NAME="rampazzo-files"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${RAMPAZZO_PORT:-8443}"

echo ""
echo "============================================"
echo "  Rampazzo File Server - Setup"
echo "============================================"
echo ""

# =============================================================================
# 1. Instalar Python
# =============================================================================
info "Verificando Python..."
if command -v python3.11 &>/dev/null; then
    PYTHON_BIN="python3.11"
elif command -v python3.12 &>/dev/null; then
    PYTHON_BIN="python3.12"
elif command -v python3.13 &>/dev/null; then
    PYTHON_BIN="python3.13"
elif command -v python3 &>/dev/null; then
    PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 11 ]; then
        PYTHON_BIN="python3"
    else
        info "Python $PY_VER encontrado, instalando 3.11..."
        apt-get update -qq
        apt-get install -y -qq python3.11 python3.11-venv python3.11-dev
        PYTHON_BIN="python3.11"
    fi
else
    info "Instalando Python 3.11..."
    apt-get update -qq
    apt-get install -y -qq software-properties-common
    add-apt-repository -y ppa:deadsnakes/ppa
    apt-get update -qq
    apt-get install -y -qq python3.11 python3.11-venv python3.11-dev
    PYTHON_BIN="python3.11"
fi
info "Usando: $PYTHON_BIN ($($PYTHON_BIN --version))"

# =============================================================================
# 2. Crear usuario de sistema
# =============================================================================
if id "rampazzo" &>/dev/null; then
    info "Usuario 'rampazzo' ya existe"
else
    info "Creando usuario de sistema 'rampazzo'..."
    useradd --system --shell /usr/sbin/nologin --home-dir /opt/rampazzo rampazzo
fi

# =============================================================================
# 3. Crear directorios
# =============================================================================
info "Creando directorios..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$STORAGE_DIR"
mkdir -p "$BACKUP_DIR"

# =============================================================================
# 4. Copiar archivos del servidor
# =============================================================================
info "Copiando archivos del servidor..."
cp "$SCRIPT_DIR/file_server.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/backup.sh" "$INSTALL_DIR/"
# Fuerza formato Linux aunque el repo local venga con CRLF.
sed -i 's/\r$//' "$INSTALL_DIR/backup.sh"
chmod +x "$INSTALL_DIR/backup.sh"

# =============================================================================
# 5. Virtualenv + dependencias
# =============================================================================
if [ ! -d "$INSTALL_DIR/venv" ]; then
    info "Creando virtualenv..."
    $PYTHON_BIN -m venv "$INSTALL_DIR/venv"
fi

info "Instalando dependencias..."
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip -q
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" -q
info "Dependencias instaladas correctamente"

# =============================================================================
# 6.1 Instalar zstd para backups comprimidos
# =============================================================================
if command -v zstd &>/dev/null; then
    info "zstd ya esta instalado"
else
    info "Instalando zstd..."
    apt-get update -qq
    apt-get install -y -qq zstd
fi

# =============================================================================
# 6.2 Instalar cron si no existe (para backups semanales)
# =============================================================================
if command -v crontab &>/dev/null; then
    info "cron/crontab ya esta instalado"
else
    info "Instalando cron..."
    apt-get update -qq
    apt-get install -y -qq cron
fi
systemctl enable cron >/dev/null 2>&1 || true
systemctl start cron >/dev/null 2>&1 || true

# =============================================================================
# 6.3 Configurar .env (API Key + Backup)
# =============================================================================
ENV_FILE="$INSTALL_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    info "Archivo .env ya existe, conservando configuracion actual"
else
    info "Generando archivo .env con API key segura..."
    API_KEY=$(openssl rand -base64 32 | tr -d '/+=' | head -c 40)
    cat > "$ENV_FILE" <<EOF
RAMPAZZO_STORAGE_DIR=$STORAGE_DIR
RAMPAZZO_API_KEY=$API_KEY
RAMPAZZO_HOST=0.0.0.0
RAMPAZZO_PORT=$PORT
RAMPAZZO_MAX_FILE_SIZE_MB=5
RAMPAZZO_BACKUP_DIR=$BACKUP_DIR
RAMPAZZO_BACKUP_RETENTION_WEEKS=4
EOF
    chmod 600 "$ENV_FILE"
    echo ""
    echo -e "${YELLOW}============================================${NC}"
    echo -e "${YELLOW}  API KEY GENERADA (guardar en lugar seguro):${NC}"
    echo -e "${GREEN}  $API_KEY${NC}"
    echo -e "${YELLOW}============================================${NC}"
    echo ""
fi

if ! grep -q '^RAMPAZZO_BACKUP_DIR=' "$ENV_FILE"; then
    echo "RAMPAZZO_BACKUP_DIR=$BACKUP_DIR" >> "$ENV_FILE"
fi
if ! grep -q '^RAMPAZZO_BACKUP_RETENTION_WEEKS=' "$ENV_FILE"; then
    echo "RAMPAZZO_BACKUP_RETENTION_WEEKS=4" >> "$ENV_FILE"
fi

# =============================================================================
# 7. Permisos
# =============================================================================
info "Configurando permisos..."
chown -R rampazzo:rampazzo /opt/rampazzo
chmod 750 "$INSTALL_DIR"
chmod 750 "$STORAGE_DIR"
chmod 750 "$BACKUP_DIR"

# =============================================================================
# 8. Firewall (ufw)
# =============================================================================
if command -v ufw &>/dev/null; then
    if ufw status | grep -q "active"; then
        if ! ufw status | grep -q "$PORT"; then
            info "Abriendo puerto $PORT en ufw..."
            ufw allow "$PORT/tcp" comment "Rampazzo File Server"
        else
            info "Puerto $PORT ya esta abierto en ufw"
        fi
    else
        warn "ufw esta instalado pero no activo, omitiendo configuracion de firewall"
    fi
else
    warn "ufw no encontrado, asegurate de abrir el puerto $PORT manualmente"
fi

# =============================================================================
# 9. Instalar servicio systemd
# =============================================================================
info "Instalando servicio systemd..."
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=Rampazzo File Server
After=network.target

[Service]
Type=simple
User=rampazzo
Group=rampazzo
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$INSTALL_DIR/venv/bin/python file_server.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

# =============================================================================
# 10. Arrancar servicio
# =============================================================================
info "Iniciando servicio..."
systemctl restart "$SERVICE_NAME"
sleep 2

if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}  Servidor instalado y corriendo!${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo ""
    echo "  URL:     http://$(hostname -I | awk '{print $1}'):$PORT"
    echo "  Health:  curl http://localhost:$PORT/health"
    echo "  Logs:    journalctl -u $SERVICE_NAME -f"
    echo "  Estado:  systemctl status $SERVICE_NAME"
    echo ""
    echo "  Para la app de escritorio, configurar en config.ini:"
    echo "    [file_server]"
    echo "    url = http://TU-IP-VPS:$PORT"
    API_KEY_VAL=$(grep RAMPAZZO_API_KEY "$ENV_FILE" | cut -d= -f2)
    echo "    api_key = $API_KEY_VAL"
    echo ""
else
    error "El servicio no arranco correctamente. Revisar: journalctl -u $SERVICE_NAME -e"
fi

# =============================================================================
# 11. Cron semanal de backup (domingo 03:00)
# =============================================================================
CRON_JOB="0 3 * * 0 /usr/bin/env bash $INSTALL_DIR/backup.sh >/dev/null 2>&1"
if ! command -v crontab &>/dev/null; then
    warn "No se pudo registrar cron: comando crontab no disponible"
else
    CURRENT_CRON="$(crontab -u rampazzo -l 2>/dev/null || true)"
    if printf "%s\n" "$CURRENT_CRON" | grep -F -q "$INSTALL_DIR/backup.sh"; then
        info "Cron de backup ya existe para usuario rampazzo"
    else
        info "Registrando cron semanal de backup para usuario rampazzo..."
        {
            printf "%s\n" "$CURRENT_CRON"
            printf "%s\n" "$CRON_JOB"
        } | crontab -u rampazzo -
    fi
fi

echo "  Backup cron: domingos 03:00 -> $INSTALL_DIR/backup.sh"
