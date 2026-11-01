"""Las restricciones de cada sesión se filtran por su inicio, también al volver a consentir."""

from datetime import timedelta

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import nuevo_id
from gimnasio.entrenamiento import repositorio, servicio
from gimnasio.salud import servicio as salud
from pruebas.test_entrenamiento_api import alternativas_api as alternativas_api
from pruebas.test_entrenamiento_api import entrenamiento_api as entrenamiento_api
from pruebas.test_salud import guardar
from pruebas.test_salud_condiciones import escribir

pytestmark = pytest.mark.bd


@pytest.fixture
def sesiones_salud(alternativas_api):
    datos = alternativas_api
    datos.socio = str(datos.usuarios["socio"])
    datos.ruta = f"/api/socios/{datos.socio}/salud"
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT ejercicio_id FROM ejercicios_planificados LIMIT 1")
        datos.original = cursor.fetchone()["ejercicio_id"]
        for zona in ("rodillas", "gluteos"):
            cursor.execute("INSERT INTO zonas_ejercicio VALUES (%s,%s)", (datos.original, zona))
        for alternativa in datos.alternativas:
            cursor.execute("INSERT INTO zonas_ejercicio VALUES (%s,'gluteos')", (alternativa.bytes,))
    assert guardar(datos.cliente()).status_code == 200
    return datos


def restringir(datos, **objetivo):
    respuesta = escribir(
        datos.cliente("entrenador"),
        datos.ruta + "/restricciones",
        {
            "descripcion": "Restricción ficticia",
            **objetivo,
        },
    )
    assert respuesta.status_code == 201, respuesta.json
    return respuesta.json["restriccion_id"]


def test_traducir_condicion_sustituye_en_la_propuesta_siguiente(sesiones_salud):
    from pruebas.test_salud_condiciones import declarar, motivos

    datos = sesiones_salud
    cid = declarar(datos)
    assert motivos(datos)
    restringir(datos, zona="rodillas", condicion_id=cid)
    assert motivos(datos) == []
    propuesta = datos.cliente().get("/api/entrenamiento/propuesta").json
    assert all(e["ejercicio_hecho_id"] == str(datos.alternativas[0]) for e in propuesta["ejercicios"])


def iniciar(datos):
    with datos.app.app_context():
        identificador = str(nuevo_id())
    datos.reloj.avanzar(timedelta(seconds=1))
    propuesta = datos.cliente().get("/api/entrenamiento/propuesta").json
    cuerpo = {"id": identificador, "sesion_planificada_id": propuesta["sesion_planificada"]["id"]}
    assert escribir(datos.cliente(), "/api/entrenamiento/sesiones", cuerpo).status_code == 201
    return identificador, cuerpo


