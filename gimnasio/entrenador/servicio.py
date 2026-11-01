"""Vista del socio asignado y constancia de avisos revisados, sin alterar frenos."""

from dataclasses import asdict
from datetime import UTC

from gimnasio.acompanamiento.servicio import estados_de_socios, incorporacion_de, resumen_semanal
from gimnasio.comun.bd import LecturaConMemoria, transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.ids import desde_bytes, nuevo_id
from gimnasio.comun.reloj import reloj_actual
from gimnasio.comun.tipos import EjercicioCatalogo, MotivoBandeja, SocioBandeja
from gimnasio.entrenador import repositorio
from gimnasio.entrenamiento.servicio import (
    avisos_para_entrenador,
    avisos_para_entrenador_por_socio,
    consultar_propuesta,
    dolores_para_entrenador,
    historial_para_entrenador,
    identificar,
    ultima_serie_para_entrenador,
)
from gimnasio.permisos.servicio import socios_asignados, tiene_asignacion_vigente, tiene_consentimiento
from gimnasio.programas.servicio import listar_equipos, listar_programas, socios_con_programa
from gimnasio.reglas.bandeja import priorizar_bandeja
from gimnasio.reglas.restricciones import excluido
from gimnasio.salud.servicio import (
    condiciones_para_entrenador,
    condiciones_pendientes,
    historial_restricciones,
    registrar_consulta_ficha,
    restricciones_vigentes,
    revocaciones_de_salud,
)


def _exigir_asignacion(cursor, socio_id, entrenador_id):
    if not tiene_asignacion_vigente(cursor, socio_id, entrenador_id):
        raise ErrorDeDominio("sin_asignacion", "El socio no tiene una asignación vigente con el entrenador.", 403)


def listar_socios(usuario):
    with transaccion() as cursor:
        return socios_asignados(cursor, identificar(usuario["id"]))


def _sin_datos_salud(valor):
    """Copia la respuesta y filtra razones también dentro de ejercicios y frenos."""
    if isinstance(valor, list):
        return [_sin_datos_salud(elemento) for elemento in valor]
    if not isinstance(valor, dict):
        return valor
    if valor.get("regla") in {"dolor_reportado", "restriccion_salud"}:
        return {
            "regla": valor["regla"],
            "version": valor["version"],
            "datos": {
                clave: dato for clave, dato in valor["datos"].items() if clave in {"ejercicio_id", "ejercicio_hecho_id"}
            },
        }
    return {clave: _sin_datos_salud(dato) for clave, dato in valor.items()}


def _revision_publica(fila, consentimiento):
    return {
        "entrenador_id": str(desde_bytes(fila["entrenador_id"])),
        "nota": fila["nota"] if consentimiento else None,
        "revisada_en": fila["revisada_en"].replace(tzinfo=UTC).isoformat(),
    }


def consultar_socio(socio_texto, usuario):
    socio_id, entrenador_id = identificar(socio_texto), identificar(usuario["id"])
    with transaccion() as cursor:
        _exigir_asignacion(cursor, socio_id, entrenador_id)
        socio = next(s for s in socios_asignados(cursor, entrenador_id) if s["id"] == str(socio_id))
        consentimiento = tiene_consentimiento(cursor, socio_id, "salud")
        if consentimiento:
            registrar_consulta_ficha(cursor, socio_id, entrenador_id)
        programas = listar_programas(socio_id, cursor=cursor)
        sesiones = historial_para_entrenador(cursor, socio_id)
        acompanamiento = estados_de_socios(cursor, [socio_id])[socio_id]
        incorporacion = incorporacion_de(cursor, socio_id, acompanamiento)
        avisos = avisos_para_entrenador(cursor, socio_id)
        revisiones = {
            str(desde_bytes(f["aviso_id"])): _revision_publica(f, consentimiento)
            for f in repositorio.listar_revisiones(cursor, [identificar(a["id"]) for a in avisos])
        }
        salud = (
            {
                "condiciones": condiciones_para_entrenador(cursor, socio_id),
                "dolores_reportados": dolores_para_entrenador(cursor, socio_id),
                "restricciones_salud": [
                    asdict(r) for r in restricciones_vigentes(socio_id, cursor=cursor, consentimiento=True)
                ],
            }
            if consentimiento
            else None
        )
    for aviso in avisos:
        aviso["revision"] = revisiones.get(aviso["id"])
        aviso["revisado"] = aviso["revision"] is not None
    return {
        "socio": socio,
        "figura_cuerpo": socio["figura_cuerpo"],
        "programa_vigente": programas[-1] if programas else None,
        "sesiones_realizadas": sesiones if consentimiento else _sin_datos_salud(sesiones),
        "avisos": avisos if consentimiento else _sin_datos_salud(avisos),
        "salud": salud,
        "sin_consentimiento": not consentimiento,
        "incorporacion": incorporacion,
        "riesgo_abandono": acompanamiento["riesgo"],
    }


