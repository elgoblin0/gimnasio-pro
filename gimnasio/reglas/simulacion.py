"""Visitas simuladas deterministas, en hora local y sin consultar el reloj."""

from datetime import time, timedelta
from hashlib import sha256

from gimnasio.reglas.zonas_sede import ZONAS_SEDE


def _numero(*partes):
    return int.from_bytes(sha256(repr(partes).encode()).digest()[:8], "big")


def zona_simulada(socio_id, instante, semilla):
    """Intervalos por socio de 10 a 25 minutos; cada intervalo cambia de zona."""
    duracion = 10 + _numero(str(socio_id), semilla) % 16
    minuto = instante.hour * 60 + instante.minute
    posicion = minuto // duracion + _numero(str(socio_id), semilla, "zona")
    return ZONAS_SEDE[posicion % len(ZONAS_SEDE)]


def simular_visitas(desde, hasta, horario, aforo_maximo, simulados, abiertas, ocupacion_real, semilla):
    """Genera hechos en (desde, hasta], sin modificar el estado recibido.

    Las horas punta y su proporción siguen el historial de la demo: 07, 18 y
    19 entre semana, 09 los sábados. El cierre admite salidas, nunca entradas.
    """
    horario = dict(horario)
    presentes = dict(abiertas)
    eventos = []
    tope = max(0, aforo_maximo * 4 // 5 - ocupacion_real)
    instante = desde.replace(second=0, microsecond=0) + timedelta(minutes=1)
    while instante <= hasta:
        franjas = horario.get(str(instante.isoweekday()), horario.get(instante.isoweekday(), ()))
        abierto = any(
            time.fromisoformat(inicio) <= instante.time().replace(tzinfo=None) < time.fromisoformat(fin)
            for inicio, fin in franjas
        )
        for socio, entrada in sorted(presentes.items(), key=lambda par: str(par[0])):
            duracion = 40 + _numero(str(socio), entrada.isoformat(), semilla, "duracion") % 71
            if not abierto or instante - entrada >= timedelta(minutes=duracion) or len(presentes) > tope:
                eventos.append(("salida", socio, instante))
                del presentes[socio]
        if abierto:
            hora = instante.hour
            peso = (
                (10 if hora == 9 else 1)
                if instante.isoweekday() == 6
                else {
                    7: 10,
                    18: 10,
                    19: 8,
                    14: 2,
                }.get(hora, 1)
            )
            for socio in sorted(simulados, key=str):
                if len(presentes) >= tope:
                    break
                if socio not in presentes and _numero(semilla, str(socio), instante.isoformat()) % 600 < peso:
                    eventos.append(("entrada", socio, instante))
                    presentes[socio] = instante
        instante += timedelta(minutes=1)
    return eventos
