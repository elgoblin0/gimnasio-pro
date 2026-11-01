"""Incorporación y riesgo de abandono por reglas; ningún dato de salud entra a este cálculo."""

from datetime import date, timedelta

from gimnasio.comun.tipos import Razon
from gimnasio.reglas.version import VERSION_REGLAS

DIAS_DE_INCORPORACION = 90
AUSENCIA_INCORPORACION = 7
AUSENCIA_HABITUAL = 14
DIAS_DE_VENTANA = 28
MINIMO_DE_VISITAS_ANTERIORES = 4


def dia_de_incorporacion(alta: date, hoy: date) -> int | None:
    """El día del alta es el 1; después del día 90 la incorporación terminó."""
    dia = (hoy - alta).days + 1
    return dia if 1 <= dia <= DIAS_DE_INCORPORACION else None


def razones_de_riesgo(alta: date, hoy: date, visitas: tuple[date, ...], ultimo_hasta: date | None) -> tuple[Razon, ...]:
    """Basta una razón para que el socio esté en riesgo de abandono; sin razones, no lo está."""
    razones = []
    umbral = AUSENCIA_INCORPORACION if dia_de_incorporacion(alta, hoy) else AUSENCIA_HABITUAL
    dias = (hoy - max(visitas, default=alta)).days
    if dias >= umbral:
        razones.append(Razon("ausencia", VERSION_REGLAS, (("dias", str(dias)), ("umbral", str(umbral)))))
    corte = hoy - timedelta(days=DIAS_DE_VENTANA)
    recientes = sum(corte < visita <= hoy for visita in visitas)
    anteriores = sum(corte - timedelta(days=DIAS_DE_VENTANA) < visita <= corte for visita in visitas)
    if anteriores >= MINIMO_DE_VISITAS_ANTERIORES and recientes * 2 <= anteriores:
        razones.append(
            Razon("tendencia", VERSION_REGLAS, (("recientes", str(recientes)), ("anteriores", str(anteriores))))
        )
    if ultimo_hasta is not None and ultimo_hasta < hoy:
        razones.append(Razon("membresia_vencida", VERSION_REGLAS, (("hasta", ultimo_hasta.isoformat()),)))
    return tuple(razones)
