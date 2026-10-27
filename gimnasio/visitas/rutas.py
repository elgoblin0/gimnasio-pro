"""Operaciones de recepción sobre visitas."""

from flask import Blueprint, jsonify, request

from gimnasio.permisos.servicio import requiere, usuario_actual
from gimnasio.visitas import servicio

bp = Blueprint("visitas", __name__, url_prefix="/api")


@bp.post("/entradas")
@requiere("visitas.registrar")
def registrar_entrada():
    entrada = servicio.registrar_entrada(request.get_json(silent=True), usuario_actual())
    return jsonify({"entrada": entrada}), 201
