"""Errores de dominio y respuestas de error en JSON para la API."""

from flask import jsonify, request
from werkzeug.exceptions import HTTPException


class ErrorDeDominio(Exception):
    """Error esperado de un caso de uso. `codigo` es estable y lo usa el frontend."""

    def __init__(self, codigo, mensaje, estado_http=400):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.estado_http = estado_http


def respuesta_de_error(codigo, mensaje, estado_http):
    return jsonify({"error": {"codigo": codigo, "mensaje": mensaje}}), estado_http


def registrar_manejadores(app):
    @app.errorhandler(ErrorDeDominio)
    def error_de_dominio(error):
        return respuesta_de_error(error.codigo, error.mensaje, error.estado_http)

    @app.errorhandler(HTTPException)
    def error_http(error):
        # Las páginas conservan el error HTML de Flask; la API siempre responde JSON.
        if not request.path.startswith("/api/"):
            return error
        codigo = (error.name or "error").lower().replace(" ", "_")
        return respuesta_de_error(codigo, error.description, error.code)
