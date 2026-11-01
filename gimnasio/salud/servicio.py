"""Ficha de salud y tratamiento condicionado por consentimiento y asignación vigente."""

from contextlib import nullcontext
from datetime import UTC, date, datetime
from decimal import Decimal

from mysql.connector import IntegrityError, errorcode

from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.ids import desde_bytes, desde_texto, nuevo_id
from gimnasio.comun.reloj import reloj_actual
from gimnasio.comun.tipos import ZONAS_CUERPO, RestriccionSalud
from gimnasio.permisos.servicio import tiene_asignacion_vigente
from gimnasio.salud import repositorio


def aviso_personal_vigente(socio_id, *, cursor):
    fila = repositorio.aviso_personal_vigente(cursor, socio_id)
    return fila["texto"] or None if fila else None


def escribir_aviso_personal(socio_texto, usuario, datos):
    socio_id = _identificar(socio_texto)
    with transaccion() as cursor:
        _autorizar(cursor, socio_id, usuario, bloquear=True)
        if usuario["rol"] != "entrenador":
            raise ErrorDeDominio("sin_permiso", "Solo el entrenador asignado escribe avisos para el personal.", 403)
        if (
            not isinstance(datos, dict)
            or set(datos) != {"texto"}
            or not isinstance(datos["texto"], str)
            or len(datos["texto"]) > 200
        ):
            raise ErrorDeDominio("texto_invalido", "Escribí un aviso para el personal de hasta 200 caracteres.", 422)
        texto = datos["texto"].strip()
        identificador = nuevo_id()
        repositorio.insertar_aviso_personal(
            cursor, identificador, socio_id, texto, _identificar(usuario["id"]), reloj_actual().ahora()
        )
    return {"aviso_personal_id": str(identificador)}


def registrar_consulta_ficha(cursor, socio_id, consultado_por):
    repositorio.insertar_consulta_ficha(cursor, nuevo_id(), socio_id, consultado_por, reloj_actual().ahora())


def consultar_consultas_ficha(socio_id, pagina):
    try:
        pagina = int(pagina)
        if pagina < 1 or pagina > 2147483647:
            raise ValueError
    except (ValueError, TypeError) as error:
        raise ErrorDeDominio("pagina_invalida", "Indicá una página mayor que cero.", 422) from error
    with transaccion() as cursor:
        filas = repositorio.listar_consultas_ficha(cursor, socio_id, pagina)
    return {"consultas": [_publicar(f) for f in filas[:50]], "pagina": pagina, "hay_mas": len(filas) > 50}


def _dato_descargable(valor):
    if isinstance(valor, dict):
        return {clave: _dato_descargable(dato) for clave, dato in valor.items()}
    if isinstance(valor, list):
        return [_dato_descargable(dato) for dato in valor]
    if isinstance(valor, bytes):
        return str(desde_bytes(valor))
    if isinstance(valor, datetime):
        return valor.replace(tzinfo=UTC).isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return str(valor)
    return valor


def descargar_datos_propios(socio_id):
    with transaccion() as cursor:
        return _dato_descargable(repositorio.datos_propios(cursor, socio_id))


def _identificar(texto):
    try:
        return desde_texto(texto)
    except (ValueError, AttributeError, TypeError) as error:
        raise ErrorDeDominio("id_invalido", "El identificador debe ser un UUIDv7.", 422) from error


def filtrar_al_momento(filas, momento):
    momento = momento.astimezone(UTC).replace(tzinfo=None) if momento.tzinfo else momento
    return _convertir_restricciones(
        f for f in filas if f["registrada_en"] <= momento and (f["levantada_en"] is None or f["levantada_en"] > momento)
    )


def historial_restricciones(socio_id, *, cursor, consentimiento):
    return leer_con_consentimiento(
        consentimiento, lambda: repositorio.restricciones_con_levantamiento(cursor, socio_id)
    )


def restricciones_al_iniciar(socio_id, momento, *, cursor, consentimiento):
    return filtrar_al_momento(historial_restricciones(socio_id, cursor=cursor, consentimiento=consentimiento), momento)


