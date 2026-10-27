"""Recorrido mínimo del programa, sin ajustes automáticos (issue #38)."""

from gimnasio.comun.tipos import DatosPropuesta, PendienteEntrenamiento, PropuestaSesion, Razon

VERSION_REGLAS = "1.0.0"


def proponer_sesion(entrada: DatosPropuesta) -> PropuestaSesion:
    """Elige la primera sesión con pendientes y conserva su prescripción completa.

    Solo las series realizadas vigentes acreditan trabajo. Las entradas y salidas
    de visitas no forman parte de esta entrada. Ni el día ni el cambio de semana
    agregan volumen o reinician el programa. La fecha y el lunes local llegan
    calculados por quien llama, sin consultar el reloj ni filtrar el historial
    a la semana actual.
    """
    contexto = (
        ("fecha_local", entrada.fecha_local.isoformat()),
        ("semana_local", entrada.semana_local.isoformat()),
    )
    if entrada.programa is None:
        return PropuestaSesion(
            None,
            (),
            (
                Razon(
                    "sin_programa",
                    VERSION_REGLAS,
                    contexto + (("explicacion", "No hay programa de entrenamiento para proponer una sesión."),),
                ),
            ),
            VERSION_REGLAS,
        )

    realizadas = {
        (serie.sesion_planificada_id, serie.ejercicio_id, serie.numero_serie)
        for serie in entrada.series_realizadas
        if serie.vigente
    }
    for sesion in entrada.programa.sesiones:
        pendientes = tuple(
            PendienteEntrenamiento(ejercicio.ejercicio_id, numeros)
            for ejercicio in sesion.ejercicios
            if (
                numeros := tuple(
                    numero
                    for numero in range(1, ejercicio.series + 1)
                    if (sesion.id, ejercicio.ejercicio_id, numero) not in realizadas
                )
            )
        )
        if pendientes:
            return PropuestaSesion(
                sesion,
                pendientes,
                (
                    Razon(
                        "primera_sesion_pendiente",
                        VERSION_REGLAS,
                        contexto
                        + (
                            ("sesion_planificada_id", sesion.id),
                            ("series_pendientes", str(sum(len(p.series) for p in pendientes))),
                            (
                                "explicacion",
                                "Se propone la primera sesión planificada de la secuencia con trabajo pendiente. "
                                "Solo las series realizadas vigentes acreditan trabajo; "
                                "una ausencia no agrega volumen.",
                            ),
                        ),
                    ),
                    Razon(
                        "respeto_programa_entrenador",
                        VERSION_REGLAS,
                        (
                            (
                                "explicacion",
                                "Se respeta el plan del entrenador sin ajustes "
                                "de carga, repeticiones, series ni volumen.",
                            ),
                        ),
                    ),
                ),
                VERSION_REGLAS,
            )

    return PropuestaSesion(
        None,
        (),
        (
            Razon(
                "secuencia_realizada",
                VERSION_REGLAS,
                contexto
                + (
                    (
                        "explicacion",
                        "No queda trabajo pendiente en la secuencia del programa; no se reinicia automáticamente.",
                    ),
                ),
            ),
        ),
        VERSION_REGLAS,
    )
