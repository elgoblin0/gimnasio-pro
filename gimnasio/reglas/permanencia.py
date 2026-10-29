"""Permanencia habitual y visitas por conciliar; VERSION_PERMANENCIA = "1.0.0"."""

import statistics

from gimnasio.comun.tipos import PermanenciaHabitual, Razon

VERSION_PERMANENCIA = "1.0.0"


def calcular_permanencia_habitual(duraciones_minutos: tuple[int, ...]) -> PermanenciaHabitual:
    """Percentiles inclusivos con interpolación lineal; todos los minutos usan round()."""
    observaciones = len(duraciones_minutos)
    if observaciones < 5:
        return PermanenciaHabitual(suficiente=False, observaciones=observaciones)
    percentiles = statistics.quantiles(duraciones_minutos, n=4, method="inclusive")
    return PermanenciaHabitual(
        suficiente=True,
        observaciones=observaciones,
        mediana=round(statistics.median(duraciones_minutos)),
        p25=round(percentiles[0]),
        p75=round(percentiles[2]),
    )


def es_visita_por_conciliar(duracion_minutos: int, permanencia_sede: PermanenciaHabitual) -> tuple[bool, Razon]:
    umbral = max(2 * permanencia_sede.mediana, 180) if permanencia_sede.suficiente else 240
    return duracion_minutos > umbral, Razon(
        "visita_por_conciliar",
        VERSION_PERMANENCIA,
        (
            ("duracion_minutos", str(duracion_minutos)),
            ("umbral_minutos", str(umbral)),
            ("suficiente", "si" if permanencia_sede.suficiente else "no"),
        ),
    )
