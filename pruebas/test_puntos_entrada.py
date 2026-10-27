"""Los arranques documentados usan la aplicación modular sin SQL heredado."""

import importlib
import runpy
from pathlib import Path

import pytest
from flask import Flask


@pytest.mark.parametrize("modulo", ["app", "wsgi"])
def test_importacion_sirve_inicio_b_y_api_modular_sin_conectar(monkeypatch, modulo):
    def conectar_prohibido(*args, **kwargs):
        pytest.fail("Importar o servir estáticos no debe abrir la base de datos")

    monkeypatch.setenv("GIMNASIO_ENTORNO", "prueba")
    monkeypatch.setenv("MODO_DEMO", "0")
    monkeypatch.setattr("mysql.connector.connect", conectar_prohibido)
    aplicacion = importlib.reload(importlib.import_module(modulo)).app
    assert Path(aplicacion.static_folder).resolve() == Path("gimnasio/static").resolve()
    cliente = aplicacion.test_client()
    inicio = cliente.get("/")
    assert inicio.status_code == 200
    assert b'data-direccion="b"' in inicio.data
    assert cliente.get("/api/estado").get_json()["estado"] == "ok"
    assert cliente.get("/api/sesion").get_json() == {"usuario": None}
    rutas = {regla.rule for regla in aplicacion.url_map.iter_rules()}
    assert {"/api/entradas", "/api/salidas", "/api/entrenamiento/propuesta"} <= rutas
    assert "/api/socios/<int:socio_id>/checkin" not in rutas


def test_python_app_arranca_la_misma_aplicacion_modular(monkeypatch):
    monkeypatch.setenv("GIMNASIO_ENTORNO", "prueba")
    monkeypatch.setenv("MODO_DEMO", "0")
    ejecuciones = []
    monkeypatch.setattr(Flask, "run", lambda self, **opciones: ejecuciones.append((self, opciones)))
    runpy.run_path("app.py", run_name="__main__")
    assert len(ejecuciones) == 1
    aplicacion, opciones = ejecuciones[0]
    assert opciones == {"port": 5002}
    assert "entrenamiento" in aplicacion.blueprints
    assert aplicacion.test_client().get("/api/estado").status_code == 200
