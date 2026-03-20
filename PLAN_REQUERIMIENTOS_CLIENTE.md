# Plan de Implementación - Requerimientos Primera Reunión Cliente

**Fecha:** 27/02/2026  
**Origen:** Puntos acordados en reunión con el cliente

---

## Resumen de Requerimientos

| # | Requerimiento | Prioridad | Complejidad |
|---|---------------|-----------|-------------|
| 1 | Llamados de atención a responsables de tareas y cambio de estados | Alta | Media |
| 2 | Alertas con tiempo fijado para vencimientos | Alta | Baja |
| 3 | Popups para alertas de tareas y recordatorios con vencimientos | Alta | Media |
| 4 | Abogado solo ve lo asignado | Media | Baja |
| 5 | Secretaria ve todas las carpetas y clientes | Media | Media |
| 6 | Rol intermedio entre administrador y super (solo lectura de movimientos) | Media | Media |
| 7 | Verificación de mensaje/tarea leído (log para admin) | Media | Alta |
| 8 | Recordatorios por vencimiento en popups y alertas | Alta | Media |
| 9 | Sección de seguridad: acceso por IP/WiFi específica | Baja | Alta |
| 10 | Una sola sesión activa por PC | Alta | Media |

---

## 1. Llamados de atención a responsables de tareas y cambio de estados

**Descripción:** Notificar al responsable cuando se asigna una tarea o cuando cambia el estado de una tarea que le concierne.

**Estado actual:** Existe `NotificacionController.create_for_tarea_asignada()` que se llama al crear una tarea nueva (ver `tarea_form.py`).

**Tareas:**
- [ ] Extender el flujo para crear notificación cuando se **actualiza** una tarea (cambio de estado) y el responsable es distinto del usuario que editó.
- [ ] Crear `create_for_tarea_estado_cambiado()` en `NotificacionController`.
- [ ] En `TareaController.update()`, después de persistir, detectar si cambió `estado` y emitir notificación al `responsable_username`.
- [ ] Asegurar que el responsable reciba el "llamado de atención" visible en la campanita de notificaciones.

**Archivos a modificar:**
- `controllers/tarea_controller.py` o hook en `base_controller` para tareas
- `controllers/notificacion_controller.py`
- `views/tareas/tarea_form.py` (al guardar edición)

---

## 2. Alertas con tiempo fijado para vencimientos

**Descripción:** Poder configurar a qué hora(s) del día se disparan las alertas de vencimientos (ej: a las 8:00 y 14:00).

**Estado actual:** `core/scheduler.py` ejecuta `check_tareas_vencidas()` cada 30 minutos y `check_turnos_proximos()` cada 60 minutos.

**Tareas:**
- [ ] Agregar opciones en `config.ini` (sección `[alertas]`):
  - `horas_alertas = 8,12,14,18` (lista de horas en que se disparan alertas)
- [ ] Modificar el scheduler para usar `cron` en lugar de `interval` para las alertas de tareas/turnos.
- [ ] Crear vista de configuración en **Configuración → General** para que el admin pueda ajustar las horas sin editar el `.ini` (opcional en fase 2).

**Archivos a modificar:**
- `config.py` – leer `horas_alertas`
- `config.ini.example` – documentar sección `[alertas]`
- `core/scheduler.py` – cambiar jobs a cron con horas configurables

---

## 3. Popups para alertas de tareas y recordatorios con vencimientos

**Descripción:** Mostrar popups (ventanas emergentes) con las alertas de tareas vencidas y recordatorios, incluyendo la fecha de vencimiento.

**Estado actual:** Las alertas aparecen en el dashboard (columna derecha) y en la campanita de notificaciones. No hay popup modal automático al iniciar o al detectar nuevas alertas.

**Tareas:**
- [ ] Crear componente `AlertaVencimientoPopup` (QDialog) que muestre:
  - Lista de tareas vencidas con descripción, carpeta, responsable, fecha vencimiento.
  - Lista de turnos próximos (recordatorios) con fecha y hora.
  - Botón "Ir a tarea" / "Ir a turno" para navegar.