def _convertir_restricciones(filas):
    return tuple(
        RestriccionSalud(
            str(desde_bytes(f["ejercicio_id"])) if f["ejercicio_id"] else None,
            f["patron_movimiento"],
            f["zona"],
            f["descripcion"],
        )
        for f in filas
    )


def _autorizar(cursor, socio_id, usuario, *, bloquear=False):
    if bloquear:
        repositorio.bloquear_socio(cursor, socio_id)
    if usuario["rol"] == "entrenador":
        if not tiene_asignacion_vigente(cursor, socio_id, _identificar(usuario["id"])):
            raise ErrorDeDominio("sin_asignacion", "No tenés una asignación vigente con el socio.", 403)
    elif usuario["rol"] != "socio" or _identificar(usuario["id"]) != socio_id:
        raise ErrorDeDominio("sin_permiso", "Tu rol no permite esta acción.", 403)
    if not tiene_consentimiento_salud(cursor, socio_id):
        raise ErrorDeDominio("sin_consentimiento", "Se necesita consentimiento de salud vigente.", 403)


def _publicar(fila):
    return {
        clave: str(desde_bytes(valor))
        if isinstance(valor, bytes)
        else valor.replace(tzinfo=UTC).isoformat()
        if hasattr(valor, "isoformat")
        else valor
        for clave, valor in fila.items()
        if clave != "anonimizada"
    }


def consultar_salud(socio_texto, usuario, *, solo_condiciones=False):
    from gimnasio.entrenamiento.servicio import dolores_para_entrenador
    from gimnasio.programas.servicio import listar_ejercicios

    socio_id = _identificar(socio_texto)
    with transaccion() as cursor:
        _autorizar(cursor, socio_id, usuario)
        if usuario["rol"] == "entrenador":
            registrar_consulta_ficha(cursor, socio_id, _identificar(usuario["id"]))
        resultado = {"condiciones": condiciones_para_entrenador(cursor, socio_id)}
        if usuario["rol"] == "entrenador" and not solo_condiciones:
            resultado["aviso_personal"] = aviso_personal_vigente(socio_id, cursor=cursor)
        if not solo_condiciones:
            restricciones = [_publicar(f) for f in repositorio.restricciones_vigentes(cursor, socio_id)]
            # El socio no puede leer el catálogo: el nombre viaja con la restricción.
            if any(r["ejercicio_id"] for r in restricciones):
                nombres = {e["id"]: e["nombre"] for e in listar_ejercicios(cursor=cursor)}
                for restriccion in restricciones:
                    restriccion["ejercicio_nombre"] = nombres.get(restriccion["ejercicio_id"])
            resultado["restricciones"] = restricciones
            resultado["dolores"] = dolores_para_entrenador(cursor, socio_id)
    return resultado


def condiciones_para_entrenador(cursor, socio_id):
    """Lectura interna: el llamador ya comprobó asignación y consentimiento."""
    return [_publicar(f) for f in repositorio.condiciones_vigentes(cursor, socio_id)]


def _texto(datos, campo, *, opcional=False):
    valor = datos.get(campo)
    if opcional and valor is None:
        return None
    if not isinstance(valor, str) or not valor.strip() or len(valor) > 1000:
        raise ErrorDeDominio("texto_invalido", "Escribí un texto de hasta 1000 caracteres.", 422)
    return valor.strip()


def _insertar_id_nuevo(insertar, *argumentos):
    """El id de un dato borrado sigue ocupado aunque ya no se pueda leer."""
    try:
        insertar(*argumentos)
    except IntegrityError as error:
        if error.errno != errorcode.ER_DUP_ENTRY:
            raise
        raise ErrorDeDominio("id_en_uso", "Ese dato ya no se puede registrar. Volvé a intentarlo.", 409) from error


def _condicion(cursor, socio_id, condicion_id):
    fila = next((f for f in repositorio.condiciones_vigentes(cursor, socio_id) if f["id"] == condicion_id.bytes), None)
    if fila is None:
        raise ErrorDeDominio("condicion_invalida", "Elegí una condición vigente del socio.", 422)
    return fila


