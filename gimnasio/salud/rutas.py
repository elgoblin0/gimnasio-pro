"""Consentimiento de salud propio (ADR 0006 y 0025)."""

from flask import Blueprint, jsonify, request

from gimnasio.comun.ids import desde_texto
from gimnasio.permisos.servicio import requiere, usuario_actual
from gimnasio.salud import servicio

bp = Blueprint("salud", __name__, url_prefix="/api/yo/consentimientos")


@bp.get("")
@requiere("consentimientos.gestionar_propios")
def consultar():
    return jsonify(servicio.consultar_consentimiento(desde_texto(usuario_actual()["id"])))


@bp.post("/salud")
@requiere("consentimientos.gestionar_propios")
def registrar():
    return jsonify(
        servicio.registrar_consentimiento(desde_texto(usuario_actual()["id"]), request.get_json(silent=True))
    )
