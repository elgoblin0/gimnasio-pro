"""Programas por socio y versión, catálogo, alternativas y estado de equipos."""

import json
from contextlib import nullcontext
from datetime import UTC
from decimal import Decimal, InvalidOperation

from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.ids import desde_bytes, desde_texto, nuevo_id
from gimnasio.comun.reloj import reloj_actual
from gimnasio.comun.tipos import EjercicioCatalogo
from gimnasio.permisos.servicio import tiene_asignacion_vigente, tiene_consentimiento
from gimnasio.programas import repositorio
from gimnasio.reglas.restricciones import choques_con_restricciones
from gimnasio.salud.servicio import restricciones_vigentes

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


def _leer_catalogo(cursor):
    estados = {fila["nombre"]: fila["estado"] for fila in repositorio.leer_equipos(cursor)}
    ejercicios = {}
    for fila in repositorio.leer_ejercicios(cursor):
        identificador = str(desde_bytes(fila["id"]))
        ejercicios[identificador] = {
            **fila,
            "id": identificador,
            "medidas_aplicables": json.loads(fila["medidas_aplicables"]),
            "zonas": sorted(json.loads(fila["zonas"])),
            "estado_equipo": estados.get(fila["equipo"], "disponible"),
            "alternativas": [],
        }
    for fila in repositorio.leer_alternativas(cursor):
        ejercicios[str(desde_bytes(fila["ejercicio_id"]))]["alternativas"].append(
            str(desde_bytes(fila["alternativa_id"]))
        )
    return ejercicios


def listar_ejercicios():
    with transaccion() as cursor:
        return list(_leer_catalogo(cursor).values())


def _rechazar_alternativa(identificador, motivo):
    raise ErrorDeDominio("alternativa_invalida", f"{identificador}: {motivo}", 422)


def _id_alternativa(identificador):
    try:
        if not isinstance(identificador, str):
            raise ValueError
        return desde_texto(identificador)
    except (ValueError, AttributeError) as error:
        raise ErrorDeDominio(
            "alternativa_invalida", f"{identificador}: el identificador debe ser un UUIDv7.", 422
        ) from error


def reemplazar_alternativas(ejercicio_id, datos):
    original_id = _id_alternativa(ejercicio_id)
    if not isinstance(datos, dict) or set(datos) != {"alternativas"} or not isinstance(datos["alternativas"], list):
        _rechazar_alternativa(ejercicio_id, "enviá una lista de alternativas.")
    alternativas = datos["alternativas"]
    if len(alternativas) > 8:
        _rechazar_alternativa(ejercicio_id, "se permiten hasta 8 alternativas.")
    with transaccion() as cursor:
        # Serializa reemplazos antes de abrir la lectura consistente del catálogo.
        if repositorio.bloquear_ejercicio(cursor, original_id) is None:
            _rechazar_alternativa(ejercicio_id, "el ejercicio no existe.")
        catalogo = _leer_catalogo(cursor)
        original = catalogo[str(original_id)]
        identificadores = []
        for texto in alternativas:
            identificador = _id_alternativa(texto)
            alternativa = catalogo.get(str(identificador))
            if alternativa is None:
                _rechazar_alternativa(texto, "el ejercicio no existe.")
            if identificador == original_id:
                _rechazar_alternativa(texto, "no puede ser el mismo ejercicio.")
            if identificador in identificadores:
                _rechazar_alternativa(texto, "la alternativa está repetida.")
            if alternativa["patron_movimiento"] != original["patron_movimiento"]:
                _rechazar_alternativa(texto, "debe tener igual patrón de movimiento.")
            if alternativa["equipo"] == original["equipo"]:
                _rechazar_alternativa(texto, "debe tener distinto equipo.")
            identificadores.append(identificador)
        repositorio.reemplazar_alternativas(cursor, original_id, identificadores)
        return {**original, "alternativas": [str(identificador) for identificador in identificadores]}


def _equipo_publico(fila):
    return {
        **fila,
        "id": str(desde_bytes(fila["id"])),
        "autor_id": str(desde_bytes(fila["autor_id"])) if fila["autor_id"] else None,
        "ultimo_cambio": fila["ultimo_cambio"].replace(tzinfo=UTC).isoformat() if fila["ultimo_cambio"] else None,
    }


