"""Reutilización de conexiones entre solicitudes (ADR 0033), sobre MySQL real."""

import re
import uuid
from pathlib import Path

import pytest

from gimnasio import HILOS_EN_PRODUCCION, crear_app
from gimnasio.comun.bd import conectar, conexion_actual, parametros_desde_entorno


@pytest.fixture
def app(bd_limpia, reloj_fijo):
    """Una sola conexión reutilizable: si se reutiliza, las dos solicitudes ven el mismo CONNECTION_ID."""
    parametros = bd_limpia | {"pool_name": uuid.uuid4().hex, "pool_size": 1}
    return crear_app(
        {"ENTORNO": "prueba", "SECRET_KEY": "solo-pruebas", "MODO_DEMO": False, "BD": parametros}, reloj_fijo
    )


def un_valor(sql):
    with conexion_actual().cursor() as cursor:
        cursor.execute(sql)
        return cursor.fetchone()[0]


def test_produccion_reutiliza_una_conexion_por_hilo_de_gunicorn(monkeypatch):
    monkeypatch.setenv("GIMNASIO_BD_NOMBRE", "base_de_produccion")
    parametros = crear_app({"ENTORNO": "produccion", "SECRET_KEY": "x"}).config["BD"]
    assert parametros["pool_size"] == HILOS_EN_PRODUCCION
    assert parametros["database"] == "base_de_produccion"
    render = (Path(__file__).parent.parent / "render.yaml").read_text(encoding="utf-8")
    assert int(re.search(r"--threads (\d+)", render).group(1)) == HILOS_EN_PRODUCCION


def test_fuera_de_produccion_cada_solicitud_abre_la_suya():
    assert crear_app({"ENTORNO": "desarrollo", "SECRET_KEY": "x"}).config.get("BD") is None
    assert "pool_name" not in parametros_desde_entorno()


@pytest.mark.bd
def test_solicitudes_seguidas_usan_la_misma_conexion_y_siguen_en_utc(app):
    with app.app_context():
        primera = un_valor("SELECT CONNECTION_ID()")
        un_valor("SELECT 1")
        conexion_actual().cursor().execute("SET time_zone = '+03:00'")
    with app.app_context():
        assert un_valor("SELECT CONNECTION_ID()") == primera
        assert un_valor("SELECT @@session.time_zone") == "+00:00"


@pytest.mark.bd
def test_la_solicitud_siguiente_ve_lo_que_otro_confirmo_y_no_hereda_lo_sin_confirmar(app, bd_limpia):
    with app.app_context():
        # Una lectura abre una lectura consistente: no debe pasar a la solicitud siguiente.
        assert un_valor("SELECT COUNT(*) FROM simulacion_demo") == 0
    afuera = conectar(bd_limpia)
    with afuera.cursor() as cursor:
        cursor.execute("INSERT INTO simulacion_demo (generada_hasta) VALUES (UTC_TIMESTAMP())")
    afuera.commit()
    afuera.close()
    with app.app_context():
        assert un_valor("SELECT COUNT(*) FROM simulacion_demo") == 1
        conexion_actual().cursor().execute("DELETE FROM simulacion_demo")
    with app.app_context():
        assert un_valor("SELECT COUNT(*) FROM simulacion_demo") == 1


@pytest.mark.bd
def test_un_candado_olvidado_no_pasa_a_la_solicitud_siguiente(app):
    with app.app_context():
        assert un_valor("SELECT GET_LOCK('prueba_conexiones_reutilizables', 0)") == 1
    with app.app_context():
        assert un_valor("SELECT RELEASE_ALL_LOCKS()") == 0


@pytest.mark.bd
def test_una_conexion_cortada_se_reemplaza(app, bd_limpia):
    with app.app_context():
        cortada = un_valor("SELECT CONNECTION_ID()")
    administracion = conectar(bd_limpia)
    with administracion.cursor() as cursor:
        cursor.execute(f"KILL {cortada}")
    administracion.close()
    with app.app_context():
        assert un_valor("SELECT CONNECTION_ID()") != cortada
