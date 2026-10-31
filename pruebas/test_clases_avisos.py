"""Cambios de cupo, cancelaciones y avisos al socio (#219, ADR 0029)."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier, Event
from uuid import uuid4

import pytest
from flask import g
from mysql.connector import Error as ErrorMySQL
from test_clases_reservas import agenda, entrar, escribir, solicitar
from test_clases_reservas import reservas as reservas

from gimnasio.clases import servicio
from gimnasio.comun.bd import conexion_actual, transaccion
from gimnasio.comun.ids import desde_bytes, desde_texto

pytestmark = pytest.mark.bd


def cambiar(cliente, clase, datos, cupo, **otros):
    entrar(cliente, "administracion")
    respuesta = cliente.put(
        f"/api/clases/{clase}",
        json=datos | {"cupo": cupo} | otros,
        headers={"X-Gimnasio": "1", "Idempotency-Key": str(uuid4())},
    )
    assert respuesta.status_code == 200, respuesta.get_json()
    entrar(cliente, "recepcion")


def avisos(app):
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT * FROM avisos_socio ORDER BY registrado_en,id")
        return [
            dict(fila, socio_id=str(desde_bytes(fila["socio_id"])), id=str(desde_bytes(fila["id"])))
            for fila in cursor.fetchall()
        ]


def test_bajar_subir_restablece_orden_sin_duplicar(reservas):
    app, cliente, clase, socios, datos, _ = reservas
    cambiar(cliente, clase, datos, 3)
    originales = [solicitar(cliente, clase, socio).get_json()["id"] for socio in socios[:3]]
    cambiar(cliente, clase, datos, 1)
    assert [agenda(cliente, socio)[0]["reserva"]["estado"] for socio in socios[:3]] == [
        "con_lugar",
        "en_espera",
        "en_espera",
    ]
    assert [(a["socio_id"], a["tipo"]) for a in avisos(app)] == [(socio, "volvio_a_espera") for socio in socios[1:3]]
    cambiar(cliente, clase, datos, 3)
    assert [agenda(cliente, socio)[0]["reserva"]["id"] for socio in socios[:3]] == originales
    assert all(agenda(cliente, socio)[0]["reserva"]["estado"] == "con_lugar" for socio in socios[:3])
    assert [(a["socio_id"], a["tipo"]) for a in avisos(app)[2:]] == [
        (socio, "paso_a_tener_lugar") for socio in socios[1:3]
    ]
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT COUNT(*) AS cantidad FROM reservas")
        assert cursor.fetchone()["cantidad"] == 3
        cursor.execute("SELECT COUNT(*) AS cantidad FROM cupos_ocurrencia")
        assert cursor.fetchone()["cantidad"] == 0


def test_subir_da_lugar_solo_al_primero_de_espera(reservas):
    app, cliente, clase, socios, datos, _ = reservas
    for socio in socios[:3]:
        assert solicitar(cliente, clase, socio).status_code == 201
    cambiar(cliente, clase, datos, 2)
    assert [(a["socio_id"], a["tipo"]) for a in avisos(app)] == [(socios[1], "paso_a_tener_lugar")]
    assert agenda(cliente, socios[2])[0]["reserva"]["posicion"] == 1


def test_cancelar_propia_avisa_solo_a_quien_sube_y_reintento_no_duplica(reservas):
    app, cliente, clase, socios, _, _ = reservas
    primera = solicitar(cliente, clase, socios[0]).get_json()
    for socio in socios[1:3]:
        assert solicitar(cliente, clase, socio).status_code == 201
    with cliente.session_transaction() as sesion:
        sesion["usuario_id"] = socios[0]
    ruta = f"/api/clases/reservas/{primera['id']}/cancelar"
    clave = str(uuid4())
    assert escribir(cliente, ruta, clave=clave).status_code == 200
    assert escribir(cliente, ruta, clave=clave).status_code == 200
    assert escribir(cliente, ruta).status_code == 200
    assert [(a["socio_id"], a["tipo"]) for a in avisos(app)] == [(socios[1], "paso_a_tener_lugar")]


def test_cancelaciones_simultaneas_con_aviso_reintentan_interbloqueo(reservas, monkeypatch):
    app, cliente, clase, socios, _, _ = reservas
    propias = [solicitar(cliente, clase, socio).get_json()["id"] for socio in socios[:3]]
    barrera = Barrier(2)
    clase_bloqueada = Event()
    bloquear_socio = servicio.socios.bloquear_socio_activo
    bloquear_clase = servicio.repositorio.clase_para_reserva
    intentos = {socio: 0 for socio in socios[:2]}

    def bloquear_socio_a_la_vez(socio_id, *, cursor):
        bloquear_socio(socio_id, cursor=cursor)
        g.socio_cancelando = str(socio_id)
        intentos[str(socio_id)] += 1
        if intentos[str(socio_id)] == 1:
            barrera.wait(timeout=10)

    def bloquear_clase_en_orden(cursor, clase_id):
        # Ambos socios conservan su bloqueo; quien tiene lugar obtiene primero la clase.
        if g.socio_cancelando == socios[1]:
            assert clase_bloqueada.wait(timeout=10)
        resultado = bloquear_clase(cursor, clase_id)
        if g.socio_cancelando == socios[0]:
            clase_bloqueada.set()
        return resultado

    monkeypatch.setattr(servicio.socios, "bloquear_socio_activo", bloquear_socio_a_la_vez)
    monkeypatch.setattr(servicio.repositorio, "clase_para_reserva", bloquear_clase_en_orden)

    def cancelar(indice):
        with app.test_client() as propio:
            with propio.session_transaction() as sesion:
                sesion["usuario_id"] = socios[indice]
            with app.app_context():
                conexion_id = conexion_actual().connection_id
                ruta = f"/api/clases/reservas/{propias[indice]}/cancelar"
                clave = str(uuid4())
                respuesta = escribir(propio, ruta, clave=clave)
                assert respuesta.status_code == 200, respuesta.get_json()
                assert escribir(propio, ruta, clave=clave).data == respuesta.data
                return conexion_id

    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        conexiones = list(ejecutor.map(cancelar, range(2)))
    assert len(set(conexiones)) == 2
    assert sorted(intentos.values()) == [1, 2]
    assert agenda(cliente, socios[2])[0]["reserva"]["estado"] == "con_lugar"
    assert [(a["socio_id"], a["tipo"]) for a in avisos(app)] == [
        (socios[1], "paso_a_tener_lugar"),
        (socios[2], "paso_a_tener_lugar"),
    ]
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT reserva_id FROM cancelaciones_reserva ORDER BY reserva_id")
        assert cursor.fetchall() == [{"reserva_id": desde_texto(reserva_id).bytes} for reserva_id in propias[:2]]


def test_reintento_revierte_cancelacion_y_aviso_antes_de_recalcular(reservas, monkeypatch):
    app, cliente, clase, socios, _, _ = reservas
    primera = solicitar(cliente, clase, socios[0]).get_json()["id"]
    assert solicitar(cliente, clase, socios[1]).status_code == 201
    insertar_aviso = servicio.repositorio.insertar_aviso
    intentos = []

    def insertar_y_fallar_una_vez(*argumentos):
        insertar_aviso(*argumentos)
        intentos.append(1)
        if len(intentos) == 1:
            raise ErrorMySQL(errno=1213, msg="Interbloqueo de prueba")

    monkeypatch.setattr(servicio.repositorio, "insertar_aviso", insertar_y_fallar_una_vez)
    with cliente.session_transaction() as sesion:
        sesion["usuario_id"] = socios[0]
    ruta = f"/api/clases/reservas/{primera}/cancelar"
    clave = str(uuid4())
    respuesta = escribir(cliente, ruta, clave=clave)
    assert respuesta.status_code == 200
    assert escribir(cliente, ruta, clave=clave).data == respuesta.data
    assert len(intentos) == 2
    assert [(a["socio_id"], a["tipo"]) for a in avisos(app)] == [(socios[1], "paso_a_tener_lugar")]
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT reserva_id FROM cancelaciones_reserva")
        assert cursor.fetchall() == [{"reserva_id": desde_texto(primera).bytes}]


@pytest.mark.parametrize("codigo,intentos_esperados", [(1213, 3), (1205, 1), (1062, 1)])
def test_reintento_acotado_solo_para_interbloqueo(reservas, monkeypatch, codigo, intentos_esperados):
    app, cliente, clase, socios, _, autor = reservas
    primera = solicitar(cliente, clase, socios[0]).get_json()["id"]
    assert solicitar(cliente, clase, socios[1]).status_code == 201
    intentos = []
    error = ErrorMySQL(errno=codigo, msg="Error de prueba")

    def fallar_al_avisar(*argumentos):
        intentos.append(1)
        raise error

    monkeypatch.setattr(servicio.repositorio, "insertar_aviso", fallar_al_avisar)
    with app.app_context(), pytest.raises(ErrorMySQL) as resultado:
        servicio.cancelar(primera, autor)
    assert resultado.value is error
    assert len(intentos) == intentos_esperados
    assert avisos(app) == []
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT COUNT(*) AS cantidad FROM cancelaciones_reserva")
        assert cursor.fetchone()["cantidad"] == 0


def test_empezada_conserva_cupo_y_estado_sin_avisos(reservas):
    app, cliente, clase, socios, datos, _ = reservas
    cambiar(cliente, clase, datos, 2)
    for socio in socios[:3]:
        assert solicitar(cliente, clase, socio).status_code == 201
    antes = [agenda(cliente, socio)[0]["reserva"] for socio in socios[:3]]
    app.extensions["reloj"].fijar(datetime(2026, 10, 27, 21, tzinfo=UTC))
    cambiar(cliente, clase, datos, 1)
    assert [agenda(cliente, socio)[0]["reserva"] for socio in socios[:3]] == antes
    assert agenda(cliente)[0]["cupo"] == 2
    assert avisos(app) == []
    lista = cliente.get(f"/api/clases/{clase}/2026-10-27/reservas").get_json()["reservas"]
    assert [r["estado"] for r in lista] == ["con_lugar", "con_lugar", "en_espera"]
    cambiar(cliente, clase, datos, 4)
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT cupo FROM cupos_ocurrencia")
        assert cursor.fetchall() == [{"cupo": 2}]
    assert [agenda(cliente, socio)[0]["reserva"] for socio in socios[:3]] == antes


def test_sin_cambio_de_cupo_no_congela(reservas):
    app, cliente, clase, socios, datos, _ = reservas
    assert solicitar(cliente, clase, socios[0]).status_code == 201
    app.extensions["reloj"].fijar(datetime(2026, 10, 27, 21, tzinfo=UTC))
    cambiar(cliente, clase, datos, 1, nombre="Clase corregida")
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT COUNT(*) AS cantidad FROM cupos_ocurrencia")
        assert cursor.fetchone()["cantidad"] == 0


def test_aviso_visto_sigue_visto_y_solo_cambio_real_crea_nuevo(reservas):
    app, cliente, clase, socios, datos, _ = reservas
    for socio in socios[:2]:
        assert solicitar(cliente, clase, socio).status_code == 201
    cambiar(cliente, clase, datos, 2)
    with cliente.session_transaction() as sesion:
        sesion["usuario_id"] = socios[1]
    aviso = cliente.get("/api/yo/avisos").get_json()["avisos"][0]
    ruta = f"/api/yo/avisos/{aviso['id']}/visto"
    clave = str(uuid4())
    assert escribir(cliente, ruta, clave=clave).status_code == 200
    assert escribir(cliente, ruta, clave=clave).status_code == 200
    assert escribir(cliente, ruta).status_code == 200
    assert cliente.get("/api/yo/avisos").get_json() == {"avisos": []}
    cambiar(cliente, clase, datos, 2)
    assert len(avisos(app)) == 1
    cambiar(cliente, clase, datos, 1)
    with cliente.session_transaction() as sesion:
        sesion["usuario_id"] = socios[1]
    nuevos = cliente.get("/api/yo/avisos").get_json()["avisos"]
    assert [a["tipo"] for a in nuevos] == ["volvio_a_espera"]
    assert nuevos[0]["id"] != aviso["id"]
    with cliente.session_transaction() as sesion:
        sesion["usuario_id"] = socios[0]
    assert escribir(cliente, ruta).status_code == 404
    assert cliente.get("/api/yo/avisos").get_json() == {"avisos": []}
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT COUNT(*) AS cantidad FROM vistos_aviso_socio")
        assert cursor.fetchone()["cantidad"] == 1


def test_cancelar_ocurrencia_no_reaparece_ni_afecta_otra_fecha(reservas):
    app, cliente, clase, socios, datos, autor = reservas
    for socio in socios[:3]:
        assert solicitar(cliente, clase, socio).status_code == 201
    assert solicitar(cliente, clase, socios[0], "2026-11-03").status_code == 201
    ruta = f"/api/clases/{clase}/2026-10-27/cancelar"
    clave = str(uuid4())
    for reintento in (clave, clave, None):
        assert escribir(cliente, ruta, {"motivo": "Entrenador ausente"}, reintento).status_code == 200
    assert len(avisos(app)) == 3
    assert {a["tipo"] for a in avisos(app)} == {"ocurrencia_cancelada"}
    filas = agenda(cliente)
    assert filas[0]["cancelada"] is True
    assert filas[1]["cancelada"] is False
    assert filas[1]["libres"] == 0
    assert solicitar(cliente, clase, socios[3]).status_code == 409
    cambiar(cliente, clase, datos, 4, hora_inicio="20:00", dia_semana=3)
    fila = next(f for f in agenda(cliente) if f["fecha"] == "2026-10-27")
    assert fila["cancelada"] is True
    assert fila["hora_inicio"] == "18:00"
    assert len(avisos(app)) == 3
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT autor_id FROM cancelaciones_reserva")
        assert cursor.fetchall() == [{"autor_id": desde_texto(autor["id"]).bytes}] * 3
        cursor.execute("SELECT COUNT(*) AS cantidad FROM cancelaciones_ocurrencia")
        assert cursor.fetchone()["cantidad"] == 1


def test_cancelacion_sin_reservas_fija_ocurrencia_y_exige_motivo(reservas):
    app, cliente, clase, _, _, _ = reservas
    ruta = f"/api/clases/{clase}/2026-10-27/cancelar"
    for cuerpo in (None, {}, {"motivo": " "}, {"motivo": 2}):
        assert escribir(cliente, ruta, cuerpo).status_code == 422
    assert escribir(cliente, ruta, {"motivo": "Mantenimiento"}).status_code == 200
    assert agenda(cliente)[0]["cancelada"] is True
    assert avisos(app) == []


@pytest.mark.parametrize(
    "rol,estado", [("socio", 403), ("entrenador", 403), ("recepcion", 200), ("administracion", 200)]
)
def test_permisos_cancelar_ocurrencia(reservas, rol, estado):
    _, cliente, clase, _, _, _ = reservas
    entrar(cliente, rol)
    assert (
        escribir(cliente, f"/api/clases/{clase}/2026-10-27/cancelar", {"motivo": "Mantenimiento"}).status_code == estado
    )


@pytest.mark.parametrize(
    "rol,estado", [("socio", 200), ("entrenador", 403), ("recepcion", 403), ("administracion", 403)]
)
def test_permisos_avisos_propios(reservas, rol, estado):
    _, cliente, _, _, _, _ = reservas
    entrar(cliente, rol)
    assert cliente.get("/api/yo/avisos").status_code == estado
    respuesta = escribir(cliente, "/api/yo/avisos/019a2700-0000-7000-8000-000000000001/visto")
    assert respuesta.status_code == (404 if rol == "socio" else 403)


def test_agenda_etag_304_y_200_tras_reserva(reservas):
    _, cliente, clase, socios, _, _ = reservas
    primera = cliente.get("/api/clases/agenda")
    assert primera.status_code == 200
    etiqueta = primera.headers["ETag"]
    assert "private" in primera.headers["Cache-Control"]
    assert cliente.get("/api/clases/agenda", headers={"If-None-Match": etiqueta}).status_code == 304
    assert solicitar(cliente, clase, socios[0]).status_code == 201
    segunda = cliente.get("/api/clases/agenda", headers={"If-None-Match": etiqueta})
    assert segunda.status_code == 200
    assert segunda.headers["ETag"] != etiqueta
