"""Validaciones de datos: DNI, CUIL, email."""
import re


def validate_cuil(cuil: str) -> tuple[bool, str]:
    """Validar formato de CUIL argentino (XX-XXXXXXXX-X)."""
    if not cuil:
        return True, ""  # Opcional
    digits = re.sub(r'[^\d]', '', cuil)
    if len(digits) != 11:
        return False, "El CUIL debe tener 11 digitos"
    prefix = digits[:2]
    if prefix not in ("20", "23", "24", "27", "30", "33", "34"):
        return False, "CUIL invalido: prefijo debe ser 20, 23, 24, 27, 30, 33 o 34"
    return True, ""


def validate_dni(dni: str) -> tuple[bool, str]:
    """Validar formato de DNI."""
    if not dni:
        return True, ""
    digits = re.sub(r'[^\d]', '', dni)
    if len(digits) < 7 or len(digits) > 8:
        return False, "El DNI debe tener 7 u 8 digitos"
    return True, ""


def validate_email(email: str) -> tuple[bool, str]:
    """Validar formato de email."""
    if not email:
        return True, ""
    pattern = r'^[\w.\-+]+@[\w.\-]+\.\w{2,}$'
    if not re.match(pattern, email):
        return False, "Formato de email invalido"
    return True, ""


def validate_phone(phone: str) -> tuple[bool, str]:
    """Validar telefono argentino."""
    if not phone:
        return True, ""
    digits = re.sub(r'[^\d]', '', phone)
    if len(digits) < 7 or len(digits) > 13:
        return False, "Telefono invalido"
    return True, ""


def format_cuil(cuil: str) -> str:
    """Formatear CUIL a formato XX-XXXXXXXX-X."""
    digits = re.sub(r'[^\d]', '', cuil)
    if len(digits) == 11:
        return f"{digits[:2]}-{digits[2:10]}-{digits[10]}"
    return cuil