def declarar_condicion(socio_texto, usuario, datos):
    socio_id = _identificar(socio_texto)
    with transaccion() as cursor:
        _autorizar(cursor, socio_id, usuario, bloquear=True)
        if not isinstance(datos, dict) or set(datos) - {"id", "descripcion", "reemplaza_a"}:
            raise ErrorDeDominio("datos_invalidos", "Indicá la condición de salud.", 422)
        descripcion = _texto(datos, "descripcion")
        identificador = _identificar(datos["id"]) if "id" in datos else nuevo_id()
        reemplaza = _identificar(datos["reemplaza_a"]) if datos.get("reemplaza_a") is not None else None
        # El id del hecho también permite reintentar con otra clave.
        cursor_fila = repositorio.obtener_condicion(cursor, identificador)
        if cursor_fila:
            if cursor_fila["socio_id"] != socio_id.bytes:
                raise ErrorDeDominio("id_ajeno", "La condición pertenece a otro socio.", 403)
            return {"condicion": _publicar(cursor_fila)}
        if reemplaza:
            _condicion(cursor, socio_id, reemplaza)
        _insertar_id_nuevo(
            repositorio.insertar_condicion,
            cursor,
            identificador,
            socio_id,
            descripcion,
            reemplaza,
            reloj_actual().ahora(),
        )
        return {"condicion": _publicar(repositorio.obtener_condicion(cursor, identificador))}


def gestionar(socio_texto, usuario, datos, *, condicion_texto=None, restriccion_texto=None):
    from gimnasio.programas.servicio import listar_ejercicios

    socio_id = _identificar(socio_texto)
    with transaccion() as cursor:
        _autorizar(cursor, socio_id, usuario, bloquear=True)
        if usuario["rol"] != "entrenador":
            raise ErrorDeDominio("sin_permiso", "Solo el entrenador asignado gestiona restricciones.", 403)
        if not isinstance(datos, dict):
            raise ErrorDeDominio("datos_invalidos", "Indicá los datos de salud.", 422)
        autor_id, ahora = _identificar(usuario["id"]), reloj_actual().ahora()
        if restriccion_texto:
            if datos:
                raise ErrorDeDominio("datos_invalidos", "El levantamiento no admite otros datos.", 422)
            rid = _identificar(restriccion_texto)
            filas = repositorio.restricciones_con_levantamiento(cursor, socio_id)
            fila = next((f for f in filas if f["id"] == rid.bytes), None)
            if fila is None:
                raise ErrorDeDominio("restriccion_invalida", "Elegí una restricción del socio.", 422)
            if fila["levantada_en"] is None:
                repositorio.insertar_restriccion(cursor, nuevo_id(), socio_id, fila, autor_id, ahora, rid)
            return {"restriccion_id": str(rid)}
        condicion = None
        if condicion_texto is not None or datos.get("condicion_id") is not None:
            cid = _identificar(condicion_texto if condicion_texto is not None else datos["condicion_id"])
            condicion = _condicion(cursor, socio_id, cid)
        if condicion_texto:
            if set(datos) - {"nota"}:
                raise ErrorDeDominio("datos_invalidos", "La revisión admite solo una nota.", 422)
            nota = _texto(datos, "nota", opcional=True)
            if condicion["revision_id"] is None:
                repositorio.insertar_revision(cursor, nuevo_id(), cid, autor_id, nota, ahora)
            return {"condicion_id": str(cid)}
        if set(datos) - {"id", "ejercicio_id", "patron_movimiento", "zona", "descripcion", "condicion_id"}:
            raise ErrorDeDominio("datos_invalidos", "Indicá un solo objetivo para la restricción.", 422)
        objetivos = [c for c in ("ejercicio_id", "patron_movimiento", "zona") if datos.get(c) is not None]
        if len(objetivos) != 1:
            raise ErrorDeDominio(
                "objetivo_invalido", "Elegí exactamente un ejercicio, patrón de movimiento o zona del cuerpo.", 422
            )
        descripcion = _texto(datos, "descripcion")
        objetivo = objetivos[0]
        valor = datos[objetivo]
        if not isinstance(valor, str):
            raise ErrorDeDominio("objetivo_invalido", "Elegí un objetivo del catálogo.", 422)
        if objetivo == "zona":
            valido = valor in ZONAS_CUERPO
        else:
            ejercicios = listar_ejercicios(cursor=cursor)
            valido = valor in {e["id" if objetivo == "ejercicio_id" else "patron_movimiento"] for e in ejercicios}
        if not valido:
            raise ErrorDeDominio("objetivo_invalido", "Elegí un objetivo del catálogo.", 422)
        identificador = _identificar(datos["id"]) if "id" in datos else nuevo_id()
        existente = repositorio.obtener_restriccion(cursor, identificador)
        if existente:
            if existente["socio_id"] != socio_id.bytes:
                raise ErrorDeDominio("id_ajeno", "La restricción pertenece a otro socio.", 403)
            return {"restriccion_id": str(identificador)}
        _insertar_id_nuevo(
            repositorio.insertar_restriccion,
            cursor,
            identificador,
            socio_id,
            {objetivo: _identificar(valor).bytes if objetivo == "ejercicio_id" else valor, "descripcion": descripcion},
            autor_id,
            ahora,
        )
        if condicion and condicion["revision_id"] is None:
            repositorio.insertar_revision(cursor, nuevo_id(), cid, autor_id, None, ahora)
    return {"restriccion_id": str(identificador)}


