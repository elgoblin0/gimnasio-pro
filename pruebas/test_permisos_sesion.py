"""Sesión por rol, "entrar como…", límite de intentos, CSRF y consentimientos, sobre MySQL (ADR 0006)."""

from datetime import timedelta

import pytest
from flask import jsonify

from gimnasio.comun.bd import transaccion
from gimnasio.permisos import servicio

pytestmark = pytest.mark.bd

CABECERA = {"X-Gimnasio": "1"}
CLAVE = "clave-de-prueba"


def crear(app, rol, cedula, clave=CLAVE, es_demo=False, correo=None, nombre="Ana"):
    persona = {"nombre": nombre, "apellido": "Prueba", "cedula": cedula, "correo": correo}
    with app.app_context(), transaccion() as cursor:
        return servicio.crear_usuario(cursor, persona, rol, clave, es_demo)


def entrar(cliente, identificador, clave=CLAVE):
    return cliente.post("/api/sesion", json={"identificador": identificador, "clave": clave}, headers=CABECERA)


def test_inicia_sesion_con_cedula_o_correo_y_la_cierra(app_con_bd):
    crear(app_con_bd, "recepcion", "4567890", correo="Rocio@Demo.Gimnasio.invalid", nombre="Rocío")
    cliente = app_con_bd.test_client()
    assert cliente.get("/api/sesion").status_code == 401

    respuesta = entrar(cliente, "4.567.890")
    assert respuesta.status_code == 200
    assert respuesta.get_json()["usuario"]["rol"] == "recepcion"
    assert cliente.get("/api/sesion").get_json()["usuario"]["nombre"] == "Rocío"

    assert cliente.delete("/api/sesion", headers=CABECERA).status_code == 204
    assert cliente.get("/api/sesion").status_code == 401
    assert entrar(cliente, "rocio@demo.gimnasio.invalid").status_code == 200


def test_clave_incorrecta_y_usuario_inexistente_responden_igual(app_con_bd):
    crear(app_con_bd, "socio", "1234567")
    cliente = app_con_bd.test_client()
    mala = entrar(cliente, "1234567", "otra-clave-cualquiera")
    inexistente = entrar(cliente, "7654321")
    assert mala.status_code == inexistente.status_code == 401
    assert mala.get_json() == inexistente.get_json()


def test_el_sexto_intento_fallido_en_15_minutos_devuelve_429(app_con_bd, reloj_fijo):
    crear(app_con_bd, "socio", "1234567")
    cliente = app_con_bd.test_client()
    for _ in range(5):
        assert entrar(cliente, "1234567", "incorrecta").status_code == 401
        reloj_fijo.avanzar(timedelta(minutes=2))
    bloqueado = entrar(cliente, "1234567")
    assert bloqueado.status_code == 429
    assert bloqueado.get_json()["error"]["codigo"] == "demasiados_intentos"

    # Cuando el primer fallo sale de la ventana de 15 minutos, la clave correcta vuelve a entrar.
    reloj_fijo.avanzar(timedelta(minutes=6))
    assert entrar(cliente, "1234567").status_code == 200


def test_usuarios_demo_e_inactivos_no_entran_con_clave(app_con_bd):
    crear(app_con_bd, "socio", "9900001", clave=None, es_demo=True)
    usuario_id = crear(app_con_bd, "socio", "1234567")
    with app_con_bd.app_context(), transaccion() as cursor:
        cursor.execute("UPDATE usuarios SET activo = FALSE WHERE id = %s", (usuario_id.bytes,))
    cliente = app_con_bd.test_client()
    assert entrar(cliente, "9900001", "").status_code == 401
    assert entrar(cliente, "1234567").status_code == 401


def test_entrar_como_no_existe_fuera_del_modo_demo(app_con_bd):
    crear(app_con_bd, "socio", "9900001", clave=None, es_demo=True)
    respuesta = app_con_bd.test_client().post("/api/sesion/demo/socio", headers=CABECERA)
    assert respuesta.status_code == 404


def test_entrar_como_solo_usa_usuarios_demo(app_con_bd):
    app_con_bd.config["MODO_DEMO"] = True
    crear(app_con_bd, "socio", "9900001", clave=None, es_demo=True, nombre="Lucía")
    crear(app_con_bd, "recepcion", "1234567")  # real: nunca debe abrirse por "entrar como…"
    cliente = app_con_bd.test_client()

    socio = cliente.post("/api/sesion/demo/socio", headers=CABECERA)
    assert socio.status_code == 200
    usuario = socio.get_json()["usuario"]
    assert (usuario["nombre"], usuario["rol"], usuario["es_demo"]) == ("Lucía", "socio", True)

    recepcion = cliente.post("/api/sesion/demo/recepcion", headers=CABECERA)
    assert recepcion.status_code == 404
    assert recepcion.get_json()["error"]["codigo"] == "sin_usuario_demo"
    assert cliente.post("/api/sesion/demo/invitado", headers=CABECERA).status_code == 404


def test_los_cambios_sin_encabezado_anti_csrf_se_rechazan(app_con_bd):
    crear(app_con_bd, "socio", "1234567")
    respuesta = app_con_bd.test_client().post("/api/sesion", json={"identificador": "1234567", "clave": CLAVE})
    assert respuesta.status_code == 403
    assert respuesta.get_json()["error"]["codigo"] == "falta_encabezado"


def test_requiere_aplica_la_matriz(app_con_bd):
    @app_con_bd.get("/api/prueba/visitas")
    @servicio.requiere("visitas.registrar")
    def solo_recepcion():
        return jsonify({"ok": True})

    crear(app_con_bd, "socio", "1111111")
    crear(app_con_bd, "recepcion", "2222222")
    cliente = app_con_bd.test_client()
    assert cliente.get("/api/prueba/visitas").status_code == 401
    entrar(cliente, "1111111")
    assert cliente.get("/api/prueba/visitas").status_code == 403
    entrar(cliente, "2222222")
    assert cliente.get("/api/prueba/visitas").status_code == 200


def test_un_usuario_desactivado_pierde_la_sesion_abierta(app_con_bd):
    usuario_id = crear(app_con_bd, "socio", "1234567")
    cliente = app_con_bd.test_client()
    entrar(cliente, "1234567")
    with app_con_bd.app_context(), transaccion() as cursor:
        cursor.execute("UPDATE usuarios SET activo = FALSE WHERE id = %s", (usuario_id.bytes,))
    assert cliente.get("/api/sesion").status_code == 401


def test_consentimientos_solo_agregan_y_vale_el_ultimo(app_con_bd, reloj_fijo):
    socio = crear(app_con_bd, "socio", "1234567")
    with app_con_bd.app_context():
        with transaccion() as cursor:
            assert not servicio.tiene_consentimiento(cursor, socio, "salud")
            servicio.registrar_consentimiento(cursor, socio, "salud", True, "2026-10", socio)
        reloj_fijo.avanzar(timedelta(days=3))
        with transaccion() as cursor:
            assert servicio.tiene_consentimiento(cursor, socio, "salud")
            servicio.registrar_consentimiento(cursor, socio, "salud", False, "2026-10", socio)
        with transaccion() as cursor:
            assert not servicio.tiene_consentimiento(cursor, socio, "salud")
            cursor.execute("SELECT COUNT(*) AS cantidad FROM consentimientos")
            assert cursor.fetchone()["cantidad"] == 2
