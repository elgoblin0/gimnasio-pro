"""Lectura de programas por socio y versión, y gestión del estado de equipos."""

import json
from contextlib import nullcontext
from datetime import UTC

from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.ids import desde_bytes, desde_texto, nuevo_id
from gimnasio.comun.reloj import reloj_actual
from gimnasio.programas import repositorio

MEDIDAS = ("repeticiones", "carga", "duracion", "distancia")
OBJETIVOS = (
    "repeticiones_minimas",
    "repeticiones_maximas",
    "rir_objetivo",
    "descanso",
    "carga",
    "duracion",
    "distancia",
)


def _equipo_publico(fila):
    return {
        **fila,
        "id": str(desde_bytes(fila["id"])),
        "autor_id": str(desde_bytes(fila["autor_id"])) if fila["autor_id"] else None,
        "ultimo_cambio": fila["ultimo_cambio"].replace(tzinfo=UTC).isoformat() if fila["ultimo_cambio"] else None,
    }


def listar_equipos():
    with transaccion() as cursor:
        return [_equipo_publico(fila) for fila in repositorio.leer_equipos(cursor)]


def equipos_fuera_de_servicio(cursor=None, *, momento=None):
    """Nombres no disponibles al momento indicado, o actuales si se omite."""
    with nullcontext(cursor) if cursor is not None else transaccion() as cursor:
        return frozenset(
            fila["nombre"]
            for fila in repositorio.leer_equipos(cursor, momento=momento)
            if fila["estado"] == "fuera_de_servicio" and fila["nombre"] not in ("", "sin equipo")
        )


def cambiar_estado_equipo(equipo_id, datos, usuario):
    try:
        equipo_id = desde_texto(equipo_id)
    except (ValueError, AttributeError) as error:
        raise ErrorDeDominio("id_invalido", "El identificador debe ser un UUIDv7.", 422) from error
    if not isinstance(datos, dict) or set(datos) - {"estado", "motivo"}:
        raise ErrorDeDominio("cuerpo_invalido", "Enviá estado y un motivo opcional.", 422)
    estado, motivo = datos.get("estado"), datos.get("motivo")
    if estado not in ("disponible", "fuera_de_servicio"):
        raise ErrorDeDominio("estado_invalido", "Elegí disponible o fuera_de_servicio.", 422)
    if motivo is not None and (not isinstance(motivo, str) or len(motivo) > 500):
        raise ErrorDeDominio("motivo_invalido", "El motivo debe ser texto de hasta 500 caracteres.", 422)
    reloj = reloj_actual()
    with transaccion() as cursor:
        # Primera lectura: serializa cambios antes de abrir la lectura consistente del historial.
        if repositorio.bloquear_equipo(cursor, equipo_id) is None:
            raise ErrorDeDominio("equipo_inexistente", "El equipo no existe.", 404)
        equipo = repositorio.leer_equipos(cursor, equipo_id)[0]
        if equipo["estado"] == estado:
            raise ErrorDeDominio("estado_sin_cambio", "El equipo ya tiene ese estado.", 409)
        repositorio.insertar_cambio_estado(
            cursor, nuevo_id(reloj), equipo_id, estado, motivo, desde_texto(usuario["id"]), reloj.ahora()
        )
        return _equipo_publico(repositorio.leer_equipos(cursor, equipo_id)[0])


def equipos_fuera_de_servicio_en_momentos(cursor, momentos):
    """Resuelve el historial de sesiones en una sola lectura."""
    por_momento = dict.fromkeys(momentos, frozenset())
    if por_momento:
        for fila in repositorio.leer_equipos_en_momentos(cursor, por_momento):
            por_momento[fila["momento"]] |= {fila["nombre"]}
    return por_momento


def validar_medidas_aplicables(medidas):
    """El catálogo usa una lista JSON de nombres; carga en kg, duración en s y distancia en m."""
    if not isinstance(medidas, list) or any(not isinstance(medida, str) or medida not in MEDIDAS for medida in medidas):
        raise ValueError("Las medidas aplicables deben ser una lista de repeticiones, carga, duracion o distancia.")


def listar_programas(socio_id, *, cursor=None):
    """Devuelve todas las versiones del socio en orden ascendente, con sesiones y ejercicios por posición.

    Uso interno desde servicios de entrenamiento: el llamador controla el acceso al socio.
    Los identificadores se devuelven en texto, las fechas en UTC y los decimales sin redondear.
    """
    return _leer(socio_id, cursor=cursor)


def obtener_programa(socio_id, version):
    """Lee una versión explícita, o None si no existe para ese socio; nunca elige otra versión."""
    if type(version) is not int:
        raise ValueError("La versión del programa de entrenamiento debe ser un entero.")
    programas = _leer(socio_id, version)
    return programas[0] if programas else None


def _leer(socio_id, version=None, *, cursor=None):
    with nullcontext(cursor) if cursor is not None else transaccion() as cursor:
        filas = repositorio.leer_por_socio(cursor, socio_id, version)
    programas = {}
    sesiones = {}
    for fila in filas:
        programa_id = str(desde_bytes(fila["programa_id"]))
        if programa_id not in programas:
            programas[programa_id] = {
                "id": programa_id,
                "socio_id": str(desde_bytes(fila["socio_id"])),
                "version": fila["version"],
                "creado_en": fila["creado_en"].replace(tzinfo=UTC),
                "sesiones_planificadas": [],
            }
        if fila["sesion_id"] is None:
            continue
        sesion_id = str(desde_bytes(fila["sesion_id"]))
        if sesion_id not in sesiones:
            sesiones[sesion_id] = {
                "id": sesion_id,
                "posicion": fila["sesion_posicion"],
                "nombre": fila["sesion_nombre"],
                "ejercicios_planificados": [],
            }
            programas[programa_id]["sesiones_planificadas"].append(sesiones[sesion_id])
        if fila["planificado_id"] is None:
            continue
        medidas = json.loads(fila["medidas_aplicables"])
        validar_medidas_aplicables(medidas)
        if any(
            fila[campo] is not None
            for medida in MEDIDAS
            if medida not in medidas
            for campo in (("repeticiones_minimas", "repeticiones_maximas") if medida == "repeticiones" else (medida,))
        ):
            raise ValueError("Las medidas no aplicables del ejercicio planificado deben ser NULL.")
        sesiones[sesion_id]["ejercicios_planificados"].append(
            {
                "id": str(desde_bytes(fila["planificado_id"])),
                "ejercicio_id": str(desde_bytes(fila["ejercicio_id"])),
                "nombre": fila["ejercicio_nombre"],
                "posicion": fila["ejercicio_posicion"],
                "medidas_aplicables": medidas,
                "series": fila["series"],
                **{medida: fila[medida] for medida in OBJETIVOS},
                "patron_movimiento": fila["patron_movimiento"],
                "equipo": fila["equipo"],
                "incremento_carga": fila["incremento_carga"],
                "zonas": sorted(json.loads(fila["zonas"])),
                "alternativas": sorted(json.loads(fila["alternativas"]), key=lambda a: (a["orden"], a["ejercicio_id"])),
            }
        )
    return list(programas.values())
