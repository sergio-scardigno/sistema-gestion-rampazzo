"""Formateo de datos para presentacion."""
from datetime import datetime


def format_date(iso_date: str) -> str:
    """Formatear fecha ISO a dd/mm/yyyy."""
    if not iso_date or len(iso_date) < 10:
        return iso_date or ""
    try:
        dt = datetime.fromisoformat(iso_date[:10])
        return dt.strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return iso_date


def format_currency(amount) -> str:
    """Formatear monto como moneda."""
    try:
        return f"${float(amount):,.2f}"
    except (ValueError, TypeError):
        return "$0.00"


def format_cuil_display(cuil: str) -> str:
    """Formatear CUIL para display."""
    if not cuil:
        return ""
    digits = "".join(c for c in cuil if c.isdigit())
    if len(digits) == 11:
        return f"{digits[:2]}-{digits[2:10]}-{digits[10]}"
    return cuil
