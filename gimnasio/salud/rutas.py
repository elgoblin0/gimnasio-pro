"""Consentimiento de salud propio (ADR 0006 y 0025)."""

from flask import Blueprint, jsonify, request

from gimnasio.comun.ids import desde_texto
from gimnasio.permisos.servicio import requiere, usuario_actual
from gimnasio.salud import servicio

bp = Blueprint("salud", __name__, url_prefix="/api")


@bp.post("/socios/<socio_id>/aviso-personal")
@requiere("avisos_personal.escribir")
def escribir_aviso_personal(socio_id):
    return jsonify(servicio.escribir_aviso_personal(socio_id, usuario_actual(), request.get_json(silent=True))), 201


@bp.get("/yo/salud/consultas")
@requiere("salud.ver_propia")
def consultas_ficha():
    return jsonify(
        servicio.consultar_consultas_ficha(desde_texto(usuario_actual()["id"]), request.args.get("pagina", "1"))
    )


@bp.get("/yo/datos")
@requiere("datos.descargar_propios")
def descargar_datos():
    respuesta = jsonify(servicio.descargar_datos_propios(desde_texto(usuario_actual()["id"])))
    respuesta.headers["Content-Disposition"] = 'attachment; filename="mis-datos.json"'
    respuesta.cache_control.no_store = True
    return respuesta


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
