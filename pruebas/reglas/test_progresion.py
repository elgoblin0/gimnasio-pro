"""Vectores del motor 2.0: ADR 0012, 0015 y 0016, sin base ni reloj."""

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


def test_evalua_historial_de_la_misma_sesion_planificada():
    anterior = replace(historial(), sesion_planificada_id="proxima")
    propuesta = proponer_sesion(entrada((anterior,), subas=(SubaCarga("sentadilla", LUNES),)))
    assert propuesta.prescripcion[0].carga == Decimal("40")
    assert propuesta.frenos == ("tope_semanal",)
    assert {r.regla for r in propuesta.explicacion} >= {"subir_carga", "tope_semanal"}


@pytest.mark.parametrize("cargas", [("40", "45", "35"), ("35", "45", "40"), ("45", "40", "35")])
def test_carga_base_minima_no_depende_del_orden(cargas):
    ultima = historial()
    ultima = replace(
        ultima,
        series=tuple(replace(serie, carga=Decimal(carga)) for serie, carga in zip(ultima.series, cargas, strict=True)),
    )
    propuesta = proponer_sesion(entrada((ultima,)))
    assert propuesta.prescripcion[0].carga == Decimal("37.5")
    razon = next(r for r in propuesta.explicacion if r.regla == "subir_carga")
    assert dict(razon.datos)["carga_base"] == "35"
    assert "35 kg" in dict(razon.datos)["explicacion"]
    assert propuesta.version == "2.0.0"


@pytest.mark.parametrize(
    "repeticiones,baja,cantidad",
    [
        ((7, 10, 10), False, 1),
        ((7, 7, 10), True, 2),
        ((7, 7, 10, 10), False, 2),
    ],
)
def test_bajar_exige_mayoria_estricta_en_dos_sesiones(repeticiones, baja, cantidad):
    rir = (2,) * len(repeticiones)
    anterior = historial(repeticiones, rir, identificador="primera", fecha=LUNES - timedelta(days=7))
    ultima = historial(repeticiones, rir)
    propuesta = proponer_sesion(entrada((anterior, ultima)))
    assert propuesta.prescripcion[0].carga == Decimal("37.5" if baja else "40")
    reglas = {r.regla for r in propuesta.explicacion}
    assert ("bajar_carga" in reglas) is baja
    if baja:
        datos = dict(next(r for r in propuesta.explicacion if r.regla == "bajar_carga").datos)
        assert datos["carga_base"] == "40"
        assert datos["series_bajo_piso"] == str((cantidad, cantidad))
        assert "2 de 3" in datos["explicacion"]


@pytest.mark.parametrize(
    "repeticiones,rir,regla,carga",
    [
        ((10, 10, 10), (2, 2, 2), "mantener_carga", "35"),
        ((12, 12, 12), (1, 1, 1), "mantener_por_rir", "35"),
        ((7, 7, 10), (2, 2, 2), "bajar_carga", "32.5"),
    ],
)
def test_carga_base_minima_tambien_al_mantener_y_bajar(repeticiones, rir, regla, carga):
    ultima = historial(repeticiones, rir)
    ultima = replace(
        ultima,
        series=tuple(
            replace(serie, carga=Decimal(valor)) for serie, valor in zip(ultima.series, ("40", "35", "45"), strict=True)
        ),
    )
    anterior = replace(ultima, sesion_realizada_id="primera", fecha_local=LUNES - timedelta(days=7))
    propuesta = proponer_sesion(entrada((anterior, ultima)))
    assert propuesta.prescripcion[0].carga == Decimal(carga)
    datos = dict(next(r for r in propuesta.explicacion if r.regla == regla).datos)
    assert datos["carga_base"] == "35"


