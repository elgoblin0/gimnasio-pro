"""Registro de pago y renovación en una sola transacción."""

from datetime import UTC
from zoneinfo import ZoneInfo

from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.ids import desde_bytes, desde_texto, nuevo_id
from gimnasio.comun.reloj import fecha_local, reloj_actual
from gimnasio.pagos import repositorio
from gimnasio.socios import servicio as socios


def identificar(texto):
    try:
        if not isinstance(texto, str):
            raise ValueError
        return desde_texto(texto)
    except (ValueError, AttributeError) as error:
        raise ErrorDeDominio("id_invalido", "El identificador debe ser un UUIDv7.", 422) from error


def validar_entero(valor, nombre, minimo=0, maximo=18446744073709551615):
    if type(valor) is not int or valor < minimo:
        raise ErrorDeDominio("entero_invalido", f"{nombre} debe ser un entero mayor o igual a {minimo}.", 422)
    if valor > maximo:
        raise ErrorDeDominio("entero_fuera_de_rango", f"{nombre} excede el valor admitido.", 422)
    return valor


def validar_tipo(datos):
    if not isinstance(datos, dict) or set(datos) != {"nombre", "duracion_dias", "precio"}:
        raise ErrorDeDominio("cuerpo_invalido", "Enviá nombre, duracion_dias y precio.", 422)
    nombre = datos["nombre"]
    if not isinstance(nombre, str) or not nombre.strip() or len(nombre.strip()) > 120:
        raise ErrorDeDominio("nombre_invalido", "Indicá un nombre de hasta 120 caracteres.", 422)
    return (
        nombre.strip(),
        validar_entero(datos["duracion_dias"], "La duración", 1, 4294967295),
        validar_entero(datos["precio"], "El precio"),
    )


def tipo_publico(fila):
    return {
        "id": str(desde_bytes(fila["id"])),
        "nombre": fila["nombre"],
        "duracion_dias": fila["duracion_dias"],
        "precio": fila["precio"],
        "archivado": bool(fila["archivado"]),
    }


def _tipo(cursor, tipo_id):
    tipo = repositorio.obtener_tipo(cursor, tipo_id)
    if tipo is None:
        raise ErrorDeDominio("tipo_inexistente", "El tipo de membresía no existe.", 404)
    return tipo


def listar_tipos(*, incluir_archivados=False):
    with transaccion() as cursor:
        return [tipo_publico(fila) for fila in repositorio.listar_tipos(cursor, incluir_archivados)]


def guardar_tipo(datos, tipo_id=None):
    nombre, duracion, precio = validar_tipo(datos)
    ahora = reloj_actual().ahora()
    identificador = identificar(tipo_id) if tipo_id is not None else nuevo_id()
    with transaccion() as cursor:
        if tipo_id is None:
            repositorio.insertar_tipo(cursor, identificador, nombre, duracion, precio, ahora)
        else:
            _tipo(cursor, identificador)
            repositorio.cambiar_tipo(cursor, identificador, nombre, duracion, precio, ahora)
        return tipo_publico(_tipo(cursor, identificador))


def archivar_tipo(tipo_id):
    tipo_id = identificar(tipo_id)
    with transaccion() as cursor:
        _tipo(cursor, tipo_id)
        repositorio.archivar_tipo(cursor, tipo_id, reloj_actual().ahora())
        return tipo_publico(_tipo(cursor, tipo_id))


def registrar_pago(datos, usuario):
    requeridos = {"socio_id", "tipo_id", "medio"}
    if not isinstance(datos, dict) or not requeridos <= set(datos) or set(datos) - requeridos - {"monto"}:
        raise ErrorDeDominio("cuerpo_invalido", "Enviá socio_id, tipo_id, medio y opcionalmente monto.", 422)
    socio_id, tipo_id = identificar(datos["socio_id"]), identificar(datos["tipo_id"])
    medio = datos["medio"]
    if not isinstance(medio, str) or medio not in {"efectivo", "transferencia", "tarjeta", "otro"}:
        raise ErrorDeDominio("medio_invalido", "Elegí efectivo, transferencia, tarjeta u otro.", 422)
    monto = validar_entero(datos["monto"], "El monto") if "monto" in datos else None
    ahora, pago_id = reloj_actual().ahora(), nuevo_id()
    with transaccion() as cursor:
        tipo = _tipo(cursor, tipo_id)
        if tipo["archivado"]:
            raise ErrorDeDominio("tipo_archivado", "El tipo de membresía está archivado.", 422)
        sede = repositorio.zona_sede(cursor)
        if sede is None:
            raise ErrorDeDominio("sede_inexistente", "La sede no existe.", 404)
        monto = tipo["precio"] if monto is None else monto
        socios.bloquear_socio_activo(socio_id, cursor=cursor)
        repositorio.insertar_pago(cursor, pago_id, socio_id, tipo_id, medio, monto, identificar(usuario["id"]), ahora)
        membresia = socios.renovar_membresia(
            socio_id,
            pago_id,
            tipo_id,
            tipo["duracion_dias"],
            fecha_local(ahora, ZoneInfo(sede["zona_horaria"])),
            ahora,
            cursor=cursor,
        )
        return {
            "id": str(pago_id),
            "socio_id": str(socio_id),
            "tipo_id": str(tipo_id),
            "medio": medio,
            "monto": monto,
            "autor_id": usuario["id"],
            "registrado_en": ahora.astimezone(UTC).isoformat(),
            "membresia": membresia,
        }
