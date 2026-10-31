"""Vista del socio asignado y constancia de avisos revisados, sin alterar frenos."""

from dataclasses import asdict
from datetime import UTC

from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.ids import desde_bytes, nuevo_id
from gimnasio.comun.reloj import reloj_actual
from gimnasio.comun.tipos import MotivoBandeja, SocioBandeja
from gimnasio.entrenador import repositorio
from gimnasio.entrenamiento.servicio import (
    avisos_para_entrenador,
    consultar_propuesta,
    dolores_para_entrenador,
    historial_para_entrenador,
    identificar,
    ultima_serie_para_entrenador,
)
from gimnasio.permisos.servicio import socios_asignados, tiene_asignacion_vigente, tiene_consentimiento
from gimnasio.programas.servicio import listar_equipos, listar_programas
from gimnasio.reglas.bandeja import priorizar_bandeja
from gimnasio.salud.servicio import restricciones_vigentes


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
        programas = listar_programas(socio_id, cursor=cursor)
        sesiones = historial_para_entrenador(cursor, socio_id)
        avisos = avisos_para_entrenador(cursor, socio_id)
        revisiones = {
            str(desde_bytes(f["aviso_id"])): _revision_publica(f, consentimiento)
            for f in repositorio.listar_revisiones(cursor, [identificar(a["id"]) for a in avisos])
        }
        salud = (
            {
                "dolores_reportados": dolores_para_entrenador(cursor, socio_id),
                "restricciones_salud": [asdict(r) for r in restricciones_vigentes(socio_id, cursor=cursor)],
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
    }


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


def consultar_bandeja(usuario):
    """Lectura de asignaciones vigentes; no crea propuestas ni avisos persistidos."""
    entrenador_id = identificar(usuario["id"])
    socios = []
    with transaccion() as cursor:
        equipos = {e["nombre"]: e for e in listar_equipos(cursor=cursor)}
        for socio in socios_asignados(cursor, entrenador_id):
            socio_id = identificar(socio["id"])
            motivos = []
            avisos = avisos_para_entrenador(cursor, socio_id)
            revisados = {
                str(desde_bytes(f["aviso_id"]))
                for f in repositorio.listar_revisiones(cursor, [identificar(a["id"]) for a in avisos])
            }
            for aviso in avisos:
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
            programas = listar_programas(socio_id, cursor=cursor)
            if not programas:
                fecha = repositorio.fecha_asignacion_vigente(cursor, socio_id, entrenador_id)
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
            socios.append({**socio, "motivos": motivos})
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
