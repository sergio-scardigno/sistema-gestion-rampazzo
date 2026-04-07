# Sistema Rampazzo

Sistema de gestion integral para estudio juridico previsional. Aplicacion de escritorio construida con **Python** y **PySide6** (Qt), con base de datos local **SQLite** y sincronizacion bidireccional con **MongoDB Atlas**.

Diseñado para gestionar el ciclo completo de un estudio: desde la consulta inicial del cliente, pasando por la apertura de carpetas, seguimiento de tareas y turnos ANSES, hasta el cobro de honorarios y la generacion de reportes.

**Versión de aplicación:** 1.7.0

---

## Notas de versión — 1.7.0 (abril 2026)

Esta versión amplía el modelo de **carpetas** con un flujo por **etapas procesales**, **responsables por etapa**, **plazos y recordatorios** con notificaciones programadas, un **dashboard** más operativo (KPIs de plazos y tablas por etapa), **sincronización** de las nuevas tablas con MongoDB y mejoras transversales en formularios, permisos y bloqueos de edición.

**Alcance del listado:** corresponde al conjunto de cambios presentes en el árbol de trabajo de Git en la fecha de referencia **7 de abril de 2026** (archivos modificados y nuevos respecto del último commit de la rama actual). No había commits con esa fecha al documentar; el listado describe el estado del repositorio listo para integrar como 1.7.0.

### 1. Flujo por etapas de carpeta y trazabilidad

El `ExpedienteController` define un catálogo ordenado de **etapas** (`ETAPAS`: códigos, títulos, instrucciones breves). Cada carpeta lleva `etapa_codigo` (valor por defecto al crear). Al cambiar de etapa o de responsables se actualiza el **historial de estados** y se pueden generar **notificaciones** al responsable principal y al encargado de la etapa. Se añadieron consultas de negocio: carpetas pendientes por etapa para el usuario, métricas relacionadas, búsqueda ampliada y cierre formal conservando la lógica existente.

### 2. Línea de tiempo visual de etapas

Nuevo widget `ExpedienteEtapasTimeline`: franja horizontal con el orden de etapas, indicación de etapa **anterior** y **actual** y trazos/flechas entre nodos para lectura rápida del avance procesal en la ficha de carpeta.

### 3. Encargados secundarios por etapa

Nueva tabla `expediente_etapa_responsables` y `ExpedienteEtapaResponsableController`: permite asignar un **encargado distinto por etapa** (además del responsable principal de la carpeta). La **visibilidad** de listados (`get_scoped`, variantes con cliente) considera al encargado **efectivo** de la etapa actual. Las notificaciones de tipo `expediente_etapa_encargado` avisan al usuario asignado cuando corresponde.

### 4. Recordatorios de plazos por carpeta

Nueva tabla `expediente_recordatorios` y `ExpedienteRecordatorioController`: fecha de disparo, título, mensaje, usuario a notificar, vínculo opcional a `etapa_codigo` y marca **plazo crítico**. El **scheduler** ejecuta `check_recordatorios_expedientes` **una vez al día (08:00)**, crea notificaciones internas (`recordatorio_expediente`) y marca el registro como disparado para no repetir; los registros sincronizan como el resto del modelo.

### 5. Dashboard operativo

El dashboard incorpora **KPIs de plazos** (críticos vencidos, próximos siete días, vencimientos del día), tablas de detalle y el bloque **Asignado a mí por etapa** (combo de etapa + tabla con carpeta, cliente, etapa e indicación de qué hacer). Se integra el refresco con recordatorios de expedientes donde aplica.

### 6. Notificaciones, campana y alertas al iniciar sesión

`NotificacionController` amplía tipos y flujos: recordatorios de carpeta, encargado de etapa, y convivencia con actualización de mensajes de tareas. Los tipos relevantes aparecen en **popup de alertas** al login y en la **campana** (`notification_bell`, `login_task_alerts_popup`).

### 7. Rol «analisis» en RBAC

En `core/permissions.py` se incorpora el rol **analisis** (misma matriz operativa que **abogado** en documentos/carpetas/tareas/turnos/comunicaciones), con alias y descripción para la UI.

### 8. Auto-archivado de carpetas cerradas

`ExpedienteController.auto_archivar_cerrados` y job en **scheduler** (diario a las **03:00**) para pasar a estado archivado las carpetas que llevan **cerradas** más de un umbral de días, reduciendo ruido en vistas activas.

### 9. Referencias múltiples de expediente y copia rápida de claves

