"""Vectores del movimiento ficticio, sin SQL ni reloj global."""

from datetime import datetime, timedelta

import pytest

from gimnasio.reglas.simulacion import simular_visitas, zona_simulada

HORARIO = {"2": [["06:00", "22:00"]]}
DESDE = datetime(2026, 10, 27, 5)
HASTA = datetime(2026, 10, 27, 23)
SOCIOS = list(range(60))


@pytest.mark.parametrize("ocupacion_real", [0, 12, 47, 48, 60])
def test_determinismo_tope_horario_y_cierre(ocupacion_real):
    argumentos = (DESDE, HASTA, HORARIO, 60, SOCIOS, {}, ocupacion_real, 20261027)
    eventos = simular_visitas(*argumentos)
    assert eventos == simular_visitas(*argumentos)
    presentes = {}
    for tipo, socio, instante in eventos:
        assert DESDE < instante <= HASTA
        assert 6 <= instante.hour <= 22
        if tipo == "entrada":
            assert instante.hour < 22
            assert socio not in presentes
            presentes[socio] = instante
        else:
            duracion = (instante - presentes.pop(socio)).total_seconds() / 60
            assert 40 <= duracion <= 110 or instante.hour == 22
        assert len(presentes) <= max(0, 48 - ocupacion_real)
    assert not presentes
    if ocupacion_real < 48:
        assert eventos


def test_estado_inicial_se_cierra_y_no_se_modifica():
    abiertas = {socio: DESDE - timedelta(minutes=10) for socio in SOCIOS}
    copia = dict(abiertas)
    eventos = simular_visitas(DESDE, DESDE + timedelta(minutes=1), HORARIO, 60, SOCIOS, abiertas, 0, 1)
    assert len(eventos) == 60
    assert all(tipo == "salida" for tipo, _, _ in eventos)
    assert abiertas == copia


@pytest.mark.parametrize("aforo,ocupacion_real", [(61, 0), (61, 9), (4, 2)])
def test_ocupacion_real_reduce_simuladas_abiertas(aforo, ocupacion_real):
    desde = DESDE.replace(hour=19)
    abiertas = {socio: desde for socio in SOCIOS[: aforo * 4 // 5]}
    eventos = simular_visitas(desde, desde + timedelta(minutes=1), HORARIO, aforo, SOCIOS, abiertas, ocupacion_real, 1)
    for tipo, socio, instante in eventos:
        if tipo == "entrada":
            abiertas[socio] = instante
        else:
            abiertas.pop(socio)
    assert ocupacion_real + len(abiertas) <= aforo * 4 // 5


def test_consultas_partidas_conservan_eventos_y_duraciones():
    corte = DESDE + timedelta(hours=14, seconds=23)
    primeros = simular_visitas(DESDE, corte, HORARIO, 60, SOCIOS, {}, 0, 1)
    abiertas = {}
    for tipo, socio, instante in primeros:
        if tipo == "entrada":
            abiertas[socio] = instante
        else:
            abiertas.pop(socio)
    segundos = simular_visitas(corte, HASTA, HORARIO, 60, SOCIOS, abiertas, 0, 1)
    assert primeros + segundos == simular_visitas(DESDE, HASTA, HORARIO, 60, SOCIOS, {}, 0, 1)


def test_zona_estable_con_cambios_cada_diez_a_veinticinco_minutos():
    inicio = DESDE.replace(hour=0)
    zonas = [zona_simulada("socio", inicio + timedelta(minutes=minuto), 1) for minuto in range(1440)]
    cambios = [minuto for minuto in range(1, 1440) if zonas[minuto] != zonas[minuto - 1]]
    assert cambios
    assert all(10 <= siguiente - anterior <= 25 for anterior, siguiente in zip(cambios, cambios[1:], strict=False))
    assert zona_simulada("socio", inicio, 1) == zona_simulada("socio", inicio + timedelta(seconds=59), 1)
