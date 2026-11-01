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
    "riesgo_abandono",
)


def _del_grupo(motivo, tipo):
    return motivo.tipo == tipo or tipo == "aviso_seguridad" and motivo.tipo == "condicion_sin_revisar"


def priorizar_bandeja(socios):
    """Recibe socios inmutables con motivos y fechas ISO en UTC.

    Cada socio aparece una vez con todos sus motivos. Los grupos vacíos
    conservan el orden estable; la antigüedad usa solo el motivo prioritario.
    """
    grupos = {tipo: [] for tipo in GRUPOS}
    for socio in socios:
        if not socio.motivos:
            continue
        tipo = next(tipo for tipo in GRUPOS if any(_del_grupo(m, tipo) for m in socio.motivos))
        fecha = min(m.fecha for m in socio.motivos if _del_grupo(m, tipo))
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
                    key=lambda socio: (min(m.fecha for m in socio.motivos if _del_grupo(m, tipo)), socio.id),
                )
            ),
        )
        for tipo in GRUPOS
    )