- `ExpedientesReferenciaWidget`: gestión de **referencias** por tipo (ANSES, IPS, SRT, Judicial) persistidas en datos de rama, con lista editable.
- `ClickCopyLineEdit`: **un clic** copia al portapapeles el contenido de campos sensibles (p. ej. claves), con estilo de lectura clara.

### 10. Base de datos local y migraciones

`core/db_local.py`: creación de tablas e **índices** para recordatorios y encargados por etapa; migraciones incrementales (p. ej. columnas nuevas en `expediente_recordatorios`) para bases ya existentes.

### 11. Sincronización SQLite ↔ MongoDB Atlas

`sync_engine` incluye las colecciones `expediente_recordatorios` y `expediente_etapa_responsables` en el flujo de tablas sincronizadas; `db_remote` ajusta índices y coherencia con el remoto.

### 12. Bloqueos de edición en MongoDB

La configuración de caducidad de **locks** pasa a **segundos** (`lock_expiry_seconds` en `config.ini.example` y `LOCK_EXPIRY_SECONDS` en `config.py`), alineada con `lock_manager` (bloqueo pesimista al editar).

### 13. Formularios y vistas (UI)

Cambios extensos en **carpetas** (`expediente_form`, `expediente_list`), **clientes**, **dashboard**, **tareas**, **turnos**, **documentos**, **movimientos**, **ventana principal** y **tabla filtrable** (`filterable_table`), para integrar etapas, timeline, referencias, recordatorios y flujos ya descritos.

### 14. Otros controladores y utilidades

Ajustes en `documento_controller`, `expediente_estado_controller`, `reporte_controller`, `turno_controller`; corrección menor en `utils/export.py`.

### 15. Script de release multiplataforma

Ajustes en `release_multiplataforma.ps1` (lectura y actualización de `APP_VERSION` en `config.py` para empaquetado).

### 16. Pruebas automatizadas

Nuevos tests de integración para **recordatorios de expediente** y **encargados por etapa**; ampliaciones en expediente, historial de estados, sync, turnos, movimientos, permisos y BD local. La suite total pasa a **489 tests** (ver sección Testing).

---

## Stack tecnologico

| Tecnologia | Version minima | Rol en el sistema |
|---|---|---|
| **Python** | 3.12+ | Lenguaje principal |
| **PySide6** | 6.6.0 | Interfaz grafica de escritorio (Qt for Python) |
| **SQLite** | incluido en Python | Base de datos local (cache offline) |
| **MongoDB Atlas** | - | Base de datos remota (fuente de verdad central) |
| **pymongo** | 4.6.0 | Driver de conexion a MongoDB |
| **dnspython** | 2.4.0 | Resolucion DNS para conexiones SRV de Atlas |
| **bcrypt** | 4.1.0 | Hashing seguro de contraseñas |
| **APScheduler** | 3.10.0 | Programacion de tareas automaticas (sync, backups, alertas) |
| **reportlab** | 4.1.0 | Generacion de reportes en PDF |
| **matplotlib** | 3.8.0 | Graficos en reportes y auditoria |
| **pandas** | 2.1.0 | Manipulacion de datos para exportacion Excel |
| **openpyxl** | 3.1.0 | Lectura/escritura de archivos Excel |
| **python-Levenshtein** | 0.25.0 | Deteccion de duplicados por similitud de texto |
| **cryptography** | 42.0.0 | Encriptacion de campos sensibles |
| **pytest** | 8.0.0 | Framework de testing |
| **pytest-cov** | 5.0.0 | Reporte de cobertura de codigo |
| **pytest-qt** | 4.4.0 | Testing de interfaces PySide6/Qt |

---

## Arquitectura del sistema

```mermaid
flowchart TD
    subgraph ui [Interfaz - PySide6]
        LoginView
        MainWindow
        Views["Vistas por modulo"]
    end

    subgraph ctrl [Controladores]
        BaseController
        AuthController
        AuditController
        SpecificControllers["ClienteController, ExpedienteController, TareaController, TurnoController, ConsultaController, ComunicacionController, DocumentoController, MovimientoController, ReporteController"]
    end

    subgraph core [Nucleo]
        Auth["auth.py - Sesion y login"]
        Audit["audit.py - Log inmutable"]
        Permissions["permissions.py - RBAC"]
        SyncEngine["sync_engine.py - Sincronizacion"]
        Scheduler["scheduler.py - Jobs automaticos"]
        ConnMonitor["connection_monitor.py"]
    end

    subgraph storage [Almacenamiento]
        SQLite["SQLite local - data/local.db"]
        MongoDB["MongoDB Atlas - Nube"]
    end

    ui --> ctrl
    ctrl --> core
    core --> storage
    SyncEngine -->|"push pending"| MongoDB
    SyncEngine -->|"pull remote"| SQLite
    ConnMonitor -->|"verifica conexion"| MongoDB
```