- [ ] Integrar con el scheduler: al detectar nuevas alertas (o al iniciar sesión), mostrar el popup si hay alertas pendientes y el usuario no lo cerró recientemente.
- [ ] Agregar preferencia "Mostrar popup al iniciar" (config o por usuario).
- [ ] Asegurar que las alertas del scheduler lleguen a las notificaciones internas (`notificaciones`) para que aparezcan en la campanita y en el popup.

**Archivos a crear/modificar:**
- `views/widgets/alerta_vencimiento_popup.py` (nuevo)
- `views/dashboard_view.py` o `main_window.py` – disparar popup al cargar
- `core/scheduler.py` – insertar notificaciones en `notificaciones` cuando detecte vencidas (además del listado interno)

---

## 4. El abogado solo puede ver lo asignado

**Descripción:** El rol Abogado debe ver únicamente las carpetas/tareas/documentos asignados a él.

**Estado actual:** `core/permissions.py` define `ROLES_GLOBALES = {"administrador", "superusuario"}`. Los roles `secretaria`, `agente` y `abogado` ya usan `scope_where()` y ven solo registros donde `responsable_username = ?` (o responsable_secundario en expedientes).

**Tareas:**
- [ ] Verificar que el Abogado efectivamente use `scope_where` en todos los controladores que aplican filtro por rol (expedientes, tareas, turnos, etc.).
- [ ] Revisar `ExpedienteController.get_scoped()`, `TareaController.get_scoped()`, etc. para asegurar que no haya fugas.
- [ ] Documentar en README que el Abogado tiene visibilidad restringida por asignación.

**Archivos a revisar:**
- `core/permissions.py` – mantener abogado fuera de `ROLES_GLOBALES`
- `controllers/*` – verificar uso consistente de `get_scoped` para abogado

---

## 5. La secretaria puede ver todas las carpetas y todos los clientes

**Descripción:** La Secretaria debe tener visibilidad global sobre clientes y expedientes (carpetas), a diferencia del Abogado.

**Estado actual:** Secretaria, Agente y Abogado comparten la misma lógica: scope restringido por `responsable_username`. No hay distinción.

**Tareas:**
- [ ] Introducir lógica de visibilidad por rol y módulo:
  - `secretaria`: global para `clientes` y `expedientes`, scope para `tareas`, `turnos`, `comunicaciones`.
  - `abogado`: scope para todo.
  - `agente`: scope para todo (mantener comportamiento actual o redefinir con el cliente).
- [ ] Crear función `scope_where_por_modulo(rol, username, tabla)` que devuelva condición vacía para secretaria en clientes/expedientes.
- [ ] Actualizar `ClienteController.get_scoped()` y `ExpedienteController.get_scoped()` para usar esta lógica.
- [ ] Asegurar que tareas y turnos sigan filtrados por responsable para secretaria (o confirmar con cliente si secretaria ve todo también).

**Archivos a modificar:**
- `core/permissions.py` – nuevas constantes y función `scope_where_por_modulo`
- `controllers/cliente_controller.py`
- `controllers/expediente_controller.py`

---

## 6. Rol intermedio entre administrador y super (solo lectura de movimientos)

**Descripción:** Nuevo rol que ve los movimientos (económicos) pero no puede modificarlos. Puede ver todo lo demás que un admin pero con restricciones en administración.

**Estado actual:** Roles: `secretaria`, `agente`, `abogado`, `administrador`, `superusuario`. No existe rol intermedio.

**Tareas:**
- [ ] Definir nuevo rol, ej: `supervisor` o `direccion_lectura`:
  - Ver: clientes, expedientes, tareas, turnos, comunicaciones, documentos, **movimientos** (solo lectura), reportes, auditoría.
  - No puede: crear/editar/eliminar movimientos, gestionar usuarios, configurar sistema.
