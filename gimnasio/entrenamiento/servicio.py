"""Compone programa e historial vigente con el motor puro, sin ajustes ni salud."""

from collections import Counter
from zoneinfo import ZoneInfo

from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.ids import desde_bytes, desde_texto
from gimnasio.comun.reloj import fecha_local, inicio_de_semana, reloj_actual
from gimnasio.comun.tipos import (
    DatosPropuesta,
    EjercicioPlanificado,
    ProgramaEntrenamiento,
    SerieRealizada,
    SesionPlanificada,
)
from gimnasio.entrenamiento import repositorio
from gimnasio.permisos.servicio import tiene_asignacion_vigente
from gimnasio.programas.servicio import listar_programas
from gimnasio.reglas.sesion import proponer_sesion


def identificar(texto):
    try:
        if not isinstance(texto, str):
            raise ValueError("El identificador debe ser texto.")
        return desde_texto(texto)
    except (ValueError, AttributeError) as error:
        raise ErrorDeDominio("id_invalido", "El identificador debe ser un UUIDv7.", 422) from error


def autorizar_socio(cursor, socio_id, usuario):
    socio = repositorio.obtener_socio(cursor, socio_id)
    if socio is None or socio["rol"] != "socio" or not socio["activo"]:
        raise ErrorDeDominio("socio_inexistente", "El socio no existe.", 404)
    if usuario["rol"] == "socio" and identificar(usuario["id"]) == socio_id:
        return
    if usuario["rol"] == "entrenador" and tiene_asignacion_vigente(cursor, socio_id, identificar(usuario["id"])):
        return
    raise ErrorDeDominio("sin_alcance", "No tenés acceso al entrenamiento de este socio.", 403)


def convertir_programa(programa):
    if programa is None:
        return None
    return ProgramaEntrenamiento(
        tuple(
            SesionPlanificada(
                sesion["id"],
                tuple(
                    EjercicioPlanificado(
                        ejercicio["id"],
                        ejercicio["series"],
                        ejercicio["repeticiones"],
                        ejercicio["carga"],
                        ejercicio["duracion"],
                        ejercicio["distancia"],
                    )
                    for ejercicio in sesion["ejercicios_planificados"]
                ),
            )
            for sesion in programa["sesiones_planificadas"]
        )
    )


def convertir_series(filas):
    cantidades = Counter()
    series = []
    for fila in filas:
        sesion_id = str(desde_bytes(fila["sesion_planificada_id"]))
        ejercicio_id = str(desde_bytes(fila["ejercicio_planificado_id"]))
        cantidades[sesion_id, ejercicio_id] += 1
        series.append(
            SerieRealizada(
                sesion_id,
                ejercicio_id,
                cantidades[sesion_id, ejercicio_id],
                fila["repeticiones"],
                fila["carga"],
                duracion=fila["duracion"],
                distancia=fila["distancia"],
            )
        )
    return tuple(series), cantidades


def consultar_propuesta(socio_texto, usuario):
    socio_id = identificar(socio_texto)
    ahora = reloj_actual().ahora()
    with transaccion() as cursor:
        autorizar_socio(cursor, socio_id, usuario)
        sede = repositorio.obtener_sede(cursor)
        if sede is None:
            raise ErrorDeDominio("sede_inexistente", "La sede no existe.", 404)
        filas = repositorio.listar_series_vigentes(cursor, socio_id)
    programas = listar_programas(socio_id)
    programa = programas[-1] if programas else None
    local = fecha_local(ahora, ZoneInfo(sede["zona_horaria"]))
    series, cantidades = convertir_series(filas)
    propuesta = proponer_sesion(DatosPropuesta(convertir_programa(programa), local, inicio_de_semana(local), series))
    respuesta = {
        "sesion_planificada": None,
        "ejercicios": [],
        "explicacion": [
            {"regla": razon.regla, "version": razon.version, "datos": dict(razon.datos)}
            for razon in propuesta.explicacion
        ],
        "version_reglas": propuesta.version,
        "fecha_local": local.isoformat(),
        "semana_local": inicio_de_semana(local).isoformat(),
    }
    if propuesta.sesion_planificada is None:
        return respuesta
    sesion = next(s for s in programa["sesiones_planificadas"] if s["id"] == propuesta.sesion_planificada.id)
    respuesta["sesion_planificada"] = {"id": sesion["id"], "nombre": sesion["nombre"], "posicion": sesion["posicion"]}
    pendientes = {p.ejercicio_id: len(p.series) for p in propuesta.pendientes}
    respuesta["ejercicios"] = [
        {
            "id": e["id"],
            "ejercicio_id": e["ejercicio_id"],
            "nombre": e["nombre"],
            "posicion": e["posicion"],
            "medidas_aplicables": e["medidas_aplicables"],
            "objetivos": {m: e[m] for m in ("series", "repeticiones", "carga", "duracion", "distancia")},
            "realizado": cantidades[sesion["id"], e["id"]],
            "pendiente": pendientes.get(e["id"], 0),
        }
        for e in sesion["ejercicios_planificados"]
    ]
    return respuesta
