"""Compone programa e historial vigente con el motor puro, sin ajustes ni salud."""

from collections import Counter
from datetime import UTC
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
from gimnasio.programas.servicio import OBJETIVOS, listar_programas
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
                        repeticiones_minimas=ejercicio["repeticiones_minimas"],
                        repeticiones_maximas=ejercicio["repeticiones_maximas"],
                        carga=ejercicio["carga"],
                        rir_objetivo=ejercicio["rir_objetivo"],
                        descanso=ejercicio["descanso"],
                        duracion=ejercicio["duracion"],
                        distancia=ejercicio["distancia"],
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
                rir=fila["rir"],
                ejercicio_hecho_id=str(desde_bytes(fila["ejercicio_hecho_resuelto_id"])),
            )
        )
    return tuple(series), cantidades


def cargas_anteriores(filas, zona, sesion=None):
    """Última serie vigente por ejercicio realizado, excluyendo sesiones posteriores."""
    resultado = {}
    for fila in filas:
        if sesion is not None and (fila["sesion_creada_en"], fila["sesion_realizada_id"]) >= (
            sesion["creada_en"],
            sesion["id"],
        ):
            continue
        resultado[str(desde_bytes(fila["ejercicio_hecho_resuelto_id"]))] = {
            "carga": fila["carga"],
            "repeticiones": fila["repeticiones"],
            "fecha_local": fecha_local(fila["registrada_en"].replace(tzinfo=UTC), zona).isoformat(),
        }
    return resultado


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
    anteriores = cargas_anteriores(filas, ZoneInfo(sede["zona_horaria"]))
    pendientes = {p.ejercicio_id: len(p.series) for p in propuesta.pendientes}
    respuesta["ejercicios"] = [
        {
            "id": e["id"],
            "ejercicio_id": e["ejercicio_id"],
            "carga_anterior": anteriores.get(e["ejercicio_id"]),
            "nombre": e["nombre"],
            "posicion": e["posicion"],
            "medidas_aplicables": e["medidas_aplicables"],
            **{
                campo: e[campo]
                for campo in ("zonas", "patron_movimiento", "equipo", "incremento_carga", "alternativas")
            },
            "objetivos": {m: e[m] for m in ("series", *OBJETIVOS)},
            "realizado": cantidades[sesion["id"], e["id"]],
            "pendiente": pendientes.get(e["id"], 0),
        }
        for e in sesion["ejercicios_planificados"]
    ]
    return respuesta


def sesion_publica(fila):
    return {
        "id": str(desde_bytes(fila["id"])),
        "socio_id": str(desde_bytes(fila["socio_id"])),
        "sesion_planificada_id": str(desde_bytes(fila["sesion_planificada_id"])),
        "creada_en": fila["creada_en"].replace(tzinfo=UTC).isoformat(),
    }


def serie_publica(fila):
    return {
        "id": str(desde_bytes(fila["id"])),
        "sesion_realizada_id": str(desde_bytes(fila["sesion_realizada_id"])),
        "ejercicio_planificado_id": str(desde_bytes(fila["ejercicio_planificado_id"])),
        **{m: fila[m] for m in repositorio.MEDIDAS},
        "rir": fila["rir"],
        "ejercicio_hecho_id": str(desde_bytes(fila["ejercicio_hecho_resuelto_id"])),
        "autor_id": str(desde_bytes(fila["autor_id"])),
        "registrada_en": fila["registrada_en"].replace(tzinfo=UTC).isoformat(),
    }


def _sesion_propia(cursor, sesion_id, usuario):
    fila = repositorio.obtener_sesion(cursor, sesion_id)
    if fila is None:
        raise ErrorDeDominio("sesion_inexistente", "La sesión realizada no existe.", 404)
    _exigir_propiedad(fila, usuario)
    return fila


def _exigir_propiedad(fila, usuario):
    if str(desde_bytes(fila["socio_id"])) != usuario["id"]:
        raise ErrorDeDominio("sin_alcance", "No tenés acceso a esta sesión realizada.", 403)


def _exigir_destino_serie(fila, sesion_id, ejercicio_id):
    if (
        desde_bytes(fila["sesion_realizada_id"]) != sesion_id
        or desde_bytes(fila["ejercicio_planificado_id"]) != ejercicio_id
    ):
        raise ErrorDeDominio("id_ajeno", "El identificador corresponde a otra serie realizada.", 403)