- [ ] Agregar rol a `ROLES` y `ROL_ALIAS` en `permissions.py`.
- [ ] Permisos: `movimientos.read` (sin `movimientos.create`, `movimientos.update`, `movimientos.delete`).
- [ ] En vistas de movimientos (`movimiento_list`, `movimiento_form`), ocultar botones Alta/Editar/Eliminar para este rol.
- [ ] Migración de BD: agregar usuario de ejemplo o instrucciones para crear el rol en UI de usuarios.

**Archivos a modificar:**
- `core/permissions.py`
- `views/administracion/movimiento_list.py`
- `views/config/usuarios_view.py` – permitir asignar nuevo rol
- `controllers/auth_controller.py` – validar rol en seed/default users si aplica

---

## 7. Verificación de mensaje/tarea leído (log para admin)

**Descripción:** Registrar cuando un usuario "lee" una tarea (o mensaje) y permitir al administrador consultar un log de lecturas.

**Estado actual:** No existe registro de lectura. Las notificaciones tienen `leida` pero no hay log de auditoría de "quién leyó qué y cuándo".

**Tareas:**
- [ ] Crear tabla `tarea_lecturas` (o `lecturas_log`):
  - `_id`, `id_tarea`, `username`, `leido_at`, `ip_origen` (opcional)
- [ ] Al abrir el detalle de una tarea (o al hacer clic en notificación de tarea), registrar lectura si el usuario es el responsable o tiene permiso.
- [ ] Crear vista "Log de lecturas" en módulo Auditoría (o nueva sección) accesible solo para admin/super.
- [ ] Mostrar por tarea: lista de lecturas con usuario y fecha.
- [ ] Considerar extensión a comunicaciones si el cliente lo requiere.

**Archivos a crear/modificar:**
- `core/db_local.py` – nueva tabla `tarea_lecturas`
- `core/db_remote.py` / `sync_engine.py` – incluir en sincronización si es multi-sede
- `controllers/audit_controller.py` o nuevo `LecturaController`
- `views/tareas/tarea_form.py` o `tarea_list` – llamar a registro de lectura al abrir
- `views/auditoria/` – nueva pestaña o vista "Log de lecturas"

---

## 8. Recordatorios por vencimiento en popups y alertas (prioritario)

**Descripción:** Enfatizado por el cliente: los recordatorios de vencimiento deben mostrarse en popups y alertas de forma destacada.

**Tareas:**
- [ ] Unificar con el punto 3: los recordatorios (tareas próximas a vencer, no solo vencidas) deben incluirse.
- [ ] Extender `TareaController`: método `get_proximas_a_vencer(dias=3)` para tareas que vencen en los próximos N días.
- [ ] El scheduler debe generar notificaciones para:
  - Tareas vencidas (ya existe)
  - Tareas próximas a vencer (nuevo)
  - Turnos próximos (ya existe)
- [ ] Todas deben llegar a popup y campanita.
- [ ] Permitir configurar "días de antelación" para recordatorios (ej: 1, 3, 7 días antes).

**Archivos a modificar:**
- `controllers/tarea_controller.py` – `get_proximas_a_vencer()`
- `core/scheduler.py` – job para tareas próximas a vencer
- `config.py` – `ALERTAS_DIAS_ANTICIPACION`
- Popup de alertas (punto 3)

---

## 9. Sección de seguridad: acceso solo desde IP o WiFi específica

**Descripción:** Posibilidad de habilitar que el programa se abra desde internet pero únicamente desde direcciones IP o redes WiFi autorizadas.

**Estado actual:** La aplicación es desktop (PySide6). No hay capa de red expuesta directamente; la conexión a MongoDB Atlas es saliente. El "acceso desde internet" probablemente se refiere a:
- Opción A: Que la app acepte conexiones entrantes (servidor) – poco común en desktop.
- Opción B: Restringir desde qué IP/máquina se puede usar la app (verificación al iniciar).
- Opción C: Si en el futuro se expone una API/web, filtrar por IP.

