"""Servidor demo y navegador para los recorridos de punta a punta."""

import json
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
from gimnasio.comun.bd import conectar, parametros_desde_entorno, transaccion
from gimnasio.comun.ids import a_bytes, desde_bytes, nuevo_id
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


@pytest.fixture
def programa_demo(demo_aislada):
    """Programa ficticio explícito para probar pantallas antes de extender la semilla de etapa 1."""
    with demo_aislada.app.app_context(), transaccion() as cursor:
        reloj = demo_aislada.app.extensions["reloj"]
        cursor.execute("SELECT id FROM usuarios WHERE rol='socio' AND es_demo=TRUE ORDER BY id LIMIT 1")
        socio = desde_bytes(cursor.fetchone()["id"])
        cursor.execute(
            "SELECT COALESCE(MAX(version),0)+1 AS version FROM programas_entrenamiento WHERE socio_id=%s",
            (a_bytes(socio),),
        )
        version = cursor.fetchone()["version"]
        programa, sesion = nuevo_id(reloj), nuevo_id(reloj)

        def insertar(tabla, **valores):
            columnas = ", ".join(valores)
            parametros = ", ".join("%s" for _ in valores)
            cursor.execute(f"INSERT INTO {tabla} ({columnas}) VALUES ({parametros})", tuple(valores.values()))

        insertar(
            "programas_entrenamiento",
            id=a_bytes(programa),
            socio_id=a_bytes(socio),
            version=version,
            creado_en=reloj.ahora(),
        )
        insertar(
            "sesiones_planificadas",
            id=a_bytes(sesion),
            programa_id=a_bytes(programa),
            posicion=1,
            nombre="Fuerza y cardio",
        )
        ejercicios = []
        for posicion, nombre, medidas, series in (
            (1, "Sentadilla ficticia", ["repeticiones", "carga"], 2),
            (2, "Caminata ficticia", ["duracion", "distancia"], 1),
        ):
            ejercicio, planificado = nuevo_id(reloj), nuevo_id(reloj)
            insertar(
                "ejercicios",
                id=a_bytes(ejercicio),
                nombre=nombre,
                medidas_aplicables=json.dumps(medidas),
                actualizada_en=reloj.ahora(),
            )
            insertar(
                "ejercicios_planificados",
                id=a_bytes(planificado),
                sesion_planificada_id=a_bytes(sesion),
                ejercicio_id=a_bytes(ejercicio),
                posicion=posicion,
                series=series,
                repeticiones_minimas=8 if posicion == 1 else None,
                repeticiones_maximas=12 if posicion == 1 else None,
                carga="20.50" if posicion == 1 else None,
                descanso=90 if posicion == 1 else None,
                duracion=120 if posicion == 2 else None,
                distancia="1500.25" if posicion == 2 else None,
            )
            ejercicios.append(planificado)
    return SimpleNamespace(socio=socio, programa=programa, planificada=sesion, ejercicios=ejercicios)


@pytest.fixture(scope="session")
def navegador(url_base, playwright):
    # El canal chromium usa el mismo ejecutable cuya instalación comprueba url_base.
    with playwright.chromium.launch(channel="chromium") as navegador:
        yield navegador


@pytest.fixture
def pagina(navegador):
    with navegador.new_context(locale="es-PY") as contexto:
        yield contexto.new_page()
