"""Gimnasio Pro: monolito modular con blueprints de Flask (ADR 0001)."""

import os
import secrets

from flask import Flask

from gimnasio.comun.errores import registrar_manejadores
from gimnasio.comun.reloj import RelojSistema

ENTORNOS = ("desarrollo", "prueba", "produccion")


def _config_desde_entorno():
    return {
        "ENTORNO": os.environ.get("GIMNASIO_ENTORNO", "desarrollo"),
        "SECRET_KEY": os.environ.get("GIMNASIO_CLAVE_SECRETA"),
        "MODO_DEMO": os.environ.get("MODO_DEMO") == "1",
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

    from gimnasio.sistema.rutas import bp as sistema

    app.register_blueprint(sistema)

    @app.get("/")
    def inicio():
        return app.send_static_file("index.html")

    return app