def crear_sesion(datos, usuario):
    if not isinstance(datos, dict) or set(datos) != {"id", "sesion_planificada_id"}:
        raise ErrorDeDominio("cuerpo_invalido", "Enviá id y sesion_planificada_id.", 422)
    sesion_id, planificada_id = identificar(datos["id"]), identificar(datos["sesion_planificada_id"])
    ahora = reloj_actual().ahora()
    with transaccion() as cursor:
        anterior = repositorio.obtener_sesion(cursor, sesion_id)
        if anterior is not None:
            _exigir_propiedad(anterior, usuario)
            if desde_bytes(anterior["sesion_planificada_id"]) != planificada_id:
                raise ErrorDeDominio("id_ajeno", "El identificador corresponde a otra sesión planificada.", 403)
            return sesion_publica(anterior)
        planificada = repositorio.obtener_planificada(cursor, planificada_id)
        if planificada is None:
            raise ErrorDeDominio("planificada_inexistente", "La sesión planificada no existe.", 404)
        _exigir_propiedad(planificada, usuario)
        repositorio.insertar_sesion(cursor, sesion_id, identificar(usuario["id"]), planificada_id, ahora)
        # Tras un INSERT duplicado concurrente, leer el registro confirmado y validar su pertenencia.
        fila = repositorio.obtener_sesion(cursor, sesion_id, actual=True)
        _exigir_propiedad(fila, usuario)
        if desde_bytes(fila["sesion_planificada_id"]) != planificada_id:
            raise ErrorDeDominio("id_ajeno", "El identificador corresponde a otra sesión planificada.", 403)
        return sesion_publica(fila)


def registrar_serie(sesion_texto, datos, usuario):
    campos = {"id", "ejercicio_planificado_id"}
    if (
        not isinstance(datos, dict)
        or not campos <= set(datos)
        or set(datos) - campos - set(repositorio.MEDIDAS) - {"rir"}
    ):
        raise ErrorDeDominio("cuerpo_invalido", "Enviá id, ejercicio_planificado_id y sus medidas aplicables.", 422)
    rir = datos.get("rir")
    if rir is not None and (type(rir) is not int or not 0 <= rir <= 10):
        raise ErrorDeDominio("rir_invalido", "El RIR debe ser un entero entre 0 y 10.", 400)
    sesion_id = identificar(sesion_texto)
    serie_id, ejercicio_id = identificar(datos["id"]), identificar(datos["ejercicio_planificado_id"])
    ahora = reloj_actual().ahora()
    with transaccion() as cursor:
        sesion = _sesion_propia(cursor, sesion_id, usuario)
        anterior = repositorio.obtener_serie(cursor, serie_id)
        if anterior is not None:
            _exigir_destino_serie(anterior, sesion_id, ejercicio_id)
            return serie_publica(anterior)
        ejercicio = repositorio.obtener_ejercicio_planificado(cursor, ejercicio_id)
        if ejercicio is None:
            raise ErrorDeDominio("ejercicio_inexistente", "El ejercicio planificado no existe.", 404)
        if ejercicio["sesion_planificada_id"] != sesion["sesion_planificada_id"]:
            raise ErrorDeDominio("ejercicio_invalido", "El ejercicio no pertenece a esta sesión planificada.", 422)
        try:
            repositorio.insertar_serie(
                cursor,
                serie_id,
                sesion_id,
                ejercicio_id,
                identificar(usuario["id"]),
                ahora,
                rir=rir,
                **{m: datos.get(m) for m in repositorio.MEDIDAS},
            )
        except ValueError as error:
            raise ErrorDeDominio("medidas_invalidas", str(error), 422) from error
        fila = repositorio.obtener_serie(cursor, serie_id, actual=True)
        _exigir_destino_serie(fila, sesion_id, ejercicio_id)
        return serie_publica(fila)


def consultar_sesion(sesion_texto, usuario):
    sesion_id = identificar(sesion_texto)
    with transaccion() as cursor:
        sesion = _sesion_propia(cursor, sesion_id, usuario)
        filas = repositorio.listar_series_vigentes(cursor, identificar(usuario["id"]), sesion_id)
        historial = repositorio.listar_series_vigentes(cursor, identificar(usuario["id"]))
        sede = repositorio.obtener_sede(cursor)
    programas = listar_programas(identificar(usuario["id"]))
    planificada = next(
        s
        for p in programas
        for s in p["sesiones_planificadas"]
        if s["id"] == str(desde_bytes(sesion["sesion_planificada_id"]))
    )
    anteriores = cargas_anteriores(historial, ZoneInfo(sede["zona_horaria"]), sesion)
    cantidades = Counter(str(desde_bytes(f["ejercicio_planificado_id"])) for f in filas)
    return {
        "sesion_realizada": sesion_publica(sesion),
        "series": [serie_publica(f) for f in filas],
        "ejercicios": [
            {
                "id": e["id"],
                "nombre": e["nombre"],
                "carga_anterior": anteriores.get(e["ejercicio_id"]),
                "medidas_aplicables": e["medidas_aplicables"],
                **{
                    campo: e[campo]
                    for campo in ("zonas", "patron_movimiento", "equipo", "incremento_carga", "alternativas")
                },
                "objetivos": {m: e[m] for m in ("series", *OBJETIVOS)},
                "realizado": cantidades[e["id"]],
                "pendiente": max(0, e["series"] - cantidades[e["id"]]),
            }
            for e in planificada["ejercicios_planificados"]
        ],
    }
