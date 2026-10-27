"""Consulta de membresía para visitas, sin consumir entradas."""

from datetime import date
from uuid import UUID

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import desde_bytes
from gimnasio.socios import repositorio


def consultar_membresia(socio_id: UUID, fecha_local: date) -> dict | None:
    """Devuelve la membresía vigente del socio activo, o None si no autoriza por vigencia.

    El llamador pasa el día en America/Asuncion. Ambos extremos son inclusivos;
    las visitas anteriores no consumen cupo. Visita abierta y aforo se comprueban
    en el servicio de visitas (#40). Las superposiciones quedan fuera de etapa 1.
    """
    with transaccion() as cursor:
        membresia = repositorio.buscar_membresia_vigente(cursor, socio_id, fecha_local)
    if membresia is None or membresia["rol"] != "socio" or not membresia["activo"]:
        return None
    return {
        "id": str(desde_bytes(membresia["id"])),
        "socio_id": str(desde_bytes(membresia["socio_id"])),
        "desde": membresia["desde"],
        "hasta": membresia["hasta"],
    }
