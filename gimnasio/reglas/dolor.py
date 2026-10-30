"""Freno 1: dolor actual y de la sesión realizada anterior."""

from dataclasses import replace
from decimal import Decimal

from gimnasio.comun.tipos import Razon
from gimnasio.reglas.alternativas import elegir_alternativas
from gimnasio.reglas.version import VERSION_REGLAS


def aplicar_dolor(
    prescripcion, ejercicio, catalogo, actuales, anteriores, razones=(), equipos_fuera_de_servicio=frozenset()
):
    zonas = set(ejercicio.zonas) & (set(actuales) | set(anteriores))
    if not zonas:
        return prescripcion, (), ()
    suba = next((r for r in razones if r.regla == "subir_carga"), None)
    if suba:
        prescripcion = replace(
            prescripcion,
            carga=Decimal(dict(suba.datos)["carga_base"]),
            repeticiones_minimas=prescripcion.repeticiones_maximas,
        )
    explicacion = "Dolor reportado en la sesión anterior: no sube la carga de esta zona en esta sesión."
    hecho_id = None
    if set(ejercicio.zonas) & set(actuales):
        alternativas, razon = elegir_alternativas(
            ejercicio.ejercicio_id,
            catalogo,
            zonas_excluidas=actuales,
            motivo="dolor_reportado",
            equipos_fuera_de_servicio=equipos_fuera_de_servicio,
        )
        if alternativas:
            hecho_id = alternativas[0].ejercicio_id
            explicacion = dict(razon.datos)["explicacion"]
        else:
            prescripcion = replace(prescripcion, series=0)
            explicacion = "Se quita el ejercicio: no hay una alternativa que evite las zonas con dolor."
    prescripcion = replace(prescripcion, ejercicio_hecho_id=hecho_id)
    return (
        prescripcion,
        (
            Razon(
                "dolor_reportado",
                VERSION_REGLAS,
                (
                    ("ejercicio_id", prescripcion.ejercicio_id),
                    ("ejercicio_hecho_id", hecho_id or ""),
                    ("zonas", ", ".join(sorted(zonas))),
                    ("explicacion", explicacion + " No se sube la carga. Se avisa al entrenador."),
                ),
            ),
        ),
        ("dolor_reportado",),
    )