**Flujo de datos:**
1. La UI llama a los controladores para operaciones CRUD.
2. Los controladores escriben en SQLite local y marcan el registro como `pending`.
3. El `SyncEngine` (cada 5 minutos) sube los pendientes a MongoDB Atlas y baja los cambios remotos.
4. Si no hay conexion, la app funciona 100% offline contra SQLite. Al reconectar, se sincronizan los cambios acumulados.
5. Los borrados se gestionan como **tombstones** (`is_deleted`, `deleted_at`, `deleted_by`) para mantener consistencia entre nodos.
6. Si hay edicion concurrente, el sistema registra conflictos en `sync_conflicts` para auditoria y resolucion.

---

## Estructura de carpetas

```
sistema-gestion-rampazzo/
├── main.py                    # Punto de entrada de la aplicacion
├── config.py                  # Configuracion central (lee config.ini)
├── config.ini                 # Configuracion local (no versionado)
├── config.ini.example         # Plantilla de configuracion
├── requirements.txt           # Dependencias Python
├── pytest.ini                 # Configuracion de pytest
├── .coveragerc                # Configuracion de cobertura
├── .gitignore
│
├── core/                      # Nucleo del sistema
│   ├── auth.py                #   Login, sesion, hash de passwords
│   ├── audit.py               #   Log de auditoria inmutable (triggers SQLite)
│   ├── permissions.py         #   Roles, permisos y visibilidad (RBAC)
│   ├── db_local.py            #   SQLite: esquema, CRUD helpers, migraciones
│   ├── db_remote.py           #   Conexion a MongoDB Atlas
│   ├── sync_engine.py         #   Sincronizacion bidireccional SQLite <-> Atlas
│   ├── scheduler.py           #   APScheduler: sync, backups, alertas
│   ├── connection_monitor.py  #   Monitoreo de conectividad
│   ├── lock_manager.py        #   Bloqueo de edicion concurrente
│   └── session_guard.py       #   Control de sesion activa
│
├── controllers/               # Logica de negocio y CRUD
│   ├── base_controller.py     #   Controlador CRUD generico
│   ├── auth_controller.py     #   Gestion de usuarios y autenticacion
│   ├── cliente_controller.py  #   CRUD de clientes
│   ├── consulta_controller.py #   CRUD de consultas (legado, no visible en UI)
│   ├── expediente_controller.py # CRUD de carpetas (etapas, metricas, recordatorios)
│   ├── expediente_recordatorio_controller.py # Plazos y recordatorios por carpeta
│   ├── expediente_etapa_responsable_controller.py # Encargado secundario por etapa
│   ├── tarea_controller.py    #   CRUD de tareas
│   ├── turno_controller.py    #   CRUD de turnos ANSES
│   ├── comunicacion_controller.py # CRUD de comunicaciones
│   ├── documento_controller.py #  Gestion documental con versionado
│   ├── movimiento_controller.py # Movimientos economicos
│   ├── reporte_controller.py  #   KPIs y consultas agregadas
│   └── audit_controller.py    #   Consultas al log de auditoria
│
├── models/
│   └── base_model.py          # Helpers: new_id(), now_iso(), base_fields()
│
├── views/                     # Interfaz grafica PySide6
│   ├── login_view.py          #   Pantalla de login
│   ├── main_window.py         #   Ventana principal con sidebar dinamico
│   ├── dashboard_view.py      #   Dashboard con KPIs y alertas
│   ├── clientes/              #   Listado y formulario de clientes
│   ├── consultas/             #   CRM de consultas (legado, no visible en UI)
│   ├── expedientes/           #   Gestion de carpetas (con pestañas)
│   ├── tareas/                #   Seguimiento de tareas
│   ├── turnos/                #   Turnos ANSES
│   ├── comunicaciones/        #   Registro de comunicaciones
│   ├── documentos/            #   Gestion documental
│   ├── administracion/        #   Movimientos economicos
│   ├── reportes/              #   Reportes con graficos y exportacion
│   ├── auditoria/             #   Log de auditoria y estadisticas
│   ├── config/                #   Gestion de empleados/usuarios
│   ├── migration/             #   Wizard de migracion desde Excel
│   └── widgets/               #   Componentes reutilizables
│       ├── filterable_table.py #    Tabla con busqueda y paginacion
│       ├── expediente_etapas_timeline.py # Linea de tiempo de etapas de carpeta
│       ├── expedientes_referencia_widget.py # Referencias ANSES, IPS, SRT, Judicial
│       ├── click_copy_line_edit.py # Copiar clave al clic
│       └── sync_indicator.py  #    Indicador de estado de conexion
│
├── utils/
│   ├── validators.py          # Validaciones: DNI, CUIL, email, telefono
│   ├── formatters.py          # Formato de fechas, moneda, CUIL
│   ├── export.py              # Exportacion a PDF y Excel
│   ├── system_bundle.py       # Backup/import completo (SQLite + Mongo) en ZIP
│   └── migration/             # Utilidades de migracion desde Excel
│       ├── excel_reader.py
│       ├── normalizer.py
│       ├── deduplicator.py
│       └── importer.py
│
├── resources/
│   ├── styles/theme.qss       # Hoja de estilos Qt (tema oscuro/dorado)
│   └── fonts/                 # Fuentes TTF (Lato)
│
├── data/                      # Datos locales (no versionado)
│   ├── local.db               #   Base de datos SQLite
│   ├── backups/               #   Backups automaticos
│   └── documentos/            #   Archivos de documentos adjuntos
│
├── tests/                     # Suite de testing (489 tests)
│   ├── conftest.py            #   Fixtures globales
│   ├── unit/                  #   156 tests unitarios
│   ├── integration/           #   324 tests de integracion
│   └── ui/                    #   9 smoke tests de UI
│
└── .github/
    └── workflows/tests.yml    # Pipeline CI con 4 etapas
```