def listar_equipos(*, cursor=None):
    with nullcontext(cursor) if cursor is not None else transaccion() as cursor:
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


def socios_con_programa(cursor, socio_ids):
    """Cuáles de los socios tienen alguna versión, sin leer sus programas."""
    return {desde_bytes(fila["socio_id"]) for fila in repositorio.socios_con_programa(cursor, socio_ids)}


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
                "duracion_semanas": fila.get("duracion_semanas"),
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
                "semana": fila.get("semana"),
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
                "carga_partida": fila.get("carga_partida"),
                **{medida: fila[medida] for medida in OBJETIVOS},
                "patron_movimiento": fila["patron_movimiento"],
                "equipo": fila["equipo"],
                "incremento_carga": fila["incremento_carga"],
                "zonas": sorted(json.loads(fila["zonas"])),
                "alternativas": sorted(json.loads(fila["alternativas"]), key=lambda a: (a["orden"], a["ejercicio_id"])),
            }
        )
    return list(programas.values())


def _programa_invalido(detalle):
    raise ErrorDeDominio("programa_invalido", detalle, 422)


def _validar_numero(valor, campo, minimo, maximo, *, entero=False):
    if isinstance(valor, bool) or (entero and type(valor) is not int):
        _programa_invalido(f"{campo}: enviá un número válido.")
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        _programa_invalido(f"{campo}: enviá un número válido.")
    if not numero.is_finite() or not minimo <= numero <= maximo:
        _programa_invalido(f"{campo}: debe estar entre {minimo} y {maximo}.")


def _validar_publicacion(datos, catalogo, cargas):
    if (
        not isinstance(datos, dict)
        or set(datos) - {"version_base", "semanas", "sesiones", "plantilla_id"}
        or not {"version_base", "semanas", "sesiones"} <= set(datos)
    ):
        _programa_invalido("Enviá version_base, semanas y sesiones.")
    if datos["version_base"] is not None and (type(datos["version_base"]) is not int or datos["version_base"] < 1):
        _programa_invalido("version_base: debe ser un entero positivo o null.")
    _validar_numero(datos["semanas"], "semanas", 4, 12, entero=True)
    sesiones = datos["sesiones"]
    if not isinstance(sesiones, list) or not 1 <= len(sesiones) <= 6:
        _programa_invalido("Enviá entre 1 y 6 sesiones.")
    resultado = []
    for sesion in sesiones:
        if not isinstance(sesion, dict) or set(sesion) != {"nombre", "ejercicios"}:
            _programa_invalido("Cada sesión debe tener nombre y ejercicios.")
        nombre = sesion["nombre"]
        if not isinstance(nombre, str) or not nombre.strip() or len(nombre.strip()) > 108:
            _programa_invalido("El nombre de la sesión debe tener entre 1 y 108 caracteres.")
        ejercicios = sesion["ejercicios"]
        if not isinstance(ejercicios, list) or not 1 <= len(ejercicios) <= 12:
            _programa_invalido("Enviá entre 1 y 12 ejercicios por sesión.")
        validados = []
        for ejercicio in ejercicios:
            if not isinstance(ejercicio, dict) or set(ejercicio) - {
                "ejercicio_id",
                "series",
                "carga_partida",
                *OBJETIVOS,
            }:
                _programa_invalido("El ejercicio tiene campos desconocidos.")
            identificador = ejercicio.get("ejercicio_id")
            if not isinstance(identificador, str) or identificador not in catalogo:
                _programa_invalido("El ejercicio debe pertenecer al catálogo.")
            _validar_numero(ejercicio.get("series"), "series", 1, 10, entero=True)
            medidas = catalogo[identificador]["medidas_aplicables"]
            validado = {**ejercicio}
            partida = ejercicio.get("carga_partida")
            if partida is not None:
                if "carga" not in medidas:
                    _programa_invalido("carga_partida: no es aplicable al ejercicio.")
                _validar_numero(partida, "carga_partida", 0, Decimal("999999.99"))
                if Decimal(str(partida)).as_tuple().exponent < -2:
                    _programa_invalido("carga_partida: admite hasta dos decimales.")
            for medida in MEDIDAS:
                campos = ("repeticiones_minimas", "repeticiones_maximas") if medida == "repeticiones" else (medida,)
                for campo in campos:
                    valor = ejercicio.get(campo)
                    if medida not in medidas:
                        if valor is not None:
                            _programa_invalido(f"{campo}: no es aplicable al ejercicio.")
                        continue
                    if campo == "carga" and valor is None:
                        valor = partida if partida is not None else cargas.get(identificador)
                        if valor is None:
                            _programa_invalido("carga: es obligatoria si el socio no tiene historial del ejercicio.")
                        validado[campo] = valor
                    maximo = (
                        Decimal("999999.99")
                        if campo == "carga"
                        else (Decimal("99999999.99") if campo == "distancia" else 2147483647)
                    )
                    minimo = 0 if campo == "carga" else (Decimal("0.01") if campo == "distancia" else 1)
                    _validar_numero(
                        valor,
                        campo,
                        minimo,
                        maximo,
                        entero=campo in ("repeticiones_minimas", "repeticiones_maximas", "duracion"),
                    )
            if "repeticiones" in medidas and ejercicio["repeticiones_minimas"] > ejercicio["repeticiones_maximas"]:
                _programa_invalido("El mínimo de repeticiones no puede superar el máximo.")
            for campo, minimo, maximo in (("rir_objetivo", 0, 5), ("descanso", 0, 2147483647)):
                if ejercicio.get(campo) is not None:
                    _validar_numero(ejercicio[campo], campo, minimo, maximo, entero=True)
            validados.append(validado)
        resultado.append({"nombre": nombre.strip(), "ejercicios": validados})
    partidas = {}
    for sesion in resultado:
        for ejercicio in sesion["ejercicios"]:
            if ejercicio.get("carga_partida") is not None:
                identificador = ejercicio["ejercicio_id"]
                partida = Decimal(str(ejercicio["carga_partida"]))
                if identificador in partidas and partidas[identificador] != partida:
                    _programa_invalido("carga_partida: debe ser igual en toda la versión.")
                partidas[identificador] = partida
    for sesion in resultado:
        for ejercicio in sesion["ejercicios"]:
            ejercicio["carga_partida"] = partidas.get(ejercicio["ejercicio_id"])
    return resultado


