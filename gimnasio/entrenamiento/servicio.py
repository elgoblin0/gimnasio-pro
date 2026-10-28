"""Compone programa e historial vigente con el motor puro, con doble progresión."""

import json
from collections import Counter
from contextlib import nullcontext
from datetime import UTC
from zoneinfo import ZoneInfo

from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.ids import desde_bytes, desde_texto, nuevo_id
from gimnasio.comun.reloj import fecha_local, inicio_de_semana, reloj_actual
from gimnasio.comun.tipos import (
    Chequeo,
    DatosPropuesta,
    EjercicioCatalogo,
    EjercicioPlanificado,
    HistorialEjercicio,
    ProgramaEntrenamiento,
    SerieRealizada,
    SesionPlanificada,
    SubaCarga,
)
from gimnasio.entrenamiento import repositorio
from gimnasio.permisos.servicio import tiene_asignacion_vigente
from gimnasio.programas.servicio import OBJETIVOS, listar_programas
from gimnasio.reglas.alternativas import elegir_alternativas
from gimnasio.reglas.progresion import historial_para_sesion
from gimnasio.reglas.records import detectar_records
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
                        ejercicio_catalogo_id=ejercicio["ejercicio_id"],
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


def preparar_historial(filas, zona, local, sesion_planificada_id=None):
    """Agrupa hechos vigentes por sesión y ejercicio planificado del catálogo.

    Una corrección no cambia la fecha de la sesión. Una alternativa acredita
    al ejercicio del catálogo que estaba planificado (ADR 0012).
    """
    sesiones = {}
    for fila in sorted(
        filas, key=lambda f: (f["sesion_creada_en"], f["sesion_realizada_id"], f["registrada_en"], f["id"])
    ):
        fecha = fecha_local(fila["sesion_creada_en"].replace(tzinfo=UTC), zona)
        if fecha > local:
            continue
        ejercicio_id = str(desde_bytes(fila["ejercicio_catalogo_id"]))
        sesion_id = str(desde_bytes(fila["sesion_realizada_id"]))
        clave = (sesion_id, ejercicio_id)
        if clave not in sesiones:
            sesiones[clave] = (str(desde_bytes(fila["sesion_planificada_id"])), fecha, [])
        series = sesiones[clave][2]
        series.append(
            SerieRealizada(
                sesiones[clave][0],
                ejercicio_id,
                len(series) + 1,
                fila["repeticiones"],
                fila["carga"],
                rir=fila["rir"],
                ejercicio_hecho_id=str(desde_bytes(fila["ejercicio_hecho_resuelto_id"])),
            )
        )
    historial = tuple(
        HistorialEjercicio(ejercicio, sesion, planificada, fecha, tuple(series))
        for (sesion, ejercicio), (planificada, fecha, series) in sesiones.items()
    )
    historial = historial_para_sesion(historial, sesion_planificada_id, inicio_de_semana(local))
    return historial


def preparar_subas(efectivas, zona, local):
    subas = []
    for efectiva in efectivas:
        fecha = fecha_local(efectiva["creada_en"].replace(tzinfo=UTC), zona)
        if not inicio_de_semana(local) <= fecha <= local:
            continue
        ejercicios = {e["id"]: e for e in json.loads(efectiva["ejercicios"])}
        for razon in json.loads(efectiva["explicacion"]):
            ejercicio = ejercicios.get(razon["datos"].get("ejercicio_id"))
            if (
                razon["regla"] == "subir_carga"
                and ejercicio
                and not {"tope_semanal", "chequeo_desfavorable"} & {r["regla"] for r in ejercicio["explicacion"]}
            ):
                subas.append(
                    SubaCarga(ejercicio["ejercicio_id"], fecha, str(desde_bytes(efectiva["sesion_planificada_id"])))
                )
    return tuple(subas)


