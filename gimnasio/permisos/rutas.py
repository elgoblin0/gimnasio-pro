from flask import Blueprint, jsonify, request

from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.permisos import servicio

bp = Blueprint("permisos", __name__, url_prefix="/api/sesion")

METODOS_QUE_CAMBIAN = {"POST", "PUT", "PATCH", "DELETE"}


@bp.before_app_request
def exigir_encabezado_anti_csrf():
    # Junto con SameSite=Lax, un formulario de otro sitio no puede enviar este encabezado (ADR 0006).
    if (
        request.method in METODOS_QUE_CAMBIAN
        and request.path.startswith("/api/")
        and request.headers.get("X-Gimnasio") != "1"
    ):
        raise ErrorDeDominio("falta_encabezado", "Falta el encabezado X-Gimnasio.", 403)


@bp.post("")
def iniciar():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict) or not all(
        isinstance(datos.get(campo), str) for campo in ("identificador", "clave")
    ):
        raise ErrorDeDominio("cuerpo_invalido", "Enviá identificador y clave como texto.", 400)
    ip = request.remote_addr or "desconocida"
    usuario = servicio.iniciar_sesion(datos["identificador"], datos["clave"], ip)
    return jsonify({"usuario": usuario})


@bp.get("")
def ver():
    usuario = servicio.usuario_actual()
    if usuario is None:
        raise ErrorDeDominio("sin_sesion", "No hay una sesión iniciada.", 401)
    return jsonify({"usuario": usuario})


@bp.delete("")
def cerrar():
    servicio.cerrar_sesion()
    return "", 204


@bp.post("/demo/<rol>")
def entrar_como(rol):
    return jsonify({"usuario": servicio.entrar_como_demo(rol)})
