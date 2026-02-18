## Plantillas CSV para Migración (modo seguro “por partes”)

El sistema **importa desde Excel (`.xlsx`)**, no desde CSV directamente.  
Estos CSV sirven como **plantilla**: los abrís en Excel, los pegás / importás a una hoja y luego **guardás como `.xlsx`** para usar el **Asistente de Migración**.

### 1) Nombres de hoja (MUY IMPORTANTE)

El asistente aplica mapeos automáticos **solo si el nombre de la hoja coincide exactamente** con alguno de estos:

- `CARPETAS`
- `BASE DE DATOS`
- `EXP IPS `  (nota: tiene **un espacio al final**, así aparece en `gestion-rampazzo.xlsx`)
- `RTI DESFAVORABLES`
- `SEGUIMIENTO EXP`
- `FALTA EDAD`
- `TURNOS ANSES NUEVO`

Si el nombre no coincide, esa hoja **no se importará**.

### 2) Orden de columnas y filas “vacías”

- **El orden de columnas es fijo** (por posición). No reordenes columnas.
- Algunas plantillas incluyen **filas iniciales vacías** (o una fila “título”) para respetar desde qué fila empieza a leer el asistente.
  - Conservalas tal cual al pasar a `.xlsx`.

### 3) Hojas sin encabezado

Estas hojas empiezan a leerse desde la fila 1, por lo que **no deben llevar encabezado** (si agregás encabezado, se importará como un registro):

- `RTI DESFAVORABLES` (en `PLANTILLA_RTI_DESFAVORABLES.csv`)
- `TURNOS ANSES NUEVO` (en `PLANTILLA_TURNOS_ANSES_NUEVO.csv`)

### 4) Advertencia especial: `TURNOS ANSES NUEVO`

Esa hoja solo trae `id_carpeta` y `observaciones`.  
**No la importes sola**, porque podría crear clientes “vacíos”. Usala únicamente junto con otra hoja que tenga el mismo `id_carpeta` y traiga al menos `nombre_completo` y/o `cuil` (por ejemplo `CARPETAS` o `SEGUIMIENTO EXP`), para que el asistente pueda **fusionar** por `id_carpeta`.

### 5) Importación “por partes” (recomendado)

Para minimizar riesgos:

- Armá varios archivos `.xlsx` chicos (por ejemplo 200–500 filas por vez).
- Corré el asistente por cada archivo.
- Mantené consistentes los `id_carpeta` entre hojas dentro del mismo `.xlsx` para que la deduplicación/fusión funcione.

