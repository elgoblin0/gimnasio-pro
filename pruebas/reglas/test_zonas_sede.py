"""Vectores de ubicación en las zonas de la sede."""

from datetime import UTC, datetime, timedelta

import pytest

from gimnasio.reglas.zonas_sede import ubicar_en_zona

AHORA = datetime(2026, 10, 27, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    "series,entrada,esperada",
    [
        ([(19, "cinta")], 60, "cardio"),
        ([(20, "barra")], 60, "peso_libre"),
        ([(1, "polea")], 60, "musculacion"),
        ([(1, "m?quina de remo")], 60, "musculacion"),
        ([(21, "cinta")], 60, "en_la_sede"),
        ([(19, "cinta")], 10, "en_la_sede"),
        ([(1, "desconocido")], 60, "funcional"),
        ([(1, "")], 60, "funcional"),
        ([(1, "cinta"), (19, "barra")], 60, "cardio"),
        ([(-1, "cinta")], 60, "en_la_sede"),
        ([], 60, "en_la_sede"),
    ],
)
def test_ubicacion(series, entrada, esperada):
    assert (
        ubicar_en_zona(
            [(AHORA - timedelta(minutes=minutos), equipo) for minutos, equipo in series],
            AHORA,
            AHORA - timedelta(minutes=entrada),
        )
        == esperada
    )
