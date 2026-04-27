"""Tests unitarios para dias habiles Argentina."""
from datetime import date

from core.dias_habiles import (
    es_dia_habil,
    get_feriados_año,
    restar_dias_habiles,
    sumar_dias_habiles,
)


def test_ano_nuevo_2025_no_habil():
    assert not es_dia_habil(date(2025, 1, 1))


def test_sabado_domingo_no_habil():
    assert not es_dia_habil(date(2025, 1, 4))  # sabado
    assert not es_dia_habil(date(2025, 1, 5))  # domingo


def test_lunes_normal_habil():
    assert es_dia_habil(date(2025, 1, 6))


def test_get_feriados_año_ordenado_y_sin_duplicados():
    f = get_feriados_año(2025)
    assert f == sorted(f)
    assert len(f) == len(set(f))


def test_restar_un_dia_habil_desde_lunes():
    # Lunes 6 ene 2025 -> un dia habil antes = viernes 3 ene
    assert restar_dias_habiles(date(2025, 1, 6), 1) == date(2025, 1, 3)


def test_restar_cero_devuelve_referencia():
    d = date(2025, 6, 10)
    assert restar_dias_habiles(d, 0) == d


def test_sumar_y_restar_consistentes():
    base = date(2025, 1, 6)  # lunes
    forward = sumar_dias_habiles(base, 1)
    assert forward == date(2025, 1, 7)
    back = restar_dias_habiles(forward, 1)
    assert back == base


def test_restar_muchos_dias_habiles_monotono():
    ref = date(2026, 6, 15)
    a30 = restar_dias_habiles(ref, 30)
    a60 = restar_dias_habiles(ref, 60)
    assert a60 < a30 < ref
