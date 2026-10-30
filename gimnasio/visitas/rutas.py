"""Operaciones de recepción sobre visitas."""

from flask import Blueprint, jsonify, request

from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.permisos.servicio import requiere, usuario_actual
from gimnasio.visitas import servicio

bp = Blueprint("visitas", __name__, url_prefix="/api")


@bp.post("/entradas")
@requiere("visitas.registrar")
def registrar_entrada():
    entrada = servicio.registrar_entrada(request.get_json(silent=True), usuario_actual())
    return jsonify({"entrada": entrada, **_estado_recepcion()}), 201


@bp.post("/salidas")
@requiere("visitas.registrar")
def registrar_salida():
    salida = servicio.registrar_salida(request.get_json(silent=True), usuario_actual())
    return jsonify({"salida": salida, **_estado_recepcion()}), 201


@bp.get("/visitas")
@requiere("visitas.ver")
def listar_visitas():
    if request.args.get("abiertas", "1") != "1":
        raise ErrorDeDominio("consulta_invalida", "Esta lectura requiere abiertas=1.", 422)
    return _respuesta_condicional(servicio.consultar_visitas())


@bp.get("/ocupacion")
@requiere("ocupacion.ver")
def consultar_ocupacion():
    datos = servicio.consultar_ocupacion()
    if usuario_actual()["rol"] != "recepcion":
        datos.pop("por_conciliar")
        datos.pop("sede_id")
    return _respuesta_condicional(datos)


@bp.get("/visitas/socios")
@requiere("visitas.ver")
def listar_socios():
    return jsonify({"socios": servicio.listar_socios()})


@bp.post("/visitas/<entrada_id>/conciliacion")
@requiere("visitas.registrar")
def conciliar_salida(entrada_id):
    salida = servicio.conciliar_salida(entrada_id, request.get_json(silent=True), usuario_actual())
    return jsonify({"salida": salida, **_estado_recepcion()}), 201


def _estado_recepcion():
    return {"ocupacion": servicio.consultar_ocupacion(), "visitas": servicio.listar_visitas()}


def _respuesta_condicional(datos):
    respuesta = jsonify(datos)
    etiqueta = datos["version"]
    # Las duraciones pueden variar en segundos dentro de la misma versión por minuto.
    respuesta.set_etag(etiqueta, weak=True)
    respuesta.cache_control.private = True
    respuesta.cache_control.no_cache = True
    return respuesta.make_conditional(request)


@bp.get("/mejores-horarios")
@requiere("ocupacion.ver")
def consultar_mejores_horarios():
    return jsonify(servicio.consultar_mejores_horarios())
