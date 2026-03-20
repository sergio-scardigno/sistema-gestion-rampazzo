# Rampazzo File Server (VPS)

Servidor HTTP para almacenamiento centralizado de documentos del sistema.
Permite que varias PCs trabajen sobre los mismos archivos sin depender de rutas locales.

---

## Que incluye esta carpeta

- `file_server.py`: API FastAPI para upload/download/delete y monitoreo.
- `requirements.txt`: dependencias del servidor.
- `setup.sh`: instalacion automatica en Ubuntu (systemd + ufw + cron).
- `backup.sh`: backup comprimido semanal con rotacion automatica.
- `rampazzo-files.service`: plantilla de servicio systemd.
- `.env.example`: variables de entorno requeridas.

---

## Variables de entorno

En `/opt/rampazzo/server/.env`:

```env
RAMPAZZO_STORAGE_DIR=/opt/rampazzo/documentos
RAMPAZZO_API_KEY=CAMBIAR-POR-UNA-CLAVE-SEGURA
RAMPAZZO_HOST=0.0.0.0
RAMPAZZO_PORT=8443
RAMPAZZO_MAX_FILE_SIZE_MB=5
RAMPAZZO_BACKUP_DIR=/opt/rampazzo/backups
RAMPAZZO_BACKUP_RETENTION_WEEKS=4
```

---

## Instalacion en VPS (Ubuntu)

Desde esta carpeta:

```bash
chmod +x setup.sh backup.sh
sed -i 's/\r$//' setup.sh backup.sh
sudo ./setup.sh
```

El setup realiza automaticamente:

1. Instalacion/verificacion de Python 3.11+.
2. Creacion de usuario de sistema `rampazzo`.
3. Creacion de directorios:
   - `/opt/rampazzo/server`
   - `/opt/rampazzo/documentos`
   - `/opt/rampazzo/backups`
4. Instalacion de dependencias Python.
5. Instalacion de `zstd` y `cron` (si faltan).
6. Creacion/actualizacion de `.env` con variables de backup.
7. Instalacion y arranque de `rampazzo-files.service`.
8. Registro de cron semanal de backup (domingo 03:00).

---

## Endpoints disponibles

Todos (excepto `/health`) requieren header:

`x-api-key: <RAMPAZZO_API_KEY>`

- `GET /health`: estado del server y espacio libre.
- `POST /upload/{file_path}`: subir archivo.
- `GET /download/{file_path}`: descargar archivo.
- `DELETE /delete/{file_path}`: eliminar archivo.
- `GET /stats`: estadisticas de almacenamiento por carpeta/expediente.
- `GET /backups`: lista de backups comprimidos disponibles.

Ejemplo:

```bash
API_KEY=$(grep RAMPAZZO_API_KEY /opt/rampazzo/server/.env | cut -d= -f2)
curl -H "x-api-key: $API_KEY" http://localhost:8443/backups
```

---

## Backup semanal comprimido

`backup.sh` genera archivos:

`docs_backup_YYYYMMDD_HHMMSS.tar.zst`

Por defecto en:

`/opt/rampazzo/backups`

Compresion usada:

- `tar --zstd` (alto ratio para PDFs/imagenes).

Rotacion:

- elimina backups mas viejos que `RAMPAZZO_BACKUP_RETENTION_WEEKS` (default 4).

Cron configurado por setup:

```cron
0 3 * * 0 /usr/bin/env bash /opt/rampazzo/server/backup.sh >/dev/null 2>&1
```

Ejecucion manual:

```bash
sudo -u rampazzo /usr/bin/env bash /opt/rampazzo/server/backup.sh
ls -lh /opt/rampazzo/backups
```

---

## Recuperacion de documentos desde backup

Ejemplo de restauracion:

```bash
cd /opt/rampazzo
tar --zstd -xf backups/docs_backup_YYYYMMDD_HHMMSS.tar.zst -C /
```

Esto restaura la estructura de `/opt/rampazzo/documentos/`.

---

## Troubleshooting rapido

### Error `env: bash\r: No such file or directory`

Los scripts estan en CRLF (Windows). Convertir a LF:

```bash
sed -i 's/\r$//' /opt/rampazzo/server/setup.sh /opt/rampazzo/server/backup.sh
chmod +x /opt/rampazzo/server/setup.sh /opt/rampazzo/server/backup.sh
```

### Error `crontab: command not found`

Instalar y arrancar cron:

```bash
apt-get update -qq
apt-get install -y -qq cron
systemctl enable --now cron
```

### Verificar servicio

```bash
systemctl status rampazzo-files
journalctl -u rampazzo-files -f
```
