"""Declaración, revisión y restricciones por inserción con consentimiento y asignación."""

from datetime import timedelta
from uuid import uuid4

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import nuevo_id
from gimnasio.salud import repositorio
from pruebas.test_entrenamiento_api import entrenamiento_api as entrenamiento_api
from pruebas.test_salud import guardar

pytestmark = pytest.mark.bd


def escribir(cliente, ruta, datos, clave=None):
    return cliente.post(ruta, json=datos, headers={"X-Gimnasio": "1", "Idempotency-Key": clave or str(uuid4())})


@pytest.fixture
def salud(entrenamiento_api):
    datos = entrenamiento_api
    datos.socio = str(datos.usuarios["socio"])
    datos.ruta = f"/api/socios/{datos.socio}/salud"
    assert guardar(datos.cliente()).status_code == 200
    return datos


def declarar(datos, **extras):
    respuesta = escribir(datos.cliente(), "/api/yo/salud/condiciones", {"descripcion": "Condición ficticia", **extras})
    assert respuesta.status_code == 201, respuesta.json
    return respuesta.json["condicion"]["id"]


def motivos(datos, entrenador="entrenador"):
    grupos = datos.cliente(entrenador).get("/api/entrenador/bandeja").json["grupos"]
    return [m for s in grupos[0]["socios"] for m in s["motivos"] if m["tipo"] == "condicion_sin_revisar"]


def test_declarar_revisar_reemplazar_y_reintentar(salud):
    datos = salud
    cliente = datos.cliente()
    entrenador = datos.cliente("entrenador")
    with datos.app.app_context():
        identificador = str(nuevo_id())
    cuerpo = {"id": identificador, "descripcion": "Condición ficticia"}
    clave = str(uuid4())
    primera = escribir(cliente, "/api/yo/salud/condiciones", cuerpo, clave)
    assert primera.status_code == 201
    assert escribir(cliente, "/api/yo/salud/condiciones", cuerpo, clave).json == primera.json
    assert escribir(cliente, "/api/yo/salud/condiciones", cuerpo).json == primera.json
    assert len(cliente.get("/api/yo/salud/condiciones").json["condiciones"]) == 1
    vista = entrenador.get(f"/api/entrenador/socios/{datos.socio}").json
    assert vista["salud"]["condiciones"][0]["id"] == identificador
    assert len(motivos(datos)) == 1
    assert motivos(datos, "otro") == []
    assert datos.cliente("otro").get(datos.ruta).status_code == 403
    revision = datos.ruta + f"/condiciones/{identificador}/revisar"
    for _ in range(2):
        assert escribir(entrenador, revision, {"nota": "Revisión ficticia"}).status_code == 200
    assert motivos(datos) == []
    reemplazo = declarar(datos, reemplaza_a=identificador)
    condiciones = cliente.get("/api/yo/salud").json["condiciones"]
    assert [c["id"] for c in condiciones] == [reemplazo]
    assert condiciones[0]["revision_id"] is None
    assert len(motivos(datos)) == 1
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT COUNT(*) AS total FROM condiciones_salud")
        assert cursor.fetchone()["total"] == 2
        cursor.execute("SELECT COUNT(*) AS total FROM revisiones_condicion")
        assert cursor.fetchone()["total"] == 1


def test_condicion_pasa_al_nuevo_entrenador_y_conserva_antiguedad_al_consentir(salud):
    datos = salud
    declarar(datos)
    original = motivos(datos)[0]
    datos.reloj.avanzar(timedelta(days=2))
    assert guardar(datos.cliente(), False).status_code == 200
    assert motivos(datos) == []
    assert guardar(datos.cliente(), True).status_code == 200
    assert motivos(datos) == [original]
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute(
            "UPDATE asignaciones_entrenador SET hasta=%s WHERE id=%s", (datos.reloj.ahora(), datos.asignacion.bytes)
        )
        cursor.execute(
            "INSERT INTO asignaciones_entrenador (id,socio_id,entrenador_id,desde) VALUES (%s,%s,%s,%s)",
            (nuevo_id().bytes, datos.usuarios["socio"].bytes, datos.usuarios["otro"].bytes, datos.reloj.ahora()),
        )
    assert motivos(datos) == []
    assert motivos(datos, "otro") == [original]
    assert datos.cliente("entrenador").get(datos.ruta).status_code == 403
    assert datos.cliente("otro").get(datos.ruta).status_code == 200


