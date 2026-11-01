"""Lectura interna; entrenamiento autoriza al socio antes de consultar salud."""

from contextlib import nullcontext

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import desde_bytes
from gimnasio.comun.tipos import RestriccionSalud
from gimnasio.salud import repositorio


def restricciones_vigentes(socio_id, *, cursor=None):
    """Solo para servicios que ya controlaron el alcance; no se expone una API."""
    with nullcontext(cursor) if cursor is not None else transaccion() as lectura:
        filas = repositorio.restricciones_vigentes(lectura, socio_id)
    return tuple(
        RestriccionSalud(
            str(desde_bytes(f["ejercicio_id"])) if f["ejercicio_id"] else None,
            f["patron_movimiento"],
            f["zona"],
            f["descripcion"],
        )
        for f in filas
    )


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
