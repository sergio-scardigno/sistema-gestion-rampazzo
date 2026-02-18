"""Servicio de datos de oficinas ANSES y localidades argentinas.

Carga los datos una sola vez desde los archivos fuente y los mantiene en cache.
- Oficinas ANSES: anses_oficinas/oficinas_anses_parsed.json
- Localidades: anses_oficinas/localidades.csv
"""
import csv
import json
import re
import unicodedata
from pathlib import Path
from typing import Optional

from config import BASE_DIR as _BASE_DIR

_OFICINAS_JSON = _BASE_DIR / "anses_oficinas" / "oficinas_anses_parsed.json"
_LOCALIDADES_CSV = _BASE_DIR / "anses_oficinas" / "localidades.csv"

# ---------------------------------------------------------------------------
# Cache interno
# ---------------------------------------------------------------------------
_oficinas_data: list[dict] | None = None
_localidades_data: list[dict] | None = None


# ===================================================================
# OFICINAS ANSES
# ===================================================================

def _load_oficinas() -> list[dict]:
    """Carga el JSON de oficinas una sola vez."""
    global _oficinas_data
    if _oficinas_data is not None:
        return _oficinas_data
    try:
        with open(_OFICINAS_JSON, "r", encoding="utf-8") as f:
            _oficinas_data = json.load(f)
    except Exception:
        _oficinas_data = []
    return _oficinas_data