def consultar_resumen_semanal(socio_texto, usuario, semana_texto=None):
    """El mismo resumen que ve el socio; sin consentimiento de salud, sin sus datos (ADR 0024)."""
    socio_id, entrenador_id = identificar(socio_texto), identificar(usuario["id"])
    with transaccion() as cursor:
        _exigir_asignacion(cursor, socio_id, entrenador_id)
        consentimiento = tiene_consentimiento(cursor, socio_id, "salud")
        resumen = resumen_semanal(cursor, socio_id, semana_texto)
    return resumen if consentimiento else _sin_datos_salud(resumen)


def revisar_avisos(socio_texto, datos, usuario):
    socio_id, entrenador_id = identificar(socio_texto), identificar(usuario["id"])
    with transaccion() as cursor:
        _exigir_asignacion(cursor, socio_id, entrenador_id)
        if not isinstance(datos, dict) or not isinstance(datos.get("aviso_ids"), list):
            raise ErrorDeDominio("datos_invalidos", "Indicá los avisos a revisar.", 422)
        nota = datos.get("nota")
        if nota is not None and (not isinstance(nota, str) or len(nota) > 500):
            raise ErrorDeDominio("nota_invalida", "La nota admite hasta 500 caracteres.", 422)
        ids = set(identificar(texto) for texto in datos["aviso_ids"])
        avisos = {identificar(f["id"]) for f in avisos_para_entrenador(cursor, socio_id, bloquear=True)}
        if ids - avisos:
            raise ErrorDeDominio("aviso_ajeno", "Uno de los avisos no pertenece al socio.", 422)
        revisados = {desde_bytes(f["aviso_id"]) for f in repositorio.listar_revisiones(cursor, ids, actual=True)}
        reloj = reloj_actual()
        ahora = reloj.ahora()
        for aviso_id in sorted(ids - revisados):
            repositorio.insertar_revision(cursor, nuevo_id(reloj), aviso_id, entrenador_id, nota, ahora)
    return {"aviso_ids": sorted(str(identificador) for identificador in ids)}


def _fecha_restriccion(cursor, socio_id, ejercicio):
    # consultar_propuesta ya leyó estas filas: LecturaConMemoria evita repetir la consulta.
    filas = [
        f for f in historial_restricciones(socio_id, cursor=cursor, consentimiento=True) if f["levantada_en"] is None
    ]
    restricciones = restricciones_vigentes(socio_id, cursor=cursor, consentimiento=True, historial=filas)
    catalogado = EjercicioCatalogo(
        ejercicio["ejercicio_id"],
        ejercicio["nombre"],
        None,
        patron_movimiento=ejercicio["patron_movimiento"],
        zonas=tuple(ejercicio["zonas"]),
    )
    return (
        min(
            fila["registrada_en"]
            for fila, restriccion in zip(filas, restricciones, strict=True)
            if excluido(catalogado, (restriccion,))
        )
        .replace(tzinfo=UTC)
        .isoformat()
    )


