"""Dias habiles de Argentina (lunes a viernes, sin feriados nacionales).

Incluye feriados inamovibles, feriados basados en Pascua (carnaval, viernes santo)
y feriados con reglas de dia habil (ej. tercer lunes de junio), para 2025-2030 y
años adyacentes mediante las mismas reglas.
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache


def _easter_sunday_western(year: int) -> date:
    """Domingo de Pascua (calendario gregoriano, algoritmo de Meeus)."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    """n-esimo weekday del mes (0=lunes .. 6=domingo), n empieza en 1."""
    first = date(year, month, 1)
    # dias hasta el primer weekday deseado
    delta = (weekday - first.weekday()) % 7
    d0 = first + timedelta(days=delta)
    return d0 + timedelta(weeks=n - 1)


@lru_cache(maxsize=128)
def get_feriados_año(year: int) -> list[date]:
    """Feriados nacionales no laborables (aproximacion para uso en plazos).

    Reglas principales (Argentina):
    - Inamovibles: 1/1, 24/3, 2/4, 1/5, 25/5, 9/7, 8/12, 25/12
    - Pascua: viernes santo; carnaval lunes y martes (antes del miercoles de ceniza)
    - Trasladables legales habituales: 3er lunes junio (Güemes), 3er lunes agosto
      (San Martin), 2do lunes octubre (diversidad cultural), 4to lunes noviembre
      (soberania nacional)
    """
    easter = _easter_sunday_western(year)
    ash_wednesday = easter - timedelta(days=46)
    carnival_monday = ash_wednesday - timedelta(days=2)
    carnival_tuesday = ash_wednesday - timedelta(days=1)
    good_friday = easter - timedelta(days=2)

    fijos = [
        date(year, 1, 1),
        date(year, 3, 24),
        date(year, 4, 2),
        date(year, 5, 1),
        date(year, 5, 25),
        date(year, 7, 9),
        date(year, 12, 8),
        date(year, 12, 25),
    ]
    moviles_regla = [
        carnival_monday,
        carnival_tuesday,
        good_friday,
        _nth_weekday_of_month(year, 6, 0, 3),   # 3er lunes junio - Güemes
        _nth_weekday_of_month(year, 8, 0, 3),   # 3er lunes agosto - San Martin
        _nth_weekday_of_month(year, 10, 0, 2),  # 2do lunes octubre
        _nth_weekday_of_month(year, 11, 0, 4),  # 4to lunes noviembre
    ]

    todos = set(fijos + moviles_regla)
    return sorted(todos)


def es_dia_habil(d: date) -> bool:
    """True si es dia laborable (no sabado, domingo ni feriado nacional)."""
    if d.weekday() >= 5:
        return False
    feriados = set(get_feriados_año(d.year))
    return d not in feriados


def restar_dias_habiles(fecha_objetivo: date, dias: int) -> date:
    """Retrocede `dias` dias habiles desde `fecha_objetivo` (excluye el propio dia).

    Si `dias` es 0, devuelve `fecha_objetivo`. El resultado es el primer dia habil
    tal que entre ese dia (inclusive) y `fecha_objetivo` (exclusive) hay exactamente
    `dias` dias habiles... En realidad lo usual es: "N dias habiles ANTES del plazo"
    = la fecha de alerta es la que queda N dias habiles antes del vencimiento.

    Interpretacion: partir de `fecha_objetivo` y retroceder hasta contar `dias`
    dias habiles (sin contar fecha_objetivo si no es habil?).

    Convencion usada: retroceder dia a dia desde fecha_objetivo - 1 dia, contando
    solo dias habiles hasta llegar a `dias` contados.

    Ejemplo: si fecha_objetivo es lunes y dias=1, se busca el viernes anterior
    (un dia habil antes del lunes).
    """
    if dias <= 0:
        return fecha_objetivo
    cur = fecha_objetivo - timedelta(days=1)
    count = 0
    while count < dias:
        if es_dia_habil(cur):
            count += 1
            if count == dias:
                return cur
        cur -= timedelta(days=1)
    return cur


def sumar_dias_habiles(fecha_inicio: date, dias: int) -> date:
    """Avanza `dias` dias habiles desde `fecha_inicio` (no cuenta fecha_inicio)."""
    if dias <= 0:
        return fecha_inicio
    cur = fecha_inicio + timedelta(days=1)
    count = 0
    while count < dias:
        if es_dia_habil(cur):
            count += 1
            if count == dias:
                return cur
        cur += timedelta(days=1)
    return cur
