"""API de clases y agenda."""

from flask import Blueprint, jsonify, request

from gimnasio.clases import servicio
from gimnasio.permisos.servicio import requiere

bp = Blueprint("clases", __name__, url_prefix="/api/clases")


@bp.get("/agenda")
@requiere("clases.ver")
def agenda():
    return jsonify(servicio.agenda())


@bp.get("")
@requiere("clases.configurar")
def listar():
    return jsonify(servicio.listar())


@bp.post("")
@requiere("clases.configurar")
def crear():
    return jsonify(servicio.guardar(request.get_json(silent=True))), 201


@bp.put("/<clase_id>")
@requiere("clases.configurar")
def cambiar(clase_id):
    return jsonify(servicio.guardar(request.get_json(silent=True), clase_id))


@bp.post("/<clase_id>/archivar")
@requiere("clases.configurar")
def archivar(clase_id):
    return jsonify(servicio.archivar(clase_id))
