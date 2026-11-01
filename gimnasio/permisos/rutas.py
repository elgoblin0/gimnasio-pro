from flask import Blueprint, jsonify, request

from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.permisos import servicio

bp = Blueprint("permisos", __name__, url_prefix="/api/sesion")

METODOS_QUE_CAMBIAN = {"POST", "PUT", "PATCH", "DELETE"}


@bp.before_app_request
def exigir_cambio_clave():
    if not request.path.startswith("/api/"):
        return None
    usuario = servicio.usuario_actual()
    if (
        usuario
        and usuario.get("debe_cambiar_clave")
        and request.endpoint not in {"permisos.cambiar_clave", "permisos.cerrar"}
    ):
        raise ErrorDeDominio("debe_cambiar_clave", "Cambiá tu clave provisional para continuar.", 403)
    return None


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
    # Sin sesión responde 200 con usuario null: no tener sesión no es un error (ADR 0006).
    return jsonify({"usuario": servicio.usuario_actual()})


@bp.delete("")
def cerrar():
    servicio.cerrar_sesion()
    return "", 204


@bp.put("/figura-cuerpo")
def cambiar_figura_cuerpo():
    datos = request.get_json(silent=True)
    figura = datos.get("figura_cuerpo") if isinstance(datos, dict) else None
    return jsonify({"usuario": servicio.cambiar_figura_cuerpo(figura)})


@bp.post("/demo/<rol>")
def entrar_como(rol):
    datos = request.get_json(silent=True)
    usuario_id = datos.get("usuario_id") if isinstance(datos, dict) else None
    return jsonify({"usuario": servicio.entrar_como_demo(rol, usuario_id)})


@bp.get("/demo/socios")
def socios_demo():
    return jsonify({"socios": servicio.socios_demo()})


@bp.post("/clave")
def cambiar_clave():
    return jsonify({"usuario": servicio.cambiar_clave(request.get_json(silent=True))})
