"""Vigencias inclusivas de las renovaciones de membresía."""

from datetime import date, timedelta


def vigencia_renovada(hoy: date, ultimo_hasta: date | None, duracion_dias: int) -> tuple[date, date]:
    if type(duracion_dias) is not int or duracion_dias <= 0:
        raise ValueError("La duración debe ser un entero mayor que cero.")
    desde = hoy if ultimo_hasta is None or ultimo_hasta < hoy else ultimo_hasta + timedelta(days=1)
    return desde, desde + timedelta(days=duracion_dias - 1)