---

## Modulos funcionales

### Dashboard

Pantalla principal que muestra al usuario un resumen operativo en tiempo real:

- **Busqueda rapida por N° de carpeta:** Campo de busqueda prominente para localizar un cliente y sus carpetas ingresando el numero de carpeta fisica. Muestra un panel con datos del cliente y accesos directos a cada carpeta.
- **KPIs:** Carpetas activas/cerradas, tareas pendientes/vencidas, total de clientes, ingresos cobrados, pendientes de cobro; **KPIs de plazos** (criticos vencidos, proximos 7 dias, vencimientos de hoy) y tablas de detalle asociadas.
- **Asignado a mi por etapa:** Filtro por etapa procesal y tabla de carpetas con indicacion breve de la accion esperada.
- **Turnos de hoy:** Tabla con los turnos programados para la fecha actual.
- **Alertas:** Carpetas sin tarea activa, turnos proximos sin documentacion, turnos sin resultado cargado.

### Clientes

Alta, baja y modificacion de clientes del estudio. Es el punto de entrada de todo nuevo caso:

- **N° de carpeta fisica** (obligatorio, numerico, unico): Cada cliente tiene asignado un numero de carpeta donde se archivan los documentos fisicos.
- **Procedencia del contacto:** De donde llego el cliente (Instagram, TikTok, Facebook, Referido, Presencial, Web, Telefono, Otro).
- Datos personales: nombre completo, DNI, CUIL, fecha de nacimiento, direccion, telefonos, email.
- Busqueda por nombre, DNI, CUIL, email o N° de carpeta.
- Busqueda directa por CUIL o por N° de carpeta.

### Carpetas

Modulo central del sistema. Cada carpeta representa un tramite o caso legal:

- **Flujo por etapas:** Cada carpeta tiene una **etapa procesal** actual (orden de trabajo del estudio), linea de tiempo en la ficha, posible **encargado por etapa**, **recordatorios de plazos** con notificacion y referencias multiples (ANSES, IPS, SRT, Judicial) segun corresponda.
- **Clasificacion por rama:** Rama + Subtipo (dependiente de la rama) para ordenar el trabajo juridico.
- **Datos principales:** Tipo de tramite, responsable, estado, prioridad, numero de tramite ANSES.
- **Campos dinamicos por rama:** el formulario activa campos especificos segun la rama seleccionada.
- **Modulo Judicial comun:** activable con checkbox para cargar fuero, juzgado, secretaria, numero de expediente, provincia, instancia, monto reclamado y etapa procesal.
- **Regla de claves ANSES/AFIP:** Clave Mi ANSES y Clave Fiscal solo visibles para rama Previsional.
- **Pestañas integradas** (en la vista de edicion):
  - Tareas asociadas a la carpeta
  - Turnos ANSES vinculados
  - Comunicaciones realizadas
  - Documentos adjuntos (con versionado)
  - Movimientos economicos
  - Historial de auditoria de la carpeta
