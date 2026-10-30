"""Consulta y cambios de estado de los equipos."""

from flask import Blueprint, jsonify, request

from gimnasio.permisos.servicio import requiere, usuario_actual
from gimnasio.programas import servicio

bp = Blueprint("programas", __name__, url_prefix="/api/equipos")


@bp.get("")
@requiere("equipos.gestionar")
def listar_equipos():
    return jsonify({"equipos": servicio.listar_equipos()})


@bp.post("/<equipo_id>/estado")
@requiere("equipos.gestionar")
def cambiar_estado_equipo(equipo_id):
    return jsonify(
        {"equipo": servicio.cambiar_estado_equipo(equipo_id, request.get_json(silent=True), usuario_actual())}
    )
