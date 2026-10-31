"""Renovaciones inclusivas sin solapamientos ni días perdidos."""

from datetime import date

import pytest

from gimnasio.reglas.membresia import vigencia_renovada


@pytest.mark.parametrize(
    "ultimo,desde,hasta",
    [
        (date(2026, 10, 30), date(2026, 10, 31), date(2026, 11, 29)),
        (date(2026, 10, 27), date(2026, 10, 28), date(2026, 11, 26)),
        (date(2026, 10, 26), date(2026, 10, 27), date(2026, 11, 25)),
        (None, date(2026, 10, 27), date(2026, 11, 25)),
    ],
)
def test_vigencia_renovada(ultimo, desde, hasta):
    assert vigencia_renovada(date(2026, 10, 27), ultimo, 30) == (desde, hasta)


def test_un_dia_y_fin_de_anio():
    assert vigencia_renovada(date(2026, 12, 31), date(2026, 12, 31), 1) == (date(2027, 1, 1), date(2027, 1, 1))


@pytest.mark.parametrize("duracion", [0, -1, True, 1.5])
def test_duracion_invalida(duracion):
    with pytest.raises(ValueError):
        vigencia_renovada(date(2026, 10, 27), None, duracion)
