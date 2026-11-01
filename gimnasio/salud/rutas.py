"""Consentimiento de salud propio (ADR 0006 y 0025)."""

from flask import Blueprint, jsonify, request

from gimnasio.comun.ids import desde_texto
from gimnasio.permisos.servicio import requiere, usuario_actual
from gimnasio.salud import servicio

bp = Blueprint("salud", __name__, url_prefix="/api")


@bp.get("/yo/consentimientos")
@requiere("consentimientos.gestionar_propios")
def consultar():
    return jsonify(servicio.consultar_consentimiento(desde_texto(usuario_actual()["id"])))


@bp.post("/yo/consentimientos/salud")
@requiere("consentimientos.gestionar_propios")
def registrar():
    return jsonify(
        servicio.registrar_consentimiento(desde_texto(usuario_actual()["id"]), request.get_json(silent=True))
    )


@bp.get("/yo/salud")
@requiere("salud.ver_propia")
def propia():
    usuario = usuario_actual()
    return jsonify(servicio.consultar_salud(usuario["id"], usuario))


@bp.route("/yo/salud/condiciones", methods=["GET", "POST"])
@requiere("salud.declarar_condicion")
def condiciones():
    usuario = usuario_actual()
    if request.method == "GET":
        return jsonify(servicio.consultar_salud(usuario["id"], usuario, solo_condiciones=True))
    return jsonify(servicio.declarar_condicion(usuario["id"], usuario, request.get_json(silent=True))), 201


@bp.get("/socios/<socio_id>/salud")
@requiere("salud.ver_asignados")
def asignado(socio_id):
    return jsonify(servicio.consultar_salud(socio_id, usuario_actual()))


@bp.post("/socios/<socio_id>/salud/restricciones")
@requiere("salud.gestionar_restricciones")
def restringir(socio_id):
    return jsonify(servicio.gestionar(socio_id, usuario_actual(), request.get_json(silent=True))), 201


@bp.post("/socios/<socio_id>/salud/restricciones/<restriccion_id>/levantar")
@requiere("salud.gestionar_restricciones")
def levantar(socio_id, restriccion_id):
    datos = request.get_json(silent=True) if request.data else {}
    return jsonify(servicio.gestionar(socio_id, usuario_actual(), datos, restriccion_texto=restriccion_id))


@bp.post("/socios/<socio_id>/salud/condiciones/<condicion_id>/revisar")
@requiere("salud.gestionar_restricciones")
def revisar(socio_id, condicion_id):
    datos = request.get_json(silent=True) if request.data else {}
    return jsonify(servicio.gestionar(socio_id, usuario_actual(), datos, condicion_texto=condicion_id))
