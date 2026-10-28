"""Vectores del motor 2.0: ADR 0012 y ADR 0015, sin base ni reloj."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from gimnasio.comun.reloj import fecha_local, inicio_de_semana
from gimnasio.comun.tipos import (
    DatosPropuesta,
    EjercicioCatalogo,
    EjercicioPlanificado,
    HistorialEjercicio,
    ProgramaEntrenamiento,
    SerieRealizada,
    SesionPlanificada,
    SubaCarga,
)
from gimnasio.reglas.sesion import proponer_sesion

LUNES = date(2026, 10, 26)
EJERCICIO = EjercicioPlanificado("planificado", 3, 8, 12, Decimal("40"), 2, 90, ejercicio_catalogo_id="sentadilla")
CATALOGO = (EjercicioCatalogo("sentadilla", "sentadilla", Decimal("2.5")),)


def historial(repeticiones=(12, 12, 12), rir=(2, 2, 2), *, fecha=LUNES - timedelta(days=1), identificador="anterior"):
    return HistorialEjercicio(
        "sentadilla",
        identificador,
        identificador,
        fecha,
        tuple(
            SerieRealizada(identificador, "sentadilla", i, reps, Decimal("40"), rir=reserva)
            for i, (reps, reserva) in enumerate(zip(repeticiones, rir, strict=True), 1)
        ),
    )


def entrada(sesiones=None, subas=(), fecha=LUNES):
    return DatosPropuesta(
        ProgramaEntrenamiento((SesionPlanificada("proxima", (EJERCICIO,)),)),
        fecha,
        inicio_de_semana(fecha),
        historial=(historial(),) if sesiones is None else sesiones,
        catalogo=CATALOGO,
        subas=subas,
    )


@pytest.mark.parametrize(
    "repeticiones,rir,carga,piso,regla",
    [
        ((12, 12, 12), (2, 3, 2), "42.5", 8, "subir_carga"),
        ((10, 10, 10), (2, 2, 2), "40", 11, "mantener_carga"),
        ((7, 7, 7), (2, 2, 2), "40", 8, "mantener_carga"),
        ((12, 12, 12), (1, 1, 1), "40", 12, "mantener_por_rir"),
        ((12, 12, 12), (None, 1, 3), "40", 12, "mantener_por_rir"),
        ((12, 12, 12), (None, 2, 3), "42.5", 8, "subir_carga"),
        ((12, 12, 12), (None, None, None), "42.5", 8, "subir_carga"),
    ],
)
def test_vectores_progresion(repeticiones, rir, carga, piso, regla):
    propuesta = proponer_sesion(entrada((historial(repeticiones, rir),)))
    assert propuesta.version == "2.0.0"
    assert propuesta.prescripcion[0].carga == Decimal(carga)
    assert propuesta.prescripcion[0].repeticiones_minimas == piso
    assert propuesta.prescripcion[0].repeticiones_maximas == 12
    razones = {r.regla: dict(r.datos) for r in propuesta.explicacion}
    assert regla in razones
    assert ("sin_rir" in razones) == (None in rir)
    if regla == "mantener_por_rir":
        assert razones[regla]["rir_minimo"] == "1"
        assert razones[regla]["rir_objetivo"] == "2"
    assert propuesta.frenos == ()
    assert all(r.version == "2.0.0" and dict(r.datos)["explicacion"] for r in propuesta.explicacion)


def test_bajar_carga_tras_dos_fallos_y_nunca_menor_que_cero():
    anterior = historial((7, 7, 7), fecha=LUNES - timedelta(days=7), identificador="primera")
    ultima = historial((6, 6, 6), (None, 2, 2))
    propuesta = proponer_sesion(entrada((anterior, ultima)))
    assert propuesta.prescripcion[0].carga == Decimal("37.5")
    assert {r.regla for r in propuesta.explicacion} >= {"bajar_carga", "sin_rir"}
    bajos = tuple(
        replace(h, series=tuple(replace(s, carga=Decimal("1")) for s in h.series)) for h in (anterior, ultima)
    )
    assert proponer_sesion(entrada(bajos)).prescripcion[0].carga == 0


def test_freno_3_tope_semanal():
    propuesta = proponer_sesion(entrada(subas=(SubaCarga("sentadilla", LUNES),)))
    assert propuesta.prescripcion[0].carga == Decimal("40")
    assert propuesta.prescripcion[0].repeticiones_minimas == 12
    assert propuesta.frenos == ("tope_semanal",)
    razon = next(r for r in propuesta.explicacion if r.regla == "tope_semanal")
    assert dict(razon.datos)["semana_local"] == "2026-10-26"
    assert "un incremento" in dict(razon.datos)["explicacion"]


@pytest.mark.parametrize("rir", [(1, 1, 1), (None, 1, 2)])
def test_mantener_por_rir_no_activa_tope_semanal(rir):
    propuesta = proponer_sesion(entrada((historial(rir=rir),), subas=(SubaCarga("sentadilla", LUNES),)))
    assert propuesta.prescripcion[0].carga == Decimal("40")
    assert propuesta.prescripcion[0].repeticiones_minimas == 12
    assert propuesta.frenos == ()
    assert "tope_semanal" not in {r.regla for r in propuesta.explicacion}


@pytest.mark.parametrize(
    "momento,frenado",
    [
        (datetime(2026, 11, 2, 2, 59, 59, tzinfo=UTC), True),
        (datetime(2026, 11, 2, 3, tzinfo=UTC), False),
    ],
)
def test_tope_se_libera_el_lunes_en_asuncion(momento, frenado):
    propuesta = proponer_sesion(entrada(subas=(SubaCarga("sentadilla", LUNES),), fecha=fecha_local(momento)))
    assert bool(propuesta.frenos) is frenado
    assert propuesta.prescripcion[0].carga == Decimal("40" if frenado else "42.5")


def test_subas_de_otro_ejercicio_y_de_otras_semanas_no_frenan():
    propuesta = proponer_sesion(
        entrada(subas=(SubaCarga("remo", LUNES), SubaCarga("sentadilla", LUNES - timedelta(days=1))))
    )
    assert propuesta.prescripcion[0].carga == Decimal("42.5")


def test_sin_historial_conserva_programa_y_no_reinicia_pendientes():
    propuesta = proponer_sesion(entrada(()))
    assert propuesta.prescripcion[0].carga == Decimal("40")
    assert propuesta.prescripcion[0].repeticiones_minimas == 8
    assert propuesta.pendientes[0].series == (1, 2, 3)
    assert proponer_sesion(entrada(())) == propuesta