**Interpretación recomendada:** Verificación al iniciar sesión: si `config.ini` tiene `[security] allowed_ips` o `allowed_networks`, la app valida que la IP actual (o red WiFi) esté en la lista. Si no, muestra error y no permite continuar.

**Tareas:**
- [ ] Agregar en `config.ini`:
  - `[security]`
  - `restrict_by_ip = true`
  - `allowed_ips = 192.168.1.100, 200.50.60.70`
  - `allowed_networks = 192.168.1.0/24` (opcional)
- [ ] Al iniciar la app (o al hacer login), obtener IP actual y verificar contra la lista.
- [ ] Para WiFi: en desktop no hay API estándar para "nombre de red WiFi" de forma portable; en Windows se podría usar `netsh wlan show interfaces`. Limitar a IP/subred es más robusto.
- [ ] Crear pestaña "Seguridad" en Configuración (solo super) con campos para IPs permitidas.

**Archivos a crear/modificar:**
- `config.py` – leer `allowed_ips`, `restrict_by_ip`
- `core/security.py` (nuevo) – validación de IP
- `main.py` o `login_view` – llamar validación antes de permitir login
- `views/config/config_tabs_view.py` – nueva pestaña Seguridad

---

## 10. Una sola sesión activa por PC

**Descripción:** Que en una misma PC solo pueda haber una sesión abierta; no se permiten dos instancias simultáneas del sistema con el mismo usuario (o en general, una sola instancia por máquina).

**Estado actual:** `core/session_guard.py` verifica estado del usuario cada 30 s (activo, pausado, force_logout). No hay bloqueo de múltiples instancias por máquina.

**Tareas:**
- [ ] Implementar **singleton por máquina**: al iniciar la app, crear un archivo lock (ej: `data/session.lock`) con `machine_id` + `pid` + timestamp.
  - Si el archivo existe y el proceso asociado sigue vivo, mostrar "Ya hay una sesión abierta en esta PC" y no permitir abrir.
- [ ] Alternativa: tabla en BD `sesiones_activas` con `machine_id`, `username`, `inicio_sesion_at`. Al login, verificar si ya existe sesión para esa máquina; si sí, bloquear o preguntar "Cerrar la otra sesión".
- [ ] Considerar: ¿una sesión por PC total, o una sesión por usuario por PC? El texto sugiere "en la PC solo haya una sesión" → una instancia por máquina.
- [ ] Usar `core/lock_manager.py` si existe lógica de lock; si no, implementar en `core/session_guard.py` o nuevo `core/single_instance.py`.

**Archivos a modificar:**
- `core/session_guard.py` o nuevo `core/single_instance.py`
- `main.py` – verificar singleton antes de mostrar ventana principal
- Posible uso de `lock_manager.py` existente

---

## Orden de implementación sugerido

1. **Fase 1 – Alertas y recordatorios (críticos)**
   - Puntos 2, 3, 8: tiempo fijado, popups, recordatorios por vencimiento.

2. **Fase 2 – Roles y visibilidad**
   - Puntos 4, 5, 6: abogado restringido, secretaria global, rol supervisor.

3. **Fase 3 – Notificaciones y lecturas**
   - Puntos 1, 7: llamados de atención por cambio de estado, log de lecturas.

4. **Fase 4 – Seguridad**
   - Puntos 9, 10: restricción por IP, una sesión por PC.

---

## Notas técnicas

- **Sincronización:** Cualquier nueva tabla (`tarea_lecturas`, etc.) debe evaluarse para inclusión en `sync_engine` si hay múltiples sedes.
- **Tests:** Cada cambio debe incluir tests unitarios/integración según corresponda.
- **Migración de datos:** Si se agregan columnas/tablas, preparar migración para BD existente (o dependencia de `init_db` con `CREATE TABLE IF NOT EXISTS`).

---

*Documento creado para guiar la implementación. Actualizar según avances y feedback del cliente.*
