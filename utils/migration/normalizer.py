"""
Motor de normalizacion de datos del Excel.
Extrae telefonos, emails, limpia nombres, normaliza CUIL, parsea fechas.
"""
import re
from datetime import datetime

# Regex para telefonos argentinos (7+ digitos seguidos, prefijo tipico)
_RE_PHONE = re.compile(r'\b(\d{7,11})\b')
# Regex para emails
_RE_EMAIL = re.compile(r'[\w.\-+]+@[\w.\-]+\.\w+', re.IGNORECASE)
# Regex para texto entre parentesis
_RE_PAREN = re.compile(r'\([^)]*\)')
# Regex para CUIL con guiones
_RE_CUIL_DASH = re.compile(r'(\d{2})-?(\d{7,8})-?(\d)')


def extract_phones(text: str) -> tuple[str, list[str]]:
    """
    Extraer telefonos de un texto (ej: campo nombre).
    Returns: (texto_limpio, lista_de_telefonos)
    """
    if not text:
        return text, []
    phones = []
    cleaned = text
    for match in _RE_PHONE.finditer(text):
        num = match.group(1)
        # Solo considerar como telefono si tiene 7-11 digitos y no es un CUIL (11 digitos empezando con 20/23/24/27)
        if len(num) >= 7:
            if len(num) == 11 and num[:2] in ("20", "23", "24", "27"):
                continue  # Es un CUIL, no un telefono
            phones.append(num)
            cleaned = cleaned.replace(num, "", 1)

    # Limpiar espacios multiples
    cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
    return cleaned, phones


def extract_email(text: str) -> tuple[str, str]:
    """
    Extraer email de un texto.
    Returns: (texto_limpio, email)
    """
    if not text:
        return text, ""
    match = _RE_EMAIL.search(text)
    if match:
        email = match.group(0)
        cleaned = text.replace(email, "").strip()
        cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
        return cleaned, email.lower()
    return text, ""


def extract_parenthetical_notes(text: str) -> tuple[str, str]:
    """
    Extraer notas entre parentesis de un texto.
    Returns: (texto_sin_parentesis, notas)
    """
    if not text:
        return text, ""
    notes = []
    for match in _RE_PAREN.finditer(text):
        note = match.group(0)
        notes.append(note)
    cleaned = _RE_PAREN.sub("", text)
    cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
    return cleaned, " ".join(notes)


def clean_name(raw_name: str) -> dict:
    """
    Procesar campo nombre crudo del Excel.
    Returns dict con: nombre, telefonos, email, notas
    """
    if not raw_name or not isinstance(raw_name, str):
        return {"nombre": str(raw_name) if raw_name else "", "telefonos": [], "email": "", "notas": ""}

    text = raw_name.strip()

    # 1. Extraer email
    text, email = extract_email(text)

    # 2. Extraer telefonos
    text, phones = extract_phones(text)

    # 3. Extraer notas entre parentesis
    text, notes = extract_parenthetical_notes(text)

    # 4. Limpiar nombre
    nombre = text.strip().upper()
    # Quitar "TEL" suelto, barras, etc.
    nombre = re.sub(r'\bTEL\b', '', nombre, flags=re.IGNORECASE)
    nombre = re.sub(r'\s*/\s*', ' ', nombre)
    nombre = re.sub(r'\s{2,}', ' ', nombre).strip()

    return {
        "nombre": nombre,
        "telefonos": phones,
        "email": email,
        "notas": notes,
    }


