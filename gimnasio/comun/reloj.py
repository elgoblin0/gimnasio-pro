"""Reloj inyectable en UTC y fechas en la zona de la sede (ADR 0005)."""

from datetime import UTC, date, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from flask import current_app

ZONA_SEDE = ZoneInfo("America/Asuncion")


class Reloj(Protocol):
    def ahora(self) -> datetime:
        """Devuelve un momento con zona horaria en UTC."""
        ...


def _en_utc(momento: datetime) -> datetime:
    if momento.utcoffset() is None:
        raise ValueError("El momento debe incluir una zona horaria")
    return momento.astimezone(UTC)


class RelojSistema:
    def ahora(self) -> datetime:
        return datetime.now(UTC)


class RelojFijo:
    def __init__(self, momento: datetime):
        self.fijar(momento)

    def ahora(self) -> datetime:
        return self._momento

    def avanzar(self, intervalo: timedelta) -> None:
        self._momento += intervalo

    def fijar(self, momento: datetime) -> None:
        self._momento = _en_utc(momento)


def reloj_actual() -> Reloj:
    return current_app.extensions["reloj"]


def fecha_local(momento: datetime, zona: ZoneInfo = ZONA_SEDE) -> date:
    return _en_utc(momento).astimezone(zona).date()


def inicio_de_semana(fecha: date) -> date:
    return fecha - timedelta(days=fecha.weekday())
