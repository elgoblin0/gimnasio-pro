"""Lo que cuenta el resumen semanal y la semana cerrada que usa por omisión."""

from datetime import date
from decimal import Decimal

import pytest

from gimnasio.reglas.resumen_semanal import (
    EjercicioDeLaSemana,
    SerieDeLaSemana,
    SesionDeLaSemana,
    resumir_semana,
    ultima_semana_cerrada,
)

SENTADILLA = EjercicioDeLaSemana("ep-1", "Sentadilla", 3)
CAMINATA = EjercicioDeLaSemana("ep-2", "Caminata", 1)


def razon(regla):
    return {"regla": regla, "version": "3.4.0", "datos": {"ejercicio_id": "ep-1"}}


def serie(ejercicio, repeticiones=None, duracion=None, distancia=None):
    return SerieDeLaSemana(ejercicio.id, repeticiones, duracion, distancia)


@pytest.mark.parametrize(
    ("hoy", "lunes"),
    [
        (date(2026, 11, 2), date(2026, 10, 26)),  # Lunes: la semana que empieza hoy sigue abierta.
        (date(2026, 11, 8), date(2026, 10, 26)),  # Domingo: todavía es la misma semana abierta.
        (date(2026, 11, 9), date(2026, 11, 2)),
    ],
)
def test_ultima_semana_cerrada(hoy, lunes):
    assert ultima_semana_cerrada(hoy) == lunes


def test_semana_sin_actividad():
    resumen = resumir_semana((), 0, 2)
    assert resumen["sin_actividad"] is True
    assert resumen["cumplido"] == {
        "sesiones_realizadas": 0,
        "sesiones_planificadas": 2,
        "series": 0,
        "volumen": {"repeticiones": 0, "duracion": 0, "distancia": "0"},
        "visitas": 0,
    }
    assert resumen["pendientes"] == {"series": [], "sesiones_sin_realizar": 2}


def test_una_visita_sin_sesion_es_actividad():
    assert resumir_semana((), 1, 0)["sin_actividad"] is False


def test_cuenta_series_volumen_y_pendientes():
    sesion = SesionDeLaSemana(
        "sr-1",
        (SENTADILLA, CAMINATA),
        (
            serie(SENTADILLA, repeticiones=10),
            serie(SENTADILLA, repeticiones=8),
            serie(CAMINATA, duracion=120, distancia=Decimal("1500.25")),
        ),
        (),
    )
    resumen = resumir_semana((sesion,), 3, 2)
    assert resumen["cumplido"]["series"] == 3
    assert resumen["cumplido"]["volumen"] == {"repeticiones": 18, "duracion": 120, "distancia": "1500.25"}
    assert resumen["pendientes"] == {
        "series": [
            {"sesion_realizada_id": "sr-1", "ejercicio_planificado_id": "ep-1", "nombre": "Sentadilla", "series": [3]}
        ],
        "sesiones_sin_realizar": 1,
    }


def test_mas_sesiones_que_las_planificadas_no_deja_negativos():
    sesiones = tuple(SesionDeLaSemana(f"sr-{n}", (), (), ()) for n in range(3))
    assert resumir_semana(sesiones, 0, 2)["pendientes"]["sesiones_sin_realizar"] == 0


def test_separa_ajustes_y_frenos_e_ignora_el_resto():
    reglas = ("subir_carga", "mantener_carga", "tope_semanal", "primera_sesion_pendiente", "dolor_reportado", "sin_rir")
    sesion = SesionDeLaSemana("sr-1", (), (), tuple(razon(r) for r in reglas))
    cambios = resumir_semana((sesion,), 0, 1)["cambios"]
    assert [r["regla"] for r in cambios["ajustes"]] == ["subir_carga", "mantener_carga"]
    assert [r["regla"] for r in cambios["frenos"]] == ["tope_semanal", "dolor_reportado"]
