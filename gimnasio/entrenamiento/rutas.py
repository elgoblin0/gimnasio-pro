"""Lecturas de entrenamiento con permisos y alcance declarados."""

from flask import Blueprint, jsonify

from gimnasio.entrenamiento import servicio
from gimnasio.permisos.servicio import requiere, usuario_actual

bp = Blueprint("entrenamiento", __name__, url_prefix="/api/entrenamiento")


@bp.get("/propuesta")
@requiere("entrenamiento.ver_propio")
def propuesta_propia():
    usuario = usuario_actual()
    return jsonify(servicio.consultar_propuesta(usuario["id"], usuario))


@bp.get("/socios/<socio_id>/propuesta")
@requiere("entrenamiento.ver_asignados")
def propuesta_asignada(socio_id):
    return jsonify(servicio.consultar_propuesta(socio_id, usuario_actual()))
