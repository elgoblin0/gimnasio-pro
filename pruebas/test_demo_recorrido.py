"""Semilla del recorrido: identidades estables y hechos de prueba separados del socio principal."""

from datetime import timedelta
from uuid import uuid4

import pytest

from gimnasio import crear_app
from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.ids import desde_bytes, nuevo_id
from gimnasio.demo import servicio as demo
from gimnasio.entrenamiento.servicio import consultar_propuesta


def test_identificadores_ficticios_estables_y_uuid7(reloj_fijo):
    ahora = reloj_fijo.ahora()
    assert demo.id_ficticio(1, ahora) == demo.id_ficticio(1, ahora)
    assert demo.id_ficticio(1, ahora).version == 7
    assert demo.id_ficticio(1, ahora) != demo.id_ficticio(2, ahora)
    assert demo.id_ficticio(1, ahora) != demo.id_ficticio(1, ahora + timedelta(days=1))


def test_reinicio_fuera_de_demo_se_rechaza_antes_de_acceder_a_la_base(monkeypatch):
    def no_acceder():
        pytest.fail("El reinicio fuera de demo no debe acceder a la base.")

    monkeypatch.setattr(demo, "transaccion", no_acceder)
    with (
        crear_app({"ENTORNO": "prueba", "MODO_DEMO": False}).app_context(),
        pytest.raises(ErrorDeDominio, match="modo demo"),
    ):
        demo.reiniciar()


@pytest.fixture
def recorrido(app_con_bd):
    app_con_bd.config["MODO_DEMO"] = True
    with app_con_bd.app_context():
        demo.reiniciar()

    def usuarios():
        with app_con_bd.app_context(), transaccion() as cursor:
            cursor.execute(
                "SELECT u.id,u.rol,p.nombre,u.es_demo FROM usuarios u "
                "JOIN personas p ON p.id=u.persona_id ORDER BY u.id"
            )
            return cursor.fetchall()

    filas = usuarios()
    principal = next(f for f in filas if f["rol"] == "socio" and f["es_demo"])
    recepcion = next(f for f in filas if f["rol"] == "recepcion")
    with app_con_bd.app_context(), transaccion() as cursor:
        cursor.execute("SELECT id FROM sedes")
        sede = desde_bytes(cursor.fetchone()["id"])

    def cliente(usuario):
        cliente = app_con_bd.test_client()
        with cliente.session_transaction() as sesion:
            sesion["usuario_id"] = str(desde_bytes(usuario["id"]))
        return cliente

    return app_con_bd, principal, recepcion, sede, filas, cliente


def escribir(cliente, ruta, cuerpo):
    return cliente.post(ruta, json=cuerpo, headers={"X-Gimnasio": "1", "Idempotency-Key": str(uuid4())})


@pytest.mark.bd
def test_principal_pendiente_sin_visita_reingresa_y_respeta_plan(recorrido, reloj_fijo):
    app, principal, recepcion, sede, _, cliente = recorrido
    socio_id = str(desde_bytes(principal["id"]))
    con_socio = cliente(principal)
    con_recepcion = cliente(recepcion)
    propuesta = con_socio.get("/api/entrenamiento/propuesta").json
    assert propuesta["sesion_planificada"] is not None
    assert all(e["realizado"] == 0 and e["pendiente"] == e["objetivos"]["series"] for e in propuesta["ejercicios"])
    assert con_recepcion.get("/api/visitas?abiertas=1").json == {"visitas": []}
    assert con_recepcion.get("/api/ocupacion").json["ocupacion_registrada"] == 0
    for _ in range(2):
        entrada = str(nuevo_id(reloj_fijo))
        assert (
            escribir(
                con_recepcion, "/api/entradas", {"id": entrada, "socio_id": socio_id, "sede_id": str(sede)}
            ).status_code
            == 201
        )
        assert (
            escribir(
                con_recepcion, "/api/salidas", {"id": str(nuevo_id(reloj_fijo)), "entrada_id": entrada}
            ).status_code
            == 201
        )
    assert con_socio.get("/api/entrenamiento/propuesta").json == propuesta
    creada = escribir(
        con_socio,
        "/api/entrenamiento/sesiones",
        {"id": str(nuevo_id(reloj_fijo)), "sesion_planificada_id": propuesta["sesion_planificada"]["id"]},
    )
    sesion = creada.json["sesion_realizada"]["id"]
    ejercicio = next(e for e in propuesta["ejercicios"] if "carga" in e["medidas_aplicables"])
    assert (
        escribir(
            con_socio,
            f"/api/entrenamiento/sesiones/{sesion}/series",
            {
                "id": str(nuevo_id(reloj_fijo)),
                "ejercicio_planificado_id": ejercicio["id"],
                "repeticiones": 10,
                "carga": "20.50",
            },
        ).status_code
        == 201
    )
    parcial = con_socio.get("/api/entrenamiento/propuesta").json
    assert parcial["sesion_planificada"] == propuesta["sesion_planificada"]
    assert [e["objetivos"] for e in parcial["ejercicios"]] == [e["objetivos"] for e in propuesta["ejercicios"]]
    assert (
        sum(e["pendiente"] for e in parcial["ejercicios"]) == sum(e["pendiente"] for e in propuesta["ejercicios"]) - 1
    )
    with app.app_context():
        demo.reiniciar()
    assert con_socio.get("/api/entrenamiento/propuesta").json == propuesta
    assert con_recepcion.get("/api/visitas?abiertas=1").json == {"visitas": []}


