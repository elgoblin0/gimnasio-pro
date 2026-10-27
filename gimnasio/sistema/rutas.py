from flask import Blueprint, current_app, jsonify

from gimnasio.sistema import servicio

bp = Blueprint("sistema", __name__, url_prefix="/api")


@bp.get("/estado")
def estado():
    return jsonify(servicio.estado_del_servicio(current_app.config))
