"""Operaciones de recepción sobre visitas."""

from flask import Blueprint, jsonify, request

from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.permisos.servicio import requiere, usuario_actual
from gimnasio.visitas import servicio

bp = Blueprint("visitas", __name__, url_prefix="/api")


@bp.post("/entradas")
@requiere("visitas.registrar")
def registrar_entrada():
    entrada = servicio.registrar_entrada(request.get_json(silent=True), usuario_actual())
    return jsonify({"entrada": entrada}), 201


@bp.post("/salidas")
@requiere("visitas.registrar")
def registrar_salida():
    return jsonify({"salida": servicio.registrar_salida(request.get_json(silent=True), usuario_actual())}), 201


@bp.get("/visitas")
@requiere("visitas.ver")
def listar_visitas():
    if request.args.get("abiertas", "1") != "1":
        raise ErrorDeDominio("consulta_invalida", "Esta lectura requiere abiertas=1.", 422)
    return jsonify({"visitas": servicio.listar_visitas()})


@bp.get("/ocupacion")
@requiere("visitas.ver")
def consultar_ocupacion():
    return jsonify(servicio.consultar_ocupacion())


@bp.get("/visitas/socios")
@requiere("visitas.ver")
def listar_socios():
    return jsonify({"socios": servicio.listar_socios()})


@bp.post("/visitas/<entrada_id>/conciliacion")
@requiere("visitas.registrar")
def conciliar_salida(entrada_id):
    salida = servicio.conciliar_salida(entrada_id, request.get_json(silent=True), usuario_actual())
    return jsonify({"salida": salida}), 201
