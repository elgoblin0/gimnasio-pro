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
