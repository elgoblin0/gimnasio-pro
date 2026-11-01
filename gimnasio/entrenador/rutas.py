"""Lecturas del entrenador y constancia de avisos revisados."""

from flask import Blueprint, jsonify, request

from gimnasio.entrenador import servicio
from gimnasio.permisos.servicio import requiere, usuario_actual

bp = Blueprint("entrenador", __name__, url_prefix="/api/entrenador")


@bp.get("/socios")
@requiere("socios.ver_asignados")
def listar_socios():
    return jsonify({"socios": servicio.listar_socios(usuario_actual())})


@bp.get("/socios/<socio_id>")
@requiere("socios.ver_asignados")
def consultar_socio(socio_id):
    return jsonify(servicio.consultar_socio(socio_id, usuario_actual()))


@bp.get("/socios/<socio_id>/resumen-semanal")
@requiere("socios.ver_asignados")
def consultar_resumen_semanal(socio_id):
    return jsonify(servicio.consultar_resumen_semanal(socio_id, usuario_actual(), request.args.get("semana")))


@bp.post("/socios/<socio_id>/avisos/revision")
@requiere("avisos.revisar")
def revisar_avisos(socio_id):
    return jsonify(servicio.revisar_avisos(socio_id, request.get_json(silent=True), usuario_actual()))


@bp.get("/bandeja")
@requiere("socios.ver_asignados")
def consultar_bandeja():
    respuesta = jsonify(servicio.consultar_bandeja(usuario_actual()))
    respuesta.add_etag()
    respuesta.cache_control.private = True
    respuesta.cache_control.no_cache = True
    return respuesta.make_conditional(request)
