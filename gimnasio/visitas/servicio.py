"""Entrada atómica: sede, socio, vigencia, visita abierta y aforo, en ese orden."""

from datetime import UTC
from zoneinfo import ZoneInfo

from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.ids import desde_bytes, desde_texto
from gimnasio.comun.reloj import fecha_local, reloj_actual
from gimnasio.socios.servicio import consultar_membresia
from gimnasio.visitas import repositorio


def identificar(texto):
    try:
        if not isinstance(texto, str):
            raise ValueError("El identificador debe ser texto.")
        return desde_texto(texto)
    except (ValueError, AttributeError) as error:
        raise ErrorDeDominio("id_invalido", "El identificador debe ser un UUIDv7.", 422) from error


def validar_cuerpo(datos, campos):
    if not isinstance(datos, dict) or set(datos) != set(campos):
        raise ErrorDeDominio("cuerpo_invalido", "Enviá únicamente los campos requeridos.", 422)
    return {campo: identificar(datos[campo]) for campo in campos}


def entrada_publica(fila):
    return {
        "id": str(desde_bytes(fila["id"])),
        "socio_id": str(desde_bytes(fila["socio_id"])),
        "sede_id": str(desde_bytes(fila["sede_id"])),
        "autor_id": str(desde_bytes(fila["autor_id"])),
        "registrada_en": fila["registrada_en"].replace(tzinfo=UTC).isoformat(),
    }


def registrar_entrada(datos, usuario):
    ids = validar_cuerpo(datos, ("id", "socio_id", "sede_id"))
    ahora = reloj_actual().ahora()
    with transaccion() as cursor:
        sede = repositorio.bloquear_sede(cursor, ids["sede_id"])
        if sede is None:
            raise ErrorDeDominio("sede_inexistente", "La sede no existe.", 404)
        socio = repositorio.bloquear_socio(cursor, ids["socio_id"])
        if socio is None or socio["rol"] != "socio":
            raise ErrorDeDominio("socio_inexistente", "El socio no existe.", 404)
        anterior = repositorio.obtener_entrada(cursor, ids["id"])
        if anterior is not None:
            if anterior["socio_id"] != socio["id"] or anterior["sede_id"] != sede["id"]:
                raise ErrorDeDominio("id_ajeno", "El identificador corresponde a otra entrada.", 403)
            return entrada_publica(anterior)
        membresia = consultar_membresia(ids["socio_id"], fecha_local(ahora, ZoneInfo(sede["zona_horaria"])))
        if not socio["activo"] or membresia is None:
            raise ErrorDeDominio("membresia_no_vigente", "El socio no tiene una membresía vigente.", 422)
        if repositorio.tiene_visita_abierta(cursor, ids["socio_id"]):
            raise ErrorDeDominio("visita_abierta", "El socio ya tiene una visita abierta.", 409)
        if repositorio.contar_ocupacion_registrada(cursor, ids["sede_id"]) >= sede["aforo_maximo"]:
            raise ErrorDeDominio("aforo_alcanzado", "Se alcanzó el aforo máximo. No se registró la entrada.", 409)
        repositorio.insertar_entrada(
            cursor, ids["id"], ids["socio_id"], ids["sede_id"], identificar(usuario["id"]), ahora
        )
        return entrada_publica(repositorio.obtener_entrada(cursor, ids["id"]))
