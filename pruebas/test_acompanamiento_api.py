"""Incorporación y riesgo de abandono en la semilla, por API y sin datos de salud."""

import json

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import desde_bytes
from gimnasio.demo.servicio import CASOS_ACOMPANAMIENTO, DIAS_DE_ALTA_LUCIA, reiniciar
from gimnasio.entrenador.servicio import consultar_bandeja, consultar_socio
from gimnasio.visitas.servicio import consultar_tarjeta

pytestmark = pytest.mark.bd


@pytest.fixture
def semilla(app_con_bd):
    app_con_bd.config["MODO_DEMO"] = True
    with app_con_bd.app_context():
        reiniciar()
        with transaccion() as cursor:
            cursor.execute(
                "SELECT u.id, p.nombre, u.rol, u.es_demo FROM usuarios u JOIN personas p ON p.id = u.persona_id"
            )
            filas = cursor.fetchall()
        socios = {f["nombre"]: str(desde_bytes(f["id"])) for f in filas if f["rol"] == "socio"}
        marcos = next(str(desde_bytes(f["id"])) for f in filas if f["rol"] == "entrenador" and f["es_demo"])
        yield socios, {"id": marcos, "rol": "entrenador"}


def _reglas(razones):
    return [razon["regla"] for razon in razones]


def test_la_semilla_cubre_cada_estado(semilla):
    socios, marcos = semilla
    esperado = {
        "Nadia": (45, []),
        "Darío": (31, ["ausencia"]),
        "Ramón": (None, ["ausencia"]),
        "Elsa": (None, ["tendencia"]),
        "Tomás": (None, []),
    }
    assert set(esperado) == {caso[0] for caso in CASOS_ACOMPANAMIENTO}
    for nombre, (dia, reglas) in esperado.items():
        tarjeta = consultar_tarjeta(socios[nombre])
        assert (tarjeta["incorporacion"] or {}).get("dia") == dia, nombre
        assert _reglas(tarjeta["riesgo_abandono"]) == reglas, nombre
        vista = consultar_socio(socios[nombre], marcos)
        assert (vista["incorporacion"]["dia"] if vista["incorporacion"] else None) == dia, nombre
        assert _reglas(vista["riesgo_abandono"]) == reglas, nombre


def test_el_riesgo_es_el_ultimo_grupo_de_la_bandeja(semilla):
    socios, marcos = semilla
    grupos = consultar_bandeja(marcos)["grupos"]
    assert grupos[-1]["tipo"] == "riesgo_abandono"
    en_riesgo = {socio["id"] for socio in grupos[-1]["socios"]}
    assert {socios["Darío"], socios["Ramón"], socios["Elsa"]} <= en_riesgo
    assert socios["Nadia"] not in en_riesgo and socios["Tomás"] not in en_riesgo


def test_los_hitos_salen_de_los_hechos(semilla):
    socios, marcos = semilla
    assert consultar_socio(socios["Nadia"], marcos)["incorporacion"]["hitos"] == {
        "programa_asignado": True,
        "primera_visita": True,
        "primera_sesion": False,
    }


def test_lucia_se_dio_de_alta_antes_de_su_historial(semilla):
    """Su resumen semanal muestra sesiones de hace semanas: el alta y las visitas las acompañan."""
    socios, marcos = semilla
    vista = consultar_socio(socios["Lucía"], marcos)
    assert vista["incorporacion"]["hitos"] == {
        "programa_asignado": True,
        "primera_visita": True,
        "primera_sesion": True,
    }
    assert vista["riesgo_abandono"] == []
    assert consultar_tarjeta(socios["Lucía"])["riesgo_abandono"] == []


def test_las_razones_no_llevan_datos_de_salud(semilla):
    socios, _ = semilla
    texto = json.dumps(consultar_tarjeta(socios["Ramón"])["riesgo_abandono"])
    for dato in ("dolor", "restriccion", "condicion", "zona"):
        assert dato not in texto


def test_socio_recibe_incorporacion_sin_riesgo(semilla, app_con_bd):
    socios, _ = semilla
    cliente = app_con_bd.test_client()
    respuesta = cliente.post(
        "/api/sesion/demo/socio", json={"usuario_id": socios["Lucía"]}, headers={"X-Gimnasio": "1"}
    )
    assert respuesta.status_code == 200, respuesta.get_json()
    cuerpo = cliente.get("/api/yo/incorporacion", headers={"X-Gimnasio": "1"}).get_json()
    assert cuerpo["incorporacion"]["dia"] == DIAS_DE_ALTA_LUCIA + 1
    assert "abandono" not in json.dumps(cuerpo)
    assert "riesgo" not in json.dumps(cuerpo)
