"""Lecturas de entrenamiento con permisos y alcance declarados."""

from flask import Blueprint, jsonify, request

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


@bp.post("/sesiones")
@requiere("entrenamiento.registrar_propio")
def crear_sesion():
    return jsonify({"sesion_realizada": servicio.crear_sesion(request.get_json(silent=True), usuario_actual())}), 201


@bp.post("/sesiones/<sesion_id>/series")
@requiere("entrenamiento.registrar_propio")
def registrar_serie(sesion_id):
    return jsonify(servicio.registrar_serie(sesion_id, request.get_json(silent=True), usuario_actual())), 201


@bp.get("/sesiones/<sesion_id>")
@requiere("entrenamiento.ver_propio")
def consultar_sesion(sesion_id):
    return jsonify(servicio.consultar_sesion(sesion_id, usuario_actual()))


@bp.get("/sesiones/<sesion_id>/ejercicios/<ejercicio_id>/alternativas")
@requiere("entrenamiento.ver_propio")
def consultar_alternativas(sesion_id, ejercicio_id):
    return jsonify(servicio.consultar_alternativas(sesion_id, ejercicio_id, usuario_actual()))


@bp.post("/sesiones/<sesion_id>/sustituciones")
@requiere("entrenamiento.registrar_propio")
def registrar_sustitucion(sesion_id):
    return jsonify(
        {"sustitucion": servicio.registrar_sustitucion(sesion_id, request.get_json(silent=True), usuario_actual())}
    ), 201
