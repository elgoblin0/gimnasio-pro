"""Ficha del socio y perfil de entrenamiento con permisos y alcance explícitos."""

from flask import Blueprint, current_app, g, jsonify, request

from gimnasio.permisos.servicio import requiere, usuario_actual
from gimnasio.socios import servicio

bp = Blueprint("socios", __name__, url_prefix="/api")


@bp.post("/socios")
@requiere("socios.dar_alta")
def dar_alta():
    respuesta = servicio.dar_alta(request.get_json(silent=True), usuario_actual(), current_app.config["MODO_DEMO"])
    if "clave_provisional" in respuesta:
        g.respuesta_para_reintento = {
            campo: valor for campo, valor in respuesta.items() if campo != "clave_provisional"
        } | {"clave_ya_entregada": True}
    return jsonify(respuesta), 201


@bp.route("/yo/ficha", methods=["GET", "PUT"])
@requiere("socios.editar_datos_propios")
def ficha_propia():
    usuario = usuario_actual()
    datos = request.get_json(silent=True) if request.method == "PUT" else None
    return jsonify(servicio.ficha_socio(usuario["id"], usuario, datos, guardar=request.method == "PUT", propia=True))


@bp.route("/socios/<socio_id>/ficha", methods=["GET", "PUT"])
@requiere("socios.editar_datos")
def ficha_socio(socio_id):
    datos = request.get_json(silent=True) if request.method == "PUT" else None
    return jsonify(servicio.ficha_socio(socio_id, usuario_actual(), datos, guardar=request.method == "PUT"))


@bp.route("/socios/<socio_id>/perfil", methods=["GET", "PUT"])
@requiere("socios.ver_asignados")
def perfil_entrenamiento(socio_id):
    datos = request.get_json(silent=True) if request.method == "PUT" else None
    return jsonify(servicio.perfil_entrenamiento(socio_id, usuario_actual(), datos, guardar=request.method == "PUT"))
