"""Propuesta mínima: secuencia del programa y series realizadas vigentes."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from gimnasio.comun.reloj import fecha_local, inicio_de_semana
from gimnasio.comun.tipos import (
    DatosPropuesta,
    EjercicioPlanificado,
    PendienteEntrenamiento,
    ProgramaEntrenamiento,
    SerieRealizada,
    SesionPlanificada,
)
from gimnasio.reglas.sesion import VERSION_REGLAS, proponer_sesion

LUNES = date(2026, 10, 26)
PRIMERA = SesionPlanificada(
    "sesion-b",
    (
        EjercicioPlanificado("sentadilla", 3, 10, 10, Decimal("42.5")),
        EjercicioPlanificado("remo", 2, 12, 12, Decimal("20")),
    ),
)
SEGUNDA = SesionPlanificada("sesion-a", (EjercicioPlanificado("sentadilla", 2, 8, 8, Decimal("45")),))
TERCERA = SesionPlanificada("sesion-c", (EjercicioPlanificado("remo", 1, 15, 15, Decimal("15")),))
PROGRAMA = ProgramaEntrenamiento((PRIMERA, SEGUNDA, TERCERA))


def realizadas(sesion):
    return tuple(
        SerieRealizada(sesion.id, ejercicio.ejercicio_id, numero, ejercicio.repeticiones_minimas, ejercicio.carga)
        for ejercicio in sesion.ejercicios
        for numero in range(1, ejercicio.series + 1)
    )


def datos(series=(), programa=PROGRAMA, fecha=LUNES):
    return DatosPropuesta(programa, fecha, inicio_de_semana(fecha), series)


@pytest.mark.parametrize(
    "entrada,sesion,pendientes,regla",
    [
        (datos(programa=None), None, (), "sin_programa"),
        (
            datos(),
            PRIMERA,
            (PendienteEntrenamiento("sentadilla", (1, 2, 3)), PendienteEntrenamiento("remo", (1, 2))),
            "primera_sesion_pendiente",
        ),
        (
            datos(realizadas(PRIMERA)[:2]),
            PRIMERA,
            (PendienteEntrenamiento("sentadilla", (3,)), PendienteEntrenamiento("remo", (1, 2))),
            "primera_sesion_pendiente",
        ),
        (
            datos(realizadas(PRIMERA)),
            SEGUNDA,
            (PendienteEntrenamiento("sentadilla", (1, 2)),),
            "primera_sesion_pendiente",
        ),
        (
            datos(realizadas(PRIMERA) + realizadas(SEGUNDA)),
            TERCERA,
            (PendienteEntrenamiento("remo", (1,)),),
            "primera_sesion_pendiente",
        ),
        (
            datos(realizadas(PRIMERA) + realizadas(SEGUNDA) + realizadas(TERCERA)),
            None,
            (),
            "secuencia_realizada",
        ),
        (
            datos(fecha=LUNES + timedelta(days=1)),
            PRIMERA,
            (PendienteEntrenamiento("sentadilla", (1, 2, 3)), PendienteEntrenamiento("remo", (1, 2))),
            "primera_sesion_pendiente",
        ),
    ],
    ids=["sin-programa", "secuencia-pendiente", "parcial", "segunda", "tercera", "realizada", "ausencia"],
)
def test_propuesta_por_secuencia_y_series_vigentes(entrada, sesion, pendientes, regla):
    propuesta = proponer_sesion(entrada)
    assert propuesta.sesion_planificada is sesion
    assert propuesta.pendientes == pendientes
    assert propuesta.explicacion[0].regla == regla
    assert propuesta.version == VERSION_REGLAS
    assert all(razon.version == VERSION_REGLAS and razon.datos for razon in propuesta.explicacion)


def test_acredita_solo_series_vigentes_de_la_sesion_y_el_ejercicio():
    serie = realizadas(PRIMERA)[0]
    entrada = datos(
        (
            serie,
            serie,  # Un reintento no acredita dos series.
            replace(serie, numero_serie=2, vigente=False),  # Corrección o anulación no vigente.
            replace(serie, sesion_planificada_id=SEGUNDA.id, numero_serie=2),
            replace(serie, ejercicio_id="otro-ejercicio", numero_serie=2),
            replace(serie, numero_serie=0),
            replace(serie, numero_serie=4),
        )
    )
    assert proponer_sesion(entrada).pendientes == (
        PendienteEntrenamiento("sentadilla", (2, 3)),
        PendienteEntrenamiento("remo", (1, 2)),
    )


def test_la_correccion_vigente_acredita_su_serie_sin_acreditar_la_anterior():
    anterior = realizadas(PRIMERA)[0]
    entrada = datos((replace(anterior, vigente=False), replace(anterior, numero_serie=2)))
    assert proponer_sesion(entrada).pendientes[0].series == (1, 3)


@pytest.mark.parametrize("cantidad", [0, 1, 2, 4])
def test_parcial_conserva_la_prescripcion_y_solo_reduce_pendientes(cantidad):
    propuesta = proponer_sesion(datos(realizadas(PRIMERA)[:cantidad]))
    assert propuesta.sesion_planificada is PRIMERA
    assert propuesta.sesion_planificada.ejercicios == PRIMERA.ejercicios
    assert tuple((e.series, e.repeticiones_minimas, e.carga) for e in propuesta.sesion_planificada.ejercicios) == (
        (3, 10, Decimal("42.5")),
        (2, 12, Decimal("20")),
    )
    assert sum(e.series * e.repeticiones_minimas for e in propuesta.sesion_planificada.ejercicios) == 54
    assert sum(len(p.series) for p in propuesta.pendientes) == 5 - cantidad


@pytest.mark.parametrize("repeticiones,carga", [(6, Decimal("40")), (15, Decimal("60"))])
def test_las_medidas_realizadas_no_ajustan_la_prescripcion(repeticiones, carga):
    serie = replace(realizadas(PRIMERA)[0], repeticiones=repeticiones, carga=carga)
    propuesta = proponer_sesion(datos((serie,)))
    assert propuesta.sesion_planificada is PRIMERA
    assert propuesta.sesion_planificada.ejercicios[0] == EjercicioPlanificado("sentadilla", 3, 10, 10, Decimal("42.5"))
    assert propuesta.pendientes[0].series == (2, 3)


@pytest.mark.parametrize("dias", [1, 6, 7, 14])
def test_ausencia_no_acumula_volumen_ni_reinicia_la_secuencia(dias):
    fecha = LUNES + timedelta(days=dias)
    assert proponer_sesion(datos(fecha=fecha)).sesion_planificada is PRIMERA
    parcial = proponer_sesion(datos(realizadas(PRIMERA)[:1], fecha=fecha))
    assert parcial.sesion_planificada is PRIMERA
    assert sum(len(p.series) for p in parcial.pendientes) == 4
    completa = realizadas(PRIMERA) + realizadas(SEGUNDA) + realizadas(TERCERA)
    propuesta = proponer_sesion(datos(completa, fecha=fecha))
    assert propuesta.sesion_planificada is None
    assert propuesta.pendientes == ()
    assert "no se reinicia" in dict(propuesta.explicacion[0].datos)["explicacion"]


@pytest.mark.parametrize("sesion", [SEGUNDA, TERCERA])
def test_realizar_una_sesion_posterior_no_salta_la_primera_pendiente(sesion):
    assert proponer_sesion(datos(realizadas(sesion))).sesion_planificada is PRIMERA


def test_sin_salud_restricciones_dolor_ni_consentimiento_propone_sin_ajustes():
    # La entrada mínima no pide ni consulta datos de salud ni consentimiento.
    propuesta = proponer_sesion(datos())
    assert propuesta.sesion_planificada is PRIMERA
    razon = next(r for r in propuesta.explicacion if r.regla == "respeto_programa_entrenador")
    assert "sin_chequeo" in {r.regla for r in propuesta.explicacion}
    assert dict(razon.datos)["explicacion"] == (
        "Se respeta el plan del entrenador sin ajustes de carga, repeticiones, series ni volumen."
    )


def test_sin_series_una_entrada_y_salida_no_acreditan_entrenamiento():
    # Pasar el tiempo de una visita no crea una serie realizada.
    antes = proponer_sesion(datos())
    despues = proponer_sesion(datos(fecha=LUNES + timedelta(days=1)))
    assert despues.sesion_planificada is antes.sesion_planificada
    assert despues.pendientes == antes.pendientes


@pytest.mark.parametrize("series", [(), realizadas(PRIMERA)[:1], realizadas(PRIMERA)])
def test_misma_entrada_produce_misma_propuesta_explicacion_y_version(series):
    entrada = datos(series)
    assert proponer_sesion(entrada) == proponer_sesion(entrada)
    propuesta = proponer_sesion(entrada)
    assert propuesta.version == VERSION_REGLAS
    assert all(r.version == propuesta.version for r in propuesta.explicacion)
    assert dict(propuesta.explicacion[0].datos)["fecha_local"] == "2026-10-26"
    assert dict(propuesta.explicacion[0].datos)["semana_local"] == "2026-10-26"


def test_entrada_y_resultado_son_inmutables():
    entrada = datos()
    propuesta = proponer_sesion(entrada)
    for objeto, atributo, valor in (
        (entrada, "programa", None),
        (PROGRAMA, "sesiones", ()),
        (PRIMERA, "ejercicios", ()),
        (PRIMERA.ejercicios[0], "carga", Decimal("100")),
        (realizadas(PRIMERA)[0], "vigente", False),
        (propuesta, "sesion_planificada", None),
        (propuesta.pendientes[0], "series", ()),
        (propuesta.explicacion[0], "version", "otra"),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(objeto, atributo, valor)
    with pytest.raises(TypeError):
        propuesta.explicacion[0].datos[0] = ("explicacion", "otra")


@pytest.mark.parametrize(
    "momento,fecha,semana",
    [
        (datetime(2026, 10, 26, 2, 59, 59, tzinfo=UTC), date(2026, 10, 25), date(2026, 10, 19)),
        (datetime(2026, 10, 26, 3, tzinfo=UTC), LUNES, LUNES),
        (datetime(2026, 11, 2, 2, 59, 59, tzinfo=UTC), date(2026, 11, 1), LUNES),
        (datetime(2026, 11, 2, 3, tzinfo=UTC), date(2026, 11, 2), date(2026, 11, 2)),
    ],
)
def test_fecha_y_semana_se_reciben_en_limites_de_asuncion(momento, fecha, semana):
    local = fecha_local(momento)
    assert local == fecha
    assert inicio_de_semana(local) == semana
    propuesta = proponer_sesion(DatosPropuesta(PROGRAMA, local, semana))
    assert propuesta.sesion_planificada is PRIMERA
    contexto = dict(propuesta.explicacion[0].datos)
    assert contexto["fecha_local"] == fecha.isoformat()
    assert contexto["semana_local"] == semana.isoformat()


def test_programa_sin_sesiones_no_propone_trabajo():
    propuesta = proponer_sesion(datos(programa=ProgramaEntrenamiento(())))
    assert propuesta.sesion_planificada is None
    assert propuesta.pendientes == ()
    assert propuesta.explicacion[0].regla == "secuencia_realizada"


def test_cardio_conserva_duracion_distancia_y_medidas_no_aplicables():
    ejercicio = EjercicioPlanificado("carrera", 2, None, None, None, duracion=120, distancia=Decimal("1500.25"))
    sesion = SesionPlanificada("cardio", (ejercicio,))
    serie = SerieRealizada("cardio", "carrera", 1, None, None, duracion=100, distancia=Decimal("1200.50"))
    entrada = DatosPropuesta(ProgramaEntrenamiento((sesion,)), LUNES, LUNES, (serie,))
    propuesta = proponer_sesion(entrada)
    assert propuesta.sesion_planificada is sesion
    assert propuesta.sesion_planificada.ejercicios == (ejercicio,)
    assert propuesta.pendientes == (PendienteEntrenamiento("carrera", (2,)),)
    assert ejercicio.duracion == 120
    assert ejercicio.distancia == Decimal("1500.25")
    assert ejercicio.repeticiones_minimas is ejercicio.carga is None


def test_motor_conserva_rango_rir_y_descanso_sin_ajustes():
    ejercicio = EjercicioPlanificado("sentadilla", 3, 8, 12, Decimal("20"), rir_objetivo=2, descanso=90)
    sesion = SesionPlanificada("fuerza", (ejercicio,))
    propuesta = proponer_sesion(datos(programa=ProgramaEntrenamiento((sesion,))))
    assert propuesta.sesion_planificada is sesion
    assert propuesta.sesion_planificada.ejercicios == (ejercicio,)
    assert propuesta.version == "3.2.0"
