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
    historial, subas = preparar_historial([nueva, futura, anterior], ZoneInfo("America/Asuncion"), date(2026, 10, 26))
    assert [h.fecha_local for h in historial] == [date(2026, 10, 25), date(2026, 10, 26)]
    assert len(subas) == 1
    assert subas[0].fecha_local == date(2026, 10, 26)
    assert historial[0].ejercicio_id == subas[0].ejercicio_id
    assert historial[0].series[0].ejercicio_hecho_id != historial[0].ejercicio_id
