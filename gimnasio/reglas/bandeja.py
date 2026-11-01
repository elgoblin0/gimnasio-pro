"""Prioridad y orden únicos de la bandeja del entrenador."""

from dataclasses import replace

from gimnasio.comun.tipos import GrupoBandeja, Razon
from gimnasio.reglas.version import VERSION_REGLAS

GRUPOS = (
    "aviso_seguridad",
    "sin_programa",
    "secuencia_terminada",
    "ejercicio_sin_alternativa",
    "sin_consentimiento_salud",
    "aviso_progresion",
)


def priorizar_bandeja(socios):
    """Recibe socios inmutables con motivos y fechas ISO en UTC.

    Cada socio aparece una vez con todos sus motivos. Los grupos vacíos
    conservan el orden estable; la antigüedad usa solo el motivo prioritario.
    """
    grupos = {tipo: [] for tipo in GRUPOS}
    for socio in socios:
        if not socio.motivos:
            continue
        tipo = next(tipo for tipo in GRUPOS if any(m.tipo == tipo for m in socio.motivos))
        fecha = min(m.fecha for m in socio.motivos if m.tipo == tipo)
        explicacion = Razon(
            "prioridad_bandeja",
            VERSION_REGLAS,
            (("grupo", tipo), ("fecha", fecha)),
        )
        grupos[tipo].append(replace(socio, explicacion=(explicacion,)))
    return tuple(
        GrupoBandeja(
            tipo,
            tuple(
                sorted(
                    grupos[tipo],
                    key=lambda socio: (min(m.fecha for m in socio.motivos if m.tipo == tipo), socio.id),
                )
            ),
        )
        for tipo in GRUPOS
    )