def _normalizar(texto: str) -> str:
    """Elimina acentos y pasa a minusculas para comparaciones."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sin_acentos.lower().strip()


_PROVINCIAS_ARGENTINAS = {
    _normalizar(p) for p in [
        "Buenos Aires", "Capital Federal", "Catamarca", "Chaco", "Chubut",
        "Córdoba", "Corrientes", "Entre Ríos", "Formosa", "Jujuy",
        "La Pampa", "La Rioja", "Mendoza", "Misiones", "Neuquén",
        "Río Negro", "Salta", "San Juan", "San Luis", "Santa Cruz",
        "Santa Fe", "Santiago del Estero", "Tierra del Fuego", "Tucumán",
    ]
}


def _es_provincia_valida(texto: str) -> bool:
    """Verifica si un texto es un nombre de provincia argentina valido."""
    return _normalizar(texto) in _PROVINCIAS_ARGENTINAS


def _provincia_efectiva(d: dict) -> str:
    """Retorna la provincia real de una oficina considerando province y province_detail.

    Muchas oficinas de Buenos Aires tienen el campo 'province' incorrecto
    (ej: 'Tucuman') pero 'province_detail' correcto (ej: 'Buenos Aires').
    Priorizamos province_detail cuando es un nombre de provincia valido.
    """
    prov = (d.get("province") or "").strip()
    prov_detail = (d.get("province_detail") or "").strip()
    # Si province_detail tiene un valor diferente y es una provincia valida, usarlo
    if prov_detail and prov_detail != prov and _es_provincia_valida(prov_detail):
        return prov_detail
    return prov


def get_provincias() -> list[str]:
    """Retorna la lista de provincias ordenadas alfabeticamente."""
    data = _load_oficinas()
    provincias = set()
    for d in data:
        prov = _provincia_efectiva(d)
        if prov:
            provincias.add(prov)
    return sorted(provincias)


def get_oficinas(provincia: str) -> list[dict]:
    """Retorna las oficinas de una provincia.

    Usa _provincia_efectiva() para considerar tanto 'province' como
    'province_detail', corrigiendo datos erroneos del JSON.

    Cada dict contiene:
        office_name, address, city, region, schedule, province
    """
    data = _load_oficinas()
    result = []
    for d in data:
        prov_real = _provincia_efectiva(d)
        if prov_real == provincia:
            result.append({
                "office_name": d.get("repeated_name") or d.get("office_name", ""),
                "address": d.get("address", "") or "",
                "city": d.get("city", "") or "",
                "region": d.get("region", "") or "",
                "schedule": d.get("schedule", "") or "",
                "province": prov_real,
            })
    # Ordenar por nombre
    result.sort(key=lambda x: x["office_name"])
    return result


def get_oficinas_nombres(provincia: str) -> list[str]:
    """Retorna solo los nombres de oficinas de una provincia (para combos)."""
    oficinas = get_oficinas(provincia)
    return [o["office_name"] for o in oficinas]


def get_oficina_info(nombre_oficina: str) -> dict | None:
    """Busca info de una oficina por nombre (busqueda case-insensitive).

    Retorna dict con: office_name, address, city, region, schedule, province
    o None si no se encuentra.
    """
    data = _load_oficinas()
    nombre_lower = nombre_oficina.lower().strip()
    for d in data:
        # Buscar en repeated_name y office_name
        rn = (d.get("repeated_name") or "").lower().strip()
        on = (d.get("office_name") or "").lower().strip()
        if nombre_lower == rn or nombre_lower == on:
            return {
                "office_name": d.get("repeated_name") or d.get("office_name", ""),
                "address": d.get("address", "") or "",
                "city": d.get("city", "") or "",
                "region": d.get("region", "") or "",
                "schedule": d.get("schedule", "") or "",
                "province": _provincia_efectiva(d),
            }
    return None


def get_provincia_de_oficina(nombre_oficina: str) -> str:
    """Retorna la provincia a la que pertenece una oficina, o cadena vacia."""
    info = get_oficina_info(nombre_oficina)
    return info["province"] if info else ""


def formato_tooltip_oficina(info: dict) -> str:
    """Genera texto para tooltip a partir de un dict de oficina."""
    lines = []
    if info.get("address"):
        lines.append(f"Direccion: {info['address']}")
    if info.get("city"):
        lines.append(f"Ciudad: {info['city']}")
    if info.get("schedule"):
        lines.append(f"Horario: {info['schedule']}")
    if info.get("region"):
        lines.append(f"Region: {info['region']}")
    return "\n".join(lines) if lines else ""


def _parsear_nombre_localidad(localidad_label: str) -> str:
    """Extrae el nombre limpio de una localidad formateada.

    Acepta formatos como:
        'CHASCOMUS (CP 7130) - Buenos Aires'  -> 'chascomus'
        'Chascomus'                            -> 'chascomus'
        'CHASCOMUS'                            -> 'chascomus'
    """
    if not localidad_label:
        return ""
    # Quitar todo desde ' (CP' o ' -' en adelante
    nombre = re.split(r"\s*\(CP|\s*-\s*", localidad_label, maxsplit=1)[0]
    return _normalizar(nombre)


def buscar_oficina_por_localidad(nombre_localidad: str) -> dict | None:
    """Busca la oficina ANSES que corresponde a una localidad.

    Intenta encontrar una oficina cuyo campo 'city' coincida con la localidad.
    Si no hay match por city, busca en 'office_name' y 'repeated_name'
    (ej: 'UDAI CHASCOMUS' matchea con localidad 'Chascomus').

    Args:
        nombre_localidad: Nombre de localidad, puede venir formateado
            como 'CHASCOMUS (CP 7130) - Buenos Aires' o solo 'Chascomus'.

    Returns:
        Dict con office_name, address, city, region, schedule, province
        o None si no se encuentra.
    """
    ciudad = _parsear_nombre_localidad(nombre_localidad)
    if not ciudad:
        return None

    data = _load_oficinas()

    # 1) Buscar coincidencia exacta por campo 'city'
    for d in data:
        city = _normalizar(d.get("city") or "")
        if city and city == ciudad:
            return {
                "office_name": d.get("repeated_name") or d.get("office_name", ""),
                "address": d.get("address", "") or "",
                "city": d.get("city", "") or "",
                "region": d.get("region", "") or "",
                "schedule": d.get("schedule", "") or "",
                "province": _provincia_efectiva(d),
            }

    # 2) Buscar en repeated_name / office_name (ej: 'UDAI Chascomus')
    for d in data:
        rn = _normalizar(d.get("repeated_name") or "")
        on = _normalizar(d.get("office_name") or "")
        # Buscar si el nombre de la ciudad aparece como palabra en el nombre
        # de la oficina (ej: "udai chascomus" contiene "chascomus")
        if ciudad in rn or ciudad in on:
            # Verificar que sea una palabra completa (no substring parcial)
            # ej: "azul" no debe matchear con "azules"
            pattern = r'\b' + re.escape(ciudad) + r'\b'
            if re.search(pattern, rn) or re.search(pattern, on):
                return {
                    "office_name": d.get("repeated_name") or d.get("office_name", ""),
                    "address": d.get("address", "") or "",
                    "city": d.get("city", "") or "",
                    "region": d.get("region", "") or "",
                    "schedule": d.get("schedule", "") or "",
                    "province": _provincia_efectiva(d),
                }

    return None


# ===================================================================
# LOCALIDADES ARGENTINAS
# ===================================================================

def _load_localidades() -> list[dict]:
    """Carga el CSV de localidades una sola vez."""
    global _localidades_data
    if _localidades_data is not None:
        return _localidades_data
    try:
        with open(_LOCALIDADES_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            _localidades_data = [
                {
                    "nombre": row.get("nombre", "").strip(),
                    "cp": row.get("cp", "").strip(),
                    "provincia": row.get("nombreProvincia", "").strip(),
                }
                for row in reader
                if row.get("nombre", "").strip()
            ]
    except Exception:
        _localidades_data = []
    return _localidades_data


def get_localidades(provincia: Optional[str] = None) -> list[dict]:
    """Retorna localidades filtradas por provincia (o todas si provincia=None).

    Cada dict contiene: nombre, cp, provincia
    """
    data = _load_localidades()
    if provincia:
        data = [d for d in data if d["provincia"] == provincia]
    return data


def get_localidades_labels(provincia: Optional[str] = None) -> list[str]:
    """Retorna strings formateados para usar en autocompletado.

    Formato: 'NOMBRE (CP XXXX) - Provincia'
    """
    locs = get_localidades(provincia)
    labels = []
    for loc in locs:
        cp_part = f" (CP {loc['cp']})" if loc["cp"] else ""
        prov_part = f" - {loc['provincia']}" if loc["provincia"] else ""
        labels.append(f"{loc['nombre']}{cp_part}{prov_part}")
    # Ordenar alfabeticamente
    labels.sort()
    return labels


def get_todas_localidades_labels() -> list[str]:
    """Retorna TODAS las localidades formateadas (sin filtro de provincia)."""
    return get_localidades_labels(provincia=None)


def get_provincias_localidades() -> list[str]:
    """Retorna las provincias disponibles en el CSV de localidades."""
    data = _load_localidades()
    provincias = sorted({d["provincia"] for d in data if d["provincia"]})
    return provincias
