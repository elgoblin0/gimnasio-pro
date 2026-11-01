from flask import Blueprint, current_app, g, jsonify, request

from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.permisos import servicio

bp = Blueprint("permisos", __name__, url_prefix="/api/sesion")
bp_usuarios = Blueprint("usuarios", __name__, url_prefix="/api")

METODOS_QUE_CAMBIAN = {"POST", "PUT", "PATCH", "DELETE"}


def _entregar_clave(respuesta, estado=200):
    if "clave_provisional" in respuesta:
        g.respuesta_para_reintento = {
            campo: valor for campo, valor in respuesta.items() if campo != "clave_provisional"
        } | {"clave_ya_entregada": True}
    return jsonify(respuesta), estado


@bp_usuarios.post("/usuarios")
@servicio.requiere("usuarios.administrar")
def alta_personal():
    return _entregar_clave(servicio.alta_personal(request.get_json(silent=True), current_app.config["MODO_DEMO"]), 201)


@bp_usuarios.get("/usuarios")
@servicio.requiere("usuarios.administrar")
def listar_usuarios():
    return jsonify(servicio.consultar_usuarios(request.args))


@bp_usuarios.post("/usuarios/<usuario_id>/desactivar")
@servicio.requiere("usuarios.administrar")
def desactivar_usuario(usuario_id):
    return jsonify(
        servicio.cambiar_estado_usuario(usuario_id, request.get_json(silent=True), False, servicio.usuario_actual())
    )


@bp_usuarios.post("/usuarios/<usuario_id>/reactivar")
@servicio.requiere("usuarios.administrar")
def reactivar_usuario(usuario_id):
    return jsonify(
        servicio.cambiar_estado_usuario(usuario_id, request.get_json(silent=True), True, servicio.usuario_actual())
    )


@bp_usuarios.post("/usuarios/<usuario_id>/clave")
@servicio.requiere("usuarios.administrar")
def restablecer_clave(usuario_id):
    return _entregar_clave(servicio.restablecer_clave(usuario_id, current_app.config["MODO_DEMO"]))


@bp_usuarios.get("/socios/sin-entrenador")
@servicio.requiere("usuarios.administrar")
def sin_entrenador():
    return jsonify(servicio.consultar_sin_entrenador())


@bp_usuarios.put("/socios/<socio_id>/entrenador")
@servicio.requiere("usuarios.administrar")
def asignar_entrenador(socio_id):
    return jsonify(servicio.asignar_entrenador(socio_id, request.get_json(silent=True)))


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