def _comprobar_asignacion(cursor, socio_id, usuario):
    if not tiene_asignacion_vigente(cursor, socio_id, desde_texto(usuario["id"])):
        raise ErrorDeDominio("sin_asignacion", "El socio no tiene una asignación vigente con el entrenador.", 403)


def _semana_tipo(programa):
    return {
        **{campo: programa[campo] for campo in ("id", "version", "duracion_semanas")},
        "sesiones": [
            {
                "nombre": (sesion["nombre"].partition(" · ")[2] or sesion["nombre"])
                if sesion["semana"] == 1
                else sesion["nombre"],
                "ejercicios": sesion["ejercicios_planificados"],
            }
            for sesion in programa["sesiones_planificadas"]
            if sesion["semana"] in (None, 1)
        ],
    }


def programa_vigente(socio_id, usuario):
    socio_id = _id_socio(socio_id)
    with transaccion() as cursor:
        _comprobar_asignacion(cursor, socio_id, usuario)
        programas = listar_programas(socio_id, cursor=cursor)
        return _semana_tipo(programas[-1]) if programas else None


def _id_socio(texto):
    try:
        return desde_texto(texto)
    except (ValueError, AttributeError) as error:
        raise ErrorDeDominio("programa_invalido", "El socio debe identificarse con un UUIDv7.", 422) from error


