"""Alternativas compatibles para una sustitución, sin efectos secundarios."""

from gimnasio.comun.tipos import Razon
from gimnasio.reglas.progresion import VERSION_REGLAS


def elegir_alternativas(ejercicio_id, catalogo, zonas_excluidas=(), ejercicios_excluidos=()):
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
        and set(e.zonas) == set(original.zonas)
        and not set(e.zonas).intersection(zonas_excluidas)
        and e.ejercicio_id not in ejercicios_excluidos
    )
    if not alternativas:
        return (), None
    primera = alternativas[0]
    return alternativas, Razon(
        "maquina_ocupada",
        VERSION_REGLAS,
        (
            ("ejercicio_id", ejercicio_id),
            ("ejercicio_hecho_id", primera.ejercicio_id),
            (
                "explicacion",
                f"{primera.nombre} usa otro equipo y conserva el patrón de movimiento y las zonas del cuerpo.",
            ),
        ),
    )