def catalogo_programa(programa):
    if programa is None:
        return ()
    ejercicios = {
        e["ejercicio_id"]: EjercicioCatalogo(e["ejercicio_id"], e["nombre"], e["incremento_carga"])
        for s in programa["sesiones_planificadas"]
        for e in s["ejercicios_planificados"]
    }
    return tuple(ejercicios.values())


def consultar_propuesta(socio_texto, usuario, planificada_id=None, *, cursor=None):
    socio_id = identificar(socio_texto)
    ahora = reloj_actual().ahora()
    with nullcontext(cursor) if cursor is not None else transaccion() as lectura:
        autorizar_socio(lectura, socio_id, usuario)
        sede = repositorio.obtener_sede(lectura)
        if sede is None:
            raise ErrorDeDominio("sede_inexistente", "La sede no existe.", 404)
        filas = repositorio.listar_series_vigentes(lectura, socio_id)
        efectivas = repositorio.listar_prescripciones(lectura, socio_id)
        chequeo = repositorio.obtener_chequeo(lectura, socio_id, fecha_local(ahora, ZoneInfo(sede["zona_horaria"])))
    programas = listar_programas(socio_id, cursor=cursor)
    programa = programas[-1] if programas else None
    if planificada_id is not None:
        programa = next(p for p in programas if any(s["id"] == str(planificada_id) for s in p["sesiones_planificadas"]))
        programa = {
            **programa,
            "sesiones_planificadas": [s for s in programa["sesiones_planificadas"] if s["id"] == str(planificada_id)],
        }
    local = fecha_local(ahora, ZoneInfo(sede["zona_horaria"]))
    series, cantidades = convertir_series(filas)
    if planificada_id is not None:
        series = ()
    programa_motor = convertir_programa(programa)
    if programa_motor is not None and planificada_id is None:
        # Las series que una prescripción efectiva quitó ya no son trabajo pendiente.
        # Conservamos cantidades reales para la pantalla y acreditamos solo ante el motor.
        originales = {e.ejercicio_id: e.series for s in programa_motor.sesiones for e in s.ejercicios}
        quitadas = {}
        for efectiva in efectivas:
            planificada = str(desde_bytes(efectiva["sesion_planificada_id"]))
            for ejercicio in json.loads(efectiva["ejercicios"]):
                if ejercicio["id"] not in originales:
                    continue
                clave = (planificada, ejercicio["id"])
                quitadas[clave] = max(
                    quitadas.get(clave, 0), originales.get(ejercicio["id"], 0) - ejercicio["objetivos"]["series"]
                )
        series += tuple(
            SerieRealizada(sesion, ejercicio, numero, None, None)
            for (sesion, ejercicio), cantidad in quitadas.items()
            for numero in range(originales[ejercicio] - cantidad + 1, originales[ejercicio] + 1)
        )
    # Primero identifica pendientes; aún no hay historial ni ajustes que exponer.
    seleccion = proponer_sesion(DatosPropuesta(programa_motor, local, inicio_de_semana(local), series))
    historial = preparar_historial(
        filas,
        ZoneInfo(sede["zona_horaria"]),
        local,
        seleccion.sesion_planificada.id if seleccion.sesion_planificada else None,
    )
    subas = preparar_subas(efectivas, ZoneInfo(sede["zona_horaria"]), local)
    propuesta = proponer_sesion(
        DatosPropuesta(
            programa_motor,
            local,
            inicio_de_semana(local),
            series,
            historial,
            catalogo_programa(programa),
            subas,
            Chequeo(chequeo["sueno"], chequeo["energia"]) if chequeo else None,
        )
    )
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
        "frenos": list(propuesta.frenos),
    }
    if propuesta.sesion_planificada is None:
        return respuesta
    sesion = next(s for s in programa["sesiones_planificadas"] if s["id"] == propuesta.sesion_planificada.id)
    respuesta["sesion_planificada"] = {"id": sesion["id"], "nombre": sesion["nombre"], "posicion": sesion["posicion"]}
    anteriores = cargas_anteriores(filas, ZoneInfo(sede["zona_horaria"]))
    prescripciones = {p.ejercicio_id: p for p in propuesta.prescripcion}
    razones = {
        e["id"]: [
            {"regla": r.regla, "version": r.version, "datos": dict(r.datos)}
            for r in propuesta.explicacion
            if dict(r.datos).get("ejercicio_id") == e["id"]
        ]
        for e in sesion["ejercicios_planificados"]
    }
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
            "objetivos": {
                **{m: e[m] for m in ("series", *OBJETIVOS)},
                **{
                    m: getattr(prescripciones[e["id"]], m)
                    for m in (
                        "series",
                        "repeticiones_minimas",
                        "repeticiones_maximas",
                        "carga",
                        "rir_objetivo",
                        "descanso",
                    )
                },
            },
            "explicacion": razones[e["id"]],
            "realizado": cantidades[sesion["id"], e["id"]],
            "pendiente": max(0, prescripciones[e["id"]].series - cantidades[sesion["id"], e["id"]]),
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
        "ejercicio_hecho_nombre": fila["ejercicio_hecho_nombre"],
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
        # Serializa el inicio por socio antes de abrir la lectura del historial y las subas.
        repositorio.obtener_socio(cursor, identificar(usuario["id"]), bloquear=True)
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
        propuesta = consultar_propuesta(usuario["id"], usuario, planificada_id, cursor=cursor)
        repositorio.insertar_sesion(cursor, sesion_id, identificar(usuario["id"]), planificada_id, ahora)
        # Tras un INSERT duplicado concurrente, leer el registro confirmado y validar su pertenencia.
        fila = repositorio.obtener_sesion(cursor, sesion_id, actual=True)
        _exigir_propiedad(fila, usuario)
        if desde_bytes(fila["sesion_planificada_id"]) != planificada_id:
            raise ErrorDeDominio("id_ajeno", "El identificador corresponde a otra sesión planificada.", 403)
        if repositorio.obtener_prescripcion(cursor, sesion_id) is None:
            repositorio.insertar_prescripcion(cursor, nuevo_id(), sesion_id, propuesta, ahora)
            repositorio.insertar_avisos(cursor, identificar(usuario["id"]), sesion_id, propuesta, ahora)
        return sesion_publica(fila)


