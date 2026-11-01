"""Alta atómica, clave de una sola entrega y acceso del socio nuevo."""

import json
from base64 import b64decode
from uuid import UUID, uuid4

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import desde_bytes, nuevo_id
from gimnasio.demo.servicio import reiniciar
from pruebas.test_pagos import escribir, filas
from pruebas.test_pagos import pagos as pagos

pytestmark = pytest.mark.bd


def alta(cliente, *, clave=None, **cambios):
    datos = {"nombre": "Nueva", "apellido": "Ficticia", "cedula": "8899001", "consentimiento_datos": True}
    return escribir(cliente, "/api/socios", datos | cambios, clave=clave)


def test_clave_una_vez_y_respuesta_guardada_saneada(pagos, caplog):
    app, cliente, autor, _ = pagos
    app.config["MODO_DEMO"] = False
    clave = str(uuid4())
    primera = alta(cliente, clave=clave)
    assert primera.status_code == 201, primera.json
    provisional = primera.json["clave_provisional"]
    assert not primera.json["clave_ya_entregada"]
    repetida = alta(cliente, clave=clave)
    assert repetida.status_code == 201
    assert repetida.json == {"usuario_id": primera.json["usuario_id"], "clave_ya_entregada": True}
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT respuesta FROM solicitudes_idempotentes WHERE clave=%s", (UUID(clave).bytes,))
        guardada = json.loads(cursor.fetchone()["respuesta"])
        assert provisional.encode() not in b64decode(guardada["cuerpo"])
        cursor.execute("SELECT COUNT(*) AS cantidad FROM personas WHERE cedula='8899001'")
        assert cursor.fetchone()["cantidad"] == 1
        cursor.execute(
            "SELECT clave_hash, debe_cambiar_clave FROM usuarios WHERE id=%s", (UUID(primera.json["usuario_id"]).bytes,)
        )
        usuario = cursor.fetchone()
        assert usuario["clave_hash"] != provisional
        assert usuario["debe_cambiar_clave"]
        cursor.execute(
            "SELECT registrado_por FROM consentimientos WHERE socio_id=%s", (UUID(primera.json["usuario_id"]).bytes,)
        )
        assert cursor.fetchone()["registrado_por"] == UUID(autor["id"]).bytes
    assert provisional not in caplog.text
    socio = app.test_client()
    assert escribir(socio, "/api/sesion", {"identificador": "8899001", "clave": provisional}).status_code == 200
    assert socio.get("/api/yo/ficha").json["error"]["codigo"] == "debe_cambiar_clave"
    assert socio.get("/api/sesion").status_code == 403
    assert (
        escribir(socio, "/api/sesion/clave", {"clave_actual": provisional, "clave_nueva": "corta"}).status_code == 422
    )
    assert (
        escribir(
            socio, "/api/sesion/clave", {"clave_actual": "incorrecta", "clave_nueva": "clave-definitiva"}
        ).status_code
        == 403
    )
    repetida = escribir(socio, "/api/sesion/clave", {"clave_actual": provisional, "clave_nueva": provisional})
    assert repetida.status_code == 422
    assert repetida.json["error"]["codigo"] == "clave_repetida"
    assert socio.get("/api/yo/ficha").json["error"]["codigo"] == "debe_cambiar_clave"
    assert (
        escribir(
            socio, "/api/sesion/clave", {"clave_actual": provisional, "clave_nueva": "clave-definitiva"}
        ).status_code
        == 200
    )
    assert socio.get("/api/yo/ficha").status_code == 200
    escribir(socio, "/api/sesion", metodo="delete")
    assert escribir(socio, "/api/sesion", {"identificador": "8899001", "clave": "clave-definitiva"}).status_code == 200


