"""Vectores de récord personal por ejercicio hecho y medida."""

from dataclasses import replace
from decimal import Decimal

import pytest

from gimnasio.comun.tipos import SerieRealizada
from gimnasio.reglas.records import detectar_records


def serie(carga="80", repeticiones=10, **campos):
    return SerieRealizada("sesion", "sentadilla", 1, repeticiones, Decimal(carga), **campos)


@pytest.mark.parametrize(
    "actual,historial,esperados",
    [
        (serie("82.5"), (serie(),), (("carga_maxima", Decimal("80")),)),
        (serie(repeticiones=11), (serie(),), (("repeticiones_a_carga", 10),)),
        (serie("75", 11), (serie(), serie("70", 20)), (("repeticiones_a_carga", 10),)),
        (serie(), (serie(),), ()),
        (serie(), (), ()),
        (serie(), (serie("100", vigente=False),), ()),
        (serie("82.5"), (serie(), serie("100", vigente=False)), (("carga_maxima", Decimal("80")),)),
        (serie("75", 9), (serie(),), ()),
        (serie("82.5", ejercicio_hecho_id="alternativa"), (serie(),), ()),
        (
            serie("82.5", ejercicio_hecho_id="alternativa"),
            (serie("80", ejercicio_hecho_id="alternativa"), serie("100")),
            (("carga_maxima", Decimal("80")),),
        ),
        (serie("82.5", vigente=False), (serie(),), ()),
        (replace(serie(), carga=None), (serie(),), ()),
        (serie(), (replace(serie(), carga=None),), ()),
        (serie(repeticiones=None), (serie(),), ()),
    ],
)
def test_detectar_records(actual, historial, esperados):
    resultado = detectar_records(actual, historial)
    assert tuple((r.medida, r.marca_anterior) for r in resultado) == esperados
    assert all(r.explicacion.version == "1.0.0" for r in resultado)