def publicar_programa(socio_id, datos, usuario):
    # Importación local para componer ambos servicios sin un ciclo al cargar los módulos.
    from gimnasio.entrenamiento.servicio import cargas_ultima_sesion

    socio_id = _id_socio(socio_id)
    reloj = reloj_actual()
    with transaccion() as cursor:
        # También serializa la primera publicación, cuando todavía no hay programa que bloquear.
        repositorio.bloquear_socio(cursor, socio_id)
        if isinstance(datos, dict) and "plantilla_id" in datos:
            _buscar_plantilla(repositorio.bloquear_plantillas(cursor), datos["plantilla_id"], activa=True)
        vigente = repositorio.version_vigente(cursor, socio_id)
        _comprobar_asignacion(cursor, socio_id, usuario)
        catalogo = _leer_catalogo(cursor)
        sesiones = _validar_publicacion(datos, catalogo, cargas_ultima_sesion(cursor, socio_id))
        if datos["version_base"] != vigente:
            raise ErrorDeDominio("version_desactualizada", "La versión vigente cambió; volvé a leer el programa.", 409)
        _comprobar_restricciones(cursor, socio_id, sesiones, catalogo)
        programa_id = nuevo_id(reloj)
        version = (vigente or 0) + 1
        repositorio.insertar_programa(cursor, programa_id, socio_id, version, datos["semanas"], reloj.ahora())
        posicion = 0
        for semana in range(1, datos["semanas"] + 1):
            for sesion in sesiones:
                posicion += 1
                sesion_id = nuevo_id(reloj)
                repositorio.insertar_sesion(
                    cursor, sesion_id, programa_id, posicion, semana, f"Semana {semana} · {sesion['nombre']}"
                )
                for orden, ejercicio in enumerate(sesion["ejercicios"], start=1):
                    repositorio.insertar_ejercicio_planificado(cursor, nuevo_id(reloj), sesion_id, orden, ejercicio)
        programa = _leer(socio_id, version, cursor=cursor)[0]
        return _semana_tipo(programa)


def listar_plantillas(*, incluir_archivadas=False, cursor=None):
    with nullcontext(cursor) if cursor is not None else transaccion() as cursor:
        plantillas, sesiones, ejercicios = repositorio.leer_plantillas(cursor)
    por_sesion = {}
    for sesion in sesiones:
        sesion["id"] = str(desde_bytes(sesion["id"]))
        sesion["plantilla_id"] = str(desde_bytes(sesion["plantilla_id"]))
        sesion["ejercicios"] = []
        por_sesion[sesion["id"]] = sesion
    for ejercicio in ejercicios:
        for campo in ("id", "sesion_id", "ejercicio_id"):
            ejercicio[campo] = str(desde_bytes(ejercicio[campo]))
        por_sesion[ejercicio["sesion_id"]]["ejercicios"].append(ejercicio)
    for plantilla in plantillas:
        plantilla["archivada"] = bool(plantilla["archivada"])
        plantilla["id"] = str(desde_bytes(plantilla["id"]))
        plantilla["creada_en"] = plantilla["creada_en"].replace(tzinfo=UTC).isoformat()
        plantilla["sesiones"] = [s for s in sesiones if s["plantilla_id"] == plantilla["id"]]
    return [p for p in plantillas if incluir_archivadas or not p["archivada"]]


def _buscar_plantilla(filas, texto, *, activa=False):
    try:
        identificador = desde_texto(texto)
    except (ValueError, AttributeError, TypeError) as error:
        raise ErrorDeDominio("plantilla_invalida", "La plantilla debe identificarse con un UUIDv7.", 422) from error
    fila = next((f for f in filas if desde_bytes(f["id"]) == identificador), None)
    if fila is None:
        raise ErrorDeDominio("plantilla_inexistente", "La plantilla no existe.", 404)
    if activa and fila["archivada"]:
        raise ErrorDeDominio("plantilla_archivada", "La plantilla está archivada. Conservamos tu formulario.", 409)
    return identificador


def _validar_plantilla(datos, catalogo):
    if not isinstance(datos, dict) or set(datos) != {"nombre", "descripcion", "sesiones"}:
        _programa_invalido("Enviá nombre, descripcion y sesiones.")
    for campo, minimo, maximo in (("nombre", 1, 120), ("descripcion", 0, 500)):
        if not isinstance(datos[campo], str) or not minimo <= len(datos[campo].strip()) <= maximo:
            _programa_invalido(f"{campo}: debe tener entre {minimo} y {maximo} caracteres.")
    # La plantilla no prescribe cargas: el entrenador las fija al publicar para un socio.
    sin_carga = {
        identificador: {**e, "medidas_aplicables": [m for m in e["medidas_aplicables"] if m != "carga"]}
        for identificador, e in catalogo.items()
    }
    return _validar_publicacion({"version_base": None, "semanas": 8, "sesiones": datos["sesiones"]}, sin_carga, {})


