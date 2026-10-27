"""Idempotencia real sobre MySQL, incluidas solicitudes concurrentes y fallos."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import uuid4

import pytest
from flask import request

from gimnasio.comun.bd import conectar, transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.idempotencia import purgar
from gimnasio.comun.migrar import aplicar, leer_migraciones
from gimnasio.permisos import servicio

pytestmark = pytest.mark.bd


@pytest.fixture
def escritura(app_con_bd):
    app = app_con_bd
    with app.app_context(), transaccion() as cursor:
        usuarios = []
        for cedula in ("1234567", "2345678"):
            usuarios.append(
                servicio.crear_usuario(
                    cursor, {"nombre": "Ana", "apellido": "Prueba", "cedula": cedula}, "socio", "clave-prueba"
                )
            )
    iniciada, continuar = Event(), Event()
    ejecuciones = []

    @app.route("/api/prueba/consentimientos", methods=["POST", "PUT", "PATCH", "DELETE"])
    def escribir():
        usuario = servicio.usuario_actual()
        ejecuciones.append(usuario["id"])
        with transaccion() as cursor:
            servicio.registrar_consentimiento(
                cursor, uuid_a_id(usuario["id"]), "salud", True, "prueba", uuid_a_id(usuario["id"])
            )
        if request.args.get("esperar"):
            iniciada.set()
            assert continuar.wait(15)
        if request.args.get("fallar"):
            raise RuntimeError("fallo de prueba después del INSERT")
        if request.args.get("rechazar"):
            raise ErrorDeDominio("prueba", "Rechazo de prueba.", 422)
        if request.method == "DELETE":
            return "", 204
        return b"respuesta\x00exacta", 201, {"Content-Type": "application/octet-stream", "Location": "/api/prueba/1"}

    def cliente(numero=0):
        nuevo = app.test_client()
        with nuevo.session_transaction() as sesion:
            sesion["usuario_id"] = str(usuarios[numero])
        return nuevo

    return app, cliente, ejecuciones, iniciada, continuar


def uuid_a_id(texto):
    from uuid import UUID

    return UUID(texto)


def enviar(cliente, clave=None, cuerpo=b"cuerpo", metodo="POST", consulta=""):
    encabezados = {"X-Gimnasio": "1", "Content-Type": "application/octet-stream"}
    if clave is not None:
        encabezados["Idempotency-Key"] = clave
    return cliente.open("/api/prueba/consentimientos" + consulta, method=metodo, data=cuerpo, headers=encabezados)


def cantidad(app, tabla="consentimientos"):
    with app.app_context(), transaccion() as cursor:
        assert tabla in {"consentimientos", "solicitudes_idempotentes"}
        cursor.execute(f"SELECT COUNT(*) AS cantidad FROM {tabla}")
        return cursor.fetchone()["cantidad"]


@pytest.mark.parametrize("metodo", ["POST", "PUT", "PATCH", "DELETE"])
def test_toda_escritura_exige_clave(escritura, metodo):
    app, cliente, ejecuciones, *_ = escritura
    assert enviar(cliente(), metodo=metodo).status_code == 428
    assert not ejecuciones
    assert cantidad(app) == 0


def test_repite_respuesta_exacta_sin_repetir_escritura(escritura):
    app, cliente, ejecuciones, *_ = escritura
    clave = str(uuid4())
    primera = enviar(cliente(), clave)
    segunda = enviar(cliente(), clave)
    assert primera.status_code == segunda.status_code == 201
    assert primera.data == segunda.data == b"respuesta\x00exacta"
    assert primera.headers == segunda.headers
    assert len(ejecuciones) == cantidad(app) == 1


def test_misma_clave_otro_cuerpo_devuelve_422(escritura):
    app, cliente, ejecuciones, *_ = escritura
    clave = str(uuid4())
    assert enviar(cliente(), clave).status_code == 201
    assert enviar(cliente(), clave, b"otro").status_code == 422
    assert len(ejecuciones) == cantidad(app) == 1


def test_clave_por_usuario_y_uuid_normalizado(escritura):
    app, cliente, ejecuciones, *_ = escritura
    clave = str(uuid4())
    assert enviar(cliente(), clave).status_code == 201
    assert enviar(cliente(), clave.upper()).status_code == 201
    assert enviar(cliente(1), clave).status_code == 201
    assert len(ejecuciones) == cantidad(app) == 2


def test_solicitudes_simultaneas_no_duplican(escritura):
    app, cliente, ejecuciones, iniciada, continuar = escritura
    clave = str(uuid4())
    with ThreadPoolExecutor(max_workers=1) as hilos:
        primera = hilos.submit(enviar, cliente(), clave, consulta="?esperar=1")
        try:
            assert iniciada.wait(10)
            assert enviar(cliente(), clave, consulta="?esperar=1").status_code == 409
            # El INSERT se ejecutó, pero todavía no se confirmó.
            assert cantidad(app) == 0
        finally:
            continuar.set()
        assert primera.result(timeout=15).status_code == 201
    assert enviar(cliente(), clave, consulta="?esperar=1").status_code == 201
    assert len(ejecuciones) == cantidad(app) == 1


def test_fallo_revierte_y_libera_el_candado(escritura):
    app, cliente, ejecuciones, *_ = escritura
    clave = str(uuid4())
    for _ in range(2):
        with pytest.raises(RuntimeError, match="fallo de prueba"):
            enviar(cliente(), clave, consulta="?fallar=1")
        assert cantidad(app) == cantidad(app, "solicitudes_idempotentes") == 0
    assert len(ejecuciones) == 2


def test_error_http_guardado_revierte_la_escritura(escritura):
    app, cliente, ejecuciones, *_ = escritura
    clave = str(uuid4())
    primera = enviar(cliente(), clave, consulta="?rechazar=1")
    segunda = enviar(cliente(), clave, consulta="?rechazar=1")
    assert primera.status_code == segunda.status_code == 422
    assert primera.data == segunda.data
    assert cantidad(app) == 0
    assert cantidad(app, "solicitudes_idempotentes") == len(ejecuciones) == 1


def test_respuesta_sin_cuerpo(escritura):
    app, cliente, ejecuciones, *_ = escritura
    clave = str(uuid4())
    assert enviar(cliente(), clave, metodo="DELETE").status_code == 204
    assert enviar(cliente(), clave, metodo="DELETE").data == b""
    assert len(ejecuciones) == cantidad(app) == 1


def test_purga_solo_mayores_a_siete_dias(escritura, reloj_fijo):
    app, cliente, *_ = escritura
    clave = str(uuid4())
    enviar(cliente(), clave)
    reloj_fijo.avanzar(timedelta(days=7))
    with app.app_context(), transaccion() as cursor:
        assert purgar(cursor, reloj_fijo.ahora()) == 0
    reloj_fijo.avanzar(timedelta(microseconds=1))
    # La purga automática permite reutilizar la clave vencida, incluso con otro cuerpo.
    assert enviar(cliente(), clave, b"nuevo").status_code == 201
    assert cantidad(app) == 2
    assert cantidad(app, "solicitudes_idempotentes") == 1


def test_migracion_repetible_con_datos_existentes(escritura):
    app, cliente, *_ = escritura
    enviar(cliente(), str(uuid4()))
    with conectar(app.config["BD"]) as conexion, conexion.cursor() as cursor:
        migracion = next(m for m in leer_migraciones() if m.version == "0005")
        cursor.execute(migracion.sql)
    assert aplicar(app.config["BD"], salida=lambda _: None) == []
    assert cantidad(app) == cantidad(app, "solicitudes_idempotentes") == 1


def test_rechaza_uuid_invalido_y_sin_sesion(escritura):
    app, cliente, ejecuciones, *_ = escritura
    assert enviar(cliente(), "invalida").status_code == 422
    assert enviar(app.test_client(), str(uuid4())).status_code == 401
    assert not ejecuciones


def test_demo_puede_reiniciarse_con_claves_guardadas(escritura):
    from gimnasio.demo.servicio import reiniciar

    app, cliente, *_ = escritura
    enviar(cliente(), str(uuid4()))
    app.config["MODO_DEMO"] = True
    with app.app_context():
        reiniciar()
    assert cantidad(app, "solicitudes_idempotentes") == 0


def test_sesion_queda_excluida_incluso_con_clave_invalida(escritura):
    app, _, ejecuciones, *_ = escritura
    app.config["MODO_DEMO"] = True
    with app.app_context(), transaccion() as cursor:
        servicio.crear_usuario(
            cursor, {"nombre": "Ana", "apellido": "Demo", "cedula": "9900001"}, "socio", es_demo=True
        )
    cliente = app.test_client()
    encabezados = {"X-Gimnasio": "1", "Idempotency-Key": "invalida"}
    assert (
        cliente.post(
            "/api/sesion", json={"identificador": "1234567", "clave": "clave-prueba"}, headers=encabezados
        ).status_code
        == 200
    )
    assert cliente.delete("/api/sesion", headers=encabezados).status_code == 204
    assert cliente.post("/api/sesion/demo/socio", headers=encabezados).status_code == 200
    assert cliente.get("/api/sesion").get_json()["usuario"]["es_demo"]
    assert cantidad(app, "solicitudes_idempotentes") == 0
    assert not ejecuciones


def test_migracion_sobre_esquema_anterior_conserva_datos(bd_vacia, tmp_path):
    for migracion in leer_migraciones():
        if migracion.version != "0005":
            (tmp_path / migracion.nombre).write_text(migracion.sql)
    aplicar(bd_vacia, carpeta=tmp_path, salida=lambda _: None)
    # Un dato ficticio previo debe sobrevivir a la ampliación del esquema.
    with conectar(bd_vacia) as conexion, conexion.cursor() as cursor:
        cursor.execute(
            "INSERT INTO sedes (id, nombre, zona_horaria, aforo_maximo, actualizada_en) "
            "VALUES (%s, 'Sede de prueba', 'America/Asuncion', 10, '2026-10-27')",
            (uuid4().bytes,),
        )
        conexion.commit()
    assert aplicar(bd_vacia, salida=lambda _: None) == ["0005"]
    with conectar(bd_vacia) as conexion, conexion.cursor() as cursor:
        cursor.execute("SELECT nombre FROM sedes")
        assert cursor.fetchall() == [("Sede de prueba",)]


def test_limite_demo_con_escritura_idempotente(escritura):
    app, cliente, ejecuciones, *_ = escritura
    app.config["MODO_DEMO"] = True
    clave = str(uuid4())
    assert enviar(cliente(), clave, b"x" * 1_000_001).status_code == 413
    assert cantidad(app) == cantidad(app, "solicitudes_idempotentes") == 0
    assert enviar(cliente(), clave, b"x" * 1_000_000).status_code == 201
    assert enviar(cliente(), clave, b"x" * 1_000_000).status_code == 201
    assert len(ejecuciones) == cantidad(app) == 1
