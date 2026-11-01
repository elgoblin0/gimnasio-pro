"""Lecturas del socio sobre su acompañamiento y su resumen semanal."""

from flask import Blueprint, jsonify, request

from gimnasio.acompanamiento import servicio
from gimnasio.permisos.servicio import requiere, usuario_actual

bp = Blueprint("acompanamiento", __name__, url_prefix="/api/yo")


@bp.get("/incorporacion")
@requiere("acompanamiento.ver_propio")
def incorporacion():
    return jsonify(servicio.consultar_incorporacion_propia(usuario_actual()))


@bp.get("/resumen-semanal")
@requiere("acompanamiento.ver_propio")
def resumen_semanal():
    return jsonify(servicio.consultar_resumen_semanal_propio(usuario_actual(), request.args.get("semana")))
