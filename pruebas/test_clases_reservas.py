"""Reservas, espera derivada, concurrencia y alcance del entrenador (ADR 0028)."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from threading import Barrier
from uuid import uuid4

import pytest

from gimnasio.clases import servicio
from gimnasio.comun.bd import conexion_actual, transaccion
from gimnasio.comun.ids import desde_bytes, desde_texto
from gimnasio.demo import servicio as demo
from gimnasio.pagos import servicio as pagos

pytestmark = pytest.mark.bd


def escribir(cliente, ruta, datos=None, clave=None):
    return cliente.post(ruta, json=datos, headers={"X-Gimnasio": "1", "Idempotency-Key": clave or str(uuid4())})


def entrar(cliente, rol):
    respuesta = cliente.post(f"/api/sesion/demo/{rol}", headers={"X-Gimnasio": "1"})
    assert respuesta.status_code == 200
    return respuesta.get_json()["usuario"]


@pytest.fixture
def reservas(app_con_bd, sembrar_demo):
    app = app_con_bd
    app.config["MODO_DEMO"] = True
    sembrar_demo(app, sin_pagos_ni_clases=True)
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT id FROM usuarios WHERE rol='socio' ORDER BY id LIMIT 4")
        socios = [str(desde_bytes(r["id"])) for r in cursor.fetchall()]
    cliente = app.test_client()
    entrar(cliente, "administracion")
    entrenador = cliente.get("/api/clases").get_json()["entrenadores"][0]["id"]
    datos = {
        "nombre": "Clase ficticia",
        "entrenador_id": entrenador,
        "dia_semana": 2,
        "hora_inicio": "18:00",
        "duracion_minutos": 60,
        "cupo": 1,
    }
    respuesta = escribir(cliente, "/api/clases", datos)
    assert respuesta.status_code == 201
    clase_id = respuesta.get_json()["id"]
    autor = entrar(cliente, "recepcion")
    return app, cliente, clase_id, socios, datos, autor


def solicitar(cliente, clase_id, socio_id=None, fecha="2026-10-27", clave=None):
    datos = {"clase_id": clase_id, "fecha": fecha}
    if socio_id is not None:
        datos["socio_id"] = socio_id
    return escribir(cliente, "/api/clases/reservas", datos, clave)


def agenda(cliente, socio_id=None):
    ruta = "/api/clases/agenda" + (f"?socio_id={socio_id}" if socio_id else "")
    respuesta = cliente.get(ruta)
    assert respuesta.status_code == 200
    return respuesta.get_json()["ocurrencias"]


def comprobar_error(respuesta, estado, codigo):
    assert respuesta.status_code == estado, respuesta.get_json()
    assert respuesta.get_json()["error"]["codigo"] == codigo


def test_cancelar_promueve_y_volver_a_reservar_va_al_final(reservas):
    app, cliente, clase, socios, _, _ = reservas
    primera = solicitar(cliente, clase, socios[0]).get_json()
    segunda = solicitar(cliente, clase, socios[1]).get_json()
    tercera = solicitar(cliente, clase, socios[2]).get_json()
    assert primera["estado"] == "con_lugar"
    assert segunda["posicion"] == 1
    assert tercera["posicion"] == 2
    assert escribir(cliente, f"/api/clases/reservas/{primera['id']}/cancelar").status_code == 200
    assert agenda(cliente, socios[1])[0]["reserva"]["estado"] == "con_lugar"
    nueva = solicitar(cliente, clase, socios[0])
    assert nueva.status_code == 201
    assert nueva.get_json()["id"] != primera["id"]
    assert nueva.get_json()["posicion"] == 2
    assert agenda(cliente, socios[2])[0]["reserva"]["posicion"] == 1
    assert agenda(cliente)[0]["libres"] == 0
    assert agenda(cliente)[0]["espera"] == 2
    with app.app_context():
        # Reiniciar respeta las claves foráneas de los dos hechos nuevos.
        demo.reiniciar()


def test_cancelada_no_cuenta_para_cupo_duplicado_ni_superposicion(reservas):
    app, cliente, clase, socios, datos, _ = reservas
    primera = solicitar(cliente, clase, socios[0]).get_json()
    assert escribir(cliente, f"/api/clases/reservas/{primera['id']}/cancelar").status_code == 200
    assert agenda(cliente)[0]["libres"] == 1
    entrar(cliente, "administracion")
    otra = escribir(cliente, "/api/clases", datos | {"nombre": "Otra clase ficticia"}).get_json()["id"]
    entrar(cliente, "recepcion")
    nueva = solicitar(cliente, otra, socios[0])
    assert nueva.status_code == 201
    assert nueva.get_json()["estado"] == "con_lugar"
    # La misma ocurrencia admite otra solicitud después de cancelar.
    assert escribir(cliente, f"/api/clases/reservas/{nueva.get_json()['id']}/cancelar").status_code == 200
    assert solicitar(cliente, clase, socios[0]).status_code == 201
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT COUNT(*) AS cantidad FROM reservas")
        assert cursor.fetchone()["cantidad"] == 3
        cursor.execute("SELECT COUNT(*) AS cantidad FROM cancelaciones_reserva")
        assert cursor.fetchone()["cantidad"] == 2


def test_dos_conexiones_por_ultimo_lugar(reservas):
    app, cliente, clase, socios, _, autor = reservas
    barrera = Barrier(2)

    def reservar(socio):
        with app.app_context():
            conexion = conexion_actual()
            identificador_conexion = conexion.connection_id
            barrera.wait(timeout=10)
            resultado = servicio.reservar({"clase_id": clase, "fecha": "2026-10-27", "socio_id": socio}, autor)
            return identificador_conexion, resultado

    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        resultados = list(ejecutor.map(reservar, socios[:2]))
    assert len({identificador for identificador, _ in resultados}) == 2
    assert sorted(r["estado"] for _, r in resultados) == ["con_lugar", "en_espera"]
    assert next(r for _, r in resultados if r["estado"] == "en_espera")["posicion"] == 1
    assert agenda(cliente)[0]["espera"] == 1


@pytest.mark.parametrize("misma_clase", [True, False])
def test_solicitudes_simultaneas_del_mismo_socio(reservas, misma_clase):
    app, cliente, clase, socios, datos, autor = reservas
    otra = clase
    if not misma_clase:
        entrar(cliente, "administracion")
        otra = escribir(cliente, "/api/clases", datos | {"nombre": "Otra clase ficticia"}).get_json()["id"]
    barrera = Barrier(2)

    def reservar(clase_id):
        from gimnasio.comun.errores import ErrorDeDominio

        with app.app_context():
            conexion_actual()
            barrera.wait(timeout=10)
            try:
                servicio.reservar({"clase_id": clase_id, "fecha": "2026-10-27", "socio_id": socios[0]}, autor)
                return "reservada"
            except ErrorDeDominio as error:
                return error.codigo

    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        resultados = list(ejecutor.map(reservar, [clase, otra]))
    assert sorted(resultados) == sorted(["reservada", "ya_reservada" if misma_clase else "reserva_superpuesta"])


@pytest.mark.parametrize("en_espera", [False, True])
def test_duplicado_y_superposicion_incluyen_espera(reservas, en_espera):
    _, cliente, clase, socios, datos, _ = reservas
    if en_espera:
        assert solicitar(cliente, clase, socios[1]).status_code == 201
    assert solicitar(cliente, clase, socios[0]).status_code == 201
    comprobar_error(solicitar(cliente, clase, socios[0]), 409, "ya_reservada")
    entrar(cliente, "administracion")
    otra = escribir(cliente, "/api/clases", datos | {"nombre": "Otra", "hora_inicio": "18:30"}).get_json()["id"]
    entrar(cliente, "recepcion")
    comprobar_error(solicitar(cliente, otra, socios[0]), 409, "reserva_superpuesta")


def test_superposicion_usa_ocurrencia_fijada_y_admite_limite_contiguo(reservas):
    app, cliente, clase, socios, datos, _ = reservas
    assert solicitar(cliente, clase, socios[0]).status_code == 201
    entrar(cliente, "administracion")
    respuesta = cliente.put(
        f"/api/clases/{clase}",
        json=datos | {"hora_inicio": "20:00"},
        headers={"X-Gimnasio": "1", "Idempotency-Key": str(uuid4())},
    )
    assert respuesta.status_code == 200
    otra = escribir(cliente, "/api/clases", datos | {"nombre": "Otra", "hora_inicio": "18:30"}).get_json()["id"]
    contigua = escribir(cliente, "/api/clases", datos | {"nombre": "Contigua", "hora_inicio": "19:00"}).get_json()["id"]
    entrar(cliente, "recepcion")
    comprobar_error(solicitar(cliente, otra, socios[0]), 409, "reserva_superpuesta")
    assert solicitar(cliente, contigua, socios[0]).status_code == 201
    # El cambio del horario semanal tampoco adelanta el límite de cancelación.
    app.extensions["reloj"].fijar(datetime(2026, 10, 27, 21, tzinfo=UTC))
    comprobar_error(solicitar(cliente, clase, socios[2]), 409, "ocurrencia_empezada")


@pytest.mark.parametrize("fecha", ["2026-10-28", "2026-11-10"])
def test_fuera_de_agenda(reservas, fecha):
    _, cliente, clase, socios, _, _ = reservas
    comprobar_error(solicitar(cliente, clase, socios[0], fecha), 422, "fuera_de_agenda")


def test_membresia_se_evalua_en_fecha_futura_y_renovacion_permite(reservas):
    app, cliente, clase, socios, _, autor = reservas
    with app.app_context(), transaccion() as cursor:
        cursor.execute("UPDATE membresias SET hasta='2026-10-28' WHERE socio_id=%s", (desde_texto(socios[0]).bytes,))
    comprobar_error(solicitar(cliente, clase, socios[0], "2026-11-03"), 422, "membresia_no_vigente")
    with app.app_context():
        tipo = pagos.guardar_tipo({"nombre": "Mensual ficticia", "duracion_dias": 30, "precio": 250000})
        pagos.registrar_pago({"socio_id": socios[0], "tipo_id": tipo["id"], "medio": "efectivo"}, autor)
    assert solicitar(cliente, clase, socios[0], "2026-11-03").status_code == 201


@pytest.mark.parametrize("cambio", ["renovar", "cambiar_membresia", "anular_pago"])
def test_cambios_de_membresia_no_reubican_reservas(reservas, cambio, monkeypatch):
    app, cliente, clase, socios, _, autor = reservas
    assert solicitar(cliente, clase, socios[0]).status_code == 201
    assert solicitar(cliente, clase, socios[1]).status_code == 201
    antes = [agenda(cliente, socio)[0] for socio in socios[:2]]
    with app.app_context():
        if cambio == "renovar":
            tipo = pagos.guardar_tipo({"nombre": "Mensual ficticia", "duracion_dias": 30, "precio": 250000})
            pagos.registrar_pago({"socio_id": socios[0], "tipo_id": tipo["id"], "medio": "efectivo"}, autor)
        elif cambio == "cambiar_membresia":
            with transaccion() as cursor:
                cursor.execute(
                    "UPDATE membresias SET desde='2026-10-01', hasta='2026-10-26' WHERE socio_id=%s",
                    (desde_texto(socios[0]).bytes,),
                )
        else:
            # #222 todavía no aporta la API de anulación en esta rama. Se simula
            # su resultado público: el pago anulado ya no otorga membresía vigente.
            monkeypatch.setattr(servicio.socios, "consultar_membresia", lambda *args, **kwargs: None)
    comprobar_error(solicitar(cliente, clase, socios[0]), 409, "ya_reservada")
    assert [agenda(cliente, socio)[0] for socio in socios[:2]] == antes
    primera = antes[0]["reserva"]["id"]
    assert escribir(cliente, f"/api/clases/reservas/{primera}/cancelar").status_code == 200
    assert agenda(cliente, socios[1])[0]["reserva"]["estado"] == "con_lugar"


def test_inicio_rechaza_reserva_y_cancelacion(reservas):
    app, cliente, clase, socios, _, _ = reservas
    reserva = solicitar(cliente, clase, socios[0]).get_json()
    app.extensions["reloj"].fijar(datetime(2026, 10, 27, 21, tzinfo=UTC))
    comprobar_error(solicitar(cliente, clase, socios[1]), 409, "ocurrencia_empezada")
    comprobar_error(escribir(cliente, f"/api/clases/reservas/{reserva['id']}/cancelar"), 409, "ocurrencia_empezada")


def test_idempotencia_encabezados_y_solo_propias(reservas):
    app, cliente, clase, socios, _, _ = reservas
    ajena = solicitar(cliente, clase, socios[1]).get_json()
    usuario = entrar(cliente, "socio")
    comprobar_error(solicitar(cliente, clase, socios[1]), 403, "sin_permiso")
    comprobar_error(escribir(cliente, f"/api/clases/reservas/{ajena['id']}/cancelar"), 403, "sin_permiso")
    assert cliente.get(f"/api/clases/agenda?socio_id={socios[1]}").status_code == 403
    assert cliente.post("/api/clases/reservas", json={}).status_code == 403
    assert cliente.post("/api/clases/reservas", json={}, headers={"X-Gimnasio": "1"}).status_code == 428
    clave = str(uuid4())
    primera = solicitar(cliente, clase, clave=clave)
    assert primera.status_code == 201
    assert solicitar(cliente, clase, clave=clave).data == primera.data
    propia = agenda(cliente)[0]["reserva"]
    assert propia == primera.get_json()
    ruta = f"/api/clases/reservas/{propia['id']}/cancelar"
    clave_cancelacion = str(uuid4())
    cancelada = escribir(cliente, ruta, clave=clave_cancelacion)
    assert cancelada.status_code == 200
    assert escribir(cliente, ruta, clave=clave_cancelacion).data == cancelada.data
    with app.app_context(), transaccion() as cursor:
        cursor.execute(
            "SELECT COUNT(*) AS cantidad FROM reservas WHERE socio_id=%s", (desde_texto(usuario["id"]).bytes,)
        )
        assert cursor.fetchone()["cantidad"] == 1
        cursor.execute("SELECT COUNT(*) AS cantidad FROM cancelaciones_reserva")
        assert cursor.fetchone()["cantidad"] == 1


@pytest.mark.parametrize(
    "rol,estado", [("socio", 403), ("recepcion", 200), ("administracion", 200), ("entrenador", 200)]
)
def test_lista_por_rol_minima_y_socio_no_asignado(reservas, rol, estado):
    app, cliente, clase, socios, _, _ = reservas
    for socio in socios[:2]:
        assert solicitar(cliente, clase, socio).status_code == 201
    with app.app_context(), transaccion() as cursor:
        cursor.execute(
            "UPDATE asignaciones_entrenador SET hasta='2026-10-26' WHERE socio_id=%s", (desde_texto(socios[0]).bytes,)
        )
    entrar(cliente, rol)
    respuesta = cliente.get(f"/api/clases/{clase}/2026-10-27/reservas")
    assert respuesta.status_code == estado
    if estado == 200:
        lista = respuesta.get_json()["reservas"]
        assert len(lista) == 2
        assert all(set(r) == {"nombre", "estado", "posicion"} for r in lista)
        assert [r["estado"] for r in lista] == ["con_lugar", "en_espera"]
        assert [r["posicion"] for r in lista] == [None, 1]
    if rol == "entrenador":
        for ruta in (
            f"/api/socios/{socios[0]}/ficha",
            f"/api/entrenador/socios/{socios[0]}",
            f"/api/socios/{socios[0]}/perfil",
            f"/api/entrenamiento/socios/{socios[0]}/propuesta",
        ):
            assert cliente.get(ruta).status_code == 403
        from gimnasio.permisos.servicio import tiene_asignacion_vigente

        with app.app_context(), transaccion() as cursor:
            assert not tiene_asignacion_vigente(
                cursor, desde_texto(socios[0]), desde_texto(reservas[4]["entrenador_id"])
            )


def test_entrenador_actual_de_otra_clase_no_ve_lista(reservas):
    app, cliente, clase, _, _, _ = reservas
    from gimnasio.permisos.servicio import crear_usuario

    with app.app_context(), transaccion() as cursor:
        otro = crear_usuario(cursor, {"nombre": "Otro", "apellido": "Ficticio", "cedula": "9911223"}, "entrenador")
    entrar(cliente, "entrenador")
    assert agenda(cliente)
    assert cliente.get(f"/api/clases/{clase}/2026-10-27/reservas").status_code == 200
    with app.app_context(), transaccion() as cursor:
        cursor.execute("UPDATE clases SET entrenador_id=%s WHERE id=%s", (otro.bytes, desde_texto(clase).bytes))
    assert cliente.get(f"/api/clases/{clase}/2026-10-27/reservas").status_code == 403
    assert agenda(cliente) == []
    assert solicitar(cliente, clase).status_code == 403


def test_agenda_y_lista_consultas_constantes(reservas, monkeypatch):
    app, cliente, clase, socios, _, autor = reservas
    for socio in socios:
        assert solicitar(cliente, clase, socio).status_code == 201
    consultas = []

    @contextmanager
    def contar():
        with transaccion() as cursor:
            ejecutar = cursor.execute

            def ejecutar_contando(*args, **kwargs):
                consultas.append(args[0])
                return ejecutar(*args, **kwargs)

            monkeypatch.setattr(cursor, "execute", ejecutar_contando)
            yield cursor

    monkeypatch.setattr(servicio, "transaccion", contar)
    with app.app_context():
        assert len(servicio.agenda(autor)["ocurrencias"]) == 2
        assert len(consultas) == 4
        consultas.clear()
        assert len(servicio.listar_reservas(clase, "2026-10-27", autor)["reservas"]) == 4
        assert len(consultas) == 2  # Una consulta de alcance y una para toda la lista.
