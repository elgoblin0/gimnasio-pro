"""El servicio prepara historial vigente, fechas locales y subas sin SQL en el motor."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from gimnasio.comun.ids import a_bytes, nuevo_id
from gimnasio.entrenamiento.servicio import preparar_historial


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
    subas = preparar_subas([domingo, lunes, futura, frenada], ZoneInfo("America/Asuncion"), date(2026, 10, 27))
    assert len(subas) == 1
    assert subas[0].fecha_local == date(2026, 10, 26)
    assert subas[0].ejercicio_id == "catalogo"
