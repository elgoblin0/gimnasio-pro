import pytest

from gimnasio import crear_app
from gimnasio.comun.errores import ErrorDeDominio


def app_de_prueba(**config):
    return crear_app({"ENTORNO": "prueba", "SECRET_KEY": "solo-pruebas", "MODO_DEMO": False} | config)


def test_desarrollo_genera_una_clave_secreta_si_falta():
    app = crear_app({"ENTORNO": "desarrollo", "SECRET_KEY": None})
    assert len(app.config["SECRET_KEY"]) == 64
    assert app.config["SESSION_COOKIE_SECURE"] is False


def test_produccion_exige_clave_secreta():
    with pytest.raises(RuntimeError):
        crear_app({"ENTORNO": "produccion", "SECRET_KEY": None})


def test_produccion_usa_cookies_seguras():
    app = crear_app({"ENTORNO": "produccion", "SECRET_KEY": "x" * 64})
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"


def test_rechaza_un_entorno_desconocido():
    with pytest.raises(ValueError):
        crear_app({"ENTORNO": "staging"})


def test_lee_la_configuracion_del_entorno(monkeypatch):
    monkeypatch.setenv("GIMNASIO_ENTORNO", "prueba")
    monkeypatch.setenv("MODO_DEMO", "1")
    app = crear_app()
    assert app.config["TESTING"] is True
    assert app.config["MODO_DEMO"] is True


def test_el_reloj_inyectado_queda_disponible():
    reloj = object()
    assert crear_app({"ENTORNO": "prueba"}, reloj=reloj).extensions["reloj"] is reloj


@pytest.mark.parametrize("modo_demo", [True, False])
def test_estado_del_servicio(modo_demo):
    respuesta = app_de_prueba(MODO_DEMO=modo_demo).test_client().get("/api/estado")
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"estado": "ok", "version_reglas": None, "modo_demo": modo_demo}


def test_sirve_la_pagina_de_inicio():
    respuesta = app_de_prueba().test_client().get("/")
    assert respuesta.status_code == 200
    assert b'type="importmap"' in respuesta.data
    assert b'<html lang="es" data-direccion="b">' in respuesta.data


def test_la_api_responde_errores_en_json():
    respuesta = app_de_prueba().test_client().get("/api/no-existe")
    assert respuesta.status_code == 404
    assert respuesta.get_json()["error"]["codigo"] == "not_found"


def test_un_error_de_dominio_se_traduce_a_json():
    app = app_de_prueba()

    @app.get("/api/falla")
    def falla():
        raise ErrorDeDominio("aforo_completo", "No hay lugar", 409)

    respuesta = app.test_client().get("/api/falla")
    assert respuesta.status_code == 409
    assert respuesta.get_json() == {"error": {"codigo": "aforo_completo", "mensaje": "No hay lugar"}}
