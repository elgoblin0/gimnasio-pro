"""Datos inmutables del motor de reglas (ADR 0001 y 0002).

Las sesiones llegan en la secuencia del programa. Los identificadores de sesión
y ejercicio distinguen el trabajo planificado; las series se numeran desde 1.
El servicio obtiene el estado vigente de los hechos (ADR 0003): una serie
corregida o anulada no vigente nunca acredita trabajo en el motor.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class EjercicioPlanificado:
    ejercicio_id: str
    series: int
    repeticiones: int
    carga: Decimal


@dataclass(frozen=True)
class SesionPlanificada:
    id: str
    ejercicios: tuple[EjercicioPlanificado, ...]


@dataclass(frozen=True)
class ProgramaEntrenamiento:
    sesiones: tuple[SesionPlanificada, ...]


@dataclass(frozen=True)
class SerieRealizada:
    sesion_planificada_id: str
    ejercicio_id: str
    numero_serie: int
    repeticiones: int
    carga: Decimal
    vigente: bool = True


@dataclass(frozen=True)
class DatosPropuesta:
    programa: ProgramaEntrenamiento | None
    fecha_local: date
    semana_local: date  # Lunes de la semana local, calculado por quien llama.
    series_realizadas: tuple[SerieRealizada, ...] = ()


@dataclass(frozen=True)
class PendienteEntrenamiento:
    """Números de serie pendientes dentro de la prescripción original."""

    ejercicio_id: str
    series: tuple[int, ...]


@dataclass(frozen=True)
class Razon:
    regla: str
    version: str
    datos: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class PropuestaSesion:
    sesion_planificada: SesionPlanificada | None
    pendientes: tuple[PendienteEntrenamiento, ...]
    explicacion: tuple[Razon, ...]
    version: str