- **Cierre formal** con resultado y fecha.
- **Visibilidad por rol:** Roles restringidos ven las carpetas donde son responsables principales o **encargados de la etapa actual**.

### Tareas

Seguimiento de acciones pendientes dentro de una carpeta:

- Tipos: Turno ANSES, Inicio virtual, Presentacion documental, Seguimiento carpeta, Notificacion, Reclamo, Audiencia, Pericia, Otro.
- Estados: Pendiente, En curso, En espera, Cumplida, Cancelada.
- Deteccion automatica de **tareas vencidas**.
- Filtro por responsable.

### Turnos ANSES

Gestion de turnos en oficinas de ANSES:

- Programacion con fecha, hora, oficina y tipo de tramite.
- Checklist de documentacion preparada.
- Flujo de estados: Pendiente, Confirmado, Asistido, No asistido, Reprogramado, Cancelado.
- **Reprogramacion:** Marca el turno original como reprogramado y crea uno nuevo con los mismos datos base.
- Alertas de turnos sin documentacion y turnos pendientes de resultado.

### Comunicaciones

Registro de todas las comunicaciones con clientes:

- Canales: WhatsApp, Llamada, Mail, Presencial, Videollamada.
- Campos: emisor, receptor, motivo, mensaje, resultado.
- Vinculacion a carpeta.

### Documentos

Gestion documental con categorias y versionado:

- **Categorias:** Identidad, Laboral, Medicos, Judiciales, Administrativos, Resoluciones, Escritos, Notificaciones, Comunicaciones, Otro.
- **Subcategorias** por categoria (ej: Identidad -> DNI, Partida nacimiento, Certificado domicilio, CUIL).
- **Versionado:** Cada documento puede tener multiples versiones con notas de cambio.
- Almacenamiento local de archivos en `data/documentos/`.

### Administracion economica

Control de honorarios y gastos del estudio:

- Tipos de movimiento: Honorario, Gasto.
- Formas de pago: Efectivo, Transferencia, Tarjeta, Cheque, Otro.
- Seguimiento de saldos por cliente.
- Estados: Pendiente, Parcial, Cancelado, Incobrable.

### Reportes

Panel de reportes con graficos interactivos y exportacion:

- **KPIs operativos:** Carpetas activas/cerradas, tareas pendientes/vencidas.
- **KPIs de clientes:** Total de clientes registrados.
- **KPIs economicos:** Ingresos cobrados, pendientes de cobro.
- **Desgloses:** Carpetas por tipo, por responsable. Clientes por procedencia.
- **Tiempos:** Promedio de resolucion por tipo de tramite.
- **Indicadores humanos:** Carga por responsable, tareas vencidas por responsable.
- **Exportacion:** PDF y Excel.

### Auditoria

Log de auditoria inmutable para trazabilidad completa:

- Registro automatico de cada accion (crear, editar, eliminar) con usuario, timestamp, datos anteriores y nuevos.
- **Proteccion por triggers SQLite:** No se permite UPDATE ni DELETE sobre la tabla `audit_log`.
- Filtros por usuario, modulo, accion y rango de fechas.
- Vista de detalle campo a campo de cada cambio.
- Estadisticas: actividad diaria, por usuario, por modulo.
- Registro de intentos de login (exitosos y fallidos).
- **Seguimiento de tareas para administracion (nuevo):**
  - Pestana dedicada para ver en una sola grilla: asignada a, fecha de asignacion, leida/no leida, fecha de lectura, estado actual, fecha de cumplimiento y dias sin leer.
  - Filtros por responsable, estado y rango de fechas.
  - Calcula cumplimiento tomando el cambio de estado cerrado en `audit_log` (Cumplida/Completada/Cancelada).

### Gestion de empleados

Administracion de usuarios del sistema:

- Alta de empleados con usuario, contraseña, nombre, email y rol.
- **Pausar/reactivar** usuarios (con signal de desconexion forzada).
- **Dar de baja** (soft-delete: el historial se conserva).
- Reset de contraseña.
- Proteccion: no se puede eliminar al unico superusuario activo ni a uno mismo.

### Migracion desde Excel / CSV

Wizard de 6 pasos para importar datos historicos:

