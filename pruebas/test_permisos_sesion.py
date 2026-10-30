"""Sesión por rol, "entrar como…", límite de intentos, CSRF y consentimientos, sobre MySQL (ADR 0006)."""

import threading
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


def test_cada_usuario_guarda_su_figura_del_cuerpo(app_con_bd):
    crear(app_con_bd, "socio", "4567891")
    cliente = app_con_bd.test_client()
    claves = {**CABECERA, "Idempotency-Key": "0193a000-0000-7000-8000-000000000001"}
    assert (
        cliente.put("/api/sesion/figura-cuerpo", json={"figura_cuerpo": "femenina"}, headers=claves).status_code == 401
    )

    assert entrar(cliente, "4567891").get_json()["usuario"]["figura_cuerpo"] is None
    invalida = cliente.put("/api/sesion/figura-cuerpo", json={"figura_cuerpo": "otra"}, headers=claves)
    assert invalida.status_code == 422
    assert (
        cliente.put("/api/sesion/figura-cuerpo", json={"figura_cuerpo": "femenina"}, headers=CABECERA).status_code
        == 428
    )

    otra_clave = {**CABECERA, "Idempotency-Key": "0193a000-0000-7000-8000-000000000002"}
    respuesta = cliente.put("/api/sesion/figura-cuerpo", json={"figura_cuerpo": "femenina"}, headers=otra_clave)
    assert respuesta.status_code == 200
    assert respuesta.get_json()["usuario"]["figura_cuerpo"] == "femenina"
    assert cliente.get("/api/sesion").get_json()["usuario"]["figura_cuerpo"] == "femenina"


def test_inicia_sesion_con_cedula_o_correo_y_la_cierra(app_con_bd):
    crear(app_con_bd, "recepcion", "4567890", correo="Rocio@Demo.Gimnasio.invalid", nombre="Rocío")
    cliente = app_con_bd.test_client()
    assert cliente.get("/api/sesion").get_json() == {"usuario": None}

    respuesta = entrar(cliente, "4.567.890")
    assert respuesta.status_code == 200
    cookie = respuesta.headers["Set-Cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Secure" not in cookie  # El cliente de pruebas usa HTTP local (ADR 0006).
    assert respuesta.get_json()["usuario"]["rol"] == "recepcion"
    assert cliente.get("/api/sesion").get_json()["usuario"]["nombre"] == "Rocío"

    cierre = cliente.delete("/api/sesion", headers=CABECERA)
    assert cierre.status_code == 204
    assert "Max-Age=0" in cierre.headers["Set-Cookie"]
    assert cliente.get("/api/sesion").get_json() == {"usuario": None}
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


@pytest.mark.parametrize(
    "metodo,ruta", [("POST", "/api/sesion"), ("DELETE", "/api/sesion"), ("POST", "/api/sesion/demo/socio")]
)
def test_los_cambios_sin_encabezado_anti_csrf_se_rechazan(app_con_bd, metodo, ruta):
    respuesta = app_con_bd.test_client().open(ruta, method=metodo, json={"identificador": "1234567", "clave": CLAVE})
    assert respuesta.status_code == 403
    assert respuesta.get_json()["error"]["codigo"] == "falta_encabezado"


@pytest.mark.parametrize(
    "permiso,rol_permitido",
    [
        ("visitas.registrar", "recepcion"),
        ("visitas.ver", "recepcion"),
        ("entrenamiento.ver_propio", "socio"),
        ("entrenamiento.ver_asignados", "entrenador"),
    ],
)
def test_requiere_aplica_la_matriz(app_con_bd, permiso, rol_permitido):
    @app_con_bd.get("/api/prueba/visitas")
    @servicio.requiere(permiso)
    def lectura():
        return jsonify({"ok": True})

    cliente = app_con_bd.test_client()
    assert cliente.get("/api/prueba/visitas").status_code == 401
    for numero, rol in enumerate(("socio", "recepcion", "entrenador", "administracion")):
        cedula = str(1_000_000 + numero)
        crear(app_con_bd, rol, cedula)
        assert entrar(cliente, cedula).status_code == 200
        assert cliente.get("/api/prueba/visitas").status_code == (200 if rol == rol_permitido else 403)


def test_un_usuario_desactivado_pierde_la_sesion_abierta(app_con_bd):
    @app_con_bd.get("/api/prueba/entrenamiento")
    @servicio.requiere("entrenamiento.ver_propio")
    def lectura():
        return "", 204

    usuario_id = crear(app_con_bd, "socio", "1234567")
    cliente = app_con_bd.test_client()
    assert entrar(cliente, "1234567").status_code == 200
    assert cliente.get("/api/prueba/entrenamiento").status_code == 204
    with app_con_bd.app_context(), transaccion() as cursor:
        cursor.execute("UPDATE usuarios SET activo = FALSE WHERE id = %s", (usuario_id.bytes,))
    assert cliente.get("/api/prueba/entrenamiento").status_code == 401
    assert cliente.get("/api/sesion").get_json() == {"usuario": None}


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


def test_el_limite_es_por_usuario_aunque_alterne_cedula_y_correo(app_con_bd):
    crear(app_con_bd, "socio", "1234567", correo="ana@demo.gimnasio.invalid")
    cliente = app_con_bd.test_client()
    for identificador in ("1234567", "ana@demo.gimnasio.invalid") * 2 + ("1.234.567",):
        assert entrar(cliente, identificador, "incorrecta").status_code == 401
    assert entrar(cliente, "ana@demo.gimnasio.invalid").status_code == 429
    assert entrar(cliente, "1234567").status_code == 429


def test_dos_fallos_simultaneos_no_esquivan_el_limite(app_con_bd):
    crear(app_con_bd, "socio", "1234567")
    for _ in range(4):
        assert entrar(app_con_bd.test_client(), "1234567", "incorrecta").status_code == 401
    barrera = threading.Barrier(2)
    codigos = []

    def intentar():
        cliente = app_con_bd.test_client()
        barrera.wait()
        codigos.append(entrar(cliente, "1234567", "incorrecta").status_code)

    hilos = [threading.Thread(target=intentar) for _ in range(2)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=30)
    assert sorted(codigos) == [401, 429]


def test_fallos_simultaneos_a_cuentas_distintas_no_esquivan_el_limite_por_ip(app_con_bd):
    for numero in range(19):
        assert entrar(app_con_bd.test_client(), str(1_000_000 + numero), "incorrecta").status_code == 401
    barrera = threading.Barrier(2)
    codigos = []

    def intentar(identificador):
        cliente = app_con_bd.test_client()
        barrera.wait()
        codigos.append(entrar(cliente, identificador, "incorrecta").status_code)

    hilos = [threading.Thread(target=intentar, args=(cedula,)) for cedula in ("2000001", "2000002")]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=30)
    assert sorted(codigos) == [401, 429]


@pytest.mark.parametrize(
    "cuerpo",
    [["1234567", CLAVE], {"identificador": 1234567, "clave": CLAVE}, {"identificador": "1234567", "clave": None}, "x"],
)
def test_rechaza_cuerpos_con_tipos_invalidos(app_con_bd, cuerpo):
    respuesta = app_con_bd.test_client().post("/api/sesion", json=cuerpo, headers=CABECERA)
    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"]["codigo"] == "cuerpo_invalido"
