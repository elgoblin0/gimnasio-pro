"""Límites de solicitudes para la instancia pública, sin dependencias adicionales."""

from ipaddress import ip_address

from flask import request
from werkzeug.exceptions import RequestEntityTooLarge

from gimnasio.comun.errores import respuesta_de_error
from gimnasio.demo.servicio import SOLICITUDES_POR_MINUTO, LimitePorIp

MAXIMO_BYTES_POR_SOLICITUD = 1_000_000


def _ip_de_la_solicitud(app):
    ip = request.remote_addr or "desconocida"
    # Solo Render garantiza el paso por Cloudflare. X-Forwarded-For puede incluir datos del cliente.
    if app.config["EN_RENDER"]:
        try:
            return str(ip_address(request.headers.get("CF-Connecting-IP", "")))
        except ValueError:
            pass
    return ip


def registrar_limites(app):
    limite = LimitePorIp()
    app.extensions["limite_demo"] = limite

    @app.before_request
    def limitar_demo():
        if not app.config["MODO_DEMO"]:
            return None
        espera = limite.espera(_ip_de_la_solicitud(app))
        if espera:
            respuesta = app.make_response(
                respuesta_de_error(
                    "demasiadas_solicitudes",
                    f"La demo admite {SOLICITUDES_POR_MINUTO} solicitudes por minuto por IP.",
                    429,
                )
            )
            respuesta.headers["Retry-After"] = str(espera)
            return respuesta
        if request.content_length is not None and request.content_length > MAXIMO_BYTES_POR_SOLICITUD:
            raise RequestEntityTooLarge()
        # Sin Content-Length, un byte extra permite detectar exceso en lugar de truncar el cuerpo.
        request.max_content_length = MAXIMO_BYTES_POR_SOLICITUD + 1
        # También controla rutas que no leen el cuerpo y transferencias sin Content-Length.
        # Flask conserva los bytes para que la ruta pueda leer JSON o formularios después.
        if len(request.get_data()) > MAXIMO_BYTES_POR_SOLICITUD:
            raise RequestEntityTooLarge()
        return None