@pytest.mark.parametrize("levantar", [False, True])
def test_restriccion_a_mitad_de_sesion_con_dolor_no_cambia_lectura_reintento_ni_consentimiento(
    sesiones_salud, levantar
):
    datos = sesiones_salud
    cliente = datos.cliente()
    if levantar:
        rid = restringir(datos, ejercicio_id=str(datos.alternativas[0]))
    sid, cuerpo = iniciar(datos)
    ruta = f"/api/entrenamiento/sesiones/{sid}"
    with datos.app.app_context():
        did, serie_id = str(nuevo_id()), str(nuevo_id())
    assert (
        escribir(
            cliente,
            ruta + "/dolores",
            {
                "id": did,
                "ejercicio_planificado_id": str(datos.ejercicios[0][0]),
                "zonas": ["rodillas"],
            },
        ).status_code
        == 201
    )
    hecha = str(datos.alternativas[1 if levantar else 0])
    assert (
        escribir(
            cliente,
            ruta + "/series",
            {
                "id": serie_id,
                "ejercicio_planificado_id": str(datos.ejercicios[0][0]),
                "ejercicio_hecho_id": hecha,
                "repeticiones": 10,
                "carga": "20.50",
            },
        ).status_code
        == 201
    )
    antes = cliente.get(ruta).json
    assert antes["ejercicios"][0]["ejercicio_hecho_id"] == hecha
    ruta_alternativas = ruta + f"/ejercicios/{datos.ejercicios[0][0]}/alternativas"
    alternativas = cliente.get(ruta_alternativas).json["alternativas"]
    datos.reloj.avanzar(timedelta(seconds=1))
    if levantar:
        assert (
            escribir(datos.cliente("entrenador"), datos.ruta + f"/restricciones/{rid}/levantar", {}).status_code == 200
        )
    else:
        restringir(datos, ejercicio_id=str(datos.alternativas[0]))
    for otorgado in (None, False, True):
        if otorgado is not None:
            datos.reloj.avanzar(timedelta(seconds=1))
            assert guardar(cliente, otorgado).status_code == 200
        assert escribir(cliente, "/api/entrenamiento/sesiones", cuerpo).status_code == 201
        if otorgado is not False:
            assert cliente.get(ruta_alternativas).json["alternativas"] == alternativas
        despues = cliente.get(ruta).json
        for campo in ("series", "sustituciones", "prescripcion_efectiva"):
            assert despues[campo] == antes[campo]
        assert [{k: v for k, v in e.items() if k != "explicacion"} for e in despues["ejercicios"]] == [
            {k: v for k, v in e.items() if k != "explicacion"} for e in antes["ejercicios"]
        ]
    # Escribir otro dolor también conserva las restricciones de inicio en la prescripción ajustada.
    with datos.app.app_context():
        did = str(nuevo_id())
    assert (
        escribir(
            cliente,
            ruta + "/dolores",
            {
                "id": did,
                "ejercicio_planificado_id": str(datos.ejercicios[0][0]),
                "zonas": ["rodillas"],
            },
        ).status_code
        == 201
    )
    assert cliente.get(ruta).json["ejercicios"] == antes["ejercicios"]
    with datos.app.app_context():
        chequeo = str(nuevo_id())
    assert (
        escribir(
            cliente,
            "/api/entrenamiento/chequeos",
            {
                "id": chequeo,
                "sueno": 5,
                "energia": 5,
                "zonas": ["rodillas"],
            },
        ).status_code
        == 201
    )
    propuesta = cliente.get("/api/entrenamiento/propuesta").json
    assert propuesta["ejercicios"][0]["ejercicio_hecho_id"] == str(datos.alternativas[0 if levantar else 1])


def test_restriccion_sin_alternativa_queda_pendiente_y_en_bandeja(sesiones_salud):
    datos = sesiones_salud
    cliente = datos.cliente()
    registrada_en = datos.reloj.ahora().isoformat()
    rid = restringir(datos, patron_movimiento="sentadilla")
    propuesta = cliente.get("/api/entrenamiento/propuesta").json
    assert all(e["no_disponible"] and e["pendiente"] == 2 for e in propuesta["ejercicios"])
    for dias in (0, 1):
        datos.reloj.avanzar(timedelta(days=dias))
        bandeja = datos.cliente("entrenador").get("/api/entrenador/bandeja")
        assert bandeja.status_code == 200
        motivos = [
            m
            for g in bandeja.json["grupos"]
            for s in g["socios"]
            for m in s["motivos"]
            if m["tipo"] == "ejercicio_sin_alternativa"
        ]
        assert motivos
        assert all(m["fecha"] == registrada_en for m in motivos)
    sid, _ = iniciar(datos)
    with datos.app.app_context():
        serie_id = str(nuevo_id())
    assert (
        escribir(
            cliente,
            f"/api/entrenamiento/sesiones/{sid}/series",
            {
                "id": serie_id,
                "ejercicio_planificado_id": str(datos.ejercicios[0][0]),
                "repeticiones": 10,
                "carga": "20.50",
            },
        ).status_code
        == 409
    )
    siguiente = cliente.get("/api/entrenamiento/propuesta").json
    assert siguiente["sesion_planificada"] == propuesta["sesion_planificada"]
    assert all(e["pendiente"] == 2 for e in siguiente["ejercicios"])
    datos.reloj.avanzar(timedelta(seconds=1))
    assert escribir(datos.cliente("entrenador"), datos.ruta + f"/restricciones/{rid}/levantar", {}).status_code == 200
    assert all(not e["no_disponible"] for e in cliente.get("/api/entrenamiento/propuesta").json["ejercicios"])


