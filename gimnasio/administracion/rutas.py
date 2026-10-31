"""Panel de configuración de la sede."""

from flask import Blueprint, jsonify, request

from gimnasio.administracion import servicio
from gimnasio.permisos.servicio import requiere, usuario_actual

bp = Blueprint("administracion", __name__, url_prefix="/api/administracion")


@bp.get("/sede")
@requiere("configuracion.editar")
def consultar_sede():
    return jsonify(servicio.consultar_sede())


@bp.put("/sede")
@requiere("configuracion.editar")
def cambiar_sede():
    return jsonify(servicio.cambiar_sede(request.get_json(silent=True), usuario_actual()))
