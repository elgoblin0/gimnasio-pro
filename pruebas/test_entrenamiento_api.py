"""Propuesta real, programa intacto y alcance por rol/asignación sobre MySQL."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier, Event
from types import SimpleNamespace
from uuid import uuid4

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import a_bytes, desde_bytes, desde_texto, nuevo_id
from gimnasio.entrenamiento import repositorio
from gimnasio.permisos.servicio import crear_usuario

pytestmark = pytest.mark.bd


@pytest.fixture
def entrenamiento_api(app_con_bd, reloj_fijo):
    datos = SimpleNamespace(app=app_con_bd, reloj=reloj_fijo, usuarios={}, sesiones=[], ejercicios=[])
    with datos.app.app_context(), transaccion() as cursor:
        datos.sede = nuevo_id(reloj_fijo)
        cursor.execute(
            "INSERT INTO sedes (id,nombre,aforo_maximo,actualizada_en) VALUES (%s,'Sede ficticia',60,%s)",
            (a_bytes(datos.sede), reloj_fijo.ahora()),
        )
        for indice, (nombre, rol) in enumerate(
            (
                ("socio", "socio"),
                ("ajeno", "socio"),
                ("entrenador", "entrenador"),
                ("otro", "entrenador"),
                ("recepcion", "recepcion"),
                ("administracion", "administracion"),
            )
        ):
            datos.usuarios[nombre] = crear_usuario(
                cursor, {"nombre": nombre, "apellido": "Ficticio", "cedula": str(9900600 + indice)}, rol
            )
        datos.asignacion = nuevo_id(reloj_fijo)
        cursor.execute(
            "INSERT INTO asignaciones_entrenador (id,socio_id,entrenador_id,desde) VALUES (%s,%s,%s,%s)",
            (
                a_bytes(datos.asignacion),
                a_bytes(datos.usuarios["socio"]),
                a_bytes(datos.usuarios["entrenador"]),
                reloj_fijo.ahora(),
            ),
        )
        datos.programa = nuevo_id(reloj_fijo)
        cursor.execute(
            "INSERT INTO programas_entrenamiento (id,socio_id,version,creado_en) VALUES (%s,%s,1,%s)",
            (a_bytes(datos.programa), a_bytes(datos.usuarios["socio"]), reloj_fijo.ahora()),
        )
        catalogo = nuevo_id(reloj_fijo)
        cursor.execute(
            "INSERT INTO ejercicios (id,nombre,medidas_aplicables,actualizada_en) "
            "VALUES (%s,'Sentadilla ficticia','[\"repeticiones\",\"carga\"]',%s)",
            (a_bytes(catalogo), reloj_fijo.ahora()),
        )
        for posicion in (1, 2):
            sesion = nuevo_id(reloj_fijo)
            datos.sesiones.append(sesion)
            cursor.execute(
                "INSERT INTO sesiones_planificadas (id,programa_id,posicion,nombre) "
                "VALUES (%s,%s,%s,'Sesión ficticia')",
                (a_bytes(sesion), a_bytes(datos.programa), posicion),
            )
            ejercicios = []
            for orden in (1, 2):
                ejercicio = nuevo_id(reloj_fijo)
                ejercicios.append(ejercicio)
                cursor.execute(
                    "INSERT INTO ejercicios_planificados "
                    "(id,sesion_planificada_id,ejercicio_id,posicion,series,"
                    "repeticiones_minimas,repeticiones_maximas,carga) "
                    "VALUES (%s,%s,%s,%s,2,10,10,20.50)",
                    (a_bytes(ejercicio), a_bytes(sesion), a_bytes(catalogo), orden),
                )
            datos.ejercicios.append(ejercicios)

    def cliente(nombre="socio"):
        cliente = datos.app.test_client()
        with cliente.session_transaction() as sesion:
            sesion["usuario_id"] = str(datos.usuarios[nombre])
        return cliente

    datos.cliente = cliente
    return datos


def registrar(datos, sesion, ejercicio, cantidad=1):
    with datos.app.app_context(), transaccion() as cursor:
        realizada = nuevo_id(datos.reloj)
        repositorio.insertar_sesion(
            cursor, realizada, datos.usuarios["socio"], datos.sesiones[sesion], datos.reloj.ahora()
        )
        for _ in range(cantidad):
            repositorio.insertar_serie(
                cursor,
                nuevo_id(datos.reloj),
                realizada,
                datos.ejercicios[sesion][ejercicio],
                datos.usuarios["socio"],
                datos.reloj.ahora(),
                repeticiones=8,
                carga=Decimal("15.25"),
            )


def test_propuesta_conserva_plan_y_distingue_posiciones_del_mismo_ejercicio(entrenamiento_api):
    datos = entrenamiento_api
    antes = datos.cliente().get("/api/entrenamiento/propuesta")
    assert antes.status_code == 200
    antes = antes.json
    assert antes["sesion_planificada"]["id"] == str(datos.sesiones[0])
    assert [e["pendiente"] for e in antes["ejercicios"]] == [2, 2]
    registrar(datos, 0, 0)
    despues = datos.cliente().get("/api/entrenamiento/propuesta").json
    assert [e["objetivos"] for e in despues["ejercicios"]] == [e["objetivos"] for e in antes["ejercicios"]]
    assert [e["realizado"] for e in despues["ejercicios"]] == [1, 0]
    assert [e["pendiente"] for e in despues["ejercicios"]] == [1, 2]
    assert despues["ejercicios"][0]["objetivos"]["carga"] == "20.50"
    assert despues["version_reglas"] == "1.0.0"
    assert "sin ajustes" in despues["explicacion"][-1]["datos"]["explicacion"]
    assert despues == datos.cliente().get("/api/entrenamiento/propuesta").json
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT COUNT(*) AS cantidad FROM series_realizadas")
        assert cursor.fetchone()["cantidad"] == 1
        cursor.execute("SELECT carga FROM ejercicios_planificados ORDER BY id")
        assert all(fila["carga"] == Decimal("20.50") for fila in cursor.fetchall())
        cursor.execute("SELECT COUNT(*) AS cantidad FROM consentimientos")
        assert cursor.fetchone()["cantidad"] == 0


def test_secuencia_terminada_no_reinicia_y_sin_programa_no_inventa(entrenamiento_api):
    datos = entrenamiento_api
    for sesion in (0, 1):
        for ejercicio in (0, 1):
            registrar(datos, sesion, ejercicio, 2)
        propuesta = datos.cliente().get("/api/entrenamiento/propuesta").json
        assert (
            propuesta["sesion_planificada"] is None
            if sesion == 1
            else propuesta["sesion_planificada"]["id"] == str(datos.sesiones[1])
        )
    assert propuesta["explicacion"][0]["regla"] == "secuencia_realizada"
    sin_programa = datos.cliente("ajeno").get("/api/entrenamiento/propuesta").json
    assert sin_programa["sesion_planificada"] is None
    assert sin_programa["explicacion"][0]["regla"] == "sin_programa"


@pytest.mark.parametrize("rol", ["recepcion", "administracion", "entrenador"])
def test_propuesta_propia_rechaza_otros_roles(entrenamiento_api, rol):
    assert entrenamiento_api.cliente(rol).get("/api/entrenamiento/propuesta").status_code == 403


def test_entrenador_solo_ve_asignacion_vigente_y_recursos_existentes(entrenamiento_api):
    datos = entrenamiento_api
    ruta = f"/api/entrenamiento/socios/{datos.usuarios['socio']}/propuesta"
    assert datos.cliente("entrenador").get(ruta).status_code == 200
    for nombre in ("otro", "socio", "recepcion", "administracion"):
        assert datos.cliente(nombre).get(ruta).status_code == 403
    assert (
        datos.cliente("entrenador").get(f"/api/entrenamiento/socios/{nuevo_id(datos.reloj)}/propuesta").status_code
        == 404
    )
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute(
            "UPDATE asignaciones_entrenador SET hasta=%s WHERE id=%s", (datos.reloj.ahora(), a_bytes(datos.asignacion))
        )
    assert datos.cliente("entrenador").get(ruta).status_code == 403


def test_visita_sin_series_no_cambia_propuesta(entrenamiento_api):
    from gimnasio.visitas import repositorio as visitas

    datos = entrenamiento_api
    antes = datos.cliente().get("/api/entrenamiento/propuesta").json
    with datos.app.app_context(), transaccion() as cursor:
        entrada = nuevo_id(datos.reloj)
        visitas.insertar_entrada(
            cursor, entrada, datos.usuarios["socio"], datos.sede, datos.usuarios["recepcion"], datos.reloj.ahora()
        )
        visitas.insertar_salida(
            cursor, nuevo_id(datos.reloj), entrada, datos.usuarios["recepcion"], datos.reloj.ahora()
        )
    assert datos.cliente().get("/api/entrenamiento/propuesta").json == antes


def test_version_nueva_con_cardio_no_mezcla_hechos_de_version_anterior(entrenamiento_api):
    datos = entrenamiento_api
    registrar(datos, 0, 0)
    with datos.app.app_context(), transaccion() as cursor:
        programa, sesion, ejercicio, planificado = (nuevo_id(datos.reloj) for _ in range(4))
        cursor.execute(
            "INSERT INTO programas_entrenamiento (id,socio_id,version,creado_en) VALUES (%s,%s,2,%s)",
            (a_bytes(programa), a_bytes(datos.usuarios["socio"]), datos.reloj.ahora()),
        )
        cursor.execute(
            "INSERT INTO sesiones_planificadas (id,programa_id,posicion,nombre) VALUES (%s,%s,1,'Cardio ficticio')",
            (a_bytes(sesion), a_bytes(programa)),
        )
        cursor.execute(
            "INSERT INTO ejercicios (id,nombre,medidas_aplicables,actualizada_en) "
            "VALUES (%s,'Carrera ficticia','[\"duracion\",\"distancia\"]',%s)",
            (a_bytes(ejercicio), datos.reloj.ahora()),
        )
        cursor.execute(
            "INSERT INTO ejercicios_planificados "
            "(id,sesion_planificada_id,ejercicio_id,posicion,series,duracion,distancia) "
            "VALUES (%s,%s,%s,1,1,120,1500.25)",
            (a_bytes(planificado), a_bytes(sesion), a_bytes(ejercicio)),
        )
    propuesta = datos.cliente().get("/api/entrenamiento/propuesta").json
    assert propuesta["sesion_planificada"]["id"] == str(sesion)
    ejercicio = propuesta["ejercicios"][0]
    assert ejercicio["realizado"] == 0
    assert ejercicio["pendiente"] == 1
    assert ejercicio["objetivos"] == {
        "series": 1,
        "repeticiones_minimas": None,
        "repeticiones_maximas": None,
        "rir_objetivo": None,
        "descanso": None,
        "carga": None,
        "duracion": 120,
        "distancia": "1500.25",
    }


def escribir(cliente, ruta, cuerpo, clave=None):
    return cliente.post(ruta, json=cuerpo, headers={"X-Gimnasio": "1", "Idempotency-Key": clave or str(uuid4())})


def iniciar(datos):
    sesion_id = str(nuevo_id(datos.reloj))
    respuesta = escribir(
        datos.cliente(),
        "/api/entrenamiento/sesiones",
        {"id": sesion_id, "sesion_planificada_id": str(datos.sesiones[0])},
    )
    assert respuesta.status_code == 201
    return sesion_id


def cuerpo_serie(datos):
    return {
        "id": str(nuevo_id(datos.reloj)),
        "ejercicio_planificado_id": str(datos.ejercicios[0][0]),
        "repeticiones": 10,
        "carga": "20.50",
    }


def cantidad(datos, tabla="series_realizadas"):
    assert tabla in {"series_realizadas", "sesiones_realizadas", "solicitudes_idempotentes", "entradas"}
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute(f"SELECT COUNT(*) AS cantidad FROM {tabla}")
        return cursor.fetchone()["cantidad"]


def test_escritura_real_reintentos_y_lectura_parcial(entrenamiento_api):
    datos = entrenamiento_api
    sesion = iniciar(datos)
    ruta = f"/api/entrenamiento/sesiones/{sesion}/series"
    cliente, cuerpo, clave = datos.cliente(), cuerpo_serie(datos), str(uuid4())
    assert cliente.post(ruta, json=cuerpo, headers={"X-Gimnasio": "1"}).status_code == 428
    assert escribir(cliente, ruta, cuerpo, "no-es-uuid").status_code == 422
    assert cliente.post(ruta, json=cuerpo, headers={"Idempotency-Key": clave}).status_code == 403
    primera = escribir(cliente, ruta, cuerpo, clave)
    assert primera.status_code == 201
    assert primera.json["serie_realizada"]["autor_id"] == str(datos.usuarios["socio"])
    assert escribir(cliente, ruta, cuerpo, clave).data == primera.data
    assert escribir(cliente, ruta, cuerpo | {"carga": "99"}, clave).status_code == 422
    assert escribir(cliente, ruta, cuerpo).json == primera.json
    guardada = cliente.get(f"/api/entrenamiento/sesiones/{sesion}").json
    assert guardada["series"] == [primera.json["serie_realizada"]]
    assert guardada["ejercicios"][0]["pendiente"] == 1
    assert guardada["series"][0]["carga"] == "20.50"
    assert cantidad(datos) == 1
    assert cantidad(datos, "entradas") == 0


def test_ids_ajenos_no_filtran_ni_sobrescriben(entrenamiento_api):
    datos = entrenamiento_api
    sesion = iniciar(datos)
    ruta = f"/api/entrenamiento/sesiones/{sesion}/series"
    cuerpo = cuerpo_serie(datos)
    assert escribir(datos.cliente(), ruta, cuerpo).status_code == 201
    assert datos.cliente("ajeno").get(f"/api/entrenamiento/sesiones/{sesion}").status_code == 403
    assert escribir(datos.cliente("ajeno"), ruta, cuerpo).status_code == 403
    assert (
        escribir(
            datos.cliente("ajeno"),
            "/api/entrenamiento/sesiones",
            {"id": sesion, "sesion_planificada_id": str(datos.sesiones[0])},
        ).status_code
        == 403
    )
    otra = iniciar(datos)
    assert escribir(datos.cliente(), f"/api/entrenamiento/sesiones/{otra}/series", cuerpo).status_code == 403
    assert (
        escribir(
            datos.cliente(), ruta, cuerpo_serie(datos) | {"ejercicio_planificado_id": str(datos.ejercicios[1][0])}
        ).status_code
        == 422
    )
    assert (
        escribir(
            datos.cliente(), ruta, cuerpo_serie(datos) | {"ejercicio_planificado_id": str(nuevo_id(datos.reloj))}
        ).status_code
        == 404
    )
    assert datos.cliente().get(f"/api/entrenamiento/sesiones/{nuevo_id(datos.reloj)}").status_code == 404
    assert cantidad(datos) == 1


@pytest.mark.parametrize(
    "cambios",
    [
        {"repeticiones": True},
        {"repeticiones": 0},
        {"repeticiones": 1.5},
        {"carga": float("nan")},
        {"carga": "Infinity"},
        {"carga": "-1"},
        {"carga": "1.001"},
        {"duracion": 10},
        {"autor_id": "arbitrario"},
        {"socio_id": "arbitrario"},
    ],
)
def test_api_rechaza_medidas_y_autor_arbitrarios(entrenamiento_api, cambios):
    datos = entrenamiento_api
    sesion = iniciar(datos)
    assert (
        escribir(
            datos.cliente(), f"/api/entrenamiento/sesiones/{sesion}/series", cuerpo_serie(datos) | cambios
        ).status_code
        == 422
    )
    assert cantidad(datos) == 0


def test_cardio_no_exige_medidas_de_fuerza(entrenamiento_api):
    datos = entrenamiento_api
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute('UPDATE ejercicios SET medidas_aplicables=\'["duracion","distancia"]\'')
        cursor.execute(
            "UPDATE ejercicios_planificados SET repeticiones_minimas=NULL,repeticiones_maximas=NULL,"
            "carga=NULL,duracion=120,distancia=1500.25"
        )
    sesion = iniciar(datos)
    cuerpo = {
        "id": str(nuevo_id(datos.reloj)),
        "ejercicio_planificado_id": str(datos.ejercicios[0][0]),
        "duracion": 121,
        "distancia": "1500.27",
    }
    respuesta = escribir(datos.cliente(), f"/api/entrenamiento/sesiones/{sesion}/series", cuerpo)
    assert respuesta.status_code == 201
    assert respuesta.json["serie_realizada"]["distancia"] == "1500.27"
    assert respuesta.json["serie_realizada"]["repeticiones"] is None


@pytest.mark.parametrize("rol", ["entrenador", "recepcion", "administracion"])
def test_solo_socio_registra_y_lee_su_sesion(entrenamiento_api, rol):
    datos = entrenamiento_api
    sesion = iniciar(datos)
    cliente = datos.cliente(rol)
    assert (
        escribir(
            cliente,
            "/api/entrenamiento/sesiones",
            {"id": str(nuevo_id(datos.reloj)), "sesion_planificada_id": str(datos.sesiones[0])},
        ).status_code
        == 403
    )
    assert escribir(cliente, f"/api/entrenamiento/sesiones/{sesion}/series", cuerpo_serie(datos)).status_code == 403
    assert cliente.get(f"/api/entrenamiento/sesiones/{sesion}").status_code == 403


def test_fallo_antes_de_guardar_respuesta_revierte_serie_y_clave(entrenamiento_api):
    from flask import request

    datos = entrenamiento_api
    estado = {"fallar": True}

    @datos.app.after_request
    def fallar(respuesta):
        if request.path.endswith("/series") and respuesta.status_code == 201 and estado["fallar"]:
            raise RuntimeError("fallo antes de guardar la respuesta")
        return respuesta

    sesion = iniciar(datos)
    ruta, cuerpo, clave = f"/api/entrenamiento/sesiones/{sesion}/series", cuerpo_serie(datos), str(uuid4())
    with pytest.raises(RuntimeError):
        escribir(datos.cliente(), ruta, cuerpo, clave)
    assert cantidad(datos) == 0
    assert cantidad(datos, "solicitudes_idempotentes") == 1
    estado["fallar"] = False
    assert escribir(datos.cliente(), ruta, cuerpo, clave).status_code == 201


def test_misma_clave_simultanea_sobre_serie_real(entrenamiento_api, monkeypatch):
    datos = entrenamiento_api
    sesion = iniciar(datos)
    tomada, continuar = Event(), Event()
    original = repositorio.insertar_serie

    def insertar(*argumentos, **nombrados):
        tomada.set()
        assert continuar.wait(15)
        return original(*argumentos, **nombrados)

    monkeypatch.setattr(repositorio, "insertar_serie", insertar)
    ruta, cuerpo, clave = f"/api/entrenamiento/sesiones/{sesion}/series", cuerpo_serie(datos), str(uuid4())
    with ThreadPoolExecutor(max_workers=1) as hilos:
        primera = hilos.submit(escribir, datos.cliente(), ruta, cuerpo, clave)
        try:
            assert tomada.wait(10)
            assert escribir(datos.cliente(), ruta, cuerpo, clave).status_code == 409
        finally:
            continuar.set()
        assert primera.result(timeout=15).status_code == 201
    assert escribir(datos.cliente(), ruta, cuerpo, clave).status_code == 201
    assert cantidad(datos) == 1


def test_dos_claves_mismo_id_de_serie_devuelven_registro_existente(entrenamiento_api, monkeypatch):
    datos = entrenamiento_api
    sesion = iniciar(datos)
    barrera = Barrier(2)
    original = repositorio.insertar_serie

    def insertar(*argumentos, **nombrados):
        barrera.wait(timeout=10)
        return original(*argumentos, **nombrados)

    monkeypatch.setattr(repositorio, "insertar_serie", insertar)
    ruta, cuerpo = f"/api/entrenamiento/sesiones/{sesion}/series", cuerpo_serie(datos)
    with ThreadPoolExecutor(max_workers=2) as hilos:
        respuestas = [hilos.submit(escribir, datos.cliente(), ruta, cuerpo) for _ in range(2)]
        respuestas = [r.result(timeout=15) for r in respuestas]
    assert [r.status_code for r in respuestas] == [201, 201]
    assert respuestas[0].json == respuestas[1].json
    assert cantidad(datos) == 1


def test_propuesta_devuelve_rango_y_catalogo_de_la_demo(entrenamiento_api):
    from gimnasio.comun.tipos import ZONAS_CUERPO
    from gimnasio.demo import servicio as demo

    datos = entrenamiento_api
    datos.app.config["MODO_DEMO"] = True
    with datos.app.app_context():
        demo.reiniciar()
        with transaccion() as cursor:
            cursor.execute("SELECT id FROM usuarios WHERE es_demo=TRUE AND rol='socio'")
            socio = cursor.fetchone()["id"]
    cliente = datos.app.test_client()
    with cliente.session_transaction() as sesion:
        sesion["usuario_id"] = str(desde_bytes(socio))
    respuesta = cliente.get("/api/entrenamiento/propuesta")
    assert respuesta.status_code == 200
    fuerza, cardio = respuesta.json["ejercicios"]
    assert fuerza["objetivos"] == {
        "series": 2,
        "repeticiones_minimas": 8,
        "repeticiones_maximas": 12,
        "rir_objetivo": 2,
        "descanso": 90,
        "carga": "20.50",
        "duracion": None,
        "distancia": None,
    }
    assert fuerza["incremento_carga"] == "2.50"
    assert cardio["incremento_carga"] is None
    assert cardio["objetivos"]["repeticiones_minimas"] is cardio["objetivos"]["repeticiones_maximas"] is None
    for ejercicio in (fuerza, cardio):
        assert ejercicio["zonas"] and set(ejercicio["zonas"]) <= set(ZONAS_CUERPO)
        assert ejercicio["patron_movimiento"] and ejercicio["equipo"]
        assert ejercicio["alternativas"]
        with datos.app.app_context(), transaccion() as cursor:
            cursor.execute(
                "SELECT e.id, e.equipo, e.patron_movimiento, z.zona FROM ejercicios e "
                "JOIN zonas_ejercicio z ON z.ejercicio_id=e.id WHERE e.id=%s",
                (a_bytes(desde_texto(ejercicio["alternativas"][0]["ejercicio_id"])),),
            )
            alternativa = cursor.fetchall()
        assert alternativa[0]["equipo"] != ejercicio["equipo"]
        assert alternativa[0]["patron_movimiento"] == ejercicio["patron_movimiento"]
        assert {f["zona"] for f in alternativa} == set(ejercicio["zonas"])


@pytest.mark.parametrize("zona", ["otra", "Pecho", "bíceps"])
def test_mysql_rechaza_zonas_fuera_del_catalogo(entrenamiento_api, zona):
    from mysql.connector import DatabaseError

    datos = entrenamiento_api
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT ejercicio_id FROM ejercicios_planificados LIMIT 1")
        ejercicio = cursor.fetchone()["ejercicio_id"]
        with pytest.raises(DatabaseError):
            cursor.execute("INSERT INTO zonas_ejercicio (ejercicio_id,zona) VALUES (%s,%s)", (ejercicio, zona))


@pytest.mark.parametrize(
    "valores", ["repeticiones_minimas=13,repeticiones_maximas=12", "rir_objetivo=-1", "rir_objetivo=6"]
)
def test_mysql_rechaza_rango_y_rir_invalidos(entrenamiento_api, valores):
    from mysql.connector import DatabaseError

    with entrenamiento_api.app.app_context(), transaccion() as cursor, pytest.raises(DatabaseError):
        cursor.execute("UPDATE ejercicios_planificados SET " + valores)
