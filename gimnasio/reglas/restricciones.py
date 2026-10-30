"""Freno 2: ninguna alternativa puede contradecir una restricción de salud."""

from dataclasses import replace

from gimnasio.comun.tipos import Razon
from gimnasio.reglas.alternativas import elegir_alternativas
from gimnasio.reglas.version import VERSION_REGLAS


def excluido(ejercicio, restricciones):
    return any(
        r.ejercicio_id == ejercicio.ejercicio_id
        or (r.patron_movimiento is not None and r.patron_movimiento == ejercicio.patron_movimiento)
        or r.zona in ejercicio.zonas
        for r in restricciones
    )


def aplicar_restricciones(
    prescripcion, ejercicio, catalogo, restricciones, zonas_dolor=(), equipos_fuera_de_servicio=frozenset()
):
    hecho = next((e for e in catalogo if e.ejercicio_id == prescripcion.ejercicio_hecho_id), ejercicio)
    if not excluido(hecho, restricciones):
        return prescripcion, (), ()
    excluidos = tuple(e.ejercicio_id for e in catalogo if excluido(e, restricciones))
    zonas = tuple({r.zona for r in restricciones if r.zona is not None} | set(zonas_dolor))
    alternativas, _ = elegir_alternativas(
        ejercicio.ejercicio_id,
        catalogo,
        zonas_excluidas=zonas,
        ejercicios_excluidos=excluidos,
        motivo="restriccion_salud",
        equipos_fuera_de_servicio=equipos_fuera_de_servicio,
    )
    hecho_id = alternativas[0].ejercicio_id if alternativas and prescripcion.series else None
    prescripcion = replace(prescripcion, ejercicio_hecho_id=hecho_id, series=prescripcion.series if hecho_id else 0)
    return (
        prescripcion,
        (
            Razon(
                "restriccion_salud",
                VERSION_REGLAS,
                (
                    ("ejercicio_id", prescripcion.ejercicio_id),
                    ("ejercicio_hecho_id", hecho_id or ""),
                    (
                        "explicacion",
                        "Se sustituye el ejercicio por una restricción registrada por tu entrenador."
                        if hecho_id
                        else "Se quita el ejercicio por una restricción registrada por tu entrenador.",
                    ),
                ),
            ),
        ),
        ("restriccion_salud",),
    )