def normalize_cuil(raw_cuil) -> dict:
    """
    Normalizar campo CUIL/DNI.
    Returns dict con: cuil, cuil_secundario, nota
    """
    if raw_cuil is None:
        return {"cuil": "", "cuil_secundario": "", "nota": ""}

    text = str(raw_cuil).strip()

    # Remove .0 from numeric conversion
    if text.endswith(".0"):
        text = text[:-2]

    # Handle double CUIL  "20052121753 (EL) // 27099801870 (ELLA)"
    if "//" in text:
        parts = text.split("//")
        cuil1_data = normalize_cuil(parts[0].strip())
        cuil2_data = normalize_cuil(parts[1].strip()) if len(parts) > 1 else {"cuil": ""}
        nota = ""
        for p in parts:
            n = _RE_PAREN.findall(p)
            if n:
                nota += " ".join(n) + " "
        return {
            "cuil": cuil1_data["cuil"],
            "cuil_secundario": cuil2_data["cuil"],
            "nota": nota.strip(),
        }

    if "/" in text and "//" not in text:
        parts = text.split("/")
        cuil1 = re.sub(r'[^\d]', '', parts[0])
        cuil2 = re.sub(r'[^\d]', '', parts[1]) if len(parts) > 1 else ""
        return {"cuil": cuil1, "cuil_secundario": cuil2, "nota": ""}

    # Remove dashes and parenthetical notes
    nota = " ".join(_RE_PAREN.findall(text))
    text = _RE_PAREN.sub("", text)
    cuil = re.sub(r'[^\d]', '', text)

    return {"cuil": cuil, "cuil_secundario": "", "nota": nota}


def parse_date(raw_date) -> str:
    """Parsear fecha a formato ISO yyyy-MM-dd."""
    if raw_date is None:
        return ""

    if isinstance(raw_date, datetime):
        return raw_date.strftime("%Y-%m-%d")

    text = str(raw_date).strip()

    # Remove time portion
    if " 00:00:00" in text:
        text = text.replace(" 00:00:00", "")

    # Already ISO format
    if re.match(r'^\d{4}-\d{2}-\d{2}', text):
        return text[:10]

    # Try dd/mm/yyyy
    match = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', text)
    if match:
        d, m, y = match.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}"

    # Try d/mm/yyyy with typos like 5/772022
    match = re.match(r'^(\d{1,2})/(\d{1,2})(\d{4})$', text)
    if match:
        d, m, y = match.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}"

    return text


def detect_estado(text: str) -> str:
    """Detectar estado a partir de texto libre."""
    if not text:
        return ""
    t = text.upper()
    if "FALLECIO" in t or "FALLECIDO" in t:
        return "Fallecido"
    if "DESFAVORABLE" in t:
        return "Desfavorable"
    if "FAVORABLE" in t:
        return "Favorable"
    if "GUARDADA" in t:
        return "Guardada"
    if "INICIADA" in t or "INICIADO" in t:
        return "Iniciado"
    if "LIQUIDACION" in t:
        return "En liquidacion"
    if "EN TRAMITE" in t:
        return "En tramite"
    if "FALTA EDAD" in t or "FALTA DOC" in t:
        return "En espera"
    return ""


def detect_tipo_tramite(text: str) -> dict:
    """Detectar tipo de tramite y responsable de texto como 'RTI/MARIANO'."""
    if not text:
        return {"tipo": "", "responsable": ""}
    t = text.strip().upper()

    # Patron TIPO/RESPONSABLE
    if "/" in t:
        parts = t.split("/", 1)
        tipo_raw = parts[0].strip()
        resp = parts[1].strip() if len(parts) > 1 else ""
    else:
        tipo_raw = t
        resp = ""

    # Map tipo keywords
    tipo_map = {
        "JUB": "Jubilacion",
        "JUBILACION": "Jubilacion",
        "RTI": "RTI",
        "PUAM": "PUAM",
        "PENSION": "Pension",
        "RECO": "Reconocimiento",
        "MINUSVALIA": "Minusvalia",
        "MISNUVALIA": "Minusvalia",
        "LABORAL": "Laboral",
        "AMPARO": "Amparo",
        "REAJUSTE": "Reajuste",
    }

    tipo = ""
    for key, val in tipo_map.items():
        if key in tipo_raw:
            tipo = val
            break

    if not tipo:
        tipo = tipo_raw

    return {"tipo": tipo, "responsable": resp}
