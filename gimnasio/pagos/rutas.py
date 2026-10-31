"""API de tipos de membresía y pagos registrados."""

from flask import Blueprint, jsonify, request

from gimnasio.pagos import servicio
from gimnasio.permisos.matriz import puede
from gimnasio.permisos.servicio import requiere, usuario_actual
from gimnasio.visitas.servicio import listar_socios

bp = Blueprint("pagos", __name__, url_prefix="/api")


@bp.get("/tipos-membresia")
@requiere("membresias.configurar", "pagos.registrar")
def tipos():
    return jsonify(
        tipos=servicio.listar_tipos(incluir_archivados=puede(usuario_actual()["rol"], "membresias.configurar"))
    )


@bp.post("/tipos-membresia")
@requiere("membresias.configurar")
def crear_tipo():
    return jsonify(servicio.guardar_tipo(request.get_json(silent=True))), 201


@bp.put("/tipos-membresia/<tipo_id>")
@requiere("membresias.configurar")
def cambiar_tipo(tipo_id):
    return jsonify(servicio.guardar_tipo(request.get_json(silent=True), tipo_id))


@bp.post("/tipos-membresia/<tipo_id>/archivar")
@requiere("membresias.configurar")
def archivar_tipo(tipo_id):
    return jsonify(servicio.archivar_tipo(tipo_id))


@bp.get("/pagos/socios")
@requiere("pagos.registrar")
def socios_para_pago():
    return jsonify(socios=listar_socios())


@bp.post("/pagos")
@requiere("pagos.registrar")
def registrar_pago():
    return jsonify(servicio.registrar_pago(request.get_json(silent=True), usuario_actual())), 201
