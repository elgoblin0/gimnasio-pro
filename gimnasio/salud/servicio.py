"""Lectura interna; entrenamiento autoriza al socio antes de consultar salud."""

from contextlib import nullcontext

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import desde_bytes
from gimnasio.comun.tipos import RestriccionSalud
from gimnasio.salud import repositorio


def tiene_consentimiento_salud(cursor, socio_id):
    fila = repositorio.consentimiento_vigente(cursor, socio_id)
    return bool(fila and fila["otorgado"])


def leer_con_consentimiento(consentimiento, leer, vacio=()):
    """Corte único del ADR 0025: sin consentimiento vigente el motor no lee datos de salud."""
    return leer() if consentimiento else vacio


def restricciones_vigentes(socio_id, *, cursor=None, consentimiento=None):
    """Solo para servicios que ya controlaron el alcance; no se expone una API.

    Quien ya conoce el consentimiento de la operación lo pasa para no consultarlo otra vez.
    """
    with nullcontext(cursor) if cursor is not None else transaccion() as lectura:
        if consentimiento is None:
            consentimiento = tiene_consentimiento_salud(lectura, socio_id)
        filas = leer_con_consentimiento(consentimiento, lambda: repositorio.restricciones_vigentes(lectura, socio_id))
    return tuple(
        RestriccionSalud(
            str(desde_bytes(f["ejercicio_id"])) if f["ejercicio_id"] else None,
            f["patron_movimiento"],
            f["zona"],
            f["descripcion"],
        )
        for f in filas
    )


def revocaciones_de_salud(socio_ids, *, cursor):
    """Fecha de la revocación vigente por socio, sin datos de salud; el socio que consiente no aparece."""
    return {
        desde_bytes(f["socio_id"]): f["registrado_en"] for f in repositorio.revocaciones_de_socios(cursor, socio_ids)
    }


def consultar_consentimiento(socio_id):
    with transaccion() as cursor:
        fila = repositorio.consentimiento_vigente(cursor, socio_id)
    return {
        "salud": {
            "otorgado": bool(fila and fila["otorgado"]),
            "version_texto": repositorio.VERSION_TEXTO,
            "texto": repositorio.TEXTO_CONSENTIMIENTO,
        }
    }


def registrar_consentimiento(socio_id, datos):
    from gimnasio.comun.errores import ErrorDeDominio
    from gimnasio.permisos import servicio as permisos

    if (
        not isinstance(datos, dict)
        or set(datos) != {"otorgado", "version_texto"}
        or type(datos["otorgado"]) is not bool
        or datos["version_texto"] != repositorio.VERSION_TEXTO
    ):
        raise ErrorDeDominio("consentimiento_invalido", "Confirmá el consentimiento con su texto vigente.", 422)
    with transaccion() as cursor:
        permisos.registrar_consentimiento(
            cursor, socio_id, "salud", datos["otorgado"], datos["version_texto"], socio_id
        )
    return consultar_consentimiento(socio_id)