@pytest.mark.bd
def test_semilla_ofrece_parcial_sin_programa_y_membresia_vencida(recorrido, reloj_fijo):
    app, _, recepcion, sede, filas, cliente = recorrido
    propuestas = []
    with app.app_context():
        for fila in filas:
            if fila["rol"] != "socio":
                continue
            usuario = {"id": str(desde_bytes(fila["id"])), "rol": "socio"}
            propuestas.append(consultar_propuesta(usuario["id"], usuario))
    assert any(
        p["sesion_planificada"] and any(e["realizado"] > 0 and e["pendiente"] > 0 for e in p["ejercicios"])
        for p in propuestas
    )
    assert any(p["sesion_planificada"] is None and p["explicacion"][0]["regla"] == "sin_programa" for p in propuestas)
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT socio_id FROM membresias WHERE hasta < '2026-10-27'")
        vencida = desde_bytes(cursor.fetchone()["socio_id"])
    assert (
        escribir(
            cliente(recepcion),
            "/api/entradas",
            {"id": str(nuevo_id(reloj_fijo)), "socio_id": str(vencida), "sede_id": str(sede)},
        ).status_code
        == 422
    )


@pytest.mark.bd
def test_ids_dominio_y_hechos_de_semilla_se_reponen_iguales(recorrido, reloj_fijo):
    app, principal, recepcion, sede, _, cliente = recorrido

    def instantanea():
        with app.app_context(), transaccion() as cursor:
            resultado = {}
            for tabla in (
                "sedes",
                "personas",
                "programas_entrenamiento",
                "sesiones_planificadas",
                "ejercicios_planificados",
                "sesiones_realizadas",
                "series_realizadas",
                "asignaciones_entrenador",
                "consentimientos",
                "membresias",
            ):
                cursor.execute(f"SELECT * FROM {tabla} ORDER BY id")
                resultado[tabla] = cursor.fetchall()
            cursor.execute("SELECT id,persona_id,rol,es_demo,activo,creado_en,actualizado_en FROM usuarios ORDER BY id")
            resultado["usuarios"] = cursor.fetchall()
            return resultado

    antes = instantanea()
    assert (
        escribir(
            cliente(recepcion),
            "/api/entradas",
            {"id": str(nuevo_id(reloj_fijo)), "socio_id": str(desde_bytes(principal["id"])), "sede_id": str(sede)},
        ).status_code
        == 201
    )
    with app.app_context():
        demo.reiniciar()
    assert instantanea() == antes
    with app.app_context(), transaccion() as cursor:
        for tabla in ("solicitudes_idempotentes", "entradas", "salidas"):
            cursor.execute(f"SELECT COUNT(*) AS cantidad FROM {tabla}")
            assert cursor.fetchone()["cantidad"] == 0
        cursor.execute("SELECT COUNT(*) AS cantidad FROM migraciones_aplicadas")
        assert cursor.fetchone()["cantidad"] == 14


