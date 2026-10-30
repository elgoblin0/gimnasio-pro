"""Vectores de ocupacion prevista, sin reloj ni base de datos."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta

import pytest

from gimnasio.reglas.horarios import VERSION_MEJORES_HORARIOS, calcular_mejores_horarios

HORARIO = tuple((dia, (("06:00", "22:00"),)) for dia in range(1, 6)) + ((6, (("08:00", "14:00"),)),)
AHORA = datetime(2026, 10, 27, 9)


def test_desempate_por_hora_y_exclusion_de_franjas_pasadas():
    resultado = calcular_mejores_horarios((), AHORA, HORARIO)
    assert [f.desde for f in resultado.hoy.franjas] == ["09:00", "10:00", "11:00"]
    assert [f.desde for f in resultado.manana.franjas] == ["06:00", "07:00", "08:00"]
    assert all(f.prevision == 0 and f.observaciones == 8 for f in resultado.hoy.franjas)
    assert VERSION_MEJORES_HORARIOS == "1.0.0"
    with pytest.raises(FrozenInstanceError):
        resultado.hoy.cerrado = True


def test_sabado_hasta_catorce_y_domingo_cerrado():
    resultado = calcular_mejores_horarios((), datetime(2026, 10, 31, 13, 30), HORARIO)
    assert [(f.desde, f.hasta) for f in resultado.hoy.franjas] == [("13:00", "14:00")]
    assert resultado.manana.cerrado
    assert not resultado.manana.franjas
    assert not resultado.manana.datos_insuficientes


def test_tres_semanas_son_insuficientes():
    resultado = calcular_mejores_horarios((), AHORA, HORARIO, semanas=3)
    assert resultado.hoy.datos_insuficientes and resultado.manana.datos_insuficientes
    assert resultado.hoy.franjas == resultado.manana.franjas == ()


def test_visita_cruza_dos_franjas_y_salida_excluida_del_muestreo():
    horario = ((2, (("09:00", "11:00"),)),)
    visitas = tuple(
        (AHORA - timedelta(weeks=n), AHORA - timedelta(weeks=n) + timedelta(hours=1, minutes=30)) for n in range(1, 9)
    )
    franjas = calcular_mejores_horarios(visitas, AHORA, horario).hoy.franjas
    assert [(f.desde, f.prevision) for f in franjas] == [("10:00", 0.5), ("09:00", 1)]


def test_apertura_parcial_y_corte_del_historial():
    resultado = calcular_mejores_horarios((), AHORA.replace(minute=30), ((2, (("08:30", "11:30"),)),))
    assert [(f.desde, f.hasta, f.observaciones) for f in resultado.hoy.franjas] == [
        ("09:00", "10:00", 7),
        ("10:00", "11:00", 8),
    ]


def test_dia_abierto_sin_franjas_restantes():
    dia = calcular_mejores_horarios((), AHORA.replace(hour=22), HORARIO).hoy
    assert not dia.franjas and not dia.cerrado and not dia.datos_insuficientes


def test_horario_partido_no_incluye_el_cierre_intermedio():
    dia = calcular_mejores_horarios((), AHORA, ((2, (("09:00", "10:00"), ("12:00", "14:00"))),)).hoy
    assert [f.desde for f in dia.franjas] == ["09:00", "12:00", "13:00"]
