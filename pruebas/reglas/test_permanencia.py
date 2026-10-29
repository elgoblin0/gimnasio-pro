"""Vectores de permanencia habitual y límites de visitas por conciliar."""

from dataclasses import FrozenInstanceError

import pytest

from gimnasio.comun.tipos import PermanenciaHabitual, Razon
from gimnasio.reglas.permanencia import (
    VERSION_PERMANENCIA,
    calcular_permanencia_habitual,
    es_visita_por_conciliar,
)


@pytest.mark.parametrize(
    "duraciones,esperada",
    [
        ((90, 30, 60, 120, 45), PermanenciaHabitual(True, 5, 60, 45, 90)),
        ((10, 20, 30, 40, 50, 60, 70, 80), PermanenciaHabitual(True, 8, 45, 28, 62)),
        ((1, 2, 3, 4), PermanenciaHabitual(False, 4)),
        ((), PermanenciaHabitual(False, 0)),
    ],
)
def test_permanencia_habitual(duraciones, esperada):
    assert calcular_permanencia_habitual(duraciones) == esperada


@pytest.mark.parametrize(
    "habitual,duracion,umbral,esperado",
    [
        (PermanenciaHabitual(True, 5, 60), 180, 180, False),
        (PermanenciaHabitual(True, 5, 60), 181, 180, True),
        (PermanenciaHabitual(True, 5, 120), 240, 240, False),
        (PermanenciaHabitual(True, 5, 120), 241, 240, True),
        (PermanenciaHabitual(False, 0), 240, 240, False),
        (PermanenciaHabitual(False, 0), 241, 240, True),
    ],
)
def test_umbral_y_razon(habitual, duracion, umbral, esperado):
    resultado, razon = es_visita_por_conciliar(duracion, habitual)
    assert resultado is esperado
    assert razon == Razon(
        "visita_por_conciliar",
        VERSION_PERMANENCIA,
        (
            ("duracion_minutos", str(duracion)),
            ("umbral_minutos", str(umbral)),
            ("suficiente", "si" if habitual.suficiente else "no"),
        ),
    )


def test_permanencia_inmutable():
    habitual = calcular_permanencia_habitual((30, 40, 50, 60, 70))
    with pytest.raises(FrozenInstanceError):
        habitual.mediana = 99