def guardar_plantilla(datos, plantilla_id=None):
    reloj = reloj_actual()
    with transaccion() as cursor:
        if plantilla_id is not None:
            identificador = _buscar_plantilla(repositorio.bloquear_plantillas(cursor), plantilla_id)
        else:
            identificador = nuevo_id(reloj)
        sesiones = _validar_plantilla(datos, _leer_catalogo(cursor))
        repositorio.guardar_plantilla(
            cursor,
            identificador,
            datos["nombre"].strip(),
            datos["descripcion"].strip(),
            reloj.ahora(),
            nueva=plantilla_id is None,
        )
        for posicion, sesion in enumerate(sesiones, 1):
            sesion_id = nuevo_id(reloj)
            repositorio.insertar_sesion_plantilla(cursor, sesion_id, identificador, posicion, sesion["nombre"])
            for orden, ejercicio in enumerate(sesion["ejercicios"], 1):
                repositorio.insertar_ejercicio_plantilla(cursor, nuevo_id(reloj), sesion_id, orden, ejercicio)
        return next(
            p for p in listar_plantillas(incluir_archivadas=True, cursor=cursor) if p["id"] == str(identificador)
        )


def archivar_plantilla(plantilla_id):
    with transaccion() as cursor:
        filas = repositorio.bloquear_plantillas(cursor)
        identificador = _buscar_plantilla(filas, plantilla_id, activa=True)
        if sum(not f["archivada"] for f in filas) <= 1:
            raise ErrorDeDominio("ultima_plantilla_activa", "Debe quedar al menos una plantilla activa.", 409)
        repositorio.archivar_plantilla(cursor, identificador)
        return next(
            p for p in listar_plantillas(incluir_archivadas=True, cursor=cursor) if p["id"] == str(identificador)
        )


def _comprobar_restricciones(cursor, socio_id, sesiones, catalogo):
    ejercicios = tuple(
        EjercicioCatalogo(
            e["id"],
            e["nombre"],
            e["incremento_carga"],
            e["equipo"],
            e["patron_movimiento"],
            tuple(e["zonas"]),
            tuple(e["alternativas"]),
        )
        for e in catalogo.values()
    )
    choques = choques_con_restricciones(
        (e["ejercicio_id"] for s in sesiones for e in s["ejercicios"]),
        restricciones_vigentes(socio_id, cursor=cursor),
        ejercicios,
        equipos_fuera_de_servicio=frozenset(
            e["equipo"] for e in catalogo.values() if e["estado_equipo"] == "fuera_de_servicio"
        ),
    )
    if not choques:
        return
    consentimiento = tiene_consentimiento(cursor, socio_id, "salud")
    lista = []
    for ejercicio, restriccion, alternativas in choques:
        datos = {
            "ejercicio_id": restriccion.ejercicio_id,
            "patron_movimiento": restriccion.patron_movimiento,
            "zona": restriccion.zona,
        }
        if consentimiento:
            datos["descripcion"] = restriccion.descripcion
        motivos = [
            catalogo[restriccion.ejercicio_id]["nombre"] if restriccion.ejercicio_id in catalogo else None,
            restriccion.patron_movimiento,
            restriccion.zona,
        ]
        lista.append(
            {
                "ejercicio_id": ejercicio.ejercicio_id,
                "nombre": ejercicio.nombre,
                "restriccion": datos,
                "mensaje": f"{ejercicio.nombre}: restricción de salud por {', '.join(m for m in motivos if m)}.",
                "alternativas": [{"ejercicio_id": a.ejercicio_id, "nombre": a.nombre} for a in alternativas],
            }
        )
    raise ErrorDeDominio(
        "choque_restriccion",
        "La semana tipo contiene ejercicios con restricciones de salud vigentes.",
        409,
        detalles={"choques": lista},
    )


def cargas_sugeridas(socio_id, ejercicios, usuario):
    from gimnasio.entrenamiento.servicio import sugerir_cargas

    socio_id = _id_socio(socio_id)
    identificadores = tuple(dict.fromkeys(ejercicios.split(","))) if ejercicios else ()
    with transaccion() as cursor:
        _comprobar_asignacion(cursor, socio_id, usuario)
        catalogo = _leer_catalogo(cursor)
        if any(i not in catalogo for i in identificadores):
            _programa_invalido("Los ejercicios deben pertenecer al catálogo.")
        return sugerir_cargas(cursor, socio_id, identificadores)