def registrar_serie(sesion_texto, datos, usuario):
    campos = {"id", "ejercicio_planificado_id"}
    if (
        not isinstance(datos, dict)
        or not campos <= set(datos)
        or set(datos) - campos - set(repositorio.MEDIDAS) - {"rir", "ejercicio_hecho_id"}
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
            return {"serie_realizada": serie_publica(anterior), "records": []}
        ejercicio = repositorio.obtener_ejercicio_planificado(cursor, ejercicio_id)
        if ejercicio is None:
            raise ErrorDeDominio("ejercicio_inexistente", "El ejercicio planificado no existe.", 404)
        if ejercicio["sesion_planificada_id"] != sesion["sesion_planificada_id"]:
            raise ErrorDeDominio("ejercicio_invalido", "El ejercicio no pertenece a esta sesión planificada.", 422)
        hecho_id = identificar(datos["ejercicio_hecho_id"]) if "ejercicio_hecho_id" in datos else None
        if hecho_id is not None:
            vigente = repositorio.sustitucion_vigente(cursor, sesion_id, ejercicio_id)
            if vigente is None or desde_bytes(vigente["ejercicio_hecho_id"]) != hecho_id:
                raise ErrorDeDominio(
                    "sustitucion_inexistente", "El ejercicio hecho exige una sustitución vigente.", 409
                )
        try:
            repositorio.insertar_serie(
                cursor,
                serie_id,
                sesion_id,
                ejercicio_id,
                identificar(usuario["id"]),
                ahora,
                rir=rir,
                ejercicio_hecho_id=hecho_id,
                **{m: datos.get(m) for m in repositorio.MEDIDAS},
            )
        except ValueError as error:
            raise ErrorDeDominio("medidas_invalidas", str(error), 422) from error
        fila = repositorio.obtener_serie(cursor, serie_id, actual=True)
        _exigir_destino_serie(fila, sesion_id, ejercicio_id)
        historial = repositorio.listar_series_vigentes(cursor, identificar(usuario["id"]))
        series, _ = convertir_series([f for f in historial if f["id"] != fila["id"]])
        actual = SerieRealizada(
            "",
            str(desde_bytes(ejercicio["ejercicio_id"])),
            1,
            fila["repeticiones"],
            fila["carga"],
            ejercicio_hecho_id=str(desde_bytes(fila["ejercicio_hecho_resuelto_id"])),
        )
        records = detectar_records(actual, series)
        return {
            "serie_realizada": serie_publica(fila),
            "records": [
                {
                    "medida": r.medida,
                    "marca": r.marca,
                    "marca_anterior": r.marca_anterior,
                    "carga": r.carga,
                    "ejercicio_hecho_id": actual.ejercicio_hecho_id,
                    "ejercicio_hecho_nombre": fila["ejercicio_hecho_nombre"],
                    "explicacion": {
                        "regla": r.explicacion.regla,
                        "version": r.explicacion.version,
                        "datos": dict(r.explicacion.datos),
                    },
                }
                for r in records
            ],
        }


def consultar_sesion(sesion_texto, usuario):
    sesion_id = identificar(sesion_texto)
    with transaccion() as cursor:
        sesion = _sesion_propia(cursor, sesion_id, usuario)
        efectiva = repositorio.obtener_prescripcion(cursor, sesion_id)
        filas = repositorio.listar_series_vigentes(cursor, identificar(usuario["id"]), sesion_id)
        historial = repositorio.listar_series_vigentes(cursor, identificar(usuario["id"]))
        sede = repositorio.obtener_sede(cursor)
        sustituciones = {}
        # Se consultan también ejercicios sin series, para recuperar la sustitución al recargar.
        cursor_ejercicios = repositorio.listar_ejercicios_sesion(cursor, sesion_id)
        for ejercicio in cursor_ejercicios:
            vigente = repositorio.sustitucion_vigente(cursor, sesion_id, desde_bytes(ejercicio["id"]))
            if vigente:
                catalogo = repositorio.listar_catalogo(cursor, desde_bytes(ejercicio["ejercicio_id"]))
                hecho = next(f for f in catalogo if f["id"] == vigente["ejercicio_hecho_id"])
                sustituciones[str(desde_bytes(ejercicio["id"]))] = {
                    "sustitucion": sustitucion_publica(vigente),
                    "nombre": hecho["nombre"],
                    "medidas_aplicables": json.loads(hecho["medidas_aplicables"]),
                    "carga_anterior": anteriores_hecho(historial, sede, sesion, vigente),
                }
    programas = listar_programas(identificar(usuario["id"]))
    planificada = next(
        s
        for p in programas
        for s in p["sesiones_planificadas"]
        if s["id"] == str(desde_bytes(sesion["sesion_planificada_id"]))
    )
    anteriores = cargas_anteriores(historial, ZoneInfo(sede["zona_horaria"]), sesion)
    cantidades = Counter(str(desde_bytes(f["ejercicio_planificado_id"])) for f in filas)
    ejercicios = json.loads(efectiva["ejercicios"]) if efectiva else None
    return {
        "prescripcion_efectiva": (
            {campo: json.loads(efectiva[campo]) for campo in ("ejercicios", "explicacion", "frenos")}
            | {"version_reglas": efectiva["version_reglas"]}
        )
        if efectiva
        else None,
        "sesion_planificada": {"id": planificada["id"], "nombre": planificada["nombre"]},
        "sesion_realizada": sesion_publica(sesion),
        "sustituciones": sustituciones,
        "series": [serie_publica(f) for f in filas],
        "ejercicios": [
            {**e, "realizado": cantidades[e["id"]], "pendiente": max(0, e["objetivos"]["series"] - cantidades[e["id"]])}
            for e in ejercicios
        ]
        if ejercicios is not None
        else [
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


def _ejercicio_de_sesion(cursor, sesion_id, ejercicio_id, usuario):
    sesion = _sesion_propia(cursor, sesion_id, usuario)
    ejercicio = repositorio.obtener_ejercicio_planificado(cursor, ejercicio_id)
    if ejercicio is None:
        raise ErrorDeDominio("ejercicio_inexistente", "El ejercicio planificado no existe.", 404)
    if ejercicio["sesion_planificada_id"] != sesion["sesion_planificada_id"]:
        raise ErrorDeDominio("ejercicio_invalido", "El ejercicio no pertenece a esta sesión planificada.", 422)
    return ejercicio


def _alternativas(cursor, ejercicio):
    filas = repositorio.listar_catalogo(cursor, desde_bytes(ejercicio["ejercicio_id"]))
    ids = tuple(str(desde_bytes(f["id"])) for f in filas[1:])
    catalogo = tuple(
        EjercicioCatalogo(
            str(desde_bytes(f["id"])),
            f["nombre"],
            f["incremento_carga"],
            f["equipo"],
            f["patron_movimiento"],
            tuple(json.loads(f["zonas"])),
            ids if i == 0 else (),
        )
        for i, f in enumerate(filas)
    )
    alternativas, razon = elegir_alternativas(str(desde_bytes(ejercicio["ejercicio_id"])), catalogo)
    return [
        {
            "ejercicio_id": e.ejercicio_id,
            "nombre": e.nombre,
            "equipo": e.equipo,
            "medidas_aplicables": json.loads(
                next(f["medidas_aplicables"] for f in filas if str(desde_bytes(f["id"])) == e.ejercicio_id)
            ),
        }
        for e in alternativas
    ], razon


def consultar_alternativas(sesion_texto, ejercicio_texto, usuario):
    with transaccion() as cursor:
        ejercicio = _ejercicio_de_sesion(cursor, identificar(sesion_texto), identificar(ejercicio_texto), usuario)
        alternativas, razon = _alternativas(cursor, ejercicio)
    return {
        "alternativas": alternativas,
        "explicacion": (
            {"regla": razon.regla, "version": razon.version, "datos": dict(razon.datos)} if razon else None
        ),
    }


def sustitucion_publica(fila):
    return {
        **{
            campo: str(desde_bytes(fila[campo]))
            for campo in ("id", "sesion_realizada_id", "ejercicio_planificado_id", "ejercicio_hecho_id", "autor_id")
        },
        "motivo": fila["motivo"],
        "registrada_en": fila["registrada_en"].replace(tzinfo=UTC).isoformat(),
    }


def registrar_sustitucion(sesion_texto, datos, usuario):
    if not isinstance(datos, dict) or set(datos) != {"id", "ejercicio_planificado_id", "ejercicio_hecho_id"}:
        raise ErrorDeDominio("cuerpo_invalido", "Enviá id, ejercicio_planificado_id y ejercicio_hecho_id.", 422)
    sesion_id = identificar(sesion_texto)
    sustitucion_id, ejercicio_id, hecho_id = (
        identificar(datos[c]) for c in ("id", "ejercicio_planificado_id", "ejercicio_hecho_id")
    )
    ahora = reloj_actual().ahora()
    with transaccion() as cursor:
        ejercicio = _ejercicio_de_sesion(cursor, sesion_id, ejercicio_id, usuario)
        anterior = repositorio.obtener_sustitucion(cursor, sustitucion_id)
        if anterior is not None:
            _exigir_destino_serie(anterior, sesion_id, ejercicio_id)
            return sustitucion_publica(anterior)
        alternativas, _ = _alternativas(cursor, ejercicio)
        if str(hecho_id) not in {e["ejercicio_id"] for e in alternativas}:
            raise ErrorDeDominio("alternativa_incompatible", "Elegí una alternativa compatible.", 422)
        repositorio.insertar_sustitucion(
            cursor, sustitucion_id, sesion_id, ejercicio_id, hecho_id, identificar(usuario["id"]), ahora
        )
        fila = repositorio.obtener_sustitucion(cursor, sustitucion_id)
        _exigir_destino_serie(fila, sesion_id, ejercicio_id)
        return sustitucion_publica(fila)


def anteriores_hecho(historial, sede, sesion, sustitucion):
    return cargas_anteriores(historial, ZoneInfo(sede["zona_horaria"]), sesion).get(
        str(desde_bytes(sustitucion["ejercicio_hecho_id"]))
    )


def consultar_progreso(socio_texto, usuario):
    """Una marca máxima vigente por sesión realizada y ejercicio hecho."""
    socio_id = identificar(socio_texto)
    with transaccion() as cursor:
        autorizar_socio(cursor, socio_id, usuario)
        filas = repositorio.listar_series_vigentes(cursor, socio_id)
        zona = ZoneInfo(repositorio.obtener_sede(cursor)["zona_horaria"])
    ejercicios = {}
    sesiones = {}
    for fila in filas:
        if fila["carga"] is None:
            continue
        ejercicio_id = str(desde_bytes(fila["ejercicio_hecho_resuelto_id"]))
        ejercicios[ejercicio_id] = fila["ejercicio_hecho_nombre"]
        clave = (ejercicio_id, fila["sesion_realizada_id"])
        anterior = sesiones.get(clave)
        if anterior is None or fila["carga"] > anterior["carga"]:
            sesiones[clave] = fila
    return {
        "ejercicios": [
            {
                "id": ejercicio_id,
                "nombre": nombre,
                "puntos": [
                    {
                        "fecha_local": fecha_local(f["sesion_creada_en"].replace(tzinfo=UTC), zona).isoformat(),
                        "carga": str(f["carga"]),
                        "repeticiones": f["repeticiones"],
                    }
                    for (hecho_id, _), f in sorted(
                        sesiones.items(), key=lambda elemento: (elemento[1]["sesion_creada_en"], elemento[0][1])
                    )
                    if hecho_id == ejercicio_id
                ],
            }
            for ejercicio_id, nombre in sorted(ejercicios.items(), key=lambda elemento: (elemento[1], elemento[0]))
        ]
    }


def registrar_chequeo(datos, usuario):
    if not isinstance(datos, dict) or set(datos) != {"id", "sueno", "energia"}:
        raise ErrorDeDominio("cuerpo_invalido", "Enviá id, sueno y energia.", 422)
    if any(type(datos[c]) is not int or not 1 <= datos[c] <= 5 for c in ("sueno", "energia")):
        raise ErrorDeDominio("chequeo_invalido", "Sueño y energía deben ser enteros entre 1 y 5.", 422)
    chequeo_id = identificar(datos["id"])
    socio_id = identificar(usuario["id"])
    ahora = reloj_actual().ahora()
    with transaccion() as cursor:
        repositorio.obtener_socio(cursor, socio_id, bloquear=True)
        anterior = repositorio.obtener_chequeo_por_id(cursor, chequeo_id)
        if anterior:
            if anterior["socio_id"] != socio_id.bytes:
                raise ErrorDeDominio("sin_alcance", "El chequeo del día pertenece a otro socio.", 403)
            return {"id": str(chequeo_id), "fecha_local": anterior["fecha_local"].isoformat()}
        sede = repositorio.obtener_sede(cursor)
        local = fecha_local(ahora, ZoneInfo(sede["zona_horaria"]))
        repositorio.insertar_chequeo(cursor, chequeo_id, socio_id, local, datos["sueno"], datos["energia"], ahora)
    return {"id": str(chequeo_id), "fecha_local": local.isoformat()}