def test_restriccion_revisa_en_la_misma_transaccion_y_levantar_no_duplica(salud, monkeypatch):
    datos = salud
    cid = declarar(datos)
    entrenador = datos.cliente("entrenador")
    with datos.app.app_context():
        identificador = str(nuevo_id())
    cuerpo = {"id": identificador, "zona": "rodillas", "descripcion": "Restricción ficticia", "condicion_id": cid}
    insertar = repositorio.insertar_revision

    def fallar(*args):
        raise RuntimeError("Fallo ficticio")

    monkeypatch.setattr(repositorio, "insertar_revision", fallar)
    with pytest.raises(RuntimeError):
        escribir(entrenador, datos.ruta + "/restricciones", cuerpo)
    assert entrenador.get(datos.ruta).json["restricciones"] == []
    monkeypatch.setattr(repositorio, "insertar_revision", insertar)
    clave = str(uuid4())
    primera = escribir(entrenador, datos.ruta + "/restricciones", cuerpo, clave)
    assert primera.status_code == 201
    assert escribir(entrenador, datos.ruta + "/restricciones", cuerpo, clave).json == primera.json
    assert escribir(entrenador, datos.ruta + "/restricciones", cuerpo).json == primera.json
    assert motivos(datos) == []
    rid = primera.json["restriccion_id"]
    assert entrenador.get(datos.ruta).json["restricciones"][0]["autor_id"] == str(datos.usuarios["entrenador"])
    for _ in range(2):
        assert escribir(entrenador, datos.ruta + f"/restricciones/{rid}/levantar", {}).status_code == 200
    assert entrenador.get(datos.ruta).json["restricciones"] == []
    assert (
        entrenador.post(
            datos.ruta + f"/restricciones/{rid}/levantar",
            headers={"X-Gimnasio": "1", "Idempotency-Key": str(uuid4())},
        ).status_code
        == 200
    )
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT COUNT(*) AS total FROM restricciones_salud")
        assert cursor.fetchone()["total"] == 2


def test_todas_las_operaciones_exigen_consentimiento_asignacion_y_rol(salud):
    datos = salud
    cid = declarar(datos)
    entrenador = datos.cliente("entrenador")
    rid = escribir(entrenador, datos.ruta + "/restricciones", {"zona": "rodillas", "descripcion": "Ficticia"}).json[
        "restriccion_id"
    ]
    operaciones = [
        ("GET", datos.ruta, None),
        ("POST", datos.ruta + "/restricciones", {"zona": "rodillas", "descripcion": "Ficticia"}),
        ("POST", datos.ruta + f"/restricciones/{rid}/levantar", {}),
        ("POST", datos.ruta + f"/condiciones/{cid}/revisar", {}),
    ]
    for rol in ("recepcion", "administracion", "socio", "otro"):
        cliente = datos.cliente(rol)
        for metodo, ruta, cuerpo in operaciones:
            respuesta = cliente.get(ruta) if metodo == "GET" else escribir(cliente, ruta, cuerpo)
            assert respuesta.status_code == 403
    assert guardar(datos.cliente(), False).status_code == 200
    for metodo, ruta, cuerpo in operaciones:
        respuesta = entrenador.get(ruta) if metodo == "GET" else escribir(entrenador, ruta, cuerpo)
        assert respuesta.status_code == 403
        assert respuesta.json["error"]["codigo"] == "sin_consentimiento"
    for ruta in ("/api/yo/salud", "/api/yo/salud/condiciones"):
        assert datos.cliente().get(ruta).status_code == 403
    assert escribir(datos.cliente(), "/api/yo/salud/condiciones", {"descripcion": "Ficticia"}).status_code == 403
    for rol in ("recepcion", "administracion", "entrenador"):
        cliente = datos.cliente(rol)
        assert cliente.get("/api/yo/salud").status_code == 403
        assert cliente.get("/api/yo/salud/condiciones").status_code == 403
        assert escribir(cliente, "/api/yo/salud/condiciones", {"descripcion": "Ficticia"}).status_code == 403


def test_validacion_de_textos_objetivos_y_condicion_ajena(salud):
    datos = salud
    for descripcion in (None, "", " ", "x" * 1001, 42):
        assert escribir(datos.cliente(), "/api/yo/salud/condiciones", {"descripcion": descripcion}).status_code == 422
    cid = declarar(datos, descripcion="x" * 1000)
    assert guardar(datos.cliente("ajeno")).status_code == 200
    assert (
        escribir(
            datos.cliente("ajeno"), "/api/yo/salud/condiciones", {"descripcion": "Ficticia", "reemplaza_a": cid}
        ).status_code
        == 422
    )
    entrenador = datos.cliente("entrenador")
    for objetivo in (
        {},
        {"zona": "rodillas", "patron_movimiento": "sentadilla"},
        {"zona": "pie"},
        {"ejercicio_id": "otro"},
        {"patron_movimiento": "inexistente"},
        {"zona": ["rodillas"]},
    ):
        assert (
            escribir(entrenador, datos.ruta + "/restricciones", {"descripcion": "Ficticia", **objetivo}).status_code
            == 422
        )
    assert escribir(entrenador, datos.ruta + f"/condiciones/{cid}/revisar", {"nota": "x" * 1001}).status_code == 422
