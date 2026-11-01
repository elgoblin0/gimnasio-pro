"""Límites de la incorporación y del riesgo de abandono."""

from datetime import date, timedelta

import pytest

from gimnasio.reglas.acompanamiento import dia_de_incorporacion, razones_de_riesgo

HOY = date(2026, 11, 2)
ALTA_VIEJA = HOY - timedelta(days=300)


def hace(*dias):
    return tuple(HOY - timedelta(days=d) for d in dias)


def reglas(alta, visitas=(), ultimo_hasta=None):
    return [razon.regla for razon in razones_de_riesgo(alta, HOY, visitas, ultimo_hasta)]


@pytest.mark.parametrize(("dias", "esperado"), [(0, 1), (89, 90), (90, None), (-1, None)])
def test_dia_de_incorporacion(dias, esperado):
    assert dia_de_incorporacion(HOY - timedelta(days=dias), HOY) == esperado


@pytest.mark.parametrize(("dias", "esperado"), [(13, []), (14, ["ausencia"])])
def test_ausencia_habitual(dias, esperado):
    assert reglas(ALTA_VIEJA, hace(dias)) == esperado


@pytest.mark.parametrize(("dias", "esperado"), [(6, []), (7, ["ausencia"])])
def test_ausencia_durante_la_incorporacion(dias, esperado):
    assert reglas(HOY - timedelta(days=30), hace(dias)) == esperado


def test_sin_visitas_cuenta_desde_el_alta():
    assert reglas(HOY - timedelta(days=6)) == []
    razon = razones_de_riesgo(HOY - timedelta(days=7), HOY, (), None)[0]
    assert (razon.regla, dict(razon.datos)) == ("ausencia", {"dias": "7", "umbral": "7"})


def test_tendencia_exige_cuatro_visitas_anteriores():
    assert reglas(ALTA_VIEJA, hace(1, 30, 31, 32)) == []
    assert reglas(ALTA_VIEJA, hace(1, 2, 30, 31, 32, 33)) == ["tendencia"]
    assert reglas(ALTA_VIEJA, hace(1, 2, 3, 30, 31, 32, 33)) == []


def test_tendencia_separa_las_ventanas_de_cuatro_semanas():
    # La visita de hace 27 días es reciente; la de hace 28, anterior.
    assert reglas(ALTA_VIEJA, hace(1, 27, 28, 29, 30, 31)) == ["tendencia"]
    assert reglas(ALTA_VIEJA, hace(1, 28, 29, 30, 31)) == ["tendencia"]
    # Hace 56 días ya queda fuera de la ventana anterior.
    assert reglas(ALTA_VIEJA, hace(1, 29, 30, 31, 56)) == []


def test_membresia_vencida_es_una_senal():
    visitas = hace(1)
    assert reglas(ALTA_VIEJA, visitas, HOY) == []
    assert reglas(ALTA_VIEJA, visitas, HOY - timedelta(days=1)) == ["membresia_vencida"]
    assert reglas(ALTA_VIEJA, visitas, None) == []


def test_acumula_todas_las_razones():
    assert reglas(ALTA_VIEJA, hace(20, 30, 31, 32, 33), HOY - timedelta(days=1)) == [
        "ausencia",
        "tendencia",
        "membresia_vencida",
    ]