1. Seleccion del archivo Excel (.xlsx/.xls) o CSV (.csv con separador `;`).
2. Seleccion de hojas (Excel) o tipo de plantilla (CSV).
3. Preview de datos.
4. Normalizacion de campos.
5. Deteccion y resolucion de duplicados (con Levenshtein).
6. Importacion final.

Se incluyen plantillas CSV en `excel/` para importacion por partes.

---

## Roles y permisos

El sistema implementa control de acceso basado en roles (RBAC). Cada rol determina que modulos puede ver y que acciones puede realizar.

Ademas de los perfiles operativos, existen dos perfiles administrativos:

- **Administrador:** acceso administrativo completo, incluyendo gestion economica.
- **Administrador (sin Contable):** perfil administrativo sin acceso a movimientos de dinero ni al modulo/pestana Contable.

| Modulo | Secretaria | Agente | Abogado | Administrador | Administrador (sin Contable) | Superusuario |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Dashboard | Leer | Leer | Leer | Leer | Leer | Leer |
| Clientes | Leer | Completo | Completo | Completo | Completo | Completo |
| Carpetas | Leer | Completo | Completo | Completo | Completo | Completo |
| Tareas | Leer | Completo | Completo | Completo | Completo | Completo |
| Turnos | Leer | Completo | Completo | Completo | Completo | Completo |
| Comunicaciones | Leer | Completo | Completo | Completo | Completo | Completo |
| Documentos | - | Leer | Completo | Completo | Completo | Completo |
| Administracion (movimientos de dinero) | - | - | - | Completo | - | Completo |
| Reportes | - | - | Leer | Completo | Completo | Completo |
| Auditoria | - | - | - | Completo | Completo | Completo |
| Empleados | - | - | - | Completo | Completo | Completo |
| Configuracion | - | - | - | - | - | Completo |
| Migracion | - | - | - | - | - | Completo |

El rol **Analisis** replica la columna **Abogado** de la tabla (mismos permisos por modulo).

**Visibilidad por asignacion:** Los roles Secretaria, Agente, Abogado y Analisis solo ven los registros asignados a ellos (filtro por `responsable_username`, y en carpetas tambien por encargado de etapa cuando corresponda). Los roles Administrador, Administrador (sin Contable) y Superusuario ven todos los registros.

---

## Sincronizacion SQLite - MongoDB Atlas

```mermaid
sequenceDiagram
    participant App as Aplicacion
    participant SQLite as SQLite Local
    participant Sync as SyncEngine
    participant Atlas as MongoDB Atlas

    App->>SQLite: CRUD (insert/update/delete)
    SQLite-->>SQLite: sync_status = pending

    loop Cada 5 minutos
        Sync->>SQLite: find_pending()
        Sync->>Atlas: replace_one(upsert=true)
        Atlas-->>Sync: OK
        Sync->>SQLite: mark_synced()

        Sync->>Atlas: find(updated_at > last_pull)
        Atlas-->>Sync: documentos nuevos/modificados
        Sync->>SQLite: insert/replace (si no hay pending local)
    end

    Note over App,Atlas: Si no hay conexion, la app trabaja 100% offline contra SQLite.
    Note over App,Atlas: Al reconectar, se sincronizan los cambios acumulados.
```

**Tablas sincronizadas:** usuarios, consultas, clientes, expedientes, tareas, turnos, comunicaciones, movimientos, documentos, modelos_escrito, escritos, expediente_estado_historial, notificaciones, expediente_recordatorios, expediente_etapa_responsables, audit_log.

**Resolucion de conflictos:** si el remoto tiene una version superior o hay cambios locales pendientes con choque de version, se registra un evento en `sync_conflicts` con snapshot local/remoto.

**Metricas de sync (`sync_meta`):**
- `sync_last_total_pushed`
- `sync_last_total_pulled`
- `sync_last_total_conflicts`
- `sync_baseline_last_snapshot` (drift local/remoto por tabla)

---

## Backup manual completo (SQLite + Mongo)

El sistema permite exportar/importar un backup hibrido completo con:
- `local/sqlite.db`
- `local/documentos/`
- `remote/mongo_dump/*.jsonl`
- `manifest.json` (version, machine_id, checksum, conteos)

**Desde UI (superusuario):**
- Modulo `Configuracion` -> pestaña `General / Logos`
- Botones: `Exportar backup completo` y `Importar backup completo`

**Desde CLI:**

```bash
# Exportar backup completo
python main.py --export-backup "C:\ruta\backup_bundle.zip"

# Validar importacion (sin aplicar cambios)
python main.py --import-backup "C:\ruta\backup_bundle.zip" --dry-run

# Importar aplicando SQLite + Mongo
python main.py --import-backup "C:\ruta\backup_bundle.zip"

# Importar solo local (sin tocar Mongo)
python main.py --import-backup "C:\ruta\backup_bundle.zip" --no-remote
```

