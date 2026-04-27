# Guia de Uso - Sistema Rampazzo

Sistema de Gestion Integral para el Estudio Juridico Previsional Rampazzo.

Esta guia esta dividida en dos partes:

- **Parte 1 - Guia Basica:** Todo lo que necesitas saber para trabajar dia a dia. Pensada para Secretarias, Agentes y Abogados.
- **Parte 2 - Guia Avanzada:** Administracion, configuracion, reportes y procesos especiales. Pensada para Administradores y Superusuarios.

---

## Indice

### Parte 1 - Guia Basica

1. [Primeros pasos](#1-primeros-pasos)
2. [El Dashboard: tu pantalla principal](#2-el-dashboard-tu-pantalla-principal)
3. [El flujo de trabajo paso a paso](#3-el-flujo-de-trabajo-paso-a-paso)
4. [Modulos principales](#4-modulos-principales)
   - [Clientes](#41-clientes)
   - [Carpetas](#42-carpetas)
   - [Tareas](#43-tareas)
   - [Turnos ANSES](#44-turnos-anses)
   - [Comunicaciones](#45-comunicaciones)
   - [Documentos](#46-documentos)
   - [Citas del estudio](#47-citas-del-estudio)
   - [Pendientes citar](#48-pendientes-citar)
5. [Tu dia a dia segun tu rol](#5-tu-dia-a-dia-segun-tu-rol)
6. [Preguntas frecuentes](#6-preguntas-frecuentes)

### Parte 2 - Guia Avanzada

7. [Administracion economica](#7-administracion-economica)
8. [Reportes y exportacion](#8-reportes-y-exportacion)
9. [Auditoria](#9-auditoria)
10. [Gestion de empleados](#10-gestion-de-empleados)
11. [Procesos especiales (detalle completo)](#11-procesos-especiales-detalle-completo)
    - [Cierre de carpeta](#111-cierre-de-carpeta)
    - [Reprogramacion de turno](#112-reprogramacion-de-turno)
    - [Versionado de documentos](#113-versionado-de-documentos)
    - [Pausar o dar de baja un empleado](#114-pausar-o-dar-de-baja-un-empleado)
    - [Notificaciones y alertas (campana, historial, login)](#115-notificaciones-y-alertas-campana-historial-login)
12. [Migracion desde Excel / CSV](#12-migracion-desde-excel--csv)
13. [Exportar / Importar sistema completo](#13-exportar--importar-sistema-completo)
14. [Backups de documentos en VPS](#14-backups-de-documentos-en-vps)
15. [Sincronizacion y trabajo offline](#15-sincronizacion-y-trabajo-offline)
16. [Referencia tecnica](#16-referencia-tecnica)

---

# PARTE 1 - GUIA BASICA

Todo lo que necesitas para trabajar dia a dia con el sistema.

---

## 1. Primeros pasos

### Como entrar al sistema

1. Abrir la aplicacion (ejecutar `python main.py` o el acceso directo del escritorio).
2. Escribir tu **Usuario** y **Contraseña**.
3. Presionar **Iniciar Sesion** (o la tecla Enter).
4. Si los datos son correctos, se abre la ventana principal.

### Popup de alertas al iniciar sesion

Si tenes **notificaciones activas** (tareas, asignaciones de carpeta, encargado de etapa, recordatorios de plazo, turnos, etc.), puede abrirse un **cuadro de dialogo** justo despues del login con la lista de alertas.

**Como funciona:**

- Las alertas mas relacionadas con **carpeta** (asignacion, encargado de etapa, recordatorio de expediente) suelen aparecer **primero**; despues el resto (por ejemplo muchas alertas de tarea), para que no se pierdan los avisos de carpeta.
- En cada fila podes usar **Descartar** para ocultar esa alerta como activa (con confirmacion). **Descartar todas** hace lo mismo para todas las filas y cierra el dialogo.
- **Descartar** no borra el historial del caso: solo marca la notificacion para que no vuelva a molestar como pendiente; si la descartaste vos a mano, el sistema **no la recrea** sola por el mismo motivo.

> **Tip:** Si te equivocas en la contraseña, se limpia el campo automaticamente para que vuelvas a intentar.

### Usuarios iniciales

La primera vez que se ejecuta el sistema, se crean estos usuarios:

| Usuario | Contraseña | Rol |
|---|---|---|
| `secretaria` | `sec123` | Secretaria |
| `agente` | `age123` | Agente |
| `abogado` | `abo123` | Abogado |
| `admin` | `admin123` | Administrador |
| `super` | `super123` | Superusuario |

> **Importante:** Estas contraseñas son provisorias. Un Administrador o Superusuario debe cambiarlas antes de usar el sistema en produccion.

### Como navegar

Al entrar, veras un **sidebar** (barra lateral izquierda) con los modulos a los que tenes acceso. Simplemente hace clic en el nombre del modulo para abrirlo.

Para **cerrar sesion**, usa el boton **Cerrar Sesion** en la parte inferior del sidebar.

### Que rol tengo y que puedo hacer

Cada usuario tiene un rol que define que puede ver y hacer. Esta es la version resumida:

- **Secretaria:** Busca informacion de clientes, carpetas, tareas, turnos y comunicaciones (solo lectura).
- **Agente:** Gestiona todo el ciclo operativo: evalua consultas, crea clientes y carpetas, programa turnos, gestiona tareas.
- **Abogado:** Igual que el agente, pero ademas maneja documentos completos y puede consultar reportes.
- **Administrador:** Ve todo el estudio (todas las carpetas, no solo los suyos), gestiona la economia, auditoria y empleados.
- **Administrador (sin Contable):** Igual que Administrador en operacion y personal, pero **sin** acceso al modulo de movimientos de dinero / pestaña contable.
- **Analisis:** Mismas capacidades operativas que **Abogado** en clientes, carpetas, tareas, turnos, comunicaciones y documentos (lectura/escritura segun modulo); no gestiona economia ni auditoria de sistema salvo lo que el rol permita igual que Abogado.
- **Superusuario:** Acceso total sin restricciones, incluyendo configuracion y migracion de datos.

> **Tip:** Si no ves algun modulo en el sidebar, es porque tu rol no tiene acceso. Consulta con tu Administrador si necesitas permisos adicionales.

**Visibilidad de registros:**

- Secretaria, Agente, Abogado y **Analisis** solo ven las carpetas, tareas, turnos y comunicaciones **asignados a ellos** (en carpetas tambien cuenta el **encargado de la etapa actual** cuando aplica).
- **Excepcion (Secretaria):** en los modulos **Clientes**, **Carpetas** y **Citas** la secretaria ve **todos** los registros del estudio (consulta y recepcion), no solo los asignados a su usuario.
- Administrador, Administrador (sin Contable) y Superusuario ven **todos los registros** del estudio.

---

## 2. El Dashboard: tu pantalla principal

El Dashboard es lo primero que ves al iniciar sesion. Te muestra un resumen de todo lo importante del dia.

### Busqueda rapida por N° de carpeta, DNI o nombre

En la parte superior del Dashboard hay un campo de busqueda. Es la herramienta mas usada del dia a dia. Permite buscar clientes de tres formas distintas:

**Como usarla:**

1. Escribir en el campo de busqueda **una** de las siguientes opciones:
   - **N° de carpeta** (por ejemplo: `1547`): busca por el numero de la carpeta fisica.
   - **DNI** (por ejemplo: `12345678` o `12.345.678`): busca por documento de identidad.
   - **Nombre** (por ejemplo: `PEREZ` o `Juan Perez`): busca por nombre del cliente.
2. Presionar **Enter** o clic en **Buscar**.
3. Si hay un unico resultado, aparece directamente el panel con los datos del cliente y sus carpetas.
4. Si hay varios resultados (por ejemplo, varios clientes con el mismo apellido), se abre un dialogo para elegir el cliente correcto.
5. Desde el panel podes hacer clic en **Abrir Cliente** o en **Abrir** en cualquier carpeta para ir directamente.
6. Para ocultar el panel, clic en **Limpiar**.

> **Tip:** Si ingresa un numero de 7 u 8 digitos, el sistema primero intenta buscarlo como DNI. Si no lo encuentra, lo prueba como N° de carpeta. Para otros largos numericos, busca primero por N° de carpeta.

### Que informacion muestra el Dashboard

- **Indicadores operativos:** Carpetas activas, cerradas, tareas pendientes y vencidas.
- **Indicadores de clientes:** Total de clientes registrados.
- **Indicadores de turnos:** Turnos de los proximos 7 dias, turnos de hoy, turnos sin documentacion lista.
- **Tabla "Turnos de Hoy":** Hora, cliente, tramite, oficina, responsable y si la documentacion esta preparada.
- **Tabla "Tareas vencidas / proximas a vencer":** Las 20 tareas mas urgentes.
- **Panel de alertas:** Hasta 15 alertas combinando tareas vencidas, turnos proximos y carpetas sin tarea activa.

**Colores de alerta:**

- Rojo: Tareas vencidas (atencion urgente)
- Dorado: Turnos proximos
- Naranja: Carpetas activas sin ninguna tarea asignada

> **Tip:** Los indicadores economicos (ingresos cobrados y pendientes) solo los ven el Administrador y el Superusuario.

### Campana de notificaciones e historial (barra superior)

En la parte superior de la ventana principal (junto al area de usuario) tenes:

- **Campana:** Abre un panel con las notificaciones **activas**. El numero rojo (badge) depende del **tipo** de aviso: en algunos casos, al **abrir** el panel dejan de sumar al contador aunque no esten marcadas como leidas en base; en otros (por ejemplo alertas de tarea) el contador puede **seguir** para que no pase desapercibido el trabajo pendiente. Las filas que ya no cuentan para el badge pueden verse **mas tenues**.
- **Boton de historial (reloj):** Abre un listado de notificaciones **recientes** (activas y ya resueltas o descartadas), util para repasar lo que paso en los ultimos dias.
- En cada notificacion del panel de la campana podes usar la **X** para **descartar** (con confirmacion). Descartar es independiente de marcar la tarea cumplida: solo oculta el aviso como pendiente.

> **Tip:** Si cerro sesion y vuelvo a entrar, el sistema reinicia el estado "visto" en pantalla de la campana; las notificaciones reales siguen en la base segun corresponda.

---

## 3. El flujo de trabajo paso a paso

Asi es como funciona el proceso tipico del estudio, desde que alguien se contacta hasta que el tramite se resuelve:

```
  CLIENTE + CARPETA         GESTION             CIERRE
 ──────────────────────       ──────────         ──────────

 1. Se crea el         -->  3. Se crean    --> 5. Se cierra
    cliente con N°          tareas y se       la carpeta
    de carpeta              programan         con resultado
                            turnos y citas
                            del estudio

 2. Se completan los   -->  4. Se registran
    datos del cliente       comunicaciones
    (procedencia,           y documentos
    CUIL, etc.)
```

### Explicacion de cada paso

**1. Se crea el cliente** -- Cuando alguien se contacta (por Instagram, TikTok, Facebook, Web, telefono, presencial o referido), se crea directamente un cliente en el sistema con el N° de carpeta fisica. Se indica la **procedencia del contacto** (de donde llego).

**2. Se completan los datos del cliente** -- Se agregan CUIL, direccion, fecha de nacimiento, obra social, etc.

**3. Se crean tareas, turnos y citas** -- Dentro de la carpeta se asignan las acciones necesarias (turno ANSES, **cita en el estudio** cuando la etapa lo requiere, presentacion de documentos, seguimiento, etc.). El modulo **Pendientes citar** ayuda a ver carpetas en etapa de citar sin cita agendada.

**4. Se registran comunicaciones y documentos** -- Se lleva un registro de cada contacto con el cliente y se adjunta la documentacion organizada por categoria.

**5. Se cierra la carpeta** -- Cuando el tramite se resuelve, se cambia el estado a Favorable, Desfavorable, Cerrado o Archivado. Se carga el resultado (obligatorio).

> **Nota clave:** El N° de carpeta fisica es el enlace entre el sistema digital y la carpeta de papeles del estudio. Se asigna al crear el cliente y aparece en todos lados: listado de clientes, carpetas y busqueda del Dashboard.

---

## 4. Modulos principales

### 4.1 Clientes

Modulo donde se guardan los datos de los clientes del estudio. Es el punto de entrada de todo nuevo caso.

**Como buscar un cliente:**

- Desde el **Dashboard**: usar la busqueda por N° de carpeta, DNI o nombre (la forma mas rapida).
- Desde el modulo **Clientes**: usar la barra de busqueda para filtrar por nombre, DNI, CUIL o N° de carpeta.

**Como crear o editar un cliente:**

1. Clic en **+ Nuevo Cliente** o seleccionar uno y clic en **Editar** (o doble clic).
2. Completar:
   - **N° de carpeta** (obligatorio, solo numeros): numero unico de la carpeta fisica.
   - **Nombre completo** (obligatorio).
   - **DNI**, **CUIL** (formato XX-XXXXXXXX-X).
   - **Fecha de nacimiento**, **Direccion**.
   - **Telefonos** (separados por coma).
   - **Email**, **Obra social**, **Actividad**.
   - **Procedencia**: de donde llego el contacto (Instagram, TikTok, Facebook, Referido, Presencial, Web, Telefono, Otro).
   - **Observaciones**.
3. Clic en **Guardar**.

> **Tip:** El N° de carpeta no se puede repetir entre clientes. Si intentas usar uno que ya existe, el sistema te avisa.

> **Tip:** Si dos personas intentan editar el mismo cliente al mismo tiempo, el sistema bloquea la edicion para el segundo usuario hasta que el primero termine.

---

### 4.2 Carpetas

Es el modulo central del sistema. Cada carpeta es un tramite o caso legal de un cliente.

**Como ver una carpeta:**

En el listado se muestran las columnas: N° Carpeta, **Rama**, **Subtipo**, Tipo Tramite, Estado, Responsable, Prioridad, Fecha Apertura y Nro. Tramite ANSES.

**Como crear o editar una carpeta:**

1. Clic en **+ Nueva Carpeta** o seleccionar una y clic en **Editar**.
2. El formulario tiene varias **pestañas**.

**Pestaña "Datos"** (la principal):

- **Cliente**: seleccionar de la lista (el texto del combo incluye nombre, CUIL y referencia de carpeta).
- **CUIL/CUIT:** campo aparte (solo lectura) con el CUIL del cliente; **un clic** copia el valor al portapapeles para pegarlo en ANSES, AFIP u otros sistemas.
- **N° Carpeta cliente:** se muestra automaticamente al elegir el cliente (solo lectura; es el numero de carpeta fisica del cliente).
- **Tipo de tramite**: Jubilacion, Retiro por salud, Laboral, Amparo, Pension, PUAM, RTI, Reajuste, Otro.
- **Rama**: Laboral, ART, Previsional, Amparos, Migraciones, Familia o Daños.
- **Subtipo**: se carga automaticamente segun la rama elegida.
- **Etapas del tramite (flujo operativo):**
  - **Clasificacion:** El sistema muestra una etiqueta que resume en que "tipo" de etapa estas (por ejemplo: no iniciada, iniciada, citado ANSES, resultado), con colores distintos para leer rapido el estado del caso.
  - **Combos de etapa:** Al elegir la etapa del flujo, el desplegable puede tener **fondo coloreado** (por ejemplo rojizo en etapas de requerimiento / no iniciada, verde en iniciada virtual o presencial). Lo mismo aplica en el listado de carpetas y en filtros del dashboard donde se elige etapa.
  - **Linea de tiempo:** Debajo aparece un **timeline por fases** (pre-tramite, turno, envio, iniciada, cierre), con una fila para etapas **no iniciadas** cuando corresponde. Si la etapa actual es de **requerimiento**, puede verse un aviso y un **parpadeo** para no perder de vista el pendiente. Tambien se muestran **plazos proximos** relacionados con la carpeta cuando hay recordatorios (los recordatorios pueden calcularse en **dias habiles** de Argentina: lun-vie sin feriados nacionales, desde el dialogo de alta o edicion de recordatorio).
  - **Modalidad (rama Previsional):** Si pasas la etapa a **iniciada virtual** o **iniciada presencial**, el sistema **ajusta** el campo de modalidad para que coincida. Al **Guardar**, si la modalidad no es coherente con la etapa, aparece un mensaje de error y **no** se guarda hasta corregirlo.
- **Responsable** (obligatorio): quien esta a cargo. El combo permite **escribir para buscar** con autocompletado: al tipear se filtran los nombres sin tener que desplazar todo el listado. Si tu rol usa **encargados por etapa**, aparecen en el mismo panel de etapas.
- **Datos especificos**: bloque dinamico que cambia segun la rama/subtipo (ej.: campos laborales, ART, previsionales, etc.).
- **Modulo Judicial**:
  - Activar el checkbox **Caso judicializado** para mostrar los campos judiciales comunes.
  - Campos judiciales: Fuero, Juzgado, Secretaria, N° expediente, Provincia, Instancia, Monto reclamado, Etapa procesal.
- **Estado**: Activo, En tramite, En espera, Guardada, Favorable, Desfavorable, Cerrado, Archivado.
- **Prioridad**: Alta, Normal, Baja.
- Otros campos: Ubicacion fisica, Link Drive, Nro. Tramite ANSES, Resultado, Fecha de cierre, Observaciones.

**Regla especial de claves ANSES/Fiscal:**

- **Clave Mi ANSES** y **Clave Fiscal** solo se muestran cuando la **Rama = Previsional**.
- En otras ramas, esos campos permanecen ocultos para simplificar la carga.

**Otras pestañas** (dentro de la misma carpeta):

- **Tareas**: tareas asignadas a este caso.
- **Turnos ANSES**: turnos programados.
- **Comunicaciones**: historial de contactos con el cliente.
- **Documentos**: archivos adjuntos.
- **Movimientos**: honorarios y gastos (solo Administrador/Superusuario).
- **Historial de Cambios**: quien modifico que y cuando (requiere permiso de auditoria).

> **Tip:** Si guardas una carpeta en estado "Activo" sin ninguna tarea asignada, el sistema te avisa con una alerta. Siempre conviene tener al menos una tarea activa.

> **Tip (etapas de citar):** Si la carpeta esta en etapa **Para citar** o **Para citar o videollamada** y aun **no** hay una cita interna en estado **Pendiente** o **Confirmada**, al **Guardar** el sistema puede preguntar si queres **crear la cita** ahora (solo si tu rol tiene permiso de alta en Citas).

---

### 4.3 Tareas

Las tareas son las acciones concretas que hay que hacer dentro de una carpeta.

**Como crear una tarea:**

1. Ir a **Tareas** en el sidebar (o desde la pestaña Tareas dentro de una carpeta).
2. Clic en **+ Nueva Tarea**.
3. Completar:
   - **Carpeta**: seleccionar el caso.
   - **Descripcion** (obligatorio): que hay que hacer.
   - **Tipo de accion**: Turno ANSES, Inicio virtual, Presentacion documental, Seguimiento, Notificacion, Reclamo, Audiencia, Pericia, Otro.
   - **Responsable** (obligatorio): quien la tiene que hacer.
   - **Fecha de vencimiento**: por defecto 30 dias.
   - **Estado**: Pendiente, En curso, En espera, Cumplida, Cancelada.
4. Clic en **Guardar**.

**Como darle seguimiento:**

- Las tareas se ordenan por fecha de vencimiento (las mas proximas primero).
- Usa el filtro de estado para ver solo las pendientes.
- Actualiza el estado a medida que avanzas (En curso, Cumplida, etc.).

> **Tip:** Las tareas vencidas (fecha pasada y estado Pendiente o En curso) aparecen automaticamente en el Dashboard con alerta roja.

---

### 4.4 Turnos ANSES

Modulo para programar y controlar los turnos en oficinas de ANSES.

**Como crear un turno:**

1. Ir a **Turnos ANSES** (o desde la pestaña Turnos dentro de una carpeta).
2. Clic en **+ Nuevo Turno**.
3. Completar:
   - **Cliente** (obligatorio).
   - **Carpeta** (opcional pero recomendado).
   - **Fecha** y **Hora** del turno.
   - **Oficina ANSES**: UDAI Resistencia, UDAI Saenz Pena, UDAI Barranqueras, UDAI Villa Angela, UDAI Charata, UDAI General San Martin, UDAI Corrientes, Otra.
   - **Tipo de tramite**: Jubilacion, PNC, PUAM, Retiro por invalidez, Pension derivada, Asignaciones, Desempleo, Progresar, Otro.
   - **Responsable** (obligatorio).
   - **Documentacion lista**: marcar el checkbox si ya esta todo preparado.
4. Clic en **Guardar**.

**Despues del turno:**

1. Seleccionar el turno.
2. Clic en **Marcar Asistido**.
3. Luego editar el turno para cargar el **Resultado** de la visita.

**Si necesitas cambiar la fecha:** Usar el boton **Reprogramar**. El sistema crea un nuevo turno con la nueva fecha y marca el anterior como "Reprogramado".

> **Tip:** Los turnos sin documentacion lista aparecen como alerta en el Dashboard. Siempre verifica que este todo preparado antes del turno.

---

### 4.5 Comunicaciones

Modulo para registrar cada contacto con los clientes (llamadas, WhatsApp, mails, etc.).

**Como registrar una comunicacion:**

1. Ir a **Comunicaciones** en el sidebar.
2. Clic en **+ Nueva Comunicacion**.
3. Completar:
   - **Carpeta** (opcional, para vincular al caso).
   - **Canal**: WhatsApp, Llamada, Mail, Presencial, Videollamada.
   - **Emisor** y **Receptor**.
   - **Motivo** y **Mensaje**.
   - **Resultado**: que se acordo o resolvio.
4. Clic en **Guardar**.

> **Tip:** Las comunicaciones no se pueden eliminar. Esto es intencional para preservar el historial completo de cada caso.

---

### 4.6 Documentos

Modulo para subir y organizar los archivos de cada carpeta.

**Como subir un documento:**

1. Ir a **Documentos** en el sidebar.
2. Clic en **+ Nuevo Documento**.
3. Completar:
   - **Carpeta** (opcional pero recomendado): escribi en el campo para buscar por **N° de carpeta**, **DNI** o **nombre y apellido** del cliente. A medida que escribis, se muestran las carpetas que coinciden. Selecciona la correcta de la lista desplegable.
   - **Nombre** (obligatorio): nombre descriptivo.
   - **Categoria** (obligatorio): Identidad, Laboral, Medicos, Judiciales, Administrativos, Resoluciones, Escritos, Notificaciones, Comunicaciones, Otro.
   - **Subcategoria**: se ajusta segun la categoria elegida.
   - **Archivo**: seleccionar el archivo a adjuntar.
4. Clic en **Guardar**.

**Como ver un documento:** Seleccionarlo y clic en **Ver/Abrir**. Se abre con el programa predeterminado de tu computadora.

**Si necesitas actualizar un documento** (por ejemplo, una nueva version de una demanda): Seleccionar el documento y clic en **Nueva Version** en lugar de crear uno nuevo. Asi se mantiene el historial completo.

> **Tip:** Podes filtrar documentos por categoria o por carpeta usando los desplegables de la parte superior.

---

### 4.7 Citas del estudio

Las **Citas** son entrevistas o encuentros **dentro del estudio** (agenda interna). No reemplazan al modulo **Turnos ANSES**, que es para la cita en la oficina de ANSES.

**Quien ve el modulo:** depende del rol (ver tabla en [Referencia tecnica](#16-referencia-tecnica)). En el sidebar aparece como **Citas**.

**Listado por dia:**

1. Abrir **Citas**.
2. Elegir la **fecha** (calendario, botones **Hoy**, dia anterior / siguiente).
3. Opcional: filtrar por **estado** (Pendiente, Confirmada, Asistio, No asistio, Cancelada).
4. La tabla muestra hora, cliente, N° carpeta cliente, tramite, motivo, estado, quien cito. La barra de busqueda filtra por cliente, DNI, numeros de carpeta, tramite o motivo.

**Nueva cita:**

1. Clic en **+ Nueva Cita**.
2. **Cliente** (obligatorio): buscar por nombre, DNI, N° carpeta fisica o N° carpeta sistema; o abrir el alta desde **Pendientes citar** / carpeta ya vinculada.
3. **Carpeta** (recomendada si el caso ya existe): vincular al expediente correcto.
4. **Fecha**, **hora**, **motivo**, **estado**, **observaciones** segun corresponda.
5. **Guardar**.

**Seguimiento:** seleccionar la fila y usar **Editar** o doble clic para cambiar estado (por ejemplo a **Asistio** o **No asistio**) o cancelar.

---

### 4.8 Pendientes citar

Vista del sidebar (cuando tu usuario puede ver **Carpetas** y **Citas**): **Pendientes citar**.

**Que muestra:** carpetas cuya **etapa** es **Para citar** o **Para citar o videollamada** y que **no** tienen ninguna cita en estado **Pendiente** ni **Confirmada** en el modulo Citas.

**Acciones por fila:**

- **Crear cita:** abre el formulario de cita con cliente y carpeta ya cargados (si tu rol **no** puede crear citas, el boton aparece deshabilitado).
- **Abrir carpeta:** abre la ficha de la carpeta para revisar datos o dejar tareas anotadas.

Usa **Pendientes citar** como cola de trabajo de recepcion o coordinacion para no dejar casos en etapa de citar sin fecha agendada en el estudio.

---

## 5. Tu dia a dia segun tu rol

### Secretaria (Recepcion)

Tu funcion principal es ser el primer punto de contacto y buscar informacion de clientes.

**Checklist diario:**

1. Abrir el **Dashboard** y revisar los turnos de hoy y las alertas; mirar la **campana** si hay numero en rojo.
2. Revisar **Citas** (agenda del dia) y la cola **Pendientes citar** para saber quien viene al estudio y que carpetas faltan agendar.
3. Si un cliente llama o se presenta, usar la **busqueda por N° de carpeta, DNI o nombre** para encontrar su informacion rapidamente.
4. Si necesitas informacion de una carpeta o tarea, podes verlos en modo lectura.

**Que SI podes hacer ademas:** Abrir el modulo **Citas** para ver la agenda del dia (solo lectura: no crear ni editar citas salvo que el Administrador cambie permisos). Usar **Pendientes citar** para ver que carpetas estan esperando cita interna.

**Que NO podes hacer:** Crear, editar o eliminar clientes, carpetas, tareas, turnos ni comunicaciones. No crear ni editar **citas** (solo consulta). No tenes acceso a Administracion, Reportes, Auditoria ni Empleados.

---

### Agente

Tu funcion principal es gestionar todo el ciclo operativo de un caso.

**Checklist diario:**

1. Revisar el **Dashboard**: tareas vencidas, turnos de hoy, alertas; **campana** e historial de notificaciones si aplica.
2. **Crear clientes nuevos** con su N° de carpeta y procedencia del contacto.
3. **Completar datos** de los clientes (CUIL, direccion, etc.).
4. **Crear carpetas** y **tareas** para las proximas acciones.
5. **Programar turnos ANSES** y verificar que la documentacion este lista.
6. Gestionar **Citas** del estudio (entrevistas internas): revisar **Pendientes citar**, crear o editar citas y marcar asistencia segun corresponda.
7. Despues de cada turno: **Marcar Asistido** y cargar el resultado.
8. **Registrar comunicaciones** con los clientes.

**Que NO podes hacer:** Crear ni editar documentos (solo verlos). No tenes acceso a Administracion economica, Reportes, Auditoria ni Empleados.

> **Importante:** Solo ves las carpetas, tareas y turnos asignados a vos (y carpetas donde seas **encargado de la etapa actual**).

---

### Abogado (Juridico)

Tu funcion principal es el aspecto legal: gestion de carpetas, documentacion y cierre de casos.

**Checklist diario:**

1. Revisar el **Dashboard**: carpetas activas, tareas pendientes, alertas; **campana** y popup de alertas tras login.
2. Trabajar en las **carpetas** asignadas: actualizar estados, etapas y linea de tiempo, crear tareas legales; revisar **Pendientes citar** y el modulo **Citas** cuando haya entrevistas internas agendadas.
3. **Gestionar documentos**: subir documentos por categoria, usar "Nueva Version" para actualizaciones.
4. **Registrar comunicaciones** legales (mails, cartas documento, cedulas).
5. **Cerrar carpetas** resueltas: cambiar estado y cargar resultado.
6. Consultar **Reportes** para analizar tiempos y carga de trabajo.

**Que NO podes hacer:** No tenes acceso a Administracion economica, Auditoria ni Empleados.

> **Importante:** Solo ves las carpetas, tareas y turnos asignados a vos (y carpetas donde seas **encargado de la etapa actual**).

---

### Analisis

Misma rutina operativa que **Abogado** para la gestion de carpetas, tareas, turnos, comunicaciones, **Citas** y documentos. Revisa el **Dashboard**, la **campana** y las alertas al iniciar sesion igual que el resto del equipo juridico.

**Que NO podes hacer:** No tenes acceso a Administracion economica, Auditoria ni Empleados (salvo lo que tu Administrador defina; en la practica equivale a Abogado en modulos visibles).

---

## 6. Preguntas frecuentes

**P: Que es el N° de carpeta y por que es obligatorio?**
R: Es el numero de la carpeta fisica donde se guardan los papeles del cliente en el estudio. Es obligatorio porque vincula el caso digital con los documentos fisicos. Cada cliente tiene un numero unico.

**P: Como busco un cliente rapidamente?**
R: Desde el **Dashboard**, escribi el N° de carpeta, el DNI o el nombre en el campo de busqueda y presiona Enter. Si hay un unico resultado se muestra directamente; si hay varios, aparece una lista para elegir.

**P: Olvide mi contraseña, que hago?**
R: Pedile a un Administrador o Superusuario que use la funcion **Resetear Clave** en el modulo de Empleados.

**P: No puedo ver una carpeta que deberia ver.**
R: Solo ves las carpetas donde sos **responsable principal** o, si aplica, **encargado de la etapa actual**. Si necesitas acceso a todos los casos, consulta con tu Administrador.

**P: Puedo trabajar sin internet?**
R: Si. La aplicacion funciona completamente offline. Los cambios se sincronizan automaticamente cuando vuelve la conexion.

**P: Como se si la sincronizacion esta funcionando?**
R: Mira el indicador en la parte inferior de la ventana. Verde = conectado y sincronizando. Rojo/Gris = offline (tus datos se guardan localmente y se suben cuando vuelva la conexion).

**P: Que pasa si dos personas editan lo mismo al mismo tiempo?**
R: El sistema usa un **bloqueo de edicion**. Si alguien ya esta editando un registro, los demas lo ven en modo lectura hasta que se libere.

---

# PARTE 2 - GUIA AVANZADA

Administracion, configuracion y procesos especiales. Orientada a Administradores y Superusuarios.

---

## 7. Administracion economica

Modulo para controlar honorarios, gastos y saldos del estudio. Solo visible para Administrador y Superusuario.

**Listado de movimientos:**

Tabla con columnas: ID, Fecha, Tipo, Monto, Forma de Pago, Estado, Saldo.

- **Filtro por tipo:** Honorario o Gasto.
- **Filtro por estado:** Pendiente, Parcial, Cancelado, Incobrable.
- **Barra inferior:** Total de montos, total de saldo pendiente y cantidad de registros.

**Como crear un movimiento:**

1. Clic en **+ Nuevo Movimiento**.
2. Completar:
   - **Cliente** y **Carpeta** (opcionales pero recomendados para vincular el movimiento al caso).
   - **Tipo** (obligatorio): Honorario o Gasto.
   - **Monto** (obligatorio): Valor mayor a 0.
   - **Fecha del movimiento**.
   - **Forma de pago**: Efectivo, Transferencia, Tarjeta, Cheque, Otro.
   - **Estado**: Pendiente, Parcial, Cancelado, Incobrable.
   - **Comprobante**: Numero o referencia.
   - **Saldo**: Monto pendiente de cobro.
3. Clic en **Guardar**.

> **Tip:** Los KPIs economicos del Dashboard (ingresos cobrados y pendientes) se alimentan de este modulo.

---

## 8. Reportes y exportacion

Panel de graficos interactivos y exportacion. Visible para Abogado (solo lectura), Administrador y Superusuario.

**Pestaña 1 - Graficos principales:**

- Carpetas por tipo de tramite (barras).
- Carga de trabajo por responsable.
- Clientes por procedencia del contacto.
- Resumen economico.

**Pestaña 2 - Tiempos y retrasos:**

- Tiempo promedio de resolucion por tipo de tramite.
- Retrasos por etapa (tareas vencidas por tipo de accion).
- Turnos vs. Casos (relacion entre turnos y carpetas).
- Clientes sin carpeta.

**Pestaña 3 - Indicadores humanos:**

- Carga por responsable (carpetas activas, tareas pendientes).
- Tareas vencidas por responsable.

**Exportacion de datos:**

| Boton | Formato | Que incluye |
|---|---|---|
| Exportar PDF | .pdf | KPIs operativos, comerciales, economicos + tabla de carpetas por tipo |
| Exportar Excel | .xlsx | Hojas: Clientes, Carpetas, Movimientos, KPIs |

---

## 9. Auditoria

Log inmutable de todas las acciones realizadas en el sistema. Solo visible para Administrador y Superusuario.

### Log de actividad (Pestaña 1)

Tabla con: Fecha/Hora, Usuario, Accion, Modulo, ID Documento, Resumen.

**Filtros disponibles:**

- **Por usuario**: quien realizo la accion.
- **Por modulo**: Clientes, Carpetas, Tareas, Turnos ANSES, Comunicaciones, Movimientos, Documentos.
- **Por accion**: Crear, Editar, Eliminar.
- **Por rango de fechas**: Desde - Hasta.

**Ver detalle de un cambio:**

Hacer doble clic en una fila del log. Se abre un dialogo con:

- Encabezado: accion, modulo, fecha, usuario, ID del documento.
- Tabla de cambios campo a campo: Campo, Valor Anterior, Valor Nuevo.
- Valores nuevos resaltados en verde, valores eliminados en rojo.

**Exportar:** El boton **Exportar a Excel** genera un archivo .xlsx con el log filtrado.

### Estadisticas por empleado (Pestaña 2)

- **KPIs**: Total acciones, acciones de hoy, usuarios activos, ultima actividad.
- **Tabla**: Usuario, Total, Creaciones, Ediciones, Eliminaciones, Ultima actividad.
- **Graficos (ultimos 30 dias)**: Actividad por usuario, actividad diaria, actividad por modulo.

### Seguimiento de tareas (Pestaña 3)

Vista pensada para Administrador/Superusuario para controlar el ciclo completo de una tarea asignada sin salir de Auditoria.

**Que muestra por cada tarea:**

- Fecha de asignacion.
- Tarea / descripcion.
- Usuario asignado.
- Estado de lectura: Leida o No leida.
- Fecha de lectura (cuando la notificacion fue abierta).
- Estado actual de la tarea.
- Fecha de cumplimiento (cuando paso a Cumplida/Completada/Cancelada).
- Dias sin leer (solo si sigue pendiente y no fue leida).

**Filtros disponibles:**

- Responsable.
- Estado.
- Rango de fechas de asignacion.

**Uso recomendado para seguimiento diario:**

1. Ir a **Auditoria -> Seguimiento de Tareas**.
2. Filtrar por responsable.
3. Revisar primero filas con **No leida** y mayor **Dias sin leer**.
4. Confirmar cumplimiento con **Estado** y **Fecha de cumplimiento**.

> **Nota tecnica:** La tabla de auditoria esta protegida por triggers de la base de datos que impiden modificar o eliminar registros. Esto garantiza la integridad del historial.

---

## 10. Gestion de empleados

Modulo para administrar los usuarios del sistema. Visible para Administrador y Superusuario.

> **Nota:** Los Administradores no pueden ver ni gestionar usuarios con rol Superusuario. Solo los Superusuarios pueden gestionar otros Superusuarios.

**Listado de empleados:**

Tabla con: Usuario, Nombre Completo, Email, Rol, Estado, Ultimo Acceso.

> Los empleados dados de baja no aparecen en la lista, pero su historial se conserva.

### Crear un nuevo empleado

1. Clic en **+ Nuevo Empleado**.
2. Completar:
   - **Usuario** (obligatorio): nombre de usuario para login.
   - **Contraseña** (obligatoria): se almacena encriptada.
   - **Nombre completo** (obligatorio).
   - **Email** (opcional).
   - **Rol** (obligatorio): Secretaria, Agente, Abogado, Analisis, Administrador, Administrador (sin Contable). (Solo los Superusuarios pueden asignar el rol Superusuario).
3. Clic en **Guardar**.

### Resetear contraseña

1. Seleccionar el usuario en la tabla.
2. Clic en **Resetear Clave**.
3. Escribir la nueva contraseña y confirmarla.
4. Clic en **Guardar**.

### Pausar un empleado (suspension temporal)

Usar cuando un empleado esta de licencia, vacaciones o necesita ser suspendido temporalmente.

1. Seleccionar el usuario.
2. Clic en **Pausar**.
3. Confirmar.
4. El usuario queda inactivo. Si tenia sesion abierta, sera **desconectado forzosamente**.
5. Para reactivar: seleccionarlo y clic en **Reactivar**.

### Dar de baja un empleado

Usar cuando un empleado deja el estudio definitivamente.

1. Seleccionar el usuario.
2. Clic en **Dar de Baja**.
3. Confirmar la primera vez.
4. Confirmar la segunda vez (doble confirmacion por seguridad).
5. El usuario desaparece de la lista. Su historial de auditoria se conserva intacto.

> **Importante:** Esta accion no se puede revertir desde la interfaz.

### Restricciones de seguridad

- No se puede eliminar o pausar a uno mismo.
- No se puede eliminar al unico superusuario activo del sistema.
- Un administrador no puede modificar a un superusuario.

---

## 11. Procesos especiales (detalle completo)

### 11.1 Cierre de carpeta

**Cuando cerrar una carpeta:**

Cuando el tramite judicial o administrativo se resuelve, ya sea con resultado favorable o desfavorable.

**Pasos:**

1. Ir al modulo **Carpetas** y abrir la carpeta.
2. Cambiar el **Estado** a uno de cierre:
   - **Favorable**: Resolucion positiva.
   - **Desfavorable**: Resolucion negativa.
   - **Cerrado**: Finalizado por otra razon.
   - **Archivado**: Caso archivado definitivamente.
3. Completar el campo **Resultado** (obligatorio). Describir el resultado del tramite.
4. El campo **Fecha de cierre** se habilita automaticamente.
5. Clic en **Guardar**.

> Si se intenta guardar una carpeta como "Activo" sin ninguna tarea activa (Pendiente, En curso o En espera), el sistema muestra una advertencia.

---

### 11.2 Reprogramacion de turno

Cuando un turno ANSES necesita cambiarse de fecha:

1. Ir al modulo **Turnos ANSES**.
2. Seleccionar el turno a reprogramar.
3. Clic en **Reprogramar**.
4. Se abre un dialogo pidiendo: nueva fecha, nueva hora y oficina (se puede cambiar o mantener).
5. Confirmar.
6. El sistema automaticamente:
   - Marca el turno original como "Reprogramado".
   - Crea un nuevo turno con los mismos datos base pero con la nueva fecha, hora y oficina.
   - El nuevo turno queda en estado "Pendiente".
   - En las observaciones del nuevo turno se agrega "Reprogramado desde turno #...".

**Marcar como asistido:**

1. Seleccionar el turno (solo disponible para turnos en estado Pendiente o Confirmado).
2. Clic en **Marcar Asistido**.
3. Confirmar.
4. Despues, editar el turno para cargar el **Resultado** de la visita.

---

### 11.3 Versionado de documentos

El sistema permite mantener multiples versiones de un mismo documento, preservando el historial completo.

**Crear una nueva version:**

1. Ir al modulo **Documentos**.
2. Seleccionar el documento existente.
3. Clic en **Nueva Version**.
4. Seleccionar el nuevo archivo y escribir notas sobre que cambio.
5. Clic en **Guardar**.
6. Se crea un nuevo registro con el numero de version incrementado.

**Ver historial de versiones:**

1. Seleccionar el documento.
2. Clic en **Historial Versiones**.
3. Se muestra una tabla con: Version, Fecha, Responsable, Tamaño, Notas, Archivo.
4. Se puede abrir cualquier version anterior.

**Ejemplo practico:**

Un escrito de demanda pasa por varias revisiones:

- Version 1: Demanda inicial (2024-01-15)
- Version 2: Correccion de datos del cliente (2024-01-20)
- Version 3: Version final presentada (2024-02-01)

Cada version queda registrada con quien la subio, cuando y por que cambio.

---

### 11.4 Pausar o dar de baja un empleado

Ver seccion [10. Gestion de empleados](#10-gestion-de-empleados) para los pasos detallados de pausa, reactivacion y baja de empleados.

---

### 11.5 Notificaciones y alertas (campana, historial, login)

**Donde aparecen**

- **Barra superior:** icono de **campana** (notificaciones activas) y boton de **historial** (reloj).
- **Al iniciar sesion:** si hay avisos pendientes, puede abrirse un **popup** con la lista (prioriza alertas de **carpeta**: asignacion, encargado de etapa, recordatorio de expediente; despues el resto, por ejemplo tareas).

**Que podes hacer**

- **Abrir la campana:** Ver todas las notificaciones activas. El **numero rojo** no siempre es "cantidad de filas": segun el tipo, abrir el panel puede hacer que algunas dejen de contar sin tocar la base; otras (como alertas de tarea) pueden seguir mostrando numero para no olvidar el trabajo.
- **Historial:** Ver las ultimas notificaciones incluyendo las ya resueltas o descartadas (consulta rapida de lo ocurrido).
- **Descartar una fila:** Quita el aviso como pendiente (con confirmacion). No reemplaza a **cumplir la tarea** ni a gestionar la carpeta: solo oculta la notificacion. Si la descartaste vos, el sistema **no la vuelve a crear** sola por el mismo motivo.
- **Descartar todas:** En el popup de login o en el panel, descarta de una vez todas las filas mostradas (con confirmacion).

**Cierre de sesion**

- Al cerrar sesion, el estado "visto" en pantalla de la campana se reinicia; al entrar de nuevo veras los contadores segun las notificaciones reales vigentes.

---

## 12. Migracion desde Excel / CSV

Asistente de 6 pasos para importar datos historicos desde archivos Excel o CSV. Solo disponible para el rol Superusuario.

El sistema acepta dos formatos de entrada:

- **Excel (.xlsx / .xls):** Se seleccionan las hojas a importar y se aplica el mapeo automatico.
- **CSV (.csv):** Archivo con separador punto y coma (`;`). Se elige el tipo de plantilla (CARPETAS, SEGUIMIENTO EXP, etc.) y el sistema aplica el mapeo de columnas por posicion. En la carpeta `excel/` se incluyen plantillas CSV de ejemplo (`PLANTILLA_CARPETAS.csv`, `PLANTILLA_FALTA_EDAD.csv`, etc.).

**Paso 1 - Seleccionar hojas / tipo de plantilla:**

- **Excel:** Se carga el archivo y se muestran las hojas disponibles con la cantidad de filas y el mapeo sugerido. Se seleccionan las hojas a importar.
- **CSV:** Se muestra un combo para elegir el tipo de plantilla. El sistema muestra una preview del archivo y el mapeo que se aplicara.

**Paso 2 - Mapeo de columnas:**

El sistema muestra el mapeo automatico de columnas a campos del sistema. Se puede ajustar si es necesario.

**Paso 3 - Normalizacion:**

Preview de los datos normalizados:

- Extraccion automatica de telefonos y emails.
- Normalizacion de CUIL.
- Correccion de formatos de fecha.
- Deteccion de estado y tipo de tramite desde observaciones.
- Tabla editable con los primeros 100 registros para revision manual.

**Paso 4 - Deduplicacion:**

El sistema detecta posibles duplicados por CUIL o similitud de nombre (algoritmo Levenshtein). Para cada duplicado se ofrece la opcion de **Fusionar** los registros.

**Paso 5 - Revision final:**

Resumen antes de importar: total de registros, fusiones aplicadas, registros efectivos a importar. Opcion para importar claves originales en observaciones.

**Paso 6 - Importacion:**

Barra de progreso y log en tiempo real. Resultado final: clientes creados, carpetas creadas, registros omitidos, errores.

### Importacion por partes con CSV (recomendado)

Para minimizar riesgos al importar grandes volumenes de datos:

1. Usar las plantillas CSV de la carpeta `excel/` como modelo.
2. Armar archivos CSV chicos (200-500 filas por vez) con separador `;`.
3. Correr el asistente con cada archivo CSV, seleccionando el tipo de plantilla correspondiente.
4. El sistema normaliza, deduplica e importa igual que con Excel.

---

## 13. Exportar / Importar sistema completo

Esta funcion permite exportar **todo** el estado del sistema en un unico ZIP (base local SQLite + documentos + dump de colecciones MongoDB) y luego importarlo para recuperacion o migracion. Solo disponible para el rol **Superusuario (Direccion)**.

### Como exportar

1. Ir al modulo **Configuracion** -> pestaña **General / Logos**.
2. En la seccion **Backups Manuales (completo híbrido)**, hacer clic en **Exportar backup completo**.
3. Elegir donde guardar el archivo ZIP (se sugiere un nombre con fecha/hora).
4. Esperar a que termine la exportacion.
5. El sistema muestra un resumen con la cantidad de registros por tabla y archivos adjuntos incluidos.

### Que contiene el ZIP

- **manifest.json**: metadatos del backup (version, fecha, machine_id, checksum, conteos).
- **local/sqlite.db**: snapshot consistente de la base SQLite local.
- **local/documentos/**: archivos adjuntos locales.
- **remote/mongo_dump/*.jsonl**: dump por coleccion de MongoDB.

### Como importar

1. Ir al modulo **Configuracion** -> pestaña **General / Logos**.
2. Hacer clic en **Importar backup completo**.
3. Seleccionar el archivo ZIP exportado previamente.
4. El sistema primero hace una validacion previa (dry-run) y luego pide confirmacion.
5. Confirmar la operacion. El sistema creara:
   - Una **nueva base de datos** (archivo `.db` con nombre que incluye fecha/hora).
   - Un **nuevo directorio de documentos** con los archivos adjuntos del bundle.
6. El archivo `config.ini` se actualiza automaticamente para apuntar a la nueva base de datos.
7. **IMPORTANTE: Debe reiniciar la aplicacion** para que los cambios tomen efecto.

### Notas importantes

- La base de datos anterior **no se elimina**. Queda como respaldo en la carpeta `data/`.
- Las claves (Mi ANSES, Clave Fiscal) se exportan tal cual estan en la base de datos. Guarde el archivo ZIP en un lugar seguro.
- La sincronizacion con MongoDB Atlas continuara funcionando con la nueva base tras el reinicio.
- Si desea volver a la base de datos anterior, puede editar `config.ini` y cambiar `path` en la seccion `[sqlite]` a `data/local.db` (o eliminar esa linea), y reiniciar la aplicacion.
- Durante la importacion se registra un evento en auditoria (`backup_import`).

---

## 14. Backups de documentos en VPS

Esta seccion aplica cuando el estudio usa el servidor de archivos de `server/` en un VPS.

### Para que sirve

- Tener una copia semanal comprimida de todos los archivos subidos (PDF, imagenes, textos).
- Poder recuperar los documentos si hay daño de datos o incidente en la base.

### Donde se guarda

- Carpeta por defecto: `/opt/rampazzo/backups`
- Nombre de archivo: `docs_backup_YYYYMMDD_HHMMSS.tar.zst`

### Frecuencia

- Automatica por cron: domingo 03:00 AM (usuario `rampazzo`).

### Quien debe controlarlo

- Administrador tecnico o Superusuario con acceso al VPS.

### Como verificar rapidamente

```bash
ls -lh /opt/rampazzo/backups
```

Y desde API:

```bash
API_KEY=$(grep RAMPAZZO_API_KEY /opt/rampazzo/server/.env | cut -d= -f2)
curl -H "x-api-key: $API_KEY" http://localhost:8443/backups
```

### Recuperacion de emergencia

```bash
cd /opt/rampazzo
tar --zstd -xf backups/docs_backup_YYYYMMDD_HHMMSS.tar.zst -C /
```

Esto restaura la estructura completa de `/opt/rampazzo/documentos/`.

---

## 15. Sincronizacion y trabajo offline

### Como funciona

El sistema trabaja con dos bases de datos:

- **SQLite local:** En tu computadora. Todas las operaciones se realizan primero aca.
- **MongoDB Atlas:** En la nube. Es la base compartida entre todas las computadoras del estudio.

**Proceso automatico:**

Cada 5 minutos (configurable en `config.ini`), el sistema ejecuta un ciclo de sincronizacion:

1. **Subida (push):** Los registros marcados como "pendientes" en la base local se suben a MongoDB Atlas.
2. **Bajada (pull):** Los registros nuevos o modificados en MongoDB Atlas se descargan a la base local.

### Indicador de conexion

En la parte inferior de la ventana principal:

- **Verde:** Conectado a MongoDB Atlas. Sincronizacion activa.
- **Rojo/Gris:** Sin conexion. Trabajando en modo offline.

### Trabajo offline

Si no hay conexion a internet:

- La aplicacion **funciona normalmente** con la base de datos local.
- Todos los cambios se marcan como "pendientes".
- Cuando la conexion se restablece, el sistema **sincroniza automaticamente**.
- No se pierde ningun dato.

### Manejo de conflictos

Si un registro fue modificado localmente y tambien en MongoDB:

- El sistema detecta el choque de version.
- Se registra el conflicto en `sync_conflicts` con snapshots local/remoto.
- El registro no se pisa en silencio.

---

## 16. Referencia tecnica

### Tabla completa de permisos por rol

| Modulo | Secretaria | Agente | Abogado | Analisis | Administrador | Administrador (sin Contable) | Superusuario |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Dashboard | Ver | Ver | Ver | Ver | Ver | Ver | Ver |
| Clientes | Solo ver | Completo | Completo | Completo | Completo | Completo | Completo |
| Carpetas | Solo ver | Completo | Completo | Completo | Completo | Completo | Completo |
| Tareas | Solo ver | Completo | Completo | Completo | Completo | Completo | Completo |
| Turnos ANSES | Solo ver | Completo | Completo | Completo | Completo | Completo | Completo |
| Citas | Solo ver | Completo | Completo | Completo | Completo | Completo | Completo |
| Pendientes citar | Ver | Ver | Ver | Ver | Ver | Ver | Ver |
| Comunicaciones | Solo ver | Completo | Completo | Completo | Completo | Completo | Completo |
| Documentos | Solo ver | Solo ver | Completo | Completo | Completo | Completo | Completo |
| Administracion | - | - | - | - | Completo | - | Completo |
| Reportes | - | - | Solo ver | Solo ver | Completo | Completo | Completo |
| Auditoria | - | - | - | - | Completo | Completo | Completo |
| Empleados | - | - | - | - | Completo | Completo | Completo |
| Configuracion | - | - | - | - | - | - | Completo |
| Migracion Excel/CSV | - | - | - | - | - | - | Completo |

**"Completo"** = puede crear, ver, editar y eliminar registros en ese modulo.

**Citas / Pendientes citar:** En **Pendientes citar**, todos los roles que ven la vista pueden abrir la carpeta; el boton **Crear cita** solo esta habilitado si el rol puede **crear** citas (Agente, Abogado, Analisis y perfiles administrativos; Secretaria solo consulta el calendario).

**Analisis:** Misma matriz que **Abogado** en la tabla (documentos completos donde Abogado tiene completo; sin acceso a modulos no listados para Abogado).

**Administrador (sin Contable):** Igual que **Administrador** salvo la columna **Administracion** (movimientos de dinero / contable).

### Estados de carpetas

| Estado | Significado |
|---|---|
| Activo | En gestion activa |
| En tramite | Se esta tramitando ante ANSES u organismo |
| En espera | Esperando respuesta o documentacion |
| Guardada | Pausado temporalmente |
| Desfavorable | Resolucion negativa |
| Favorable | Resolucion positiva |
| Cerrado | Tramite finalizado |
| Archivado | Caso archivado definitivamente |

### Estados de tareas

| Estado | Significado |
|---|---|
| Pendiente | Sin iniciar |
| En curso | Se esta trabajando en ella |
| En espera | Bloqueada esperando algo externo |
| Cumplida | Completada exitosamente |
| Cancelada | Ya no es necesaria |

### Estados de turnos ANSES

| Estado | Significado |
|---|---|
| Pendiente | Programado, aun no confirmado |
| Confirmado | Confirmado por ANSES |
| Asistido | Se asistio al turno |
| No asistido | No se pudo asistir |
| Reprogramado | Se reprogramo para otra fecha |
| Cancelado | Se cancelo el turno |

### Estados de citas del estudio

| Estado | Significado |
|---|---|
| Pendiente | Agendada, aun no confirmada formalmente |
| Confirmada | Confirmada para la fecha/hora |
| Asistio | La persona concurrio a la cita |
| No asistio | No concurrio |
| Cancelada | Se anulo la cita |

### Categorias de documentos

| Categoria | Subcategorias |
|---|---|
| Identidad | DNI, Partida de nacimiento, Certificado de domicilio, CUIL, Otro |
| Laboral | Recibos de sueldo, Certificado de trabajo, ART, ANSES, Otro |
| Medicos | Certificado medico, Historia clinica, Junta medica, CUD, Otro |
| Judiciales | Demanda, Contestacion, Sentencia, Apelacion, Recurso, Otro |
| Administrativos | Tramite ANSES, Resolucion, Recurso admin., Dictamen, Otro |
| Resoluciones | Favorable, Desfavorable, Parcial, Otro |
| Escritos | Inicio, Ampliacion, Alegato, Memorial, Otro |
| Notificaciones | Cedula, Carta documento, Telegrama, Otro |
| Comunicaciones | Email, Nota, Informe, Otro |
| Otro | General |

### Campos de la carpeta (referencia completa)

| Campo | Descripcion |
|---|---|
| Cliente | Selector de cliente existente |
| CUIL/CUIT | (Solo lectura) CUIL del cliente; clic para copiar al portapapeles |
| N° Carpeta cliente | (Solo lectura) Numero de carpeta fisica del cliente |
| Tipo de tramite | Jubilacion, Retiro por salud, Laboral, Amparo, Pension, PUAM, RTI, Reajuste, Otro |
| Area | Area de trabajo |
| Fecha de apertura | Por defecto la fecha actual |
| Responsable | Empleado asignado (obligatorio) |
| Responsable secundario | Segundo responsable (opcional) |
| Estado | Activo, En tramite, En espera, Guardada, Desfavorable, Favorable, Cerrado, Archivado |
| Prioridad | Alta, Normal (defecto), Baja |
| Ubicacion fisica | Donde esta la carpeta fisica |
| Link Drive | Enlace a carpeta en Google Drive |
| Nro. Tramite ANSES | Formato: 024-XXXXXXXXXXX-XXX-XXXXXX |
| Resultado | Obligatorio al cerrar |
| Fecha de cierre | Solo disponible al cerrar |
| Observaciones | Notas generales |

### Campos del turno ANSES (referencia completa)

| Campo | Descripcion |
|---|---|
| Cliente | Selector de clientes (obligatorio) |
| Carpeta | Selector (opcional) |
| Fecha del turno | Por defecto hoy + 7 dias |
| Hora del turno | Formato HH:MM (obligatorio) |
| Oficina ANSES | UDAI Resistencia, UDAI Saenz Pena, UDAI Barranqueras, UDAI Villa Angela, UDAI Charata, UDAI General San Martin, UDAI Corrientes, Otra (obligatorio) |
| Tipo de tramite | Jubilacion, PNC, PUAM, Retiro por invalidez, Pension derivada, Asignaciones, Desempleo, Progresar, Otro |
| Codigo de turno | Codigo de confirmacion de ANSES |
| Estado | Pendiente, Confirmado, Asistido, No asistido, Reprogramado, Cancelado |
| Responsable | Empleado asignado (obligatorio) |
| Documentacion lista | Checkbox |
| Notas de preparacion | Que preparar antes del turno |
| Resultado | Se completa despues de asistir |
| Requiere nuevo turno | Checkbox si se necesita reprogramar |
| Observaciones | Notas adicionales |

### Preguntas frecuentes avanzadas

**P: Que diferencia hay entre Citas y Turnos ANSES?**
R: **Turnos ANSES** es la cita en la oficina de ANSES (fecha, UDAI, codigo de turno, documentacion, resultado de la visita). **Citas** es la agenda **interna del estudio** (entrevista en el estudio, videollamada interna, etc.) y se gestiona en el modulo **Citas** / **Pendientes citar**.

**P: Como hago para saber quien modifico una carpeta?**
R: Desde la carpeta, ir a la pestaña **Historial de Cambios** (requiere permiso de auditoria). O ir al modulo **Auditoria** y filtrar por el ID dla carpeta.

**P: Como exporto datos del estudio?**
R: Desde **Reportes** se puede exportar a PDF y Excel. Desde **Auditoria** se puede exportar el log filtrado a Excel. Para exportar **todo el sistema** (SQLite + documentos + dump Mongo), ir a **Configuracion -> General / Logos** y usar **Exportar backup completo** (solo Superusuario).

**P: Que pasa si intento asignar un N° de carpeta que ya esta en uso?**
R: El sistema no lo permite. Se muestra un error indicando que ya existe otro cliente con ese numero.

**P: Puedo cambiar el N° de carpeta de un cliente?**
R: Si, editando el cliente desde el modulo Clientes. El nuevo numero debe ser numerico y no estar en uso.

**P: Como cambio mi propia contraseña?**
R: Pedile a un Administrador o Superusuario que use **Resetear Clave**. No hay opcion de autocambio en la interfaz actual.

**P: Donde se guardan los documentos adjuntos?**
R: En la carpeta `data/documentos/` dentro del directorio de la aplicacion, organizados por carpeta.

**P: Puedo recuperar un empleado dado de baja?**
R: No desde la interfaz. La baja es un soft-delete (el registro se conserva en la base de datos pero no es visible). Un Superusuario con acceso directo a la base de datos podria revertirlo.

**P: Que pasa si el sistema se cae mientras estoy trabajando?**
R: Los datos se guardan en la base de datos local cada vez que haces clic en Guardar. Si la aplicacion se cierra inesperadamente, todo lo que hayas guardado previamente esta seguro.

### Flujo de trabajo del Administrador

**Tu funcion principal:** Control total sobre la operacion del estudio: todos los modulos, economia, auditoria y empleados.

**Modulos disponibles:** Todos excepto Configuracion y Migracion Excel/CSV.

1. **Supervisar el Dashboard:** Revisar todos los KPIs (incluyendo economicos), atender alertas de todo el equipo, revisar la **campana** si hay notificaciones propias.
2. **Supervision operativa:** Revisar carpetas de todos los responsables, verificar que no haya carpetas sin tarea activa, controlar tareas vencidas; revisar **Pendientes citar** y la agenda de **Citas** para la coordinacion del estudio.
3. **Gestion economica:** Registrar honorarios y gastos, controlar saldos pendientes.
4. **Reportes:** Generar y exportar reportes en PDF y Excel, analizar indicadores humanos.
5. **Auditoria:** Revisar el log de actividad, filtrar por usuario/modulo/fecha, exportar logs.
6. **Gestion de empleados:** Crear empleados, resetear contraseñas, pausar o dar de baja usuarios.

**Que NO podes hacer:** No podes acceder a Configuracion del sistema, realizar migraciones desde Excel, ni gestionar usuarios con rol Superusuario.

### Flujo de trabajo del Superusuario (Direccion)

**Tu funcion principal:** Acceso total al sistema sin restricciones.

**Modulos disponibles:** Todos sin excepcion.

Ademas de todo lo que puede hacer un Administrador:

1. **Configuracion del sistema:** Gestionar la configuracion general, crear usuarios de cualquier rol (incluyendo otros superusuarios). Revisar **campana** e historial como cualquier usuario cuando haya alertas personales.
2. **Migracion desde Excel / CSV:** Importar datos historicos usando el asistente de 6 pasos.
3. **Exportar / Importar sistema completo:** Generar un ZIP hibrido (SQLite + documentos + Mongo) o restaurar desde uno existente (ver seccion 13).
4. **Supervision total:** Vision global de toda la operacion del estudio.
