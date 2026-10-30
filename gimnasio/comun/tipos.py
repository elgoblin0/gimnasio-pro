"""Datos inmutables del motor de reglas (ADR 0001 y 0002).

Las sesiones llegan en la secuencia del programa. Los identificadores de sesión
y ejercicio distinguen el trabajo planificado; las series se numeran desde 1.
El servicio obtiene el estado vigente de los hechos (ADR 0003): una serie
corregida o anulada no vigente nunca acredita trabajo en el motor.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

ZONAS_CUERPO = (
    "pecho",
    "espalda_alta",
    "dorsales",
    "hombros",
    "biceps",
    "triceps",
    "abdomen",
    "gluteos",
    "cuadriceps",
    "isquiotibiales",
    "pantorrillas",
    "zona_lumbar",
    "rodillas",
    "cuello",
)


@dataclass(frozen=True)
class EjercicioPlanificado:
    ejercicio_id: str
    series: int
    repeticiones_minimas: int | None
    repeticiones_maximas: int | None
    carga: Decimal | None
    rir_objetivo: int | None = None
    descanso: int | None = None
    duracion: int | None = None
    distancia: Decimal | None = None
    ejercicio_catalogo_id: str | None = None


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
    repeticiones: int | None
    carga: Decimal | None
    vigente: bool = True
    duracion: int | None = None
    distancia: Decimal | None = None
    rir: int | None = None
    ejercicio_hecho_id: str | None = None


@dataclass(frozen=True)
class EjercicioCatalogo:
    ejercicio_id: str
    nombre: str
    incremento_carga: Decimal | None
    equipo: str = ""
    patron_movimiento: str = ""
    zonas: tuple[str, ...] = ()
    alternativas: tuple[str, ...] = ()


@dataclass(frozen=True)
class HistorialEjercicio:
    ejercicio_id: str  # Del catálogo planificado: una alternativa acredita al original.
    sesion_realizada_id: str
    sesion_planificada_id: str
    fecha_local: date
    series: tuple[SerieRealizada, ...]


@dataclass(frozen=True)
class SubaCarga:
    ejercicio_id: str
    fecha_local: date
    sesion_planificada_id: str | None = None


@dataclass(frozen=True)
class Chequeo:
    sueno: int
    energia: int


@dataclass(frozen=True)
class RestriccionSalud:
    ejercicio_id: str | None = None
    patron_movimiento: str | None = None
    zona: str | None = None
    descripcion: str = ""


@dataclass(frozen=True)
class DatosPropuesta:
    programa: ProgramaEntrenamiento | None
    fecha_local: date
    semana_local: date  # Lunes de la semana local, calculado por quien llama.
    series_realizadas: tuple[SerieRealizada, ...] = ()
    historial: tuple[HistorialEjercicio, ...] = ()
    catalogo: tuple[EjercicioCatalogo, ...] = ()
    subas: tuple[SubaCarga, ...] = ()
    chequeo: Chequeo | None = None
    dolores_actuales: tuple[str, ...] = ()
    dolores_anteriores: tuple[str, ...] = ()
    restricciones: tuple[RestriccionSalud, ...] = ()
    equipos_fuera_de_servicio: frozenset[str] = frozenset()


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
class PrescripcionEjercicio:
    ejercicio_id: str  # Identificador del ejercicio planificado, igual que los pendientes.
    series: int
    repeticiones_minimas: int | None
    repeticiones_maximas: int | None
    carga: Decimal | None
    rir_objetivo: int | None
    descanso: int | None
    ejercicio_hecho_id: str | None = None
    no_disponible: bool = False


@dataclass(frozen=True)
class PropuestaSesion:
    sesion_planificada: SesionPlanificada | None
    pendientes: tuple[PendienteEntrenamiento, ...]
    explicacion: tuple[Razon, ...]
    version: str
    prescripcion: tuple[PrescripcionEjercicio, ...] = ()
    frenos: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecordPersonal:
    medida: str
    marca: Decimal | int
    marca_anterior: Decimal | int
    carga: Decimal
    explicacion: Razon


@dataclass(frozen=True)
class PermanenciaHabitual:
    suficiente: bool
    observaciones: int
    mediana: int | None = None
    p25: int | None = None
    p75: int | None = None


@dataclass(frozen=True)
class FranjaPrevista:
    desde: str
    hasta: str
    prevision: float
    observaciones: int


@dataclass(frozen=True)
class MejoresHorariosDia:
    franjas: tuple[FranjaPrevista, ...]
    cerrado: bool = False
    datos_insuficientes: bool = False


@dataclass(frozen=True)
class MejoresHorarios:
    hoy: MejoresHorariosDia
    manana: MejoresHorariosDia
