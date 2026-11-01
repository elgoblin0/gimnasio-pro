"""Registro de pago y renovación en una sola transacción."""

from contextlib import nullcontext
from datetime import UTC, date, datetime, time, timedelta
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


def registrar_pago(datos, usuario, *, cursor=None):
    requeridos = {"socio_id", "tipo_id", "medio"}
    if not isinstance(datos, dict) or not requeridos <= set(datos) or set(datos) - requeridos - {"monto"}:
        raise ErrorDeDominio("cuerpo_invalido", "Enviá socio_id, tipo_id, medio y opcionalmente monto.", 422)
    socio_id, tipo_id = identificar(datos["socio_id"]), identificar(datos["tipo_id"])
    medio = datos["medio"]
    if not isinstance(medio, str) or medio not in {"efectivo", "transferencia", "tarjeta", "otro"}:
        raise ErrorDeDominio("medio_invalido", "Elegí efectivo, transferencia, tarjeta u otro.", 422)
    monto = validar_entero(datos["monto"], "El monto") if "monto" in datos else None
    with transaccion() if cursor is None else nullcontext(cursor) as cursor:
        tipo = _tipo(cursor, tipo_id)
        if tipo["archivado"]:
            raise ErrorDeDominio("tipo_archivado", "El tipo de membresía está archivado.", 422)
        sede = repositorio.zona_sede(cursor)
        if sede is None:
            raise ErrorDeDominio("sede_inexistente", "La sede no existe.", 404)
        monto = tipo["precio"] if monto is None else monto
        socios.bloquear_socio_activo(socio_id, cursor=cursor)
        ahora, pago_id = reloj_actual().ahora(), nuevo_id()
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


def anular_pago(pago_id, datos, usuario):
    pago_id = identificar(pago_id)
    motivo = datos.get("motivo") if isinstance(datos, dict) else None
    if not isinstance(motivo, str) or not 1 <= len(motivo.strip()) <= 500:
        raise ErrorDeDominio("motivo_invalido", "Indicá un motivo de hasta 500 caracteres.", 422)
    with transaccion() as cursor:
        pago = repositorio.obtener_pago(cursor, pago_id)
        if pago is None:
            raise ErrorDeDominio("pago_inexistente", "El pago no existe.", 404)
        socio_id = desde_bytes(pago["socio_id"])
        socios.bloquear_socio(socio_id, cursor=cursor)
        ultimo = repositorio.ultimo_pago(cursor, socio_id)
        if ultimo is None or ultimo["id"] != pago["id"]:
            raise ErrorDeDominio("no_es_ultimo_pago", "Solo se puede anular el último pago no anulado.", 409)
        identificador, ahora = nuevo_id(), reloj_actual().ahora()
        repositorio.insertar_anulacion(
            cursor, identificador, pago_id, motivo.strip(), identificar(usuario["id"]), ahora
        )
        return {"id": str(identificador), "pago_id": str(pago_id), "motivo": motivo.strip()}


def _pago_publico(fila):
    resultado = {campo: fila[campo] for campo in ("socio", "tipo", "medio", "monto", "autor")}
    resultado.update({campo: str(desde_bytes(fila[campo])) for campo in ("id", "socio_id", "tipo_id", "autor_id")})
    resultado["registrado_en"] = fila["registrado_en"].replace(tzinfo=UTC).isoformat()
    resultado["anulacion"] = None
    if fila["anulacion_id"]:
        resultado["anulacion"] = {
            "id": str(desde_bytes(fila["anulacion_id"])),
            "motivo": fila["motivo"],
            "autor_id": str(desde_bytes(fila["anulacion_autor_id"])),
            "registrado_en": fila["anulada_en"].replace(tzinfo=UTC).isoformat(),
        }
    return resultado


def intervalo_fechas(desde, hasta, hoy, zona):
    try:
        desde = date.fromisoformat(desde) if desde is not None else hoy
        hasta = date.fromisoformat(hasta) if hasta is not None else hoy
        if not 0 <= (hasta - desde).days < 62:
            raise ValueError
        return (
            datetime.combine(desde, time.min, zona).astimezone(UTC),
            datetime.combine(hasta + timedelta(days=1), time.min, zona).astimezone(UTC),
        )
    except (ValueError, TypeError, OverflowError) as error:
        raise ErrorDeDominio("fechas_invalidas", "Elegí un intervalo de hasta 62 días.", 422) from error


def listar_pagos(desde=None, hasta=None):
    with transaccion() as cursor:
        zona = ZoneInfo(repositorio.zona_sede(cursor)["zona_horaria"])
        limites = intervalo_fechas(desde, hasta, fecha_local(reloj_actual().ahora(), zona), zona)
        pagos = [_pago_publico(fila) for fila in repositorio.listar_pagos(cursor, *limites)]
    return {"pagos": pagos, "total": sum(pago["monto"] for pago in pagos if pago["anulacion"] is None)}


def pagos_propios(usuario):
    socio_id = identificar(usuario["id"])
    with transaccion() as cursor:
        zona = ZoneInfo(repositorio.zona_sede(cursor)["zona_horaria"])
        pagos = [_pago_publico(fila) for fila in repositorio.listar_pagos(cursor, socio_id=socio_id)]
    membresia = socios.membresia_para_tarjeta(socio_id, fecha_local(reloj_actual().ahora(), zona))
    return {"membresia": membresia, "dias_restantes": membresia["dias_restantes"], "pagos": pagos}