@pytest.mark.parametrize(
    "cantidad,rir,regla,carga",
    [
        (1, 2, "mantener_carga", "40"),
        (1, 1, "mantener_carga", "40"),
        (4, 2, "subir_carga", "42.5"),
    ],
)
def test_subir_y_mantener_por_rir_exigen_series_planificadas(cantidad, rir, regla, carga):
    ultima = historial((12,) * cantidad, (rir,) * cantidad)
    propuesta = proponer_sesion(entrada((ultima,)))
    assert propuesta.prescripcion[0].carga == Decimal(carga)
    assert propuesta.explicacion[1].regla == regla


@pytest.mark.parametrize(
    "repeticiones,regla,carga",
    [
        ((12, 12, 12), "subir_carga", "42.5"),
        ((10, 10, 10), "mantener_carga", "40"),
    ],
)
def test_historial_excluye_solo_misma_planificada_de_semana_actual(repeticiones, regla, carga):
    anterior = replace(historial(repeticiones), sesion_planificada_id="proxima")
    actual = replace(
        historial((10,) if regla == "subir_carga" else (12,), (2,), fecha=LUNES),
        sesion_planificada_id="proxima",
        sesion_realizada_id="actual",
    )
    propuesta = proponer_sesion(entrada((anterior, actual)))
    assert propuesta.prescripcion[0].carga == Decimal(carga)
    assert propuesta.explicacion[1].regla == regla
    frenada = proponer_sesion(entrada((anterior, actual), subas=(SubaCarga("sentadilla", LUNES),)))
    assert bool(frenada.frenos) is (regla == "subir_carga")


@pytest.mark.parametrize("rir", [2, None])
def test_sin_rir_objetivo_no_menciona_rir_ni_guarda_none(rir):
    datos = entrada((historial(rir=(rir,) * 3),))
    ejercicio = replace(EJERCICIO, rir_objetivo=None)
    datos = replace(datos, programa=ProgramaEntrenamiento((SesionPlanificada("proxima", (ejercicio,)),)))
    propuesta = proponer_sesion(datos)
    assert propuesta.prescripcion[0].carga == Decimal("42.5")
    for razon in propuesta.explicacion:
        assert "RIR" not in dict(razon.datos)["explicacion"]
        assert all("None" not in valor for _, valor in razon.datos)


def test_prescripcion_estable_al_registrar_la_suba_propuesta():
    anterior = replace(historial(), sesion_planificada_id="proxima")
    anterior = replace(anterior, series=tuple(replace(s, carga=Decimal("20.5")) for s in anterior.series))
    inicial = proponer_sesion(entrada((anterior,)))
    assert inicial.prescripcion[0].carga == Decimal("23")
    actual = replace(historial((12,), (2,), fecha=LUNES), sesion_planificada_id="proxima", sesion_realizada_id="actual")
    actual = replace(actual, series=(replace(actual.series[0], carga=Decimal("23")),))
    despues = proponer_sesion(
        entrada((anterior, actual), subas=(SubaCarga("sentadilla", LUNES, actual.sesion_planificada_id),))
    )
    assert despues.prescripcion == inicial.prescripcion


def test_suba_de_sesion_a_frena_sesion_b_en_la_misma_semana():
    anterior = historial(fecha=LUNES - timedelta(days=7), identificador="anterior")
    anterior = replace(anterior, series=tuple(replace(s, carga=Decimal("20.5")) for s in anterior.series))
    sesion_a = replace(
        historial(fecha=LUNES, identificador="sesion-a"),
        series=tuple(replace(s, carga=Decimal("23")) for s in historial().series),
    )
    datos = entrada(
        (anterior, sesion_a), fecha=LUNES + timedelta(days=3), subas=(SubaCarga("sentadilla", LUNES, "sesion-a"),)
    )
    propuesta = proponer_sesion(datos)
    assert propuesta.prescripcion[0].carga == Decimal("23")
    assert propuesta.frenos == ("tope_semanal",)
    assert {r.regla for r in propuesta.explicacion} >= {"subir_carga", "tope_semanal"}
