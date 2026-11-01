"""Límites temporales del historial de restricciones y corte por consentimiento."""

from datetime import UTC, datetime, timedelta

from gimnasio.salud import servicio


def test_alta_inclusiva_y_levantamiento_exclusivo():
    inicio = datetime(2026, 11, 1, 12)
    baja = inicio + timedelta(hours=1)
    fila = {
        "ejercicio_id": None,
        "patron_movimiento": None,
        "zona": "rodillas",
        "descripcion": "Ficticia",
        "registrada_en": inicio,
        "levantada_en": baja,
    }
    assert servicio.filtrar_al_momento([fila], inicio - timedelta(microseconds=1)) == ()
    assert len(servicio.filtrar_al_momento([fila], inicio.replace(tzinfo=UTC))) == 1
    assert len(servicio.filtrar_al_momento([fila], datetime.fromisoformat("2026-11-01T09:00:00-03:00"))) == 1
    assert len(servicio.filtrar_al_momento([fila], baja - timedelta(microseconds=1))) == 1
    assert servicio.filtrar_al_momento([fila], baja) == ()
    assert servicio.filtrar_al_momento([{**fila, "levantada_en": None}], baja)


def test_sin_consentimiento_no_consulta_restricciones(monkeypatch):
    def no_leer(*args):
        raise AssertionError("No debe leer salud sin consentimiento")

    monkeypatch.setattr(servicio.repositorio, "restricciones_con_levantamiento", no_leer)
    assert servicio.restricciones_al_iniciar(None, datetime(2026, 11, 1), cursor=None, consentimiento=False) == ()
