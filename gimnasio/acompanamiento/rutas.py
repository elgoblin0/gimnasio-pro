"""Lecturas del socio sobre su acompañamiento."""

from flask import Blueprint, jsonify

from gimnasio.acompanamiento import servicio
from gimnasio.permisos.servicio import requiere, usuario_actual

bp = Blueprint("acompanamiento", __name__, url_prefix="/api/yo")


@bp.get("/incorporacion")
@requiere("acompanamiento.ver_propio")
def incorporacion():
    return jsonify(servicio.consultar_incorporacion_propia(usuario_actual()))