@pytest.mark.bd
def test_desplazar_reloj_y_reiniciar_mantiene_recorrido(recorrido, reloj_fijo):
    app, _, _, _, _, cliente = recorrido
    reloj_fijo.avanzar(timedelta(days=9))
    with app.app_context():
        demo.reiniciar()
        with transaccion() as cursor:
            cursor.execute("SELECT id FROM usuarios WHERE rol='socio' AND es_demo=TRUE")
            principal = cursor.fetchone()
            cursor.execute("SELECT id FROM usuarios WHERE rol='recepcion' AND es_demo=TRUE")
            recepcion = cursor.fetchone()
            cursor.execute("SELECT id FROM sedes")
            sede = desde_bytes(cursor.fetchone()["id"])
    assert cliente(principal).get("/api/entrenamiento/propuesta").json["sesion_planificada"] is not None
    assert (
        escribir(
            cliente(recepcion),
            "/api/entradas",
            {"id": str(nuevo_id(reloj_fijo)), "socio_id": str(desde_bytes(principal["id"])), "sede_id": str(sede)},
        ).status_code
        == 201
    )


@pytest.mark.bd
def test_semilla_permite_aforo_lleno_y_admision_tras_liberar_lugar(recorrido, reloj_fijo):
    app, _, recepcion, sede, filas, cliente = recorrido
    socios = [f for f in filas if f["rol"] == "socio"][:3]
    con_recepcion = cliente(recepcion)
    with app.app_context(), transaccion() as cursor:
        cursor.execute("UPDATE sedes SET aforo_maximo=2")
    entradas = []
    for socio in socios[:2]:
        entrada = str(nuevo_id(reloj_fijo))
        entradas.append(entrada)
        assert (
            escribir(
                con_recepcion,
                "/api/entradas",
                {"id": entrada, "socio_id": str(desde_bytes(socio["id"])), "sede_id": str(sede)},
            ).status_code
            == 201
        )
    tercero = {"id": str(nuevo_id(reloj_fijo)), "socio_id": str(desde_bytes(socios[2]["id"])), "sede_id": str(sede)}
    assert escribir(con_recepcion, "/api/entradas", tercero).status_code == 409
    assert con_recepcion.get("/api/ocupacion").json["ocupacion_registrada"] == 2
    assert len(con_recepcion.get("/api/visitas?abiertas=1").json["visitas"]) == 2
    assert (
        escribir(
            con_recepcion, "/api/salidas", {"id": str(nuevo_id(reloj_fijo)), "entrada_id": entradas[0]}
        ).status_code
        == 201
    )
    assert escribir(con_recepcion, "/api/entradas", tercero | {"id": str(nuevo_id(reloj_fijo))}).status_code == 201
    assert con_recepcion.get("/api/ocupacion").json["ocupacion_registrada"] == 2


@pytest.mark.bd
def test_completar_secuencia_de_semilla_no_reinicia_sola(recorrido, reloj_fijo):
    _, principal, _, _, _, cliente = recorrido
    con_socio = cliente(principal)
    planificadas = []
    for _ in range(2):
        propuesta = con_socio.get("/api/entrenamiento/propuesta").json
        assert propuesta["sesion_planificada"] is not None
        planificadas.append(propuesta["sesion_planificada"]["id"])
        respuesta = escribir(
            con_socio,
            "/api/entrenamiento/sesiones",
            {"id": str(nuevo_id(reloj_fijo)), "sesion_planificada_id": propuesta["sesion_planificada"]["id"]},
        )
        assert respuesta.status_code == 201
        sesion = respuesta.json["sesion_realizada"]["id"]
        for ejercicio in propuesta["ejercicios"]:
            for _ in range(ejercicio["pendiente"]):
                cuerpo = {
                    "id": str(nuevo_id(reloj_fijo)),
                    "ejercicio_planificado_id": ejercicio["id"],
                    **{
                        m: ejercicio["objetivos"]["repeticiones_minimas" if m == "repeticiones" else m]
                        for m in ejercicio["medidas_aplicables"]
                    },
                }
                assert escribir(con_socio, f"/api/entrenamiento/sesiones/{sesion}/series", cuerpo).status_code == 201
    assert len(set(planificadas)) == 2
    reloj_fijo.avanzar(timedelta(days=1))
    propuesta = con_socio.get("/api/entrenamiento/propuesta").json
    assert propuesta["sesion_planificada"] is None
    assert propuesta["explicacion"][0]["regla"] == "secuencia_realizada"
