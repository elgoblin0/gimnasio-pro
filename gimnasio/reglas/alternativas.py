"""Alternativas compatibles para una sustitución, sin efectos secundarios."""

from gimnasio.comun.tipos import Razon
from gimnasio.reglas.progresion import VERSION_REGLAS


def elegir_alternativas(ejercicio_id, catalogo, zonas_excluidas=(), ejercicios_excluidos=(), motivo="maquina_ocupada"):
    original = next((e for e in catalogo if e.ejercicio_id == ejercicio_id), None)
    if original is None:
        return (), None
    alternativas = tuple(
        e
        for e in catalogo
        if e.ejercicio_id in original.alternativas
        and e.ejercicio_id != ejercicio_id
        and e.equipo != original.equipo
        and e.patron_movimiento == original.patron_movimiento
        and (
            bool(e.zonas) and set(e.zonas) <= set(original.zonas) and set(e.zonas).isdisjoint(zonas_excluidas)
            if zonas_excluidas
            else set(e.zonas) == set(original.zonas)
        )
        and e.ejercicio_id not in ejercicios_excluidos
    )
    if not alternativas:
        return (), None
    if zonas_excluidas:
        alternativas = tuple(sorted(alternativas, key=lambda e: original.alternativas.index(e.ejercicio_id)))
    primera = alternativas[0]
    return alternativas, Razon(
        motivo,
        VERSION_REGLAS,
        (
            ("ejercicio_id", ejercicio_id),
            ("ejercicio_hecho_id", primera.ejercicio_id),
            (
                "explicacion",
                f"{primera.nombre} conserva el patrón de movimiento y no involucra la zona con dolor."
                if motivo == "dolor_reportado"
                else f"{primera.nombre} usa otro equipo y conserva el patrón de movimiento y las zonas del cuerpo.",
            ),
        ),
    )