---

## Servidor de documentos en VPS

Para compartir archivos entre multiples PCs, el proyecto incluye un servidor de archivos en `server/` (FastAPI).

### Que resuelve

- Guarda binarios en el VPS en lugar de rutas locales de cada PC.
- Permite `upload`, `download`, `delete` y vista de estadisticas.
- Limita tipo y tamaño de archivo en servidor.
- Incluye backup semanal comprimido con rotacion automatica.

### Ruta de documentacion especifica

- Ver `server/README.md` para instalacion completa, endpoints, backup y recuperacion.

### Endpoints principales

- `GET /health`
- `POST /upload/{file_path}`
- `GET /download/{file_path}`
- `DELETE /delete/{file_path}`
- `GET /stats`
- `GET /backups`

### Backup semanal de archivos del VPS

- Script: `server/backup.sh`
- Destino por defecto: `/opt/rampazzo/backups`
- Formato: `docs_backup_YYYYMMDD_HHMMSS.tar.zst`
- Retencion: `RAMPAZZO_BACKUP_RETENTION_WEEKS` (default 4)
- Cron semanal instalado por `server/setup.sh`: domingo 03:00

---

## Instalacion y configuracion

### Requisitos previos

- **Python 3.12** o superior
- **pip** (gestor de paquetes)
- Conexion a internet para la sincronizacion con MongoDB Atlas (opcional para trabajo offline)

### Pasos de instalacion

1. **Clonar el repositorio:**

```bash
git clone <url-del-repositorio>
cd sistema-gestion-rampazzo
```

2. **Crear un entorno virtual (recomendado):**

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

3. **Instalar dependencias:**

```bash
pip install -r requirements.txt
```

4. **Configurar la conexion a MongoDB Atlas:**

```bash
cp config.ini.example config.ini
```

Editar `config.ini` con las credenciales de tu cluster de MongoDB Atlas:

```ini
[mongo]
uri = mongodb+srv://<usuario>:<password>@<cluster>.mongodb.net
database = <nombre_base_de_datos>
```

> Si no se configura MongoDB, la aplicacion funciona en modo offline con SQLite unicamente.

5. **Ejecutar la aplicacion:**

```bash
python main.py
```

### Primera ejecucion

Al ejecutar por primera vez, el sistema:
- Crea la base de datos SQLite con todas las tablas.
- Aplica triggers de proteccion de auditoria.
- Crea usuarios por defecto (ver seccion siguiente).

---

## Usuarios por defecto

En la primera ejecucion (cuando no existen usuarios en la BD), se crean automaticamente:

| Usuario | Contraseña | Rol | Descripcion |
|---|---|---|---|
| `secretaria` | `sec123` | Secretaria (Recepcion) | Lectura de clientes, carpetas, tareas, turnos y comunicaciones |
| `agente` | `age123` | Agente | Operacion completa de clientes, carpetas y tareas |
| `abogado` | `abo123` | Abogado (Juridico) | Carpetas, documentos, tareas y reportes |
| `admin` | `admin123` | Administrador | Control total operativo, economico y auditoria |
| `super` | `super123` | Superusuario (Direccion) | Acceso total, configuracion y migracion |

> **Importante:** Cambiar las contraseñas por defecto inmediatamente en un entorno de produccion.
>
> El perfil **Administrador (sin Contable)** se puede crear desde **Gestion de empleados** cuando se necesite un administrador sin acceso a movimientos de dinero.
>
> Ejemplo de alta manual para ese perfil (no se crea automaticamente): usuario `admin_visor` con contraseña sugerida `adminvisor123`.

---

## Testing

El proyecto cuenta con una suite de **489 tests automatizados** organizados en 3 niveles con una cobertura de **81%+** sobre los modulos de negocio.

### Ejecutar tests

```bash
# Suite completa (489 tests)
python -m pytest tests/

# Solo tests unitarios (156 tests)
python -m pytest tests/unit/

# Solo tests de integracion (324 tests)
python -m pytest tests/integration/

# Solo smoke tests de UI (9 tests)
python -m pytest tests/ui/

# Con salida detallada
python -m pytest tests/ -v
```

### Reporte de cobertura

