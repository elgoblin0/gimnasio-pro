"""Vectores de ocurrencias con y sin fila."""

from datetime import date

import pytest

from gimnasio.reglas.clases import ocurrencias_en_rango

DESDE = date(2026, 10, 26)
HASTA = date(2026, 11, 8)
CLASE = {"id": "clase", "dia_semana": 2, "hora_inicio": "18:00", "duracion_minutos": 60, "archivada": False}
FILA = {"clase_id": "clase", "fecha": date(2026, 10, 27), "hora_inicio": "17:00", "duracion_minutos": 45}


def test_rango_de_dos_semanas_inclusivo():
    for dia in range(1, 8):
        resultado = ocurrencias_en_rango([CLASE | {"dia_semana": dia}], [], DESDE, HASTA)
        assert len(resultado) == 2
        assert all(DESDE <= fila["fecha"] <= HASTA for fila in resultado)
        assert all(fila["fecha"].isoweekday() == dia for fila in resultado)


def test_fila_conserva_hora_y_duracion_aunque_cambie_clase():
    resultado = ocurrencias_en_rango([CLASE], [FILA], DESDE, HASTA)
    assert resultado[0] == FILA
    assert resultado[1]["hora_inicio"] == "18:00"
    assert resultado[1]["duracion_minutos"] == 60


def test_mover_dia_conserva_fecha_fijada_y_genera_dia_nuevo():
    resultado = ocurrencias_en_rango([CLASE | {"dia_semana": 3}], [FILA], DESDE, HASTA)
    assert [fila["fecha"] for fila in resultado] == [date(2026, 10, 27), date(2026, 10, 28), date(2026, 11, 4)]
    assert resultado[0] == FILA


def test_archivada_conserva_solo_filas_existentes():
    assert ocurrencias_en_rango([CLASE | {"archivada": True}], [FILA], DESDE, HASTA) == [FILA]


@pytest.mark.parametrize("desde,hasta", [(date(2026, 10, 28), HASTA), (DESDE, date(2026, 10, 26))])
def test_filas_fuera_del_rango_no_aparecen(desde, hasta):
    assert ocurrencias_en_rango([CLASE | {"archivada": True}], [FILA], desde, hasta) == []


def test_entrada_vacia_y_rango_invertido():
    assert ocurrencias_en_rango([], [], DESDE, HASTA) == []
    assert ocurrencias_en_rango([CLASE], [FILA], HASTA, DESDE) == []
