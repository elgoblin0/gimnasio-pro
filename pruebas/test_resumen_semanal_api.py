"""Resumen semanal del socio y de su entrenador sobre la semilla, con permisos y el filtro de salud."""

import json

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import a_bytes, desde_bytes, desde_texto
from gimnasio.demo.servicio import reiniciar
from gimnasio.permisos.servicio import registrar_consentimiento

pytestmark = pytest.mark.bd

CABECERA = {"X-Gimnasio": "1"}
# El reloj de prueba está en el martes 27/10/2026: la última semana cerrada empieza el lunes 19.
CERRADA = "2026-10-19"


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
    lucia = next(str(desde_bytes(f["id"])) for f in filas if f["nombre"] == "Lucía" and f["es_demo"])
    return app_con_bd, lucia


def entrar(app, ruta, cuerpo=None):
    cliente = app.test_client()
    respuesta = cliente.post(ruta, json=cuerpo, headers=CABECERA)
    assert respuesta.status_code == 200, respuesta.get_json()
    return cliente


def como_lucia(app, lucia):
    return entrar(app, "/api/sesion/demo/socio", {"usuario_id": lucia})


def como_marcos(app):
    return entrar(app, "/api/sesion/demo/entrenador")


def test_por_omision_la_ultima_semana_cerrada_con_actividad_cambios_y_pendientes(semilla):
    app, lucia = semilla
    respuesta = como_lucia(app, lucia).get("/api/yo/resumen-semanal", headers=CABECERA)
    assert respuesta.status_code == 200, respuesta.get_json()
    resumen = respuesta.get_json()
    assert resumen["semana"] == {
        "lunes": CERRADA,
        "domingo": "2026-10-25",
        "anterior": "2026-10-12",
        "siguiente": None,
    }
    assert resumen["sin_actividad"] is False
    cumplido = resumen["cumplido"]
    assert (cumplido["sesiones_realizadas"], cumplido["series"]) == (1, 4)
    assert cumplido["volumen"]["repeticiones"] == 2 * 12 + 2 * 10
    assert cumplido["sesiones_planificadas"] > cumplido["sesiones_realizadas"]
    assert [r["regla"] for r in resumen["cambios"]["ajustes"]] == ["mantener_carga", "mantener_carga"]
    assert "buscás 12 repeticiones" in resumen["cambios"]["ajustes"][0]["datos"]["explicacion"]
    assert resumen["pendientes"]["sesiones_sin_realizar"] == (
        cumplido["sesiones_planificadas"] - cumplido["sesiones_realizadas"]
    )


def test_semana_elegida_y_semana_sin_actividad(semilla):
    app, lucia = semilla
    cliente = como_lucia(app, lucia)
    anterior = cliente.get("/api/yo/resumen-semanal?semana=2026-10-12", headers=CABECERA).get_json()
    assert anterior["semana"]["siguiente"] == CERRADA
    assert anterior["cumplido"]["volumen"]["repeticiones"] == 2 * 11 + 2 * 9
    assert anterior["cambios"] == {"ajustes": [], "frenos": []}
    vacia = cliente.get("/api/yo/resumen-semanal?semana=2026-09-28", headers=CABECERA).get_json()
    assert vacia["sin_actividad"] is True
    assert vacia["semana"]["anterior"] is None
    assert vacia["cumplido"]["series"] == 0


@pytest.mark.parametrize(
    ("semana", "codigo"),
    [("2026-10-20", "semana_invalida"), ("19/10/2026", "semana_invalida"), ("2026-10-26", "semana_abierta")],
)
def test_semana_que_no_es_un_lunes_cerrado(semilla, semana, codigo):
    app, lucia = semilla
    respuesta = como_lucia(app, lucia).get(f"/api/yo/resumen-semanal?semana={semana}", headers=CABECERA)
    assert respuesta.status_code == 422
    assert respuesta.get_json()["error"]["codigo"] == codigo


def test_el_entrenador_ve_el_mismo_resumen_del_socio_asignado(semilla):
    app, lucia = semilla
    propio = como_lucia(app, lucia).get("/api/yo/resumen-semanal", headers=CABECERA).get_json()
    ruta = f"/api/entrenador/socios/{lucia}/resumen-semanal"
    assert como_marcos(app).get(ruta, headers=CABECERA).get_json() == propio


def test_entrenador_sin_asignacion_recibe_403(semilla):
    app, lucia = semilla
    with app.app_context(), transaccion() as cursor:
        cursor.execute(
            "UPDATE asignaciones_entrenador SET hasta = desde WHERE socio_id = %s", (a_bytes(desde_texto(lucia)),)
        )
    respuesta = como_marcos(app).get(f"/api/entrenador/socios/{lucia}/resumen-semanal", headers=CABECERA)
    assert respuesta.status_code == 403
    assert respuesta.get_json()["error"]["codigo"] == "sin_asignacion"


def test_el_socio_no_lee_el_resumen_de_otro_por_la_ruta_del_entrenador(semilla):
    app, lucia = semilla
    ruta = f"/api/entrenador/socios/{lucia}/resumen-semanal"
    assert como_lucia(app, lucia).get(ruta, headers=CABECERA).status_code == 403


def test_sin_consentimiento_el_entrenador_no_ve_datos_de_salud(semilla):
    app, lucia = semilla
    freno = {
        "regla": "restriccion_salud",
        "version": "3.4.0",
        "datos": {"ejercicio_id": "ep", "zonas": "zona_lumbar", "explicacion": "Sin carga axial en zona lumbar."},
    }
    with app.app_context(), transaccion() as cursor:
        cursor.execute(
            """UPDATE prescripciones_efectivas p JOIN sesiones_realizadas s ON s.id = p.sesion_realizada_id
               SET p.explicacion = JSON_ARRAY_APPEND(p.explicacion, '$', CAST(%s AS JSON)) WHERE s.socio_id = %s""",
            (json.dumps(freno), a_bytes(desde_texto(lucia))),
        )
        registrar_consentimiento(cursor, desde_texto(lucia), "salud", False, "demo-1", desde_texto(lucia))
    ruta = f"/api/entrenador/socios/{lucia}/resumen-semanal"
    frenos = como_marcos(app).get(ruta, headers=CABECERA).get_json()["cambios"]["frenos"]
    assert frenos == [{"regla": "restriccion_salud", "version": "3.4.0", "datos": {"ejercicio_id": "ep"}}]
    # El socio sigue viendo sus propios datos completos.
    propios = como_lucia(app, lucia).get("/api/yo/resumen-semanal", headers=CABECERA).get_json()["cambios"]["frenos"]
    assert propios == [freno]