```bash
# Cobertura en terminal
python -m pytest tests/ --cov --cov-config=.coveragerc --cov-report=term-missing

# Generar reporte HTML interactivo
python -m pytest tests/ --cov --cov-config=.coveragerc --cov-report=html:htmlcov

# Abrir el reporte (Windows)
start htmlcov\index.html
```

### Estructura de tests

| Directorio | Tests | Que cubre |
|---|---|---|
| `tests/unit/` | 156 | Validadores, modelos, formateadores, permisos, autenticacion (con mocks) |
| `tests/integration/` | 324 | CRUD completo de todos los controladores, BD SQLite, auditoria, sincronizacion, reportes |
| `tests/ui/` | 9 | Renderizado de LoginView y MainWindow, flujo de login, permisos en sidebar |

### CI/CD

El proyecto incluye un pipeline de GitHub Actions (`.github/workflows/tests.yml`) con 4 etapas secuenciales:

1. **Unit tests** -- Tests unitarios rapidos.
2. **Integration tests** -- Tests de integracion con SQLite temporal.
3. **UI smoke tests** -- Tests de interfaz con display virtual (xvfb).
4. **Coverage report** -- Reporte de cobertura con artefacto descargable.

---

## Build y empaquetado

Para generar un ejecutable `.exe` distribuible (sin necesidad de instalar Python):

### Instalar PyInstaller

```bash
pip install pyinstaller
```

### Generar el ejecutable

```bash
pyinstaller --name "Sistema Rampazzo" ^
    --windowed ^
    --onedir ^
    --add-data "resources;resources" ^
    --add-data "config.ini.example;." ^
    --hidden-import "PySide6.QtSvg" ^
    --hidden-import "PySide6.QtSvgWidgets" ^
    main.py
```

> En Linux/macOS reemplazar `;` por `:` en `--add-data` y `^` por `\`.

### Resultado

El ejecutable se genera en `dist/Sistema Rampazzo/`:

```
dist/
└── Sistema Rampazzo/
    ├── Sistema Rampazzo.exe   # Ejecutable principal
    ├── resources/             # Estilos y fuentes
    ├── config.ini.example     # Plantilla de configuracion
    └── ...                    # Dependencias empaquetadas
```

### Antes de distribuir

1. Copiar `config.ini` con las credenciales de produccion junto al ejecutable.
2. Asegurarse de que la carpeta `data/` sea escribible (se crea automaticamente).
3. Los archivos de documentos se almacenan en `data/documentos/`.

---

## Configuracion avanzada

### config.ini

Todas las opciones de configuracion se manejan desde `config.ini`:

```ini
[mongo]
uri = mongodb+srv://<usuario>:<password>@<cluster>.mongodb.net
database = <nombre_bd>

[sync]
interval_seconds = 300       # Intervalo de sincronizacion (5 min por defecto)
lock_expiry_minutes = 15     # Expiracion de bloqueos de edicion

[machine]
id = PC-RECEPCION            # Identificador de maquina (auto-detecta si se omite)

[backup]
retention_days = 30          # Dias de retencion de backups automaticos

[security]
encryption_key =             # Clave para encriptar campos sensibles (32 caracteres)
```

### Variables de entorno

- `COMPUTERNAME` -- Se usa como identificador de maquina si no se configura en `config.ini`.

### Seguridad por red (IP/WiFi) - pendiente de implementacion

Actualmente la aplicacion **no valida todavia** IP o red WiFi en el login.
La seccion `[security]` de `config.ini` solo usa:

```ini
[security]
encryption_key =
```

Si se necesita restringir acceso desde ahora (sin cambios de codigo), usar controles de infraestructura:

- MongoDB Atlas `Network Access` (permitir solo IPs/subredes autorizadas).
- Firewall del sistema operativo para limitar ejecucion/conectividad por perfil de red.
- VPN corporativa + whitelist de rango VPN.

Diseno recomendado para una futura version avanzada:

```ini
[security]
restrict_by_ip = true
allowed_ips = 192.168.1.10,192.168.1.11
allowed_networks = 192.168.1.0/24
restrict_by_wifi = true
allowed_wifi_ssids = OficinaRampazzo,OficinaBack
single_session_per_machine = true
```

Criterio funcional esperado:

1. En login, validar IP/red actual contra `allowed_ips`/`allowed_networks`.
2. En Windows, si `restrict_by_wifi = true`, validar SSID activo.
3. Si falla validacion, bloquear inicio de sesion con mensaje explicito.
4. Mantener log de auditoria de intentos bloqueados por politica de red.

---

## Licencia

Uso privado - Estudio Rampazzo.
