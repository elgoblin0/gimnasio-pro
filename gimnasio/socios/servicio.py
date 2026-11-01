"""Ficha del socio, perfil de entrenamiento y consultas de membresía."""

from datetime import date
from uuid import UUID

from mysql.connector import IntegrityError

from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.formatos import normalizar_cedula, normalizar_correo, normalizar_telefono
from gimnasio.comun.ids import desde_bytes, desde_texto, nuevo_id
from gimnasio.comun.reloj import fecha_local, reloj_actual
from gimnasio.permisos.servicio import tiene_asignacion_vigente
from gimnasio.reglas.membresia import vigencia_renovada
from gimnasio.socios import repositorio


def bloquear_socio(socio_id, *, cursor):
    """Serializa pagos y anulaciones, incluso si el socio quedó inactivo."""
    return repositorio.bloquear_socio(cursor, socio_id)


def bloquear_socio_activo(socio_id, *, cursor):
    """Serializa pagos antes de insertar sus referencias al socio."""
    socio = bloquear_socio(socio_id, cursor=cursor)
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


def _identificador(texto):
    try:
        return desde_texto(texto)
    except (ValueError, TypeError, AttributeError) as error:
        raise ErrorDeDominio("socio_invalido", "El identificador del socio no es válido.", 422) from error


def _objeto(datos, permitidos):
    if not isinstance(datos, dict) or set(datos) - set(permitidos):
        raise ErrorDeDominio("datos_invalidos", "Enviá solo los campos permitidos del formulario.", 422)


def _validar_personales(datos):
    resultado = {}
    for campo, valor in datos.items():
        try:
            if campo in ("nombre", "apellido"):
                if not isinstance(valor, str) or not 1 <= len(valor.strip()) <= 80:
                    raise ValueError(f"El {campo} debe tener entre 1 y 80 caracteres")
                valor = valor.strip()
            elif campo == "cedula":
                valor = normalizar_cedula(valor)
            elif campo in ("telefono", "correo"):
                valor = (
                    None
                    if valor in (None, "")
                    else (normalizar_telefono(valor) if campo == "telefono" else normalizar_correo(valor))
                )
            elif campo == "fecha_nacimiento":
                valor = None if valor in (None, "") else date.fromisoformat(valor)
                if valor is not None and valor > fecha_local(reloj_actual().ahora()):
                    raise ValueError("El nacimiento no puede estar en el futuro")
        except (ValueError, TypeError) as error:
            raise ErrorDeDominio("datos_invalidos", f"{campo}: {error}", 422) from error
        resultado[campo] = valor
    return resultado


def _validar_perfil(datos):
    _objeto(datos, repositorio.CAMPOS_PERFIL)
    for campo, valor in datos.items():
        if valor is None:
            continue
        valido = False
        if campo in ("objetivo", "preferencias"):
            valido = isinstance(valor, str) and len(valor) <= 500
        elif campo == "experiencia":
            valido = isinstance(valor, str) and valor in ("inicial", "intermedia", "avanzada")
        elif campo == "disponibilidad_semanal":
            valido = type(valor) is int and 1 <= valor <= 7
        elif campo == "tiempo_por_sesion":
            valido = type(valor) is int and 15 <= valor <= 240
        if not valido:
            raise ErrorDeDominio("perfil_invalido", f"Revisá {campo.replace('_', ' ')}: el valor no es válido.", 422)
    return datos


def _datos_publicos(fila):
    return {
        campo: fila[campo].isoformat() if isinstance(fila[campo], date) else fila[campo]
        for campo in repositorio.CAMPOS_PERSONALES
    }


def ficha_socio(socio_id, usuario, datos=None, *, guardar=False, propia=False):
    socio = _identificador(socio_id)
    if propia and socio_id != usuario["id"]:
        raise ErrorDeDominio("sin_permiso", "Solo podés editar tu ficha del socio.", 403)
    personales, perfil = {}, None
    if guardar:
        permitidos = ("telefono", "correo", "perfil_entrenamiento") if propia else repositorio.CAMPOS_PERSONALES
        _objeto(datos, permitidos)
        personales = _validar_personales(
            {campo: valor for campo, valor in datos.items() if campo != "perfil_entrenamiento"}
        )
        if "perfil_entrenamiento" in datos:
            perfil = _validar_perfil(datos["perfil_entrenamiento"])
    try:
        with transaccion() as cursor:
            fila = repositorio.buscar_datos_personales(cursor, socio, bloquear=guardar)
            if fila is None:
                raise ErrorDeDominio("socio_no_encontrado", "No se encontró el socio activo.", 404)
            if guardar:
                momento = reloj_actual().ahora()
                repositorio.actualizar_datos_personales(cursor, fila["id"], personales, momento)
                fila.update(personales)
                if perfil is not None:
                    actual = repositorio.buscar_perfil_entrenamiento(cursor, socio, bloquear=True)
                    repositorio.guardar_perfil_entrenamiento(
                        cursor, socio, actual | perfil, momento, _identificador(usuario["id"])
                    )
            respuesta = {"datos_personales": _datos_publicos(fila)}
            if propia:
                respuesta["perfil_entrenamiento"] = repositorio.buscar_perfil_entrenamiento(cursor, socio)
            return respuesta
    except IntegrityError as error:
        if error.errno == 1062:
            for campo, codigo, mensaje in (
                ("cedula", "cedula_repetida", "La cédula ya está registrada."),
                ("correo", "correo_repetido", "El correo ya está registrado."),
            ):
                if f"uq_personas_{campo}" in str(error):
                    raise ErrorDeDominio(codigo, mensaje, 409) from error
        raise


def perfil_entrenamiento(socio_id, usuario, datos=None, *, guardar=False):
    socio = _identificador(socio_id)
    perfil = _validar_perfil(datos) if guardar else None
    with transaccion() as cursor:
        if not tiene_asignacion_vigente(cursor, socio, _identificador(usuario["id"])):
            raise ErrorDeDominio(
                "sin_asignacion", "Solo podés ver el perfil de entrenamiento de tus socios asignados.", 403
            )
        fila = repositorio.buscar_datos_personales(cursor, socio, bloquear=guardar)
        if fila is None:
            raise ErrorDeDominio("socio_no_encontrado", "No se encontró el socio activo.", 404)
        actual = repositorio.buscar_perfil_entrenamiento(cursor, socio, bloquear=guardar)
        if guardar:
            actual |= perfil
            repositorio.guardar_perfil_entrenamiento(
                cursor, socio, actual, reloj_actual().ahora(), _identificador(usuario["id"])
            )
        return {"perfil_entrenamiento": actual}


def membresia_para_tarjeta(socio_id: UUID, fecha_local: date) -> dict:
    """Última membresía iniciada y máximo hasta, incluidas las renovaciones futuras."""
    with transaccion() as cursor:
        membresia = repositorio.buscar_ultima_membresia(cursor, socio_id, fecha_local)
        ultimo_hasta = repositorio.buscar_ultimo_hasta(cursor, socio_id)
    if membresia is None:
        return {
            "vigente": False,
            "hasta": None,
            "dias_restantes": None,
            "ultimo_hasta": ultimo_hasta.isoformat() if ultimo_hasta else None,
        }
    return {
        "ultimo_hasta": ultimo_hasta.isoformat() if ultimo_hasta else None,
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
