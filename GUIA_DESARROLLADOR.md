# Guia del Desarrollador - Sistema Rampazzo

Guia tecnica para desarrolladores que necesiten configurar el entorno, ejecutar tests, compilar el ejecutable con PyInstaller y generar un ZIP distribuible.

---

## Indice

1. [Requisitos previos](#1-requisitos-previos)
2. [Setup del entorno de desarrollo](#2-setup-del-entorno-de-desarrollo)
3. [Ejecutar en modo desarrollo](#3-ejecutar-en-modo-desarrollo)
4. [Testing](#4-testing)
5. [Sincronizacion reforzada](#5-sincronizacion-reforzada)
6. [Backup manual completo (UI y CLI)](#6-backup-manual-completo-ui-y-cli)
   - [6.4 Servidor de archivos VPS y backup semanal](#64-servidor-de-archivos-vps-y-backup-semanal)
7. [Build del ejecutable](#7-build-del-ejecutable)
8. [Generar ZIP distribuible](#8-generar-zip-distribuible)
9. [Estructura del ZIP resultante](#9-estructura-del-zip-resultante)
10. [Distribucion e instalacion en cliente](#10-distribucion-e-instalacion-en-cliente)
11. [Estructura del proyecto](#11-estructura-del-proyecto)
12. [Troubleshooting](#12-troubleshooting)
13. [Seguridad por IP/WiFi (diseno futuro)](#13-seguridad-por-ipwifi-diseno-futuro)
14. [Notificaciones en UI (estilos y archivos clave)](#14-notificaciones-en-ui-estilos-y-archivos-clave)

---

## 1. Requisitos previos

| Requisito | Version minima | Verificar con |
|---|---|---|
| Python | 3.12+ | `python --version` |
| pip | (incluido con Python) | `pip --version` |
| Git | cualquiera | `git --version` |

No se necesita instalar nada mas de forma global. Todas las dependencias se instalan en el entorno virtual.

---

## 2. Setup del entorno de desarrollo

### 2.1 Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd sistema-gestion-rampazzo
```

### 2.2 Crear entorno virtual

```bash
python -m venv .venv
```

Activar el entorno:

```powershell
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (CMD)
.venv\Scripts\activate.bat
```

```bash
# Linux / macOS
source .venv/bin/activate
```

### 2.3 Instalar dependencias

```bash
pip install -r requirements.txt
```

Esto instala tanto las dependencias de produccion (PySide6, pymongo, etc.) como las de testing (pytest, pytest-qt, etc.).

### 2.4 Configurar la conexion a MongoDB Atlas

```bash
# Windows
copy config.ini.example config.ini

# Linux / macOS
cp config.ini.example config.ini
```

Editar `config.ini` con las credenciales reales del cluster:

```ini
[mongo]
uri = mongodb+srv://<usuario>:<password>@<cluster>.mongodb.net
database = gestion
```

> Si no se configura MongoDB, la aplicacion funciona en modo offline con SQLite unicamente.

---

## 3. Ejecutar en modo desarrollo

```bash
python main.py
```

La primera ejecucion crea automaticamente:
- `data/local.db` (base de datos SQLite)
- Usuarios por defecto (super/super123, admin/admin123, etc.)
- Triggers de proteccion de auditoria

---

## 4. Testing

### Ejecutar tests

```bash
# Suite completa (489 tests; cobertura tipica ~81%+ sobre modulos de negocio)
python -m pytest tests/

# Solo unitarios (156 tests)
python -m pytest tests/unit/

# Solo integracion (324 tests)
python -m pytest tests/integration/

# Solo smoke tests de UI (9 tests)
python -m pytest tests/ui/

# Con salida detallada
python -m pytest tests/ -v
```

### Reporte de cobertura

```bash
# En terminal
python -m pytest tests/ --cov --cov-config=.coveragerc --cov-report=term-missing

# Generar HTML interactivo
python -m pytest tests/ --cov --cov-config=.coveragerc --cov-report=html:htmlcov

# Abrir (Windows)
start htmlcov\index.html
```

---

## 5. Sincronizacion reforzada

La sincronizacion SQLite <-> Mongo incluye:

- **Tombstones** para borrado logico: `is_deleted`, `deleted_at`, `deleted_by`.
- **Deteccion de conflictos por version** con registro en `sync_conflicts`.
- **Metricas de ciclo** en `sync_meta`:
  - `sync_last_total_pushed`
  - `sync_last_total_pulled`
  - `sync_last_total_conflicts`
  - `sync_baseline_last_snapshot`

Notas de implementacion:
- `controllers/base_controller.py` usa `soft_delete()` en lugar de `DELETE` fisico.
- `core/sync_engine.py` registra conflictos de push/pull con snapshots local/remoto.
- `core/db_remote.py` asegura indices `updated_at` en colecciones sincronizadas.

---

## 6. Backup manual completo (UI y CLI)

### 6.1 Desde la UI (superusuario)

Ruta: `Configuracion -> General / Logos -> Backups Manuales`.

Acciones:
- `Exportar backup completo`
- `Importar backup completo` (incluye validacion previa `dry-run` antes de aplicar)

### 6.2 Desde CLI

```bash
# Exportar bundle hibrido completo
python main.py --export-backup "C:\ruta\backup_bundle.zip"

# Importar con validacion (sin aplicar)
python main.py --import-backup "C:\ruta\backup_bundle.zip" --dry-run

# Importar aplicando local + remoto
python main.py --import-backup "C:\ruta\backup_bundle.zip"

# Importar solo local (sin tocar Mongo)
python main.py --import-backup "C:\ruta\backup_bundle.zip" --no-remote
```

### 6.3 Formato del bundle

- `manifest.json`
- `local/sqlite.db`
- `local/documentos/`
- `remote/mongo_dump/*.jsonl`

### 6.4 Servidor de archivos VPS y backup semanal

El proyecto incluye una carpeta `server/` para alojar documentos compartidos en VPS.

Componentes:

- `server/file_server.py`: API de archivos (upload/download/delete/stats/backups).
- `server/setup.sh`: instala servicio systemd, dependencias y cron.
- `server/backup.sh`: backup `tar.zst` con retencion por semanas.
- `server/.env.example`: variables de configuracion.

Instalacion recomendada en Ubuntu:

```bash
cd server
chmod +x setup.sh backup.sh
sed -i 's/\r$//' setup.sh backup.sh
sudo ./setup.sh
```

Puntos importantes:

- El setup instala `cron` y `zstd` si faltan.
- El cron se registra como:
  `0 3 * * 0 /usr/bin/env bash /opt/rampazzo/server/backup.sh >/dev/null 2>&1`
- Los backups se guardan en `/opt/rampazzo/backups` (default).
- Endpoint de monitoreo: `GET /backups` con `x-api-key`.

Comandos de verificacion:

```bash
systemctl status rampazzo-files
sudo -u rampazzo /usr/bin/env bash /opt/rampazzo/server/backup.sh
ls -lh /opt/rampazzo/backups
```

Troubleshooting CRLF (si aparece `bash\r` o `pipefail`):

```bash
sed -i 's/\r$//' /opt/rampazzo/server/setup.sh /opt/rampazzo/server/backup.sh
```

---

## 7. Build del ejecutable

### 5.0 Build recomendado (multiplataforma)

El proyecto incluye `build.py`, que automatiza build + empaquetado en **Windows, Linux y macOS**:

```bash
python build.py
```

Este script:
- Verifica archivos del proyecto
- Genera/actualiza `build_info.py` y `build_number.txt`
- Compila con PyInstaller usando `SistemaRampazzo.spec`
- Copia `config.ini` (si existe) y `config.ini.example`
- Genera `SistemaRampazzo.zip`

### 5.1 Instalar PyInstaller

```bash
pip install pyinstaller
```

### 5.2 Compilar usando el archivo .spec

El proyecto incluye `SistemaRampazzo.spec` con toda la configuracion de build ya definida:

```bash
pyinstaller SistemaRampazzo.spec --noconfirm
```

Esto genera la carpeta `dist/SistemaRampazzo/` con el ejecutable y todas sus dependencias.

**Que hace el .spec:**
- Entry point: `main.py`
- Incluye automaticamente: `resources/` (estilos), `anses_oficinas/` (datos de oficinas), plugins de PySide6
- Modo `onedir` (carpeta con ejecutable + DLLs)
- Sin ventana de consola (`console=False`)
- Compresion UPX habilitada

### 5.3 Build alternativo (sin .spec)

Si por algun motivo no se dispone del `.spec`:

```bash
pyinstaller --name "SistemaRampazzo" ^
    --windowed ^
    --onedir ^
    --add-data "resources;resources" ^
    --add-data "anses_oficinas;anses_oficinas" ^
    --add-data ".venv\Lib\site-packages\PySide6\plugins;PySide6\plugins" ^
    main.py
```

> En Linux/macOS reemplazar `;` por `:` en `--add-data` y `^` por `\`.

### 5.4 Verificar el build

Antes de generar el ZIP, verificar que el ejecutable funciona:

```bash
dist\SistemaRampazzo\SistemaRampazzo.exe
```

Debe abrir la ventana de login sin errores. Si falla, revisar la seccion de [Troubleshooting](#10-troubleshooting).

---

## 8. Generar ZIP distribuible

Despues de un build exitoso, ejecutar el siguiente script de PowerShell desde la raiz del proyecto para generar un ZIP listo para distribuir:

### 6.1 Script de empaquetado (PowerShell)

```powershell
# --- Configuracion ---
$distDir   = "dist\SistemaRampazzo"
$zipName   = "SistemaRampazzo.zip"
$outputZip = "dist\$zipName"

# --- Verificar que el build existe ---
if (-not (Test-Path "$distDir\SistemaRampazzo.exe")) {
    Write-Error "No se encontro el ejecutable. Ejecutar primero: pyinstaller SistemaRampazzo.spec --noconfirm"
    exit 1
}

# --- Copiar config.ini.example al directorio de distribucion ---
Copy-Item "config.ini.example" "$distDir\config.ini.example" -Force

# --- Eliminar ZIP anterior si existe ---
if (Test-Path $outputZip) {
    Remove-Item $outputZip -Force
}

# --- Crear el ZIP ---
Compress-Archive -Path "$distDir\*" -DestinationPath $outputZip -CompressionLevel Optimal

# --- Resultado ---
$size = [math]::Round((Get-Item $outputZip).Length / 1MB, 1)
Write-Output ""
Write-Output "ZIP generado exitosamente:"
Write-Output "  Archivo: $outputZip"
Write-Output "  Tamano:  $size MB"
Write-Output ""
Write-Output "Listo para distribuir."
```

### 6.2 Comando rapido (una linea)

Si se prefiere hacerlo sin script:

```powershell
Copy-Item config.ini.example dist\SistemaRampazzo\config.ini.example -Force; Compress-Archive -Path "dist\SistemaRampazzo\*" -DestinationPath "dist\SistemaRampazzo.zip" -Force
```

---

## 9. Estructura del ZIP resultante

```
SistemaRampazzo.zip
├── SistemaRampazzo.exe          # Ejecutable principal
├── config.ini.example           # Plantilla de configuracion
├── resources/
│   └── styles/
│       └── theme.qss            # Tema visual de la aplicacion
├── anses_oficinas/
│   ├── localidades.csv          # Localidades para selector de turnos
│   └── oficinas_anses_parsed.json
├── PySide6/
│   └── plugins/                 # Plugins Qt necesarios
└── [DLLs y dependencias de Python empaquetadas por PyInstaller]
```

Al ejecutar por primera vez, la aplicacion crea automaticamente:

```
(junto al .exe)
├── data/
│   ├── local.db                 # Base de datos SQLite
│   ├── backups/                 # Backups automaticos
│   └── documentos/              # Archivos adjuntos
├── config.ini                   # Se crea a partir de config.ini.example
└── logs/                        # Logs de la aplicacion
```

---

## 10. Distribucion e instalacion en cliente

### Pasos para el usuario final

1. Descomprimir `SistemaRampazzo.zip` en la ubicacion deseada.
2. Renombrar `config.ini.example` a `config.ini`.
3. Editar `config.ini` con las credenciales de MongoDB Atlas (si aplica).
4. Ejecutar la app segun el sistema operativo:
   - **Windows**: `SistemaRampazzo.exe`
   - **Linux**: `./SistemaRampazzo`
   - **macOS**: `iniciar_mac.command` (primera ejecucion recomendada)

### Notas importantes

- La carpeta donde se descomprime debe tener **permisos de escritura** (la app crea `data/` y `logs/` ahi).
- Si no hay permisos de escritura, la app usa `%LOCALAPPDATA%\SistemaRampazzo\data\` como alternativa.
- Sin `config.ini` con credenciales de MongoDB, la app funciona en **modo offline** (solo SQLite local).
- Los datos del sistema (BD, documentos, backups) se almacenan en `data/` y deben incluirse en las politicas de backup del cliente.
- En **macOS**, si Gatekeeper bloquea la app descargada, ejecutar primero `iniciar_mac.command` o aplicar la alternativa manual de la seccion de Troubleshooting.

---

## 11. Estructura del proyecto

```
sistema-gestion-rampazzo/
├── main.py                      # Punto de entrada
├── config.py                    # Configuracion central (lee config.ini)
├── config.ini                   # Config local (NO versionado, tiene credenciales)
├── config.ini.example           # Plantilla segura de configuracion
├── requirements.txt             # Dependencias Python
├── SistemaRampazzo.spec         # Configuracion de PyInstaller
├── pytest.ini                   # Configuracion de pytest
├── .coveragerc                  # Configuracion de cobertura
├── .gitignore
│
├── core/                        # Nucleo: auth, sync, DB, permisos, scheduler
├── controllers/                 # Logica de negocio y CRUD
│   # ... incluye notificacion_controller.py (tipos, NOTIF_STYLES, popup login, badge),
│   # expediente_recordatorio_controller.py, expediente_etapa_responsable_controller.py
├── models/                      # Helpers de modelo (IDs, timestamps)
├── views/                       # Interfaz grafica PySide6
│   # widgets/: notification_bell.py (campana, historial), login_task_alerts_popup.py
├── utils/                       # Validadores, formatters, exportacion, migracion
├── resources/styles/            # Hoja de estilos Qt (tema oscuro/dorado)
├── anses_oficinas/              # Datos de oficinas ANSES (incluidos en el build)
├── excel/                       # Plantillas CSV para migracion de datos
├── tests/                       # Tests unitarios, integracion y UI
├── data/                        # Datos locales (NO versionado)
├── logs/                        # Logs de ejecucion (NO versionado)
└── .github/workflows/           # Pipeline CI (GitHub Actions)
```

### Archivos clave para el build

| Archivo | Rol en el build |
|---|---|
| `SistemaRampazzo.spec` | Configuracion completa de PyInstaller (entry point, datos incluidos, opciones) |
| `config.py` | Detecta si se ejecuta como `.exe` (frozen) o como script, y ajusta rutas |
| `config.ini.example` | Se copia al ZIP para que el usuario final lo renombre a `config.ini` |
| `resources/` | Estilos Qt (`resources/styles/theme.qss`), incluidos en el build via `datas` del spec |
| `anses_oficinas/` | Datos de oficinas, incluidos en el build via `datas` del spec |

### Modulo de notificaciones y expediente (referencia rapida)

| Ruta | Descripcion |
|---|---|
| `controllers/notificacion_controller.py` | Tipos de notificacion, `NOTIF_STYLES`, sincronizacion con tareas, `get_login_popup_notifications`, `get_recent_for_user`, descarte (`dismiss`), reglas de badge |
| `controllers/expediente_recordatorio_controller.py` | Recordatorios / plazos por carpeta; disparo programado vinculado al scheduler |
| `controllers/expediente_etapa_responsable_controller.py` | Encargado por etapa; visibilidad y notificaciones `expediente_etapa_encargado` |
| `views/widgets/notification_bell.py` | Campana, popup de lista activa, historial, badge, reset de sesion |
| `views/widgets/login_task_alerts_popup.py` | Dialogo post-login de alertas, descarte por fila y masivo |
| `tests/unit/test_notificacion_controller.py` | Tests unitarios del controlador de notificaciones |
| `resources/styles/theme.qss` | Estilos de contenedores (`#LoginTaskAlertsPopup`, historial, botones de descarte); los items `#notif_item` se estilizan en gran parte desde Python segun `NOTIF_STYLES` |

---

## 12. Troubleshooting

### El build falla con "No module named PySide6"

Asegurarse de que el entorno virtual esta activado y PySide6 instalado:

```bash
pip install PySide6
```

### El .exe se abre y se cierra inmediatamente

Ejecutar desde la terminal para ver el error:

```bash
dist\SistemaRampazzo\SistemaRampazzo.exe
```

O compilar temporalmente con `console=True` en el `.spec` para ver la salida en consola.

### Error "Failed to load platform plugin windows"

Los plugins de PySide6 no estan incluidos. Verificar que el `.spec` tiene la linea:

```python
datas=[..., ('.venv\\Lib\\site-packages\\PySide6\\plugins', 'PySide6\\plugins')]
```

Si el entorno virtual tiene otro nombre (ej: `venv` en lugar de `.venv`), ajustar la ruta en el `.spec`.

### El ejecutable no encuentra resources/ o anses_oficinas/

Verificar que estan declarados en `datas` del `.spec`:

```python
datas=[('resources', 'resources'), ('anses_oficinas', 'anses_oficinas'), ...]
```

### El ZIP es muy grande (>200 MB)

Es normal para aplicaciones PySide6. Para reducir el tamano:

- Asegurarse de que UPX esta instalado y accesible en el PATH (comprime DLLs).
- En el `.spec`, agregar exclusiones de modulos no usados en `excludes`.

### config.ini no se detecta en el ejecutable

La aplicacion busca `config.ini` en este orden:
1. `data/config.ini` (junto al exe, dentro de data/)
2. Si no existe pero hay un `config.ini` junto al exe, lo copia a `data/`
3. Si la carpeta del exe no tiene permisos de escritura, usa `%LOCALAPPDATA%\SistemaRampazzo\data\`

### Los tests de UI fallan en CI

Los smoke tests de UI necesitan un display virtual. En GitHub Actions, el workflow usa `xvfb-run`. Localmente en Windows/macOS no deberia haber problema.

### macOS: "app no se puede abrir" / bloqueo de Gatekeeper

macOS puede bloquear binarios descargados de internet por el atributo de cuarentena (`com.apple.quarantine`).

Opciones para resolverlo:

1. Recomendado: hacer doble click en `iniciar_mac.command` (incluido en el ZIP de macOS).
2. Alternativa: click derecho sobre `SistemaRampazzo` -> **Abrir** -> confirmar.
3. Manual por terminal (en la carpeta descomprimida):

```bash
xattr -cr .
chmod +x SistemaRampazzo
./SistemaRampazzo
```

> Nota: para distribucion externa sin advertencias de seguridad, se requiere firma/notarizacion con Apple Developer ID.

### Quiero regenerar el .spec desde cero

```bash
pyi-makespec --name "SistemaRampazzo" --windowed --onedir ^
    --add-data "resources;resources" ^
    --add-data "anses_oficinas;anses_oficinas" ^
    --add-data ".venv\Lib\site-packages\PySide6\plugins;PySide6\plugins" ^
    main.py
```

> Nota: `*.spec` esta en `.gitignore`. Si se modifica el spec, asegurarse de no perderlo. Considerar quitar `*.spec` del `.gitignore` o hacer un backup manual.

---

## Resumen: Build + ZIP con un solo comando

Comando recomendado (Windows, Linux y macOS):

```bash
python build.py
```

En Windows tambien se puede usar `build.bat`:

```bat
build.bat
```

Para orquestar build de **Windows + Linux + macOS** desde Windows (via GitHub Actions) y descargar todo en carpetas versionadas:

```bat
build_multiplataforma.bat 1.2.0
```

Si no estas en un repo git local o queres apuntar a otro repo/rama:

```bat
build_multiplataforma.bat 1.2.0 owner/repo main
```

### Release unificada (version + git + build)

Para mantener **la misma version en Git y en los builds**, usar:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\release_multiplataforma.ps1 -Version 1.6.1
```

Este flujo hace:

1. Actualiza `APP_VERSION` en `config.py`.
2. Crea commit solo de `config.py` y hace push de la rama actual.
3. Ejecuta build local (`build.py`).
4. Ejecuta build multiplataforma (`build_multiplataforma.ps1`) con la misma version.

Wrapper `.bat` equivalente:

```bat
release_multiplataforma.bat 1.6.1
```

Resultado:
- `dist_out/win-1.2.0/`
- `dist_out/linux-1.2.0/`
- `dist_out/mac-1.2.0/`

El proceso hace lo siguiente:
1. Verifica que existe `main.py` y `SistemaRampazzo.spec`
2. Activa el entorno virtual (`.venv` o `venv`)
3. Verifica/instala PyInstaller si no esta presente
4. Limpia builds anteriores (`build/` y `dist/`)
5. Compila el ejecutable con PyInstaller usando el `.spec`
6. Copia `config.ini.example` al directorio de distribucion
7. Genera `dist\SistemaRampazzo.zip` listo para distribuir

### Build manual (paso a paso)

Si se prefiere hacerlo manualmente:

```powershell
.venv\Scripts\Activate.ps1
pip install pyinstaller
pyinstaller SistemaRampazzo.spec --noconfirm
Copy-Item config.ini.example dist\SistemaRampazzo\config.ini.example -Force
Compress-Archive -Path "dist\SistemaRampazzo\*" -DestinationPath "dist\SistemaRampazzo.zip" -Force
```

El archivo `dist\SistemaRampazzo.zip` esta listo para distribuir.

---

## 13. Seguridad por IP/WiFi (diseno futuro)

### Estado actual

- Hoy la app no aplica validacion de IP o WiFi al iniciar sesion.
- La seccion `[security]` en `config.ini` solo contempla `encryption_key`.

### Configuracion objetivo (cuando se implemente)

```ini
[security]
encryption_key =

restrict_by_ip = true
allowed_ips = 192.168.1.10,192.168.1.11
allowed_networks = 192.168.1.0/24

restrict_by_wifi = true
allowed_wifi_ssids = OficinaRampazzo,OficinaBack

single_session_per_machine = true
```

### Fases recomendadas de implementacion

1. **Fase 1 (estable):** validacion por IP/subred (`allowed_ips`, `allowed_networks`).
2. **Fase 2 (Windows):** validacion de WiFi por SSID/BSSID.
3. **Fase 3 (hardening):** auditoria de bloqueos + UI de administracion en Configuracion.

### Ubicacion tecnica sugerida

- `config.py`: parseo de claves de seguridad.
- `core/security.py` (nuevo): funciones de validacion de IP/red/WiFi.
- `views/login_view.py` o `core/auth.py`: gate de validacion previo a login.
- `core/audit.py`: registrar intentos bloqueados por politica.
- `main.py`: validacion de instancia unica por maquina (`single_session_per_machine`).

### Controles temporales (antes de implementar en app)

- Restringir IPs permitidas en MongoDB Atlas (`Network Access`).
- Reglas de Firewall del SO por perfil de red.
- Uso obligatorio de VPN corporativa y whitelist del rango VPN.

---

## 14. Notificaciones en UI (estilos y archivos clave)

### Patron de estilos

- **`NOTIF_STYLES`** (en `notificacion_controller.py`): diccionario por tipo con color de fondo, borde, icono y etiqueta. Los widgets de lista (`notification_bell`, `login_task_alerts_popup`) aplican estilos **inline** en cada fila a partir de estos datos.
- **`theme.qss`**: define marcos generales (popup de login, lista, boton de historial, botones de descarte, badge en barra superior). El selector generico `#notif_item` **no** debe pisar los colores por tipo; por eso el detalle visual del contenido del item sale de Python.

### Flujo resumido

1. Tras login exitoso, `MainWindow` puede invocar `get_login_popup_notifications` y mostrar `LoginTaskAlertsPopup`.
2. La campana consulta activas + cuenta badge segun tipo (`BADGE_HIDE_ON_VIEW_TYPES`, `BADGE_PERSIST_WHEN_READ_TYPES`, etc.).
3. El historial usa `get_recent_for_user` (incluye resueltas / descartadas segun logica del controlador).
4. `dismiss_notification` / `dismiss_by_type_and_ref` marcan notificaciones como descartadas sin confundir con `resuelta_por_estado` de tareas.

Para detalle de API y tests, ver `tests/unit/test_notificacion_controller.py`.