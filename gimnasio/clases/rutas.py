"""API de clases y agenda."""

from flask import Blueprint, jsonify, request

from gimnasio.clases import servicio
from gimnasio.permisos.servicio import requiere, usuario_actual

bp = Blueprint("clases", __name__, url_prefix="/api/clases")


@bp.get("/agenda")
@requiere("clases.ver")
def agenda():
    return jsonify(servicio.agenda(usuario_actual(), request.args.get("socio_id")))


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


@bp.post("/reservas")
@requiere("clases.reservar_propias", "clases.gestionar_reservas")
def reservar():
    return jsonify(servicio.reservar(request.get_json(silent=True), usuario_actual())), 201


@bp.post("/reservas/<reserva_id>/cancelar")
@requiere("clases.reservar_propias", "clases.gestionar_reservas")
def cancelar(reserva_id):
    return jsonify(servicio.cancelar(reserva_id, usuario_actual()))


@bp.get("/<clase_id>/<fecha>/reservas")
@requiere("clases.ver_reservas")
def reservas(clase_id, fecha):
    return jsonify(servicio.listar_reservas(clase_id, fecha, usuario_actual()))
