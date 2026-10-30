"""Alternativas compatibles para una sustitución, sin efectos secundarios."""

from gimnasio.comun.tipos import Razon
from gimnasio.reglas.version import VERSION_REGLAS


def elegir_alternativas(
    ejercicio_id,
    catalogo,
    zonas_excluidas=(),
    ejercicios_excluidos=(),
    motivo="maquina_ocupada",
    equipos_fuera_de_servicio=frozenset(),
):
    original = next((e for e in catalogo if e.ejercicio_id == ejercicio_id), None)
    if original is None:
        return (), None
    alternativas = tuple(
        e
        for e in catalogo
        if e.ejercicio_id in original.alternativas
        and e.ejercicio_id != ejercicio_id
        and e.equipo != original.equipo
        and e.equipo not in equipos_fuera_de_servicio
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
    if zonas_excluidas or motivo == "equipo_fuera_de_servicio":
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
                else f"{primera.nombre} usa un equipo disponible: el equipo del ejercicio está fuera de servicio."
                if motivo == "equipo_fuera_de_servicio"
                else f"{primera.nombre} usa otro equipo y conserva el patrón de movimiento y las zonas del cuerpo.",
            ),
        ),
    )
