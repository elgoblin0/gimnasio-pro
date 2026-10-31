"""Gimnasio Pro: monolito modular con blueprints de Flask (ADR 0001)."""

import os
import secrets

from flask import Flask

from gimnasio.comun.bd import registrar_cierre
from gimnasio.comun.errores import registrar_manejadores
from gimnasio.comun.idempotencia import registrar_idempotencia
from gimnasio.comun.reloj import RelojSistema

ENTORNOS = ("desarrollo", "prueba", "produccion")


def _config_desde_entorno():
    return {
        "ENTORNO": os.environ.get("GIMNASIO_ENTORNO", "desarrollo"),
        "SECRET_KEY": os.environ.get("GIMNASIO_CLAVE_SECRETA"),
        "MODO_DEMO": os.environ.get("MODO_DEMO") == "1",
        "EN_RENDER": os.environ.get("RENDER") == "true",
    }


def crear_app(config=None, reloj=None):
    """Crea la app. `config` reemplaza lo leído del entorno; `reloj` se inyecta (ADR 0005)."""
    ajustes = _config_desde_entorno() | (config or {})
    entorno = ajustes["ENTORNO"]
    if entorno not in ENTORNOS:
        raise ValueError(f"GIMNASIO_ENTORNO debe ser uno de {ENTORNOS}, no {entorno!r}")
    if not ajustes["SECRET_KEY"]:
        if entorno == "produccion":
            raise RuntimeError("En producción hay que definir GIMNASIO_CLAVE_SECRETA")
        ajustes["SECRET_KEY"] = secrets.token_hex(32)

    app = Flask(__name__, static_folder="static", static_url_path="")
    app.config.update(
        ajustes,
        TESTING=entorno == "prueba",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # Secure solo en producción: el CI y el e2e corren sobre http://localhost (ADR 0006).
        SESSION_COOKIE_SECURE=entorno == "produccion",
    )
    app.json.ensure_ascii = False
    app.extensions["reloj"] = reloj if reloj is not None else RelojSistema()

    registrar_manejadores(app)
    registrar_cierre(app)

    from gimnasio.administracion.rutas import bp as administracion
    from gimnasio.clases.rutas import bp as clases
    from gimnasio.demo.limites import registrar_limites
    from gimnasio.entrenador.rutas import bp as entrenador
    from gimnasio.entrenamiento.rutas import bp as entrenamiento
    from gimnasio.permisos.rutas import bp as permisos
    from gimnasio.programas.rutas import bp as programas
    from gimnasio.sistema.rutas import bp as sistema
    from gimnasio.socios.rutas import bp as socios
    from gimnasio.visitas.rutas import bp as visitas

    app.register_blueprint(administracion)
    app.register_blueprint(clases)
    registrar_limites(app)
    app.register_blueprint(sistema)
    app.register_blueprint(socios)
    app.register_blueprint(permisos)
    app.register_blueprint(visitas)
    app.register_blueprint(entrenamiento)
    app.register_blueprint(entrenador)
    app.register_blueprint(programas)

    from gimnasio.permisos.servicio import usuario_actual

    registrar_idempotencia(app, usuario_actual)

    @app.get("/")
    def inicio():
        return app.send_static_file("index.html")

    @app.get("/manifest.webmanifest")
    def manifiesto():
        respuesta = app.send_static_file("manifest.webmanifest")
        respuesta.mimetype = "application/manifest+json"
        return respuesta

    @app.get("/sw.js")
    def servir_sw():
        respuesta = app.send_static_file("sw.js")
        respuesta.mimetype = "text/javascript"
        respuesta.headers["Cache-Control"] = "no-cache"
        respuesta.headers["Service-Worker-Allowed"] = "/"
        return respuesta

    return app
