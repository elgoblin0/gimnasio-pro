"""Consulta y renovación de membresías, sin consumir entradas."""

from datetime import date
from uuid import UUID

from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.ids import desde_bytes, nuevo_id
from gimnasio.reglas.membresia import vigencia_renovada
from gimnasio.socios import repositorio


def bloquear_socio_activo(socio_id, *, cursor):
    """Serializa pagos antes de insertar sus referencias al socio."""
    socio = repositorio.bloquear_socio(cursor, socio_id)
    if socio is None or socio["rol"] != "socio" or not socio["activo"]:
        raise ErrorDeDominio("socio_inactivo", "El pago requiere un socio activo.", 422)


def renovar_membresia(socio_id, pago_id, tipo_id, duracion_dias, hoy, ahora, *, cursor):
    """Inserta la renovación conservando el historial y la transacción del pago."""
    bloquear_socio_activo(socio_id, cursor=cursor)
    try:
        desde, hasta = vigencia_renovada(hoy, repositorio.ultimo_vencimiento(cursor, socio_id), duracion_dias)
    except (OverflowError, ValueError) as error:
        raise ErrorDeDominio("vigencia_invalida", "La duración excede la vigencia admitida.", 422) from error
    membresia_id = nuevo_id()
    repositorio.insertar_membresia(cursor, membresia_id, socio_id, pago_id, tipo_id, desde, hasta, ahora)
    return {"id": str(membresia_id), "desde": desde.isoformat(), "hasta": hasta.isoformat()}


def membresia_para_tarjeta(socio_id: UUID, fecha_local: date) -> dict | None:
    """Última membresía que comenzó, sin autorizar el registro de entradas."""
    with transaccion() as cursor:
        membresia = repositorio.buscar_ultima_membresia(cursor, socio_id, fecha_local)
    if membresia is None:
        return None
    return {
        "vigente": bool(
            membresia["desde"] <= fecha_local <= membresia["hasta"]
            and membresia["rol"] == "socio"
            and membresia["activo"]
        ),
        "hasta": membresia["hasta"].isoformat(),
        "dias_restantes": (membresia["hasta"] - fecha_local).days,
    }


def consultar_membresia(socio_id: UUID, fecha_local: date, *, cursor=None) -> dict | None:
    """Devuelve la membresía vigente del socio activo, o None si no autoriza por vigencia.

    El llamador pasa el día en America/Asuncion. Ambos extremos son inclusivos;
    las visitas anteriores no consumen cupo. Visita abierta y aforo se comprueban
    en el servicio de visitas (#40). Las superposiciones quedan fuera de etapa 1.
    """
    if cursor is None:
        with transaccion() as lectura:
            membresia = repositorio.buscar_membresia_vigente(lectura, socio_id, fecha_local)
    else:
        membresia = repositorio.buscar_membresia_vigente(cursor, socio_id, fecha_local)
    if membresia is None or membresia["rol"] != "socio" or not membresia["activo"]:
        return None
    return {
        "id": str(desde_bytes(membresia["id"])),
        "socio_id": str(desde_bytes(membresia["socio_id"])),
        "desde": membresia["desde"],
        "hasta": membresia["hasta"],
    }
