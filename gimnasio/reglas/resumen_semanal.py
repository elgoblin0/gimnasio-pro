"""Resumen semanal: cuenta lo cumplido, los cambios y los pendientes de una semana cerrada.

No decide nada ni guarda razones propias: solo resume hechos y explicaciones ya guardadas (ADR 0003).
"""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

AJUSTES = ("subir_carga", "bajar_carga", "mantener_carga")
FRENOS = ("dolor_reportado", "restriccion_salud", "tope_semanal", "chequeo_desfavorable")


@dataclass(frozen=True)
class EjercicioDeLaSemana:
    id: str  # Ejercicio planificado.
    nombre: str
    series: int


@dataclass(frozen=True)
class SerieDeLaSemana:
    ejercicio_planificado_id: str
    repeticiones: int | None
    duracion: int | None
    distancia: Decimal | None


@dataclass(frozen=True)
class SesionDeLaSemana:
    id: str
    ejercicios: tuple[EjercicioDeLaSemana, ...]
    series: tuple[SerieDeLaSemana, ...]
    razones: tuple[Mapping, ...]  # Explicación guardada de la prescripción, tal como se publica.


def ultima_semana_cerrada(hoy: date) -> date:
    """Lunes de la semana anterior a la de hoy: la de hoy sigue abierta hasta el domingo."""
    return hoy - timedelta(days=hoy.weekday() + 7)


def resumir_semana(sesiones: tuple[SesionDeLaSemana, ...], visitas: int, planificadas: int) -> dict:
    series = [serie for sesion in sesiones for serie in sesion.series]
    razones = [razon for sesion in sesiones for razon in sesion.razones]
    pendientes = []
    for sesion in sesiones:
        hechas = Counter(serie.ejercicio_planificado_id for serie in sesion.series)
        pendientes += [
            {
                "sesion_realizada_id": sesion.id,
                "ejercicio_planificado_id": ejercicio.id,
                "nombre": ejercicio.nombre,
                "series": list(range(hechas[ejercicio.id] + 1, ejercicio.series + 1)),
            }
            for ejercicio in sesion.ejercicios
            if hechas[ejercicio.id] < ejercicio.series
        ]
    distancia = sum((serie.distancia or Decimal(0) for serie in series), Decimal(0))
    return {
        "cumplido": {
            "sesiones_realizadas": len(sesiones),
            "sesiones_planificadas": planificadas,
            "series": len(series),
            "volumen": {
                "repeticiones": sum(serie.repeticiones or 0 for serie in series),
                "duracion": sum(serie.duracion or 0 for serie in series),
                "distancia": format(distancia.normalize(), "f"),
            },
            "visitas": visitas,
        },
        "cambios": {
            "ajustes": [razon for razon in razones if razon["regla"] in AJUSTES],
            "frenos": [razon for razon in razones if razon["regla"] in FRENOS],
        },
        "pendientes": {
            "series": pendientes,
            "sesiones_sin_realizar": max(0, planificadas - len(sesiones)),
        },
        "sin_actividad": not sesiones and not visitas,
    }
