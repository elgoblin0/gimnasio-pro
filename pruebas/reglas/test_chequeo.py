"""Freno 4: vectores y monotonía de carga y series para todas las respuestas."""

from dataclasses import replace
from decimal import Decimal

import pytest

from gimnasio.comun.tipos import Chequeo, ProgramaEntrenamiento, SesionPlanificada
from gimnasio.reglas.sesion import proponer_sesion
from pruebas.reglas.test_progresion import EJERCICIO, entrada, historial


@pytest.mark.parametrize(
    "chequeo,series,carga",
    [
        (None, 3, "42.5"),
        (Chequeo(3, 5), 3, "42.5"),
        (Chequeo(2, 5), 2, "40"),
        (Chequeo(5, 1), 2, "40"),
    ],
)
def test_vectores_chequeo(chequeo, series, carga):
    propuesta = proponer_sesion(replace(entrada(), chequeo=chequeo))
    assert propuesta.prescripcion[0].series == series
    assert propuesta.prescripcion[0].carga == Decimal(carga)
    assert ("chequeo_desfavorable" in propuesta.frenos) == (series == 2)
    if chequeo is None:
        assert "sin_chequeo" in {r.regla for r in propuesta.explicacion}


def test_freno_4_chequeo_nunca_sube():
    for sesiones in ((), (historial(),), (historial((10, 10, 10)),), (historial((6, 6, 6)), historial((7, 7, 7)))):
        base = entrada(sesiones)
        normal = proponer_sesion(base).prescripcion[0]
        for sueno in range(1, 6):
            for energia in range(1, 6):
                ajustada = proponer_sesion(replace(base, chequeo=Chequeo(sueno, energia))).prescripcion[0]
                assert ajustada.series <= normal.series
                assert ajustada.carga <= normal.carga


def test_chequeo_serie_minima_uno_sin_historial_ni_carga():
    ejercicio = replace(EJERCICIO, series=1, carga=None)
    base = replace(
        entrada(()),
        programa=ProgramaEntrenamiento((SesionPlanificada("proxima", (ejercicio,)),)),
        chequeo=Chequeo(1, 1),
    )
    propuesta = proponer_sesion(base)
    assert propuesta.prescripcion[0].series == 1
    assert propuesta.prescripcion[0].carga is None
    assert propuesta.frenos == ("chequeo_desfavorable",)
