"""El servicio prepara historial vigente, fechas locales y subas sin SQL en el motor."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from gimnasio.comun.ids import a_bytes, nuevo_id
from gimnasio.entrenamiento.servicio import preparar_historial


def test_reproyeccion_dolor_con_equipo_no_disponible_conserva_pendiente():
    import json

    from gimnasio.comun.tipos import EjercicioCatalogo
    from gimnasio.entrenamiento.servicio import proyectar_dolor

    original = EjercicioCatalogo(
        "original", "Original", None, "barra", "sentadilla", ("gluteos", "rodillas"), ("alternativa",)
    )
    alternativa = EjercicioCatalogo("alternativa", "Alternativa", None, "prensa", "sentadilla", ("gluteos",))
    efectiva = {
        "ejercicios": json.dumps(
            [
                {
                    "id": "planificado",
                    "ejercicio_id": "original",
                    "ejercicio_hecho_id": "alternativa",
                    "objetivos": {
                        "series": 2,
                        "repeticiones_minimas": 8,
                        "repeticiones_maximas": 12,
                        "carga": None,
                        "rir_objetivo": 2,
                        "descanso": 60,
                    },
                    "explicacion": [],
                }
            ]
        )
    }
    for zonas, no_disponible in ((("rodillas",), True), (("rodillas", "gluteos"), False)):
        ejercicio = proyectar_dolor(
            None,
            None,
            efectiva,
            zonas=zonas,
            catalogos={"original": (original, alternativa)},
            restricciones=(),
            equipos=frozenset({"prensa"}),
        )[0]
        assert ejercicio["objetivos"]["series"] == (2 if no_disponible else 0)
        assert ejercicio.get("no_disponible", False) is no_disponible
    assert json.loads(efectiva["ejercicios"])[0]["objetivos"]["series"] == 2


def test_historial_agrupa_sesiones_y_acredita_al_planificado(reloj_fijo):
    ids = [a_bytes(nuevo_id(reloj_fijo)) for _ in range(8)]
    momento = datetime(2026, 10, 26, 2, 59, tzinfo=UTC).replace(tzinfo=None)

    def fila(indice, carga, fecha, realizada):
        return {
            "id": ids[indice],
            "sesion_realizada_id": ids[realizada],
            "sesion_planificada_id": ids[4],
            "ejercicio_catalogo_id": ids[5],
            "ejercicio_hecho_resuelto_id": ids[6],
            "sesion_creada_en": fecha,
            "registrada_en": fecha + timedelta(hours=1),
            "repeticiones": 12,
            "carga": Decimal(carga),
            "rir": 2,
        }

    # El orden de registro de una corrección no cambia el de las sesiones.
    anterior = fila(0, "40", momento, 2)
    anterior["registrada_en"] = momento + timedelta(days=2)
    nueva = fila(1, "42.5", momento + timedelta(minutes=1), 3)
    futura = fila(7, "45", momento + timedelta(days=7), 7)
    historial = preparar_historial([nueva, futura, anterior], ZoneInfo("America/Asuncion"), date(2026, 10, 26))
    assert [h.fecha_local for h in historial] == [date(2026, 10, 25), date(2026, 10, 26)]
    assert historial[0].series[0].ejercicio_hecho_id != historial[0].ejercicio_id


def test_historial_excluye_sesion_actual_y_conserva_las_otras(reloj_fijo):
    from gimnasio.comun.ids import desde_bytes

    ids = [a_bytes(nuevo_id(reloj_fijo)) for _ in range(9)]
    domingo = datetime(2026, 10, 25, 12)

    def fila(numero, dias, planificada, carga):
        return {
            "id": ids[numero],
            "sesion_realizada_id": ids[numero],
            "sesion_planificada_id": ids[planificada],
            "ejercicio_catalogo_id": ids[8],
            "ejercicio_hecho_resuelto_id": ids[8],
            "sesion_creada_en": domingo + timedelta(days=dias),
            "registrada_en": domingo + timedelta(days=dias),
            "repeticiones": 12,
            "carga": Decimal(carga),
            "rir": 2,
        }

    filas = [fila(0, 0, 3, "20.5"), fila(1, 1, 4, "23"), fila(2, 2, 5, "23")]
    sesion_a, sesion_b = str(desde_bytes(ids[4])), str(desde_bytes(ids[5]))
    for actual in (sesion_a, sesion_b):
        historial = preparar_historial(filas, ZoneInfo("America/Asuncion"), date(2026, 10, 29), actual)
        assert len(historial) == 2
        assert all(h.sesion_planificada_id != actual for h in historial)


def test_subas_salen_de_prescripciones_y_excluyen_frenadas_y_otra_semana(reloj_fijo):
    import json

    from gimnasio.entrenamiento.servicio import preparar_subas

    planificada = a_bytes(nuevo_id(reloj_fijo))

    def efectiva(fecha, frenada=False):
        return {
            "creada_en": fecha,
            "sesion_planificada_id": planificada,
            "ejercicios": json.dumps(
                [
                    {
                        "id": "planificado",
                        "ejercicio_id": "catalogo",
                        "explicacion": [{"regla": "tope_semanal"}] if frenada else [],
                    }
                ]
            ),
            "explicacion": json.dumps([{"regla": "subir_carga", "datos": {"ejercicio_id": "planificado"}}]),
        }

    domingo = efectiva(datetime(2026, 10, 26, 2, 59))
    lunes = efectiva(datetime(2026, 10, 26, 3))
    futura = efectiva(datetime(2026, 11, 2, 3))
    frenada = efectiva(datetime(2026, 10, 27, 12), True)
    subas = preparar_subas([domingo, lunes, futura, frenada], [], ZoneInfo("America/Asuncion"), date(2026, 10, 27))
    assert len(subas) == 1
    assert subas[0].fecha_local == date(2026, 10, 26)
    assert subas[0].ejercicio_id == "catalogo"


@pytest.mark.parametrize("carga,registrado,esperada", [("10", False, "10"), ("60", False, "40"), ("10", True, "40")])
def test_carga_de_partida_publicada_con_historial(carga, registrado, esperada):
    from gimnasio.comun.tipos import DatosPropuesta, EjercicioCatalogo, HistorialEjercicio, SerieRealizada
    from gimnasio.entrenamiento.servicio import convertir_programa
    from gimnasio.reglas.sesion import proponer_sesion

    ejercicio = dict(
        id="nuevo",
        ejercicio_id="catalogo",
        series=3,
        repeticiones_minimas=8,
        repeticiones_maximas=12,
        carga=Decimal(carga),
        rir_objetivo=2,
        descanso=60,
        duracion=None,
        distancia=None,
    )
    programa = dict(duracion_semanas=4, sesiones_planificadas=[dict(id="nueva", ejercicios_planificados=[ejercicio])])
    historial = HistorialEjercicio(
        "catalogo",
        "anterior",
        "anterior",
        date(2026, 10, 25),
        tuple(SerieRealizada("anterior", "viejo", n, 10, Decimal("40"), rir=2) for n in range(1, 4)),
    )
    propuesta = proponer_sesion(
        DatosPropuesta(
            convertir_programa(programa, {"catalogo"} if registrado else ()),
            date(2026, 10, 26),
            date(2026, 10, 26),
            historial=(historial,),
            catalogo=(EjercicioCatalogo("catalogo", "Ejercicio", Decimal("2.5")),),
        )
    )
    assert propuesta.prescripcion[0].carga == Decimal(esperada)
    assert ("carga_de_partida" in {r.regla for r in propuesta.explicacion}) == (not registrado)


@pytest.mark.parametrize("carga,hay_suba", [("10", False), ("40", False), ("41", True), ("42.5", True), ("60", True)])
def test_carga_de_partida_solo_contabiliza_subas_efectivas(reloj_fijo, carga, hay_suba):
    import json
    from dataclasses import replace

    from gimnasio.comun.tipos import (
        DatosPropuesta,
        EjercicioCatalogo,
        EjercicioPlanificado,
        HistorialEjercicio,
        ProgramaEntrenamiento,
        SerieRealizada,
        SesionPlanificada,
    )
    from gimnasio.entrenamiento.servicio import preparar_subas
    from gimnasio.reglas.sesion import proponer_sesion

    lunes = date(2026, 10, 26)
    ejercicio = EjercicioPlanificado(
        "planificado",
        3,
        8,
        12,
        Decimal(carga),
        2,
        60,
        ejercicio_catalogo_id="catalogo",
        carga_de_partida=Decimal(carga),
    )
    anterior = HistorialEjercicio(
        "catalogo",
        "anterior",
        "anterior",
        lunes - timedelta(days=1),
        tuple(SerieRealizada("anterior", "viejo", n, 12, Decimal("40"), rir=2) for n in range(1, 4)),
    )
    datos = DatosPropuesta(
        ProgramaEntrenamiento((SesionPlanificada("primera", (ejercicio,)),)),
        lunes,
        lunes,
        historial=(anterior,),
        catalogo=(EjercicioCatalogo("catalogo", "Ejercicio", Decimal("2.5")),),
    )
    propuesta = proponer_sesion(datos)
    carga_efectiva = min(Decimal(carga), Decimal("42.5"))
    assert propuesta.prescripcion[0].carga == carga_efectiva
    razones = [{"regla": r.regla, "version": r.version, "datos": dict(r.datos)} for r in propuesta.explicacion]
    efectiva = {
        "creada_en": datetime(2026, 10, 26, 12),
        "sesion_planificada_id": a_bytes(nuevo_id(reloj_fijo)),
        "ejercicios": json.dumps([{"id": "planificado", "ejercicio_id": "catalogo", "explicacion": razones}]),
        "explicacion": json.dumps(razones),
    }
    subas = preparar_subas([efectiva], [], ZoneInfo("America/Asuncion"), lunes + timedelta(days=1))
    realizada = replace(
        anterior,
        sesion_planificada_id="primera",
        fecha_local=lunes,
        series=tuple(replace(s, carga=carga_efectiva) for s in anterior.series),
    )
    siguiente = proponer_sesion(
        replace(
            datos,
            fecha_local=lunes + timedelta(days=1),
            historial=(anterior, realizada),
            subas=subas,
            programa=ProgramaEntrenamiento(
                (SesionPlanificada("segunda", (replace(ejercicio, carga_de_partida=None),)),)
            ),
        )
    )
    assert siguiente.prescripcion[0].carga == carga_efectiva + (Decimal("0") if hay_suba else Decimal("2.5"))
    assert bool(subas) is hay_suba
    assert ("subir_carga" in {r.regla for r in propuesta.explicacion}) is hay_suba