@pytest.mark.parametrize("con_pago", [False, True])
def test_entrada_y_tarjeta_del_socio_nuevo(pagos, con_pago):
    app, cliente, _, datos_pago = pagos
    assert escribir(cliente, "/api/sesion/demo/recepcion").status_code == 200
    cambios = {"primer_pago": {k: v for k, v in datos_pago.items() if k != "socio_id"}} if con_pago else {}
    respuesta = alta(cliente, **cambios)
    assert respuesta.status_code == 201, respuesta.json
    assert "clave_provisional" not in respuesta.json
    socio = respuesta.json["usuario_id"]
    with app.app_context(), transaccion() as cursor:
        cursor.execute(
            "SELECT clave_hash, debe_cambiar_clave, creado_en FROM usuarios WHERE id=%s", (UUID(socio).bytes,)
        )
        usuario = cursor.fetchone()
        assert usuario["clave_hash"] is None
        assert not usuario["debe_cambiar_clave"]
        assert usuario["creado_en"] == app.extensions["reloj"].ahora().replace(tzinfo=None)
    assert escribir(cliente, "/api/sesion/demo/recepcion").status_code == 200
    tarjeta = cliente.get(f"/api/socios/{socio}/tarjeta")
    assert tarjeta.status_code == 200, tarjeta.json
    assert tarjeta.json["membresia"]["vigente"] is con_pago
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT id FROM sedes LIMIT 1")
        sede = str(desde_bytes(cursor.fetchone()["id"]))
        entrada_id = str(nuevo_id())
    entrada = escribir(cliente, "/api/entradas", {"id": entrada_id, "socio_id": socio, "sede_id": sede})
    assert entrada.status_code == (201 if con_pago else 422), entrada.json
    assert escribir(cliente, "/api/sesion/demo/socio", {"usuario_id": socio}).status_code == 200
    assert cliente.get("/api/yo/ficha").status_code == 200
    assert cliente.get("/api/yo/avisos").status_code == 200
    propuesta = cliente.get("/api/entrenamiento/propuesta")
    assert propuesta.status_code == 200, propuesta.json


@pytest.mark.parametrize("campo", ["cedula", "correo"])
@pytest.mark.parametrize("activo", [False, True])
def test_repetidos_incluso_desactivados_no_crean_persona(pagos, campo, activo):
    app, cliente, _, _ = pagos
    primera = alta(cliente, correo="alta@ejemplo.test")
    with app.app_context(), transaccion() as cursor:
        cursor.execute("UPDATE usuarios SET activo=%s WHERE id=%s", (activo, UUID(primera.json["usuario_id"]).bytes))
    antes = len(filas(app, "personas"))
    cambios = {"cedula": "8899002"} if campo == "correo" else {}
    assert alta(cliente, correo="alta@ejemplo.test" if campo == "correo" else None, **cambios).status_code == 409
    assert len(filas(app, "personas")) == antes


def test_pago_fallido_revierte_todo(pagos):
    app, cliente, _, _ = pagos
    antes = {tabla: len(filas(app, tabla)) for tabla in ("personas", "usuarios", "consentimientos", "pagos")}
    with app.app_context():
        tipo_id = str(nuevo_id())
    assert alta(cliente, primer_pago={"tipo_id": tipo_id, "medio": "efectivo"}).status_code == 404
    assert {tabla: len(filas(app, tabla)) for tabla in antes} == antes


@pytest.mark.parametrize("valor", [None, False, "true", 1])
def test_consentimiento_expreso_obligatorio(pagos, valor):
    _, cliente, _, _ = pagos
    assert alta(cliente, consentimiento_datos=valor).status_code == 422


def test_demo_tope_reintento_y_reinicio(pagos):
    app, cliente, _, _ = pagos
    clave = str(uuid4())
    primera = alta(cliente, clave=clave)
    assert alta(cliente, clave=clave).json == primera.json
    for numero in range(1, 20):
        assert alta(cliente, cedula=str(8899001 + numero)).status_code == 201
    assert alta(cliente, cedula="8899999").status_code == 429
    with app.app_context():
        reiniciar()
    assert escribir(cliente, "/api/sesion/demo/administracion").status_code == 200
    assert all(str(desde_bytes(fila["id"])) != primera.json["usuario_id"] for fila in filas(app, "usuarios"))
    assert alta(cliente).status_code == 201


@pytest.mark.parametrize("rol", ["socio", "entrenador"])
def test_roles_no_autorizados(pagos, rol):
    _, cliente, _, _ = pagos
    assert escribir(cliente, f"/api/sesion/demo/{rol}").status_code == 200
    assert alta(cliente).status_code == 403
