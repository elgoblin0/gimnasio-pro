"""Servidor demo y navegador para los recorridos de punta a punta."""

import os
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import Thread
from types import SimpleNamespace

import pytest
from mysql.connector import InterfaceError, OperationalError
from werkzeug.serving import make_server

from gimnasio import crear_app
from gimnasio.comun.bd import conectar, parametros_desde_entorno
from gimnasio.comun.migrar import aplicar
from gimnasio.comun.reloj import RelojFijo
from gimnasio.demo.servicio import reiniciar


@contextmanager
def servidor_demo(playwright):
    """Prepara una base exclusiva y la elimina aun si falla la semilla o el recorrido."""
    if not os.environ.get("GIMNASIO_BD_HOST"):
        pytest.skip("sin MySQL: definí GIMNASIO_BD_HOST para correr los e2e")
    if not Path(playwright.chromium.executable_path).is_file():
        pytest.skip("sin Chromium: ejecutá playwright install chromium")

    try:
        administracion = conectar(parametros_desde_entorno() | {"database": None, "connection_timeout": 5})
    except (InterfaceError, OperationalError):
        pytest.skip("sin MySQL: no se pudo conectar al servidor")

    with administracion, administracion.cursor() as cursor:
        nombre = f"gimnasio_e2e_{uuid.uuid4().hex}"
        cursor.execute(f"CREATE DATABASE `{nombre}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        try:
            parametros = parametros_desde_entorno(base=nombre)
            aplicar(parametros, salida=lambda _: None)
            app = crear_app(
                {"ENTORNO": "prueba", "SECRET_KEY": "solo-e2e", "MODO_DEMO": 1, "BD": parametros},
                RelojFijo(datetime(2026, 10, 27, 12, 0, tzinfo=UTC)),
            )
            with app.app_context():
                reiniciar()

            with make_server("127.0.0.1", 0, app) as servidor:
                hilo = Thread(target=servidor.serve_forever, daemon=True)
                hilo.start()
                try:
                    yield SimpleNamespace(url=f"http://127.0.0.1:{servidor.server_port}", app=app)
                finally:
                    servidor.shutdown()
                    hilo.join()
        finally:
            cursor.execute(f"DROP DATABASE IF EXISTS `{nombre}`")


@pytest.fixture(scope="session")
def url_base(playwright):
    with servidor_demo(playwright) as instancia:
        yield instancia.url


@pytest.fixture
def demo_aislada(playwright):
    """Cada caso del recorrido recibe migraciones, semilla y hechos independientes."""
    with servidor_demo(playwright) as instancia:
        yield instancia


@pytest.fixture
def pagina_demo(demo_aislada, playwright):
    with playwright.chromium.launch(channel="chromium") as navegador, navegador.new_context(locale="es-PY") as contexto:
        yield contexto.new_page()


@pytest.fixture(scope="session")
def navegador(url_base, playwright):
    # El canal chromium usa el mismo ejecutable cuya instalación comprueba url_base.
    with playwright.chromium.launch(channel="chromium") as navegador:
        yield navegador


@pytest.fixture
def pagina(navegador):
    with navegador.new_context(locale="es-PY") as contexto:
        yield contexto.new_page()