def test_bandeja_usa_la_restriccion_vigente_mas_antigua_que_excluye_el_ejercicio(sesiones_salud, monkeypatch):
    from mysql.connector.cursor import MySQLCursor

    datos = sesiones_salud
    levantada = restringir(datos, patron_movimiento="sentadilla")
    restringir(datos, zona="hombros")
    datos.reloj.avanzar(timedelta(days=1))
    assert (
        escribir(datos.cliente("entrenador"), datos.ruta + f"/restricciones/{levantada}/levantar", {}).status_code
        == 200
    )
    registrada_en = datos.reloj.ahora().isoformat()
    restringir(datos, zona="gluteos")
    datos.reloj.avanzar(timedelta(days=1))
    restringir(datos, patron_movimiento="sentadilla")
    consultas = []
    ejecutar = MySQLCursor.execute

    def contar(cursor, sql, *args, **opciones):
        if "FROM restricciones_salud" in sql:
            consultas.append(sql)
        return ejecutar(cursor, sql, *args, **opciones)

    monkeypatch.setattr(MySQLCursor, "execute", contar)
    bandeja = datos.cliente("entrenador").get("/api/entrenador/bandeja")
    assert bandeja.status_code == 200
    motivos = [m for g in bandeja.json["grupos"] for s in g["socios"] for m in s["motivos"]]
    assert motivos
    assert all(m["fecha"] == registrada_en for m in motivos)
    assert len(consultas) == 1


def test_sesiones_pasadas_proyectan_igual_y_restricciones_se_leen_una_vez(sesiones_salud, monkeypatch):
    datos = sesiones_salud
    cliente = datos.cliente()
    sid, _ = iniciar(datos)
    with datos.app.app_context():
        dolor = str(nuevo_id())
    assert (
        escribir(
            cliente,
            f"/api/entrenamiento/sesiones/{sid}/dolores",
            {
                "id": dolor,
                "ejercicio_planificado_id": str(datos.ejercicios[0][0]),
                "zonas": ["rodillas"],
            },
        ).status_code
        == 201
    )
    # Varias sesiones pasadas con la misma prescripción y dolor, para medir las lecturas.
    propuesta = cliente.get("/api/entrenamiento/propuesta").json
    with datos.app.app_context(), transaccion() as cursor:
        socio = datos.usuarios["socio"]
        for _ in range(3):
            realizada = nuevo_id()
            repositorio.insertar_sesion(cursor, realizada, socio, datos.sesiones[0], datos.reloj.ahora())
            repositorio.insertar_prescripcion(cursor, nuevo_id(), realizada, propuesta, datos.reloj.ahora())
            repositorio.insertar_dolor(cursor, nuevo_id(), socio, "rodillas", datos.reloj.ahora(), sesion_id=realizada)
    proyecciones = []
    proyectar = servicio.proyectar_dolor

    def registrar(*args, **kwargs):
        resultado = proyectar(*args, **kwargs)
        proyecciones.append(resultado)
        return resultado

    monkeypatch.setattr(servicio, "proyectar_dolor", registrar)
    assert cliente.get("/api/entrenamiento/propuesta").status_code == 200
    antes = proyecciones.copy()
    assert len(antes) == 4
    datos.reloj.avanzar(timedelta(seconds=1))
    rid = restringir(datos, zona="gluteos")
    leer = salud.repositorio.restricciones_con_levantamiento
    consultas = []

    def contar(*args):
        consultas.append(True)
        return leer(*args)

    monkeypatch.setattr(salud.repositorio, "restricciones_con_levantamiento", contar)
    proyecciones.clear()
    assert cliente.get("/api/entrenamiento/propuesta").status_code == 200
    assert proyecciones == antes
    assert len(consultas) == 1
    datos.reloj.avanzar(timedelta(seconds=1))
    assert escribir(datos.cliente("entrenador"), datos.ruta + f"/restricciones/{rid}/levantar", {}).status_code == 200
    proyecciones.clear()
    assert cliente.get("/api/entrenamiento/propuesta").status_code == 200
    assert proyecciones == antes