def consultar_bandeja(usuario):
    """Lectura de asignaciones vigentes; no crea propuestas ni avisos persistidos.

    La sondea cada entrenador con la bandeja abierta: lo que vale para todos se lee de una vez, y solo los
    socios con programa pagan el costo de su propuesta.
    """
    entrenador_id = identificar(usuario["id"])
    socios = []
    with transaccion() as lectura:
        cursor = LecturaConMemoria(lectura)
        equipos = {e["nombre"]: e for e in listar_equipos(cursor=cursor)}
        asignados = socios_asignados(cursor, entrenador_id)
        socio_ids = [identificar(socio["id"]) for socio in asignados]
        avisos_por_socio = avisos_para_entrenador_por_socio(cursor, socio_ids)
        revisados = {
            str(desde_bytes(f["aviso_id"]))
            for f in repositorio.listar_revisiones(
                cursor, [identificar(a["id"]) for avisos in avisos_por_socio.values() for a in avisos]
            )
        }
        con_programa = socios_con_programa(cursor, socio_ids)
        asignaciones = repositorio.fechas_asignacion_vigente(cursor, socio_ids, entrenador_id)
        revocaciones = revocaciones_de_salud(socio_ids, cursor=cursor)
        condiciones = condiciones_pendientes(socio_ids, cursor=cursor)
        acompanamiento = estados_de_socios(cursor, socio_ids)
        for socio, socio_id in zip(asignados, socio_ids, strict=True):
            motivos = []
            if socio_id in condiciones:
                motivos.append(
                    {"tipo": "condicion_sin_revisar", "fecha": condiciones[socio_id].replace(tzinfo=UTC).isoformat()}
                )
            for aviso in avisos_por_socio.get(socio_id, []):
                if aviso["id"] in revisados or aviso["freno"] not in {
                    "dolor_reportado",
                    "restriccion_salud",
                    "chequeo_desfavorable",
                    "tope_semanal",
                }:
                    continue
                tipo = (
                    "aviso_seguridad"
                    if aviso["freno"] in {"dolor_reportado", "restriccion_salud"}
                    else "aviso_progresion"
                )
                motivos.append({"tipo": tipo, "fecha": aviso["creado_en"], "aviso_id": aviso["id"]})
            if socio_id not in con_programa:
                fecha = asignaciones[socio_id]
                motivos.append({"tipo": "sin_programa", "fecha": fecha.replace(tzinfo=UTC).isoformat()})
            else:
                propuesta = consultar_propuesta(socio["id"], usuario, cursor=cursor, sin_chequeo=True)
                if propuesta["sesion_planificada"] is None:
                    fecha = ultima_serie_para_entrenador(cursor, socio_id)
                    if fecha is not None:
                        motivos.append({"tipo": "secuencia_terminada", "fecha": fecha.replace(tzinfo=UTC).isoformat()})
                for ejercicio in propuesta["ejercicios"]:
                    if ejercicio["no_disponible"] and ejercicio["pendiente"] > 0:
                        equipo = equipos.get(ejercicio["equipo_no_disponible"])
                        if equipo and equipo["estado"] == "fuera_de_servicio" and equipo["ultimo_cambio"]:
                            motivos.append(
                                {
                                    "tipo": "ejercicio_sin_alternativa",
                                    "fecha": equipo["ultimo_cambio"],
                                    "ejercicio_id": ejercicio["id"],
                                }
                            )
                        elif "restriccion_salud" in {r["regla"] for r in ejercicio["explicacion"]}:
                            motivos.append(
                                {
                                    "tipo": "ejercicio_sin_alternativa",
                                    "ejercicio_id": ejercicio["id"],
                                    "fecha": _fecha_restriccion(cursor, socio_id, ejercicio),
                                }
                            )
            if socio_id in revocaciones:
                fecha = revocaciones[socio_id].replace(tzinfo=UTC).isoformat()
                motivos.append({"tipo": "sin_consentimiento_salud", "fecha": fecha})
            riesgo = acompanamiento[socio_id]["riesgo"]
            if riesgo:
                motivos.append({"tipo": "riesgo_abandono", "fecha": acompanamiento[socio_id]["desde"]})
            socios.append({**socio, "motivos": motivos, "riesgo_abandono": riesgo})
    por_id = {s["id"]: s for s in socios}
    grupos = priorizar_bandeja(
        tuple(SocioBandeja(s["id"], tuple(MotivoBandeja(**m) for m in s["motivos"])) for s in socios)
    )
    return {
        "grupos": [
            {
                "tipo": grupo.tipo,
                "socios": [{**por_id[s.id], "explicacion": [asdict(r) for r in s.explicacion]} for s in grupo.socios],
            }
            for grupo in grupos
        ]
    }