def condiciones_pendientes(socio_ids, *, cursor):
    return {
        desde_bytes(f["socio_id"]): f["registrada_en"] for f in repositorio.condiciones_sin_revisar(cursor, socio_ids)
    }


def tiene_consentimiento_salud(cursor, socio_id):
    fila = repositorio.consentimiento_vigente(cursor, socio_id)
    return bool(fila and fila["otorgado"])


def leer_con_consentimiento(consentimiento, leer, vacio=()):
    """Corte único del ADR 0025: sin consentimiento vigente el motor no lee datos de salud."""
    return leer() if consentimiento else vacio


def restricciones_vigentes(socio_id, *, cursor=None, consentimiento=None, historial=None):
    """Solo para servicios que ya controlaron el alcance; no se expone una API.

    Quien ya conoce el consentimiento de la operación lo pasa para no consultarlo otra vez.
    Si ya leyó el historial de restricciones, reutiliza sus filas para obtener las vigentes.
    """
    with nullcontext(cursor) if cursor is not None else transaccion() as lectura:
        if consentimiento is None:
            consentimiento = tiene_consentimiento_salud(lectura, socio_id)
        filas = leer_con_consentimiento(
            consentimiento,
            lambda: (
                repositorio.restricciones_vigentes(lectura, socio_id)
                if historial is None
                else [f for f in historial if f["levantada_en"] is None]
            ),
        )
    return tuple(
        RestriccionSalud(
            str(desde_bytes(f["ejercicio_id"])) if f["ejercicio_id"] else None,
            f["patron_movimiento"],
            f["zona"],
            f["descripcion"],
        )
        for f in filas
    )


def revocaciones_de_salud(socio_ids, *, cursor):
    """Fecha de la revocación vigente por socio, sin datos de salud; el socio que consiente no aparece."""
    return {
        desde_bytes(f["socio_id"]): f["registrado_en"] for f in repositorio.revocaciones_de_socios(cursor, socio_ids)
    }


def consultar_consentimiento(socio_id):
    with transaccion() as cursor:
        fila = repositorio.consentimiento_vigente(cursor, socio_id)
    return {
        "salud": {
            "otorgado": bool(fila and fila["otorgado"]),
            "revocado": bool(fila and not fila["otorgado"]),
            "version_texto": repositorio.VERSION_TEXTO,
            "texto": repositorio.TEXTO_CONSENTIMIENTO,
        }
    }


def registrar_consentimiento(socio_id, datos):
    from gimnasio.permisos import servicio as permisos

    if (
        not isinstance(datos, dict)
        or set(datos) != {"otorgado", "version_texto"}
        or type(datos["otorgado"]) is not bool
        or datos["version_texto"] != repositorio.VERSION_TEXTO
    ):
        raise ErrorDeDominio("consentimiento_invalido", "Confirmá el consentimiento con su texto vigente.", 422)
    with transaccion() as cursor:
        repositorio.bloquear_socio(cursor, socio_id)
        permisos.registrar_consentimiento(
            cursor, socio_id, "salud", datos["otorgado"], datos["version_texto"], socio_id
        )
    return consultar_consentimiento(socio_id)
