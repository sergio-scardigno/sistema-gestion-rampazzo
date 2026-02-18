"""
Lector de CSV con mapeo de columnas basado en SHEET_MAPPINGS.
Produce la misma estructura de registros que read_sheet_data() del excel_reader,
permitiendo importar datos desde archivos CSV con separador punto y coma.
"""
import csv

from utils.migration.excel_reader import SHEET_MAPPINGS

_ENCODINGS_TO_TRY = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


def _read_all_rows(path: str, delimiter: str = ";") -> list[list[str]]:
    """Lee todas las filas de un CSV detectando encoding automaticamente.

    Intenta UTF-8 primero; si falla, prueba cp1252 y latin-1 que son
    los encodings habituales de archivos CSV exportados desde Excel en Windows.
    """
    for enc in _ENCODINGS_TO_TRY:
        try:
            with open(path, "r", encoding=enc, errors="strict") as f:
                rows = list(csv.reader(f, delimiter=delimiter))
            return rows
        except (UnicodeDecodeError, UnicodeError):
            continue
    # Ultimo recurso: leer con reemplazo para no perder datos
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return list(csv.reader(f, delimiter=delimiter))


def _detect_data_start(all_rows: list[list[str]], sheet_type: str) -> int:
    """Auto-detecta desde que fila (1-based) comienzan los datos reales.

    Busca una fila de encabezado (que contenga al menos 2 nombres de campo
    del mapping) dentro de las primeras filas del CSV. Los datos empiezan
    en la fila siguiente al encabezado detectado.

    Si no encuentra encabezado, devuelve el data_start original del mapping
    (util para plantillas sin encabezado como RTI DESFAVORABLES).
    """
    mapping_config = SHEET_MAPPINGS.get(sheet_type, {})
    column_mapping = mapping_config.get("columns", {})
    original_data_start = mapping_config.get("data_start", 1)

    if not column_mapping or not all_rows:
        return original_data_start

    field_names = {v.lower().strip() for v in column_mapping.values()}
    min_matches = min(2, len(field_names))

    scan_limit = min(len(all_rows), original_data_start + 1)
    last_header_idx = -1

    for i in range(scan_limit):
        row_values = {cell.strip().lower() for cell in all_rows[i] if cell.strip()}
        matches = row_values & field_names
        if len(matches) >= min_matches:
            last_header_idx = i

    if last_header_idx >= 0:
        return last_header_idx + 2  # 1-based, fila siguiente al encabezado

    return original_data_start


def detect_sheet_type(path: str, delimiter: str = ";") -> str:
    """Auto-detecta el tipo de plantilla leyendo los encabezados del CSV.

    Compara las celdas de las primeras filas contra los nombres de campo
    de cada SHEET_MAPPING y devuelve el tipo con mayor coincidencia.
    Retorna cadena vacia si no hay coincidencia clara.
    """
    all_rows = _read_all_rows(path, delimiter)
    if not all_rows:
        return ""

    # Recolectar celdas de las primeras filas (posible header) en minusculas
    scan_limit = min(len(all_rows), 5)
    header_cells: set[str] = set()
    for i in range(scan_limit):
        for cell in all_rows[i]:
            val = cell.strip().lower()
            if val:
                header_cells.add(val)

    best_type = ""
    best_score = 0

    for sheet_type_key, config in SHEET_MAPPINGS.items():
        col_map = config.get("columns", {})
        if not col_map:
            continue
        field_names = {v.lower().strip() for v in col_map.values()}
        matches = header_cells & field_names
        score = len(matches)
        # Prefer the mapping with more matches;
        # on tie, prefer the one where a higher fraction of its fields matched
        if score > best_score or (score == best_score and score > 0
                                  and len(field_names) < len(SHEET_MAPPINGS.get(best_type, {}).get("columns", {}))):
            best_score = score
            best_type = sheet_type_key

    # Require at least 2 field name matches to be confident
    if best_score >= 2:
        return best_type
    return ""


def read_csv_data(path: str, sheet_type: str, delimiter: str = ";") -> list[dict]:
    """
    Leer datos de un CSV aplicando el mapeo de columnas de SHEET_MAPPINGS.

    Auto-detecta la fila de encabezado y ajusta el inicio de datos para que
    funcione tanto con CSVs que tienen solo un header en la fila 1, como con
    plantillas que replican la estructura del Excel original (titulo + header).

    Args:
        path: ruta al archivo CSV.
        sheet_type: clave de SHEET_MAPPINGS (ej: "CARPETAS", "RTI DESFAVORABLES").
        delimiter: separador de columnas (default: ';').

    Returns:
        Lista de dicts con campos mapeados + _source_sheet + _source_row.
    """
    mapping_config = SHEET_MAPPINGS.get(sheet_type, {})
    column_mapping = mapping_config.get("columns", {})

    all_rows = _read_all_rows(path, delimiter)
    data_start = _detect_data_start(all_rows, sheet_type)
    start_idx = data_start - 1
    records = []

    for row_idx in range(start_idx, len(all_rows)):
        csv_row = all_rows[row_idx]
        record = {"_source_sheet": sheet_type, "_source_row": row_idx + 1}
        has_data = False

        for col_idx, field_name in column_mapping.items():
            list_idx = int(col_idx) - 1
            if list_idx < len(csv_row):
                val = csv_row[list_idx].strip()
                if val:
                    has_data = True
                    record[field_name] = val

        if has_data:
            records.append(record)

    return records


def get_csv_info(path: str, sheet_type: str, delimiter: str = ";") -> dict:
    """
    Retorna info basica del CSV para el tipo de plantilla dado.

    Args:
        path: ruta al archivo CSV.
        sheet_type: clave de SHEET_MAPPINGS.
        delimiter: separador de columnas (default: ';').

    Returns:
        dict con rows, columns, preview (lista de hasta 3 dicts Col1..ColN),
        has_mapping (bool).
    """
    all_rows = _read_all_rows(path, delimiter)
    data_start = _detect_data_start(all_rows, sheet_type)
    start_idx = data_start - 1

    max_cols = 0
    data_rows = 0
    preview: list[dict] = []

    for row_idx in range(start_idx, len(all_rows)):
        csv_row = all_rows[row_idx]
        has_data = any(cell.strip() for cell in csv_row)
        if has_data:
            data_rows += 1
            if len(csv_row) > max_cols:
                max_cols = len(csv_row)

            if len(preview) < 3:
                row_data = {}
                for col_i, val in enumerate(csv_row):
                    val_stripped = val.strip()
                    if val_stripped:
                        row_data[f"Col{col_i + 1}"] = val_stripped[:80]
                if row_data:
                    preview.append(row_data)

    return {
        "rows": data_rows,
        "columns": max_cols,
        "preview": preview,
        "has_mapping": sheet_type in SHEET_MAPPINGS,
    }
