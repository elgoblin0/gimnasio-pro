"""Propuesta real, programa intacto y alcance por rol/asignación sobre MySQL."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
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
    assert despues["version_reglas"] == "3.0.0"
    assert any("sin ajustes" in r["datos"]["explicacion"] for r in despues["explicacion"])
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


@pytest.mark.parametrize("con_alternativa", [True, False])
def test_equipo_fuera_de_servicio_conserva_prescripcion_efectiva(alternativas_api, con_alternativa):
    datos = alternativas_api
    cliente = datos.cliente()
    inicial = cliente.get("/api/entrenamiento/propuesta").json
    assert not inicial["ejercicios"][0]["no_disponible"]
    equipos = []
    with datos.app.app_context(), transaccion() as cursor:
        for nombre in ("barra",) if con_alternativa else ("barra", "mancuernas"):
            equipo_id = nuevo_id(datos.reloj)
            equipos.append(equipo_id)
            cursor.execute(
                "INSERT INTO equipos (id,nombre,creado_en) VALUES (%s,%s,%s)",
                (a_bytes(equipo_id), nombre, datos.reloj.ahora()),
            )
    entrenador = datos.cliente("entrenador")
    for equipo_id in equipos:
        assert (
            escribir(entrenador, f"/api/equipos/{equipo_id}/estado", {"estado": "fuera_de_servicio"}).status_code == 200
        )
    propuesta = cliente.get("/api/entrenamiento/propuesta").json
    ejercicio = propuesta["ejercicios"][0]
    assert ejercicio["no_disponible"] == (not con_alternativa)
    assert ejercicio["ejercicio_hecho_id"] == (str(datos.alternativas[0]) if con_alternativa else None)
    assert propuesta["frenos"] == []
    sesion = iniciar(datos)
    ruta = f"/api/entrenamiento/sesiones/{sesion}"
    efectiva = cliente.get(ruta).json["prescripcion_efectiva"]
    for equipo_id in equipos:
        assert escribir(entrenador, f"/api/equipos/{equipo_id}/estado", {"estado": "disponible"}).status_code == 200
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT motivo FROM sustituciones")
        assert {f["motivo"] for f in cursor.fetchall()} == ({"equipo_fuera_de_servicio"} if con_alternativa else set())
        cursor.execute("SELECT COUNT(*) AS cantidad FROM avisos_entrenador")
        assert cursor.fetchone()["cantidad"] == 0
    assert cliente.get(ruta).json["prescripcion_efectiva"] == efectiva
    respuesta = escribir(cliente, ruta + "/series", cuerpo_serie(datos))
    if con_alternativa:
        assert respuesta.status_code == 201
        assert respuesta.json["serie_realizada"]["ejercicio_hecho_id"] == str(datos.alternativas[0])
    else:
        assert respuesta.status_code == 409
        assert respuesta.json["error"]["codigo"] == "ejercicio_no_disponible"
        assert cantidad(datos) == 0
        siguiente = cliente.get("/api/entrenamiento/propuesta").json
        assert siguiente["sesion_planificada"]["id"] == inicial["sesion_planificada"]["id"]
        assert siguiente["ejercicios"][0]["pendiente"] == 2
        assert cliente.get(ruta).json["ejercicios"][0]["pendiente"] == 2


def cantidad(datos, tabla="series_realizadas"):
    assert tabla in {
        "series_realizadas",
        "sesiones_realizadas",
        "solicitudes_idempotentes",
        "entradas",
        "prescripciones_efectivas",
    }
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute(f"SELECT COUNT(*) AS cantidad FROM {tabla}")
        return cursor.fetchone()["cantidad"]


def test_resumen_parcial_con_sustitucion_zonas_dolor_records_y_pendientes(alternativas_api):
    datos = alternativas_api
    cliente = datos.cliente()
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT ejercicio_id FROM ejercicios_planificados LIMIT 1")
        original = cursor.fetchone()["ejercicio_id"]
        cursor.execute("INSERT INTO zonas_ejercicio VALUES (%s,'cuadriceps')", (original,))
        cursor.execute("INSERT INTO zonas_ejercicio VALUES (%s,'cuadriceps')", (a_bytes(datos.alternativas[0]),))
        anterior = nuevo_id(datos.reloj)
        repositorio.insertar_sesion(cursor, anterior, datos.usuarios["socio"], datos.sesiones[0], datos.reloj.ahora())
        repositorio.insertar_serie(
            cursor,
            nuevo_id(datos.reloj),
            anterior,
            datos.ejercicios[0][0],
            datos.usuarios["socio"],
            datos.reloj.ahora(),
            repeticiones=8,
            carga=Decimal("10"),
            ejercicio_hecho_id=datos.alternativas[0],
        )
    sesion = iniciar(datos)
    ruta = f"/api/entrenamiento/sesiones/{sesion}"
    assert (
        escribir(
            cliente,
            ruta + "/sustituciones",
            {
                "id": str(nuevo_id(datos.reloj)),
                "ejercicio_planificado_id": str(datos.ejercicios[0][0]),
                "ejercicio_hecho_id": str(datos.alternativas[0]),
            },
        ).status_code
        == 201
    )
    assert escribir(cliente, ruta + "/series", cuerpo_serie(datos)).status_code == 201
    with datos.app.app_context(), transaccion() as cursor:
        repositorio.insertar_dolor(
            cursor,
            nuevo_id(datos.reloj),
            datos.usuarios["socio"],
            "cuadriceps",
            datos.reloj.ahora(),
            sesion_id=desde_texto(sesion),
        )
    antes = {
        tabla: cantidad(datos, tabla)
        for tabla in (
            "series_realizadas",
            "sesiones_realizadas",
            "prescripciones_efectivas",
            "solicitudes_idempotentes",
        )
    }
    respuesta = cliente.get(ruta + "/resumen")
    assert respuesta.status_code == 200
    resumen = respuesta.json
    assert resumen["zonas_trabajadas"] == resumen["zonas_con_dolor"] == ["cuadriceps"]
    assert resumen["pendientes"] == [
        {"ejercicio_id": str(datos.ejercicios[0][0]), "series": [2]},
        {"ejercicio_id": str(datos.ejercicios[0][1]), "series": [1, 2]},
    ]
    assert resumen["sustituciones"][0]["motivo"] == "maquina_ocupada"
    assert resumen["sustituciones"][0]["ejercicio_hecho_nombre"] == "Alternativa ficticia 1"
    assert [r["medida"] for r in resumen["records"]] == ["carga_maxima"]
    assert resumen["records"][0]["marca_anterior"] == "10.00"
    assert cliente.get(ruta + "/resumen").json == resumen
    assert {tabla: cantidad(datos, tabla) for tabla in antes} == antes


@pytest.mark.parametrize("rol", ["socio", "ajeno", "entrenador", "otro", "recepcion", "administracion"])
def test_resumen_respeta_propiedad_y_asignacion(entrenamiento_api, rol):
    datos = entrenamiento_api
    sesion = iniciar(datos)
    ruta = f"/api/entrenamiento/sesiones/{sesion}/resumen"
    if rol in {"entrenador", "otro"}:
        ruta = f"/api/entrenamiento/socios/{datos.usuarios['socio']}/sesiones/{sesion}/resumen"
    respuesta = datos.cliente(rol).get(ruta)
    assert respuesta.status_code == (200 if rol in {"socio", "entrenador"} else 403)
    if respuesta.status_code == 200:
        assert respuesta.json["zonas_trabajadas"] == []
        assert respuesta.json["records"] == []
        assert respuesta.json["sustituciones"] == []
        assert [p["series"] for p in respuesta.json["pendientes"]] == [[1, 2], [1, 2]]


def test_resumen_series_corregidas_y_anuladas(entrenamiento_api):
    datos = entrenamiento_api
    sesion = iniciar(datos)
    ruta = f"/api/entrenamiento/sesiones/{sesion}"
    serie = escribir(datos.cliente(), ruta + "/series", cuerpo_serie(datos)).json["serie_realizada"]
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT ejercicio_id FROM ejercicios_planificados LIMIT 1")
        cursor.execute("INSERT INTO zonas_ejercicio VALUES (%s,'cuadriceps')", (cursor.fetchone()["ejercicio_id"],))
        repositorio.insertar_serie(
            cursor,
            nuevo_id(datos.reloj),
            desde_texto(sesion),
            datos.ejercicios[0][0],
            datos.usuarios["socio"],
            datos.reloj.ahora(),
            repeticiones=10,
            carga=Decimal("20.50"),
            corrige_a=desde_texto(serie["id"]),
            anulada=True,
            motivo="Corrección ficticia",
        )
    resumen = datos.cliente().get(ruta + "/resumen").json
    assert resumen["zonas_trabajadas"] == []
    assert resumen["records"] == []
    assert [p["series"] for p in resumen["pendientes"]] == [[1, 2], [1, 2]]


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
    fuerza, cardio, mantener = respuesta.json["ejercicios"]
    assert fuerza["objetivos"] == {
        "series": 2,
        "repeticiones_minimas": 8,
        "repeticiones_maximas": 12,
        "rir_objetivo": 2,
        "descanso": 90,
        "carga": "23.00",
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


@pytest.mark.parametrize("rir", [None, 0, 2, 5, 10])
def test_serie_guarda_rir_y_resuelve_ejercicio_hecho(entrenamiento_api, rir):
    datos = entrenamiento_api
    sesion = iniciar(datos)
    cuerpo = cuerpo_serie(datos)
    if rir is not None:
        cuerpo["rir"] = rir
    respuesta = escribir(datos.cliente(), f"/api/entrenamiento/sesiones/{sesion}/series", cuerpo)
    assert respuesta.status_code == 201
    serie = respuesta.json["serie_realizada"]
    assert serie["rir"] == rir
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute(
            "SELECT ejercicio_id FROM ejercicios_planificados WHERE id = %s", (a_bytes(datos.ejercicios[0][0]),)
        )
        assert serie["ejercicio_hecho_id"] == str(desde_bytes(cursor.fetchone()["ejercicio_id"]))
        cursor.execute(
            "SELECT rir, ejercicio_hecho_id FROM series_realizadas WHERE id = %s", (a_bytes(desde_texto(cuerpo["id"])),)
        )
        assert cursor.fetchone() == {"rir": rir, "ejercicio_hecho_id": None}
    lectura = datos.cliente().get(f"/api/entrenamiento/sesiones/{sesion}")
    assert lectura.json["series"][0]["ejercicio_hecho_id"] == serie["ejercicio_hecho_id"]
    assert lectura.json["series"][0]["rir"] == rir


@pytest.mark.parametrize("rir", [-1, 11, 1.5, True, "2", [], {}])
def test_serie_rechaza_rir_invalido(entrenamiento_api, rir):
    datos = entrenamiento_api
    sesion = iniciar(datos)
    cuerpo = {**cuerpo_serie(datos), "rir": rir}
    assert escribir(datos.cliente(), f"/api/entrenamiento/sesiones/{sesion}/series", cuerpo).status_code == 400


def test_carga_anterior_vigente_local_y_ajena_a_la_sesion_actual(entrenamiento_api):
    from datetime import UTC, datetime, timedelta

    datos = entrenamiento_api
    cliente = datos.cliente()
    assert all(e["carga_anterior"] is None for e in cliente.get("/api/entrenamiento/propuesta").json["ejercicios"])
    momento = datetime(2026, 10, 26, 2, tzinfo=UTC)
    with datos.app.app_context(), transaccion() as cursor:
        anterior = nuevo_id(datos.reloj)
        repositorio.insertar_sesion(cursor, anterior, datos.usuarios["socio"], datos.sesiones[1], momento)
        original, corregida, anulada = (nuevo_id(datos.reloj) for _ in range(3))
        for identificador, corrige, carga, minutos, anular in (
            (original, None, "15", 0, False),
            (corregida, original, "17.50", 1, False),
            (anulada, None, "99", 2, False),
            (nuevo_id(datos.reloj), anulada, "99", 3, True),
        ):
            repositorio.insertar_serie(
                cursor,
                identificador,
                anterior,
                datos.ejercicios[1][0],
                datos.usuarios["socio"],
                momento + timedelta(minutes=minutos),
                repeticiones=9,
                carga=Decimal(carga),
                corrige_a=corrige,
                motivo="Corrección ficticia" if corrige else None,
                anulada=anular,
            )
    esperada = {"carga": "17.50", "repeticiones": 9, "fecha_local": "2026-10-25"}
    assert cliente.get("/api/entrenamiento/propuesta").json["ejercicios"][0]["carga_anterior"] == esperada
    actual = iniciar(datos)
    ruta = f"/api/entrenamiento/sesiones/{actual}"
    assert escribir(cliente, ruta + "/series", cuerpo_serie(datos)).status_code == 201
    assert cliente.get(ruta).json["ejercicios"][0]["carga_anterior"] == esperada
    # Una sesión creada después tampoco cambia la referencia de la sesión abierta.
    registrar(datos, 1, 0)
    assert cliente.get(ruta).json["ejercicios"][0]["carga_anterior"] == esperada


def test_demo_propuesta_ajustada_e_historial_reproducible(entrenamiento_api):
    from datetime import timedelta

    from gimnasio.demo import servicio as demo

    datos = entrenamiento_api
    datos.app.config["MODO_DEMO"] = True

    def reiniciar_y_consultar():
        with datos.app.app_context():
            demo.reiniciar()
        cliente = datos.app.test_client()
        assert cliente.post("/api/sesion/demo/socio", headers={"X-Gimnasio": "1"}).status_code == 200
        respuesta = cliente.get("/api/entrenamiento/propuesta")
        assert respuesta.status_code == 200
        return respuesta.json

    primera = reiniciar_y_consultar()
    assert primera["version_reglas"] == "3.0.0"
    assert primera["frenos"] == []
    fuerza, cardio, mantener = primera["ejercicios"]
    assert fuerza["objetivos"]["carga"] == "23.00"
    assert fuerza["objetivos"]["repeticiones_minimas"] == 8
    assert mantener["objetivos"]["carga"] == "20.50"
    assert mantener["objetivos"]["repeticiones_minimas"] == 11
    assert [r["regla"] for r in fuerza["explicacion"]] == ["subir_carga", "sin_chequeo"]
    assert [r["regla"] for r in mantener["explicacion"]] == ["mantener_carga", "sin_chequeo"]
    assert cardio["objetivos"]["duracion"] == 120
    assert primera == reiniciar_y_consultar()
    datos.reloj.avanzar(timedelta(days=9))
    desplazada = reiniciar_y_consultar()
    assert [e["objetivos"] for e in desplazada["ejercicios"]] == [e["objetivos"] for e in primera["ejercicios"]]


def test_api_tope_semanal_desde_prescripcion_y_liberado_el_lunes(entrenamiento_api):
    from datetime import UTC, datetime, timedelta

    datos = entrenamiento_api
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("UPDATE ejercicios SET incremento_carga=2.5")
        cursor.execute(
            "UPDATE ejercicios_planificados SET repeticiones_minimas=8,repeticiones_maximas=12,rir_objetivo=2"
        )
        for fecha, carga in (
            (datetime(2026, 10, 25, 12, tzinfo=UTC), "40"),
            (datetime(2026, 10, 26, 12, tzinfo=UTC), "42.5"),
        ):
            realizada = nuevo_id(datos.reloj)
            repositorio.insertar_sesion(cursor, realizada, datos.usuarios["socio"], datos.sesiones[1], fecha)
            for _ in range(2):
                repositorio.insertar_serie(
                    cursor,
                    nuevo_id(datos.reloj),
                    realizada,
                    datos.ejercicios[1][0],
                    datos.usuarios["socio"],
                    fecha,
                    repeticiones=12,
                    carga=carga,
                    rir=2,
                )
        repositorio.insertar_prescripcion(
            cursor,
            nuevo_id(datos.reloj),
            realizada,
            {
                "version_reglas": "2.0.0",
                "frenos": [],
                "ejercicios": [
                    {
                        "id": str(datos.ejercicios[1][0]),
                        "ejercicio_id": str(
                            desde_bytes(
                                repositorio.obtener_ejercicio_planificado(cursor, datos.ejercicios[1][0])[
                                    "ejercicio_id"
                                ]
                            )
                        ),
                        "explicacion": [],
                        "objetivos": {"series": 2},
                    }
                ],
                "explicacion": [{"regla": "subir_carga", "datos": {"ejercicio_id": str(datos.ejercicios[1][0])}}],
            },
            fecha,
        )
    propuesta = datos.cliente().get("/api/entrenamiento/propuesta").json
    assert propuesta["frenos"] == ["tope_semanal"]
    assert all(e["objetivos"]["carga"] == "42.50" for e in propuesta["ejercicios"])
    datos.reloj.avanzar(timedelta(days=6))
    propuesta = datos.cliente().get("/api/entrenamiento/propuesta").json
    assert propuesta["fecha_local"] == "2026-11-02"
    assert propuesta["frenos"] == []
    assert all(e["objetivos"]["carga"] == "45.00" for e in propuesta["ejercicios"])


def test_demo_conserva_prescripcion_al_registrar_suba_actual(entrenamiento_api):
    from gimnasio.demo import servicio as demo

    datos = entrenamiento_api
    datos.app.config["MODO_DEMO"] = True
    with datos.app.app_context():
        demo.reiniciar()
    cliente = datos.app.test_client()
    assert cliente.post("/api/sesion/demo/socio", headers={"X-Gimnasio": "1"}).status_code == 200
    inicial = cliente.get("/api/entrenamiento/propuesta").json
    fuerza = inicial["ejercicios"][0]
    assert fuerza["objetivos"]["carga"] == "23.00"
    sesion = escribir(
        cliente,
        "/api/entrenamiento/sesiones",
        {
            "id": str(nuevo_id(datos.reloj)),
            "sesion_planificada_id": inicial["sesion_planificada"]["id"],
        },
    )
    assert sesion.status_code == 201
    ruta = f"/api/entrenamiento/sesiones/{sesion.json['sesion_realizada']['id']}/series"
    assert (
        escribir(
            cliente,
            ruta,
            {
                "id": str(nuevo_id(datos.reloj)),
                "ejercicio_planificado_id": fuerza["id"],
                "repeticiones": 12,
                "carga": "23.00",
                "rir": 2,
            },
        ).status_code
        == 201
    )
    actual = cliente.get("/api/entrenamiento/propuesta").json
    assert actual["frenos"] == []
    assert [e["objetivos"] for e in actual["ejercicios"]] == [e["objetivos"] for e in inicial["ejercicios"]]


@pytest.fixture
def alternativas_api(entrenamiento_api):
    datos = entrenamiento_api
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT ejercicio_id FROM ejercicios_planificados LIMIT 1")
        original = desde_bytes(cursor.fetchone()["ejercicio_id"])
        cursor.execute("UPDATE ejercicios SET equipo='barra',patron_movimiento='sentadilla'")
        datos.alternativas = []
        for orden in (1, 2):
            alternativa = nuevo_id(datos.reloj)
            datos.alternativas.append(alternativa)
            cursor.execute(
                "INSERT INTO ejercicios (id,nombre,medidas_aplicables,actualizada_en,equipo,patron_movimiento) "
                "VALUES (%s,%s,'[\"repeticiones\",\"carga\"]',%s,'mancuernas','sentadilla')",
                (a_bytes(alternativa), f"Alternativa ficticia {orden}", datos.reloj.ahora()),
            )
            cursor.execute(
                "INSERT INTO alternativas_ejercicio VALUES (%s,%s,%s)", (a_bytes(original), a_bytes(alternativa), orden)
            )
    return datos


def test_lectura_de_sesion_con_sustitucion_cuya_alternativa_salio_del_catalogo(alternativas_api):
    datos = alternativas_api
    cliente = datos.cliente()
    sesion = iniciar(datos)
    ruta = f"/api/entrenamiento/sesiones/{sesion}"
    ejercicio = str(datos.ejercicios[0][0])
    cuerpo = {
        "id": str(nuevo_id(datos.reloj)),
        "ejercicio_planificado_id": ejercicio,
        "ejercicio_hecho_id": str(datos.alternativas[0]),
    }
    assert escribir(cliente, ruta + "/sustituciones", cuerpo).status_code == 201
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("DELETE FROM alternativas_ejercicio WHERE alternativa_id=%s", (a_bytes(datos.alternativas[0]),))
    lectura = cliente.get(ruta)
    assert lectura.status_code == 200
    assert lectura.json["sustituciones"][ejercicio]["nombre"] == "Alternativa ficticia 1"


def test_sustitucion_idempotente_compatible_y_series_acreditadas(alternativas_api):
    datos = alternativas_api
    cliente = datos.cliente()
    sesion = iniciar(datos)
    ruta = f"/api/entrenamiento/sesiones/{sesion}"
    ejercicio = str(datos.ejercicios[0][0])
    alternativas = cliente.get(ruta + f"/ejercicios/{ejercicio}/alternativas")
    assert alternativas.status_code == 200
    assert [a["ejercicio_id"] for a in alternativas.json["alternativas"]] == list(map(str, datos.alternativas))
    cuerpo = {
        "id": str(nuevo_id(datos.reloj)),
        "ejercicio_planificado_id": ejercicio,
        "ejercicio_hecho_id": str(datos.alternativas[0]),
    }
    serie = cuerpo_serie(datos) | {"ejercicio_hecho_id": str(datos.alternativas[0])}
    assert escribir(cliente, ruta + "/series", serie).status_code == 409
    assert (
        escribir(
            cliente, ruta + "/sustituciones", cuerpo | {"ejercicio_hecho_id": str(nuevo_id(datos.reloj))}
        ).status_code
        == 422
    )
    clave = str(uuid4())
    primera = escribir(cliente, ruta + "/sustituciones", cuerpo, clave)
    assert primera.status_code == 201
    assert escribir(cliente, ruta + "/sustituciones", cuerpo, clave).json == primera.json
    assert escribir(cliente, ruta + "/sustituciones", cuerpo).json == primera.json
    assert (
        escribir(
            cliente, ruta + "/sustituciones", cuerpo | {"ejercicio_hecho_id": str(datos.alternativas[1])}, clave
        ).status_code
        == 422
    )
    for _ in range(2):
        assert escribir(cliente, ruta + "/series", serie | {"id": str(nuevo_id(datos.reloj))}).status_code == 201
    lectura = cliente.get(ruta).json
    assert lectura["ejercicios"][0]["pendiente"] == 0
    assert lectura["sustituciones"][ejercicio]["sustitucion"] == primera.json["sustitucion"]
    assert all(s["ejercicio_hecho_id"] == str(datos.alternativas[0]) for s in lectura["series"])
    propuesta = cliente.get("/api/entrenamiento/propuesta").json
    assert propuesta["ejercicios"][0]["pendiente"] == 0
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT COUNT(*) AS cantidad FROM sustituciones")
        assert cursor.fetchone()["cantidad"] == 1
    assert datos.cliente("ajeno").get(ruta + f"/ejercicios/{ejercicio}/alternativas").status_code == 403
    assert escribir(datos.cliente("ajeno"), ruta + "/sustituciones", cuerpo).status_code == 403
    segunda = cuerpo | {"id": str(nuevo_id(datos.reloj)), "ejercicio_hecho_id": str(datos.alternativas[1])}
    assert escribir(cliente, ruta + "/sustituciones", segunda).status_code == 201
    assert escribir(cliente, ruta + "/series", serie | {"id": str(nuevo_id(datos.reloj))}).status_code == 409
    assert (
        escribir(
            cliente,
            ruta + "/series",
            serie | {"id": str(nuevo_id(datos.reloj)), "ejercicio_hecho_id": str(datos.alternativas[1])},
        ).status_code
        == 201
    )


@pytest.mark.parametrize("con_series", [False, True])
def test_recarga_sustitucion_sin_alternativa_en_catalogo(alternativas_api, con_series):
    datos = alternativas_api
    cliente = datos.cliente()
    sesion = iniciar(datos)
    ruta = f"/api/entrenamiento/sesiones/{sesion}"
    ejercicio = str(datos.ejercicios[0][0])
    # La última sustitución debe prevalecer incluso si la anterior sigue en el catálogo.
    for alternativa in datos.alternativas:
        respuesta = escribir(
            cliente,
            ruta + "/sustituciones",
            {
                "id": str(nuevo_id(datos.reloj)),
                "ejercicio_planificado_id": ejercicio,
                "ejercicio_hecho_id": str(alternativa),
            },
        )
        assert respuesta.status_code == 201
    if con_series:
        serie = escribir(
            cliente,
            ruta + "/series",
            cuerpo_serie(datos) | {"ejercicio_hecho_id": str(datos.alternativas[-1])},
        )
        assert serie.status_code == 201
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute(
            "DELETE FROM alternativas_ejercicio WHERE alternativa_id=%s",
            (a_bytes(datos.alternativas[-1]),),
        )
    lectura = cliente.get(ruta)
    assert lectura.status_code == 200
    vigente = lectura.json["sustituciones"][ejercicio]
    assert vigente["sustitucion"] == respuesta.json["sustitucion"]
    assert vigente["nombre"] == "Alternativa ficticia 2"
    assert vigente["medidas_aplicables"] == ["repeticiones", "carga"]
    assert len(lectura.json["series"]) == int(con_series)
    if con_series:
        assert lectura.json["series"][0] == serie.json["serie_realizada"]
    # Una elección nueva conserva la validación de alternativas vigentes.
    rechazo = escribir(
        cliente,
        ruta + "/sustituciones",
        {
            "id": str(nuevo_id(datos.reloj)),
            "ejercicio_planificado_id": ejercicio,
            "ejercicio_hecho_id": str(datos.alternativas[-1]),
        },
    )
    assert rechazo.status_code == 422


def test_sustitucion_exige_clave_y_ejercicio_de_sesion(alternativas_api):
    datos = alternativas_api
    sesion = iniciar(datos)
    ruta = f"/api/entrenamiento/sesiones/{sesion}/sustituciones"
    cuerpo = {
        "id": str(nuevo_id(datos.reloj)),
        "ejercicio_planificado_id": str(datos.ejercicios[0][0]),
        "ejercicio_hecho_id": str(datos.alternativas[0]),
    }
    assert datos.cliente().post(ruta, json=cuerpo, headers={"X-Gimnasio": "1"}).status_code == 428
    assert (
        escribir(datos.cliente(), ruta, cuerpo | {"ejercicio_planificado_id": str(datos.ejercicios[1][0])}).status_code
        == 422
    )


def test_api_devuelve_records_con_marca_anterior_y_no_celebra_empate(entrenamiento_api):
    datos = entrenamiento_api
    registrar(datos, 0, 0)
    sesion = iniciar(datos)
    ruta = f"/api/entrenamiento/sesiones/{sesion}/series"
    cuerpo = cuerpo_serie(datos)
    primera = escribir(datos.cliente(), ruta, cuerpo)
    assert primera.status_code == 201
    (record,) = primera.json["records"]
    assert record["medida"] == "carga_maxima"
    assert record["marca_anterior"] == "15.25"
    assert record["marca"] == "20.50"
    assert record["ejercicio_hecho_nombre"] == "Sentadilla ficticia"
    assert escribir(datos.cliente(), ruta, cuerpo_serie(datos)).json["records"] == []
    assert escribir(datos.cliente(), ruta, cuerpo).json["records"] == []


@pytest.mark.parametrize("anulada", [False, True])
def test_record_ignora_marca_corregida_o_anulada(entrenamiento_api, anulada):
    datos = entrenamiento_api
    sesion = iniciar(datos)
    with datos.app.app_context(), transaccion() as cursor:
        anterior = nuevo_id(datos.reloj)
        for identificador, carga, corrige_a in ((anterior, "100", None), (nuevo_id(datos.reloj), "15.25", anterior)):
            repositorio.insertar_serie(
                cursor,
                identificador,
                desde_texto(sesion),
                datos.ejercicios[0][0],
                datos.usuarios["socio"],
                datos.reloj.ahora(),
                repeticiones=8,
                carga=carga,
                corrige_a=corrige_a,
                motivo="Corrección ficticia" if corrige_a else None,
                anulada=anulada if corrige_a else False,
            )
    respuesta = escribir(datos.cliente(), f"/api/entrenamiento/sesiones/{sesion}/series", cuerpo_serie(datos))
    assert respuesta.status_code == 201
    assert [r["medida"] for r in respuesta.json["records"]] == ([] if anulada else ["carga_maxima"])


def test_api_record_de_repeticiones_a_carga_mayor(entrenamiento_api):
    datos = entrenamiento_api
    sesion = iniciar(datos)
    ruta = f"/api/entrenamiento/sesiones/{sesion}/series"
    assert escribir(datos.cliente(), ruta, cuerpo_serie(datos)).json["records"] == []
    respuesta = escribir(datos.cliente(), ruta, cuerpo_serie(datos) | {"carga": "20", "repeticiones": 11})
    (record,) = respuesta.json["records"]
    assert (record["medida"], record["marca"], record["marca_anterior"]) == ("repeticiones_a_carga", 11, 10)


@pytest.mark.parametrize(
    "rol,estado", [("entrenador", 200), ("otro", 403), ("ajeno", 403), ("recepcion", 403), ("administracion", 403)]
)
def test_progreso_respeta_alcance(entrenamiento_api, rol, estado):
    datos = entrenamiento_api
    ruta = f"/api/entrenamiento/socios/{datos.usuarios['socio']}/progreso"
    assert datos.cliente(rol).get(ruta).status_code == estado


def test_progreso_carga_por_sesion_ignora_anuladas_y_usa_ejercicio_hecho(entrenamiento_api):
    from datetime import UTC, datetime, timedelta

    datos = entrenamiento_api
    assert datos.cliente().get("/api/entrenamiento/progreso").json == {"ejercicios": []}
    with datos.app.app_context(), transaccion() as cursor:
        alternativa = nuevo_id(datos.reloj)
        cursor.execute(
            "INSERT INTO ejercicios (id,nombre,medidas_aplicables,actualizada_en) "
            "VALUES (%s,'Alternativa ficticia','[\"repeticiones\",\"carga\"]',%s)",
            (a_bytes(alternativa), datos.reloj.ahora()),
        )
        for dia in (1, 2):
            momento = datetime(2026, 10, dia + 1, 1, tzinfo=UTC)
            realizada = nuevo_id(datos.reloj)
            repositorio.insertar_sesion(cursor, realizada, datos.usuarios["socio"], datos.sesiones[0], momento)
            for indice, carga in enumerate((20, 30, 80)):
                serie = nuevo_id(datos.reloj)
                argumentos = dict(repeticiones=8 + indice, carga=carga, ejercicio_hecho_id=alternativa)
                repositorio.insertar_serie(
                    cursor, serie, realizada, datos.ejercicios[0][0], datos.usuarios["socio"], momento, **argumentos
                )
                if carga == 30:
                    corregida = serie
                if carga == 80:
                    repositorio.insertar_serie(
                        cursor,
                        nuevo_id(datos.reloj),
                        realizada,
                        datos.ejercicios[0][0],
                        datos.usuarios["socio"],
                        momento + timedelta(seconds=1),
                        corrige_a=serie,
                        anulada=True,
                        motivo="Anulada ficticia",
                        **argumentos,
                    )
            # La corrección reemplaza la carga, sin modificar el hecho original.
            repositorio.insertar_serie(
                cursor,
                nuevo_id(datos.reloj),
                realizada,
                datos.ejercicios[0][0],
                datos.usuarios["socio"],
                momento + timedelta(seconds=2),
                corrige_a=corregida,
                motivo="Carga corregida ficticia",
                repeticiones=6,
                carga=35 + dia,
                ejercicio_hecho_id=alternativa,
            )
    respuesta = datos.cliente().get("/api/entrenamiento/progreso")
    assert respuesta.status_code == 200
    assert respuesta.json == {
        "ejercicios": [
            {
                "id": str(alternativa),
                "nombre": "Alternativa ficticia",
                "puntos": [
                    {"fecha_local": "2026-10-01", "carga": "36.00", "repeticiones": 6},
                    {"fecha_local": "2026-10-02", "carga": "37.00", "repeticiones": 6},
                ],
            }
        ]
    }


def test_prescripcion_efectiva_guardada_idempotente_y_estable(entrenamiento_api, monkeypatch):
    from gimnasio.entrenamiento import servicio

    datos = entrenamiento_api
    cliente = datos.cliente()
    sesion = str(nuevo_id(datos.reloj))
    cuerpo = {"id": sesion, "sesion_planificada_id": str(datos.sesiones[0])}
    clave = str(uuid4())
    respuesta = escribir(cliente, "/api/entrenamiento/sesiones", cuerpo, clave)
    assert respuesta.status_code == 201
    inicial = cliente.get(f"/api/entrenamiento/sesiones/{sesion}").json
    assert inicial["prescripcion_efectiva"]["version_reglas"] == "3.0.0"
    assert escribir(cliente, "/api/entrenamiento/sesiones", cuerpo, clave).data == respuesta.data
    assert escribir(cliente, "/api/entrenamiento/sesiones", cuerpo).json == respuesta.json
    assert cantidad(datos, "prescripciones_efectivas") == 1

    def motor_no_disponible(*args, **kwargs):
        raise AssertionError("La lectura no debe ejecutar el motor.")

    monkeypatch.setattr(servicio, "proponer_sesion", motor_no_disponible)
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("UPDATE ejercicios_planificados SET carga=99,series=8")
    guardada = cliente.get(f"/api/entrenamiento/sesiones/{sesion}").json
    assert guardada == inicial
    assert guardada["ejercicios"][0]["objetivos"]["carga"] == "20.50"


def test_fallo_prescripcion_revierte_sesion(entrenamiento_api, monkeypatch):
    datos = entrenamiento_api

    def fallar(*args, **kwargs):
        raise RuntimeError("Fallo simulado al insertar la prescripción.")

    monkeypatch.setattr(repositorio, "insertar_prescripcion", fallar)
    with pytest.raises(RuntimeError, match="Fallo simulado"):
        escribir(
            datos.cliente(),
            "/api/entrenamiento/sesiones",
            {
                "id": str(nuevo_id(datos.reloj)),
                "sesion_planificada_id": str(datos.sesiones[0]),
            },
        )
    assert cantidad(datos, "sesiones_realizadas") == 0
    assert cantidad(datos, "prescripciones_efectivas") == 0


def test_sesiones_de_semanas_distintas_cuentan_solo_sus_series(entrenamiento_api):
    from datetime import timedelta

    datos = entrenamiento_api
    cliente = datos.cliente()
    primera = iniciar(datos)
    for ejercicio in datos.ejercicios[0]:
        for _ in range(2):
            cuerpo = cuerpo_serie(datos) | {"ejercicio_planificado_id": str(ejercicio)}
            assert escribir(cliente, f"/api/entrenamiento/sesiones/{primera}/series", cuerpo).status_code == 201
    datos.reloj.avanzar(timedelta(days=7))
    segunda = iniciar(datos)
    ruta = f"/api/entrenamiento/sesiones/{segunda}"
    inicial = cliente.get(ruta).json
    assert inicial["sesion_realizada"]["sesion_planificada_id"] == str(datos.sesiones[0])
    assert inicial["prescripcion_efectiva"] is not None
    assert [(e["realizado"], e["pendiente"]) for e in inicial["ejercicios"]] == [(0, 2), (0, 2)]
    assert inicial["series"] == []

    assert escribir(cliente, ruta + "/series", cuerpo_serie(datos)).status_code == 201
    parcial = cliente.get(ruta).json
    assert [(e["realizado"], e["pendiente"]) for e in parcial["ejercicios"]] == [(1, 1), (0, 2)]
    assert parcial["prescripcion_efectiva"] == inicial["prescripcion_efectiva"]
    anterior = cliente.get(f"/api/entrenamiento/sesiones/{primera}").json
    assert [(e["realizado"], e["pendiente"]) for e in anterior["ejercicios"]] == [(2, 0), (2, 0)]


@pytest.mark.parametrize("sin_entrenador", [False, True])
def test_freno_5_aviso_por_cada_freno(entrenamiento_api, monkeypatch, sin_entrenador):
    from gimnasio.entrenamiento import servicio

    datos = entrenamiento_api
    cliente = datos.cliente()
    propuesta = cliente.get("/api/entrenamiento/propuesta").json
    # Incluye un freno futuro: el patrón no depende del catálogo actual.
    propuesta["frenos"] = ["tope_semanal", "chequeo_desfavorable", "dolor_reportado", "restriccion_salud"]
    monkeypatch.setattr(servicio, "consultar_propuesta", lambda *a, **k: propuesta)
    if sin_entrenador:
        with datos.app.app_context(), transaccion() as cursor:
            cursor.execute("UPDATE asignaciones_entrenador SET hasta=%s", (datos.reloj.ahora(),))
    cuerpo = {"id": str(nuevo_id(datos.reloj)), "sesion_planificada_id": str(datos.sesiones[0])}
    insertar = repositorio.insertar_avisos

    def fallar(*args):
        insertar(*args)
        raise ValueError("fallo después de insertar avisos")

    monkeypatch.setattr(repositorio, "insertar_avisos", fallar)
    datos.app.config["TESTING"] = True
    with pytest.raises(ValueError):
        escribir(cliente, "/api/entrenamiento/sesiones", cuerpo)
    with datos.app.app_context(), transaccion() as cursor:
        for tabla in ("avisos_entrenador", "prescripciones_efectivas", "sesiones_realizadas"):
            cursor.execute(f"SELECT COUNT(*) AS cantidad FROM {tabla}")
            assert cursor.fetchone()["cantidad"] == 0
    monkeypatch.setattr(repositorio, "insertar_avisos", insertar)
    assert escribir(cliente, "/api/entrenamiento/sesiones", cuerpo).status_code == 201
    assert escribir(cliente, "/api/entrenamiento/sesiones", cuerpo).status_code == 201
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT * FROM avisos_entrenador")
        avisos = cursor.fetchall()
        assert {a["freno"] for a in avisos} == set(propuesta["frenos"])
        assert len(avisos) == 4
        assert all(
            a["entrenador_id"] == (None if sin_entrenador else a_bytes(datos.usuarios["entrenador"])) for a in avisos
        )


def test_chequeo_idempotente_propio_y_ultimo_local(entrenamiento_api):
    datos = entrenamiento_api
    cliente = datos.cliente()
    ruta = "/api/entrenamiento/chequeos"
    cuerpo = {"id": str(nuevo_id(datos.reloj)), "sueno": 1, "energia": 5}
    clave = str(uuid4())
    primera = escribir(cliente, ruta, cuerpo, clave)
    assert primera.status_code == 201
    assert escribir(cliente, ruta, cuerpo, clave).json == primera.json
    assert escribir(cliente, ruta, cuerpo | {"energia": 4}, clave).status_code == 422
    assert escribir(datos.cliente("ajeno"), ruta, cuerpo).status_code == 403
    assert escribir(cliente, ruta, cuerpo | {"socio_id": str(datos.usuarios["ajeno"])}).status_code == 422
    assert "chequeo_desfavorable" in cliente.get("/api/entrenamiento/propuesta").json["frenos"]
    assert escribir(cliente, ruta, {"id": str(nuevo_id(datos.reloj)), "sueno": 5, "energia": 5}).status_code == 201
    assert "chequeo_desfavorable" not in cliente.get("/api/entrenamiento/propuesta").json["frenos"]
    for valor in (True, 0, 6, 2.5, "2", None):
        assert (
            escribir(cliente, ruta, {"id": str(nuevo_id(datos.reloj)), "sueno": valor, "energia": 5}).status_code == 422
        )


def test_chequeo_completar_prescripcion_no_recupera_serie_quitada(entrenamiento_api):
    datos = entrenamiento_api
    cliente = datos.cliente()
    assert (
        escribir(
            cliente, "/api/entrenamiento/chequeos", {"id": str(nuevo_id(datos.reloj)), "sueno": 1, "energia": 5}
        ).status_code
        == 201
    )
    propuesta = cliente.get("/api/entrenamiento/propuesta").json
    assert all(e["pendiente"] == e["objetivos"]["series"] == 1 for e in propuesta["ejercicios"])
    sesion = str(nuevo_id(datos.reloj))
    assert (
        escribir(
            cliente, "/api/entrenamiento/sesiones", {"id": sesion, "sesion_planificada_id": str(datos.sesiones[0])}
        ).status_code
        == 201
    )
    for ejercicio in datos.ejercicios[0]:
        assert (
            escribir(
                cliente,
                f"/api/entrenamiento/sesiones/{sesion}/series",
                {
                    "id": str(nuevo_id(datos.reloj)),
                    "ejercicio_planificado_id": str(ejercicio),
                    "repeticiones": 10,
                    "carga": 20.5,
                },
            ).status_code
            == 201
        )
    # Un chequeo posterior neutro tampoco recupera el trabajo quitado al iniciar.
    assert (
        escribir(
            cliente, "/api/entrenamiento/chequeos", {"id": str(nuevo_id(datos.reloj)), "sueno": 5, "energia": 5}
        ).status_code
        == 201
    )
    siguiente = cliente.get("/api/entrenamiento/propuesta").json
    assert siguiente["sesion_planificada"]["id"] == str(datos.sesiones[1])


def test_prescripcion_de_programa_anterior_no_interfiere(entrenamiento_api):
    datos = entrenamiento_api
    cliente = datos.cliente()
    sesion = str(nuevo_id(datos.reloj))
    assert (
        escribir(
            cliente, "/api/entrenamiento/sesiones", {"id": sesion, "sesion_planificada_id": str(datos.sesiones[0])}
        ).status_code
        == 201
    )
    # El programa nuevo no contiene los ejercicios de la prescripción anterior.
    with datos.app.app_context(), transaccion() as cursor:
        programa = nuevo_id(datos.reloj)
        cursor.execute(
            "INSERT INTO programas_entrenamiento (id,socio_id,version,creado_en) VALUES (%s,%s,2,%s)",
            (a_bytes(programa), a_bytes(datos.usuarios["socio"]), datos.reloj.ahora()),
        )
    respuesta = cliente.get("/api/entrenamiento/propuesta")
    assert respuesta.status_code == 200
    assert respuesta.json["sesion_planificada"] is None


@pytest.fixture
def dolor_api(entrenamiento_api):
    from gimnasio.demo import servicio as demo

    datos = entrenamiento_api
    datos.app.config["MODO_DEMO"] = True
    with datos.app.app_context():
        demo.reiniciar()
    cliente = datos.app.test_client()
    assert cliente.post("/api/sesion/demo/socio", headers={"X-Gimnasio": "1"}).status_code == 200
    datos.cliente_dolor = cliente
    datos.propuesta_dolor = cliente.get("/api/entrenamiento/propuesta").json
    datos.sesion_dolor = str(nuevo_id(datos.reloj))
    respuesta = escribir(
        cliente,
        "/api/entrenamiento/sesiones",
        {
            "id": datos.sesion_dolor,
            "sesion_planificada_id": datos.propuesta_dolor["sesion_planificada"]["id"],
        },
    )
    assert respuesta.status_code == 201
    datos.ruta_dolor = f"/api/entrenamiento/sesiones/{datos.sesion_dolor}"
    datos.cuerpo_dolor = {
        "id": str(nuevo_id(datos.reloj)),
        "ejercicio_planificado_id": datos.propuesta_dolor["ejercicios"][0]["id"],
        "zonas": ["rodillas"],
    }
    return datos


@pytest.mark.parametrize("freno", ["dolor_reportado", "restriccion_salud"])
def test_alternativa_inicial_no_disponible_conserva_pendiente(alternativas_api, freno):
    from gimnasio.permisos.servicio import registrar_consentimiento

    datos = alternativas_api
    cliente = datos.cliente()
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT ejercicio_id FROM ejercicios_planificados LIMIT 1")
        original = cursor.fetchone()["ejercicio_id"]
        for zona in ("rodillas", "gluteos"):
            cursor.execute("INSERT INTO zonas_ejercicio VALUES (%s,%s)", (original, zona))
        for alternativa in datos.alternativas:
            cursor.execute("INSERT INTO zonas_ejercicio VALUES (%s,'gluteos')", (a_bytes(alternativa),))
        equipo = nuevo_id(datos.reloj)
        cursor.execute(
            "INSERT INTO equipos (id,nombre,creado_en) VALUES (%s,'mancuernas',%s)",
            (a_bytes(equipo), datos.reloj.ahora()),
        )
        if freno == "restriccion_salud":
            cursor.execute(
                "INSERT INTO restricciones_salud (id,socio_id,zona,descripcion,registrada_en,autor_id) "
                "VALUES (%s,%s,'rodillas','Restricción ficticia',%s,%s)",
                (
                    a_bytes(nuevo_id(datos.reloj)),
                    a_bytes(datos.usuarios["socio"]),
                    datos.reloj.ahora(),
                    a_bytes(datos.usuarios["entrenador"]),
                ),
            )
        else:
            socio = datos.usuarios["socio"]
            registrar_consentimiento(cursor, socio, "salud", True, "1", socio)
    assert (
        escribir(
            datos.cliente("entrenador"), f"/api/equipos/{equipo}/estado", {"estado": "fuera_de_servicio"}
        ).status_code
        == 200
    )
    if freno == "dolor_reportado":
        respuesta = escribir(
            cliente,
            "/api/entrenamiento/chequeos",
            {"id": str(nuevo_id(datos.reloj)), "sueno": 5, "energia": 5, "zonas": ["rodillas"]},
        )
        assert respuesta.status_code == 201
    propuesta = cliente.get("/api/entrenamiento/propuesta").json
    assert freno in propuesta["frenos"]
    assert all(e["no_disponible"] and e["objetivos"]["series"] == 2 for e in propuesta["ejercicios"])
    sesion = iniciar(datos)
    ruta = f"/api/entrenamiento/sesiones/{sesion}"
    lectura = cliente.get(ruta).json
    assert all(e["no_disponible"] and e["pendiente"] == 2 for e in lectura["ejercicios"])
    congelada = lectura["prescripcion_efectiva"]
    assert all(e["no_disponible"] and e["objetivos"]["series"] == 2 for e in congelada["ejercicios"])
    respuesta = escribir(cliente, ruta + "/series", cuerpo_serie(datos))
    assert respuesta.status_code == 409
    assert respuesta.json["error"]["codigo"] == "ejercicio_no_disponible"
    siguiente = cliente.get("/api/entrenamiento/propuesta").json
    assert siguiente["sesion_planificada"]["id"] == propuesta["sesion_planificada"]["id"]
    assert all(e["pendiente"] == 2 for e in siguiente["ejercicios"])
    assert cliente.get(ruta).json["prescripcion_efectiva"] == congelada
    assert cantidad(datos) == 0
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT COUNT(*) AS cantidad FROM sustituciones")
        assert cursor.fetchone()["cantidad"] == 0


@pytest.mark.parametrize("series_realizadas", [0, 1, 2])
@pytest.mark.parametrize("origen_dolor", ["chequeo", "sesion"])
def test_equipo_posterior_conserva_reduccion_congelada(alternativas_api, series_realizadas, origen_dolor):
    from gimnasio.permisos.servicio import registrar_consentimiento

    datos = alternativas_api
    cliente = datos.cliente()
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("UPDATE ejercicios_planificados SET series=3")
        cursor.execute("SELECT ejercicio_id FROM ejercicios_planificados LIMIT 1")
        original = cursor.fetchone()["ejercicio_id"]
        for zona in ("rodillas", "gluteos"):
            cursor.execute("INSERT INTO zonas_ejercicio VALUES (%s,%s)", (original, zona))
        for alternativa in datos.alternativas:
            cursor.execute("INSERT INTO zonas_ejercicio VALUES (%s,'gluteos')", (a_bytes(alternativa),))
        equipo = nuevo_id(datos.reloj)
        cursor.execute(
            "INSERT INTO equipos (id,nombre,creado_en) VALUES (%s,'mancuernas',%s)",
            (a_bytes(equipo), datos.reloj.ahora()),
        )
        socio = datos.usuarios["socio"]
        registrar_consentimiento(cursor, socio, "salud", True, "1", socio)
    chequeo = {"id": str(nuevo_id(datos.reloj)), "sueno": 1, "energia": 5}
    if origen_dolor == "chequeo":
        chequeo["zonas"] = ["rodillas"]
    assert escribir(cliente, "/api/entrenamiento/chequeos", chequeo).status_code == 201
    sesion = iniciar(datos)
    ruta = f"/api/entrenamiento/sesiones/{sesion}"
    if origen_dolor == "sesion":
        assert (
            escribir(
                cliente,
                ruta + "/dolores",
                {
                    "id": str(nuevo_id(datos.reloj)),
                    "ejercicio_planificado_id": str(datos.ejercicios[0][0]),
                    "zonas": ["rodillas"],
                },
            ).status_code
            == 201
        )
    congelada = cliente.get(ruta).json["prescripcion_efectiva"]
    assert all(e["objetivos"]["series"] == 2 for e in congelada["ejercicios"])
    for ejercicio in datos.ejercicios[0]:
        for _ in range(series_realizadas):
            assert (
                escribir(
                    cliente,
                    ruta + "/series",
                    {
                        "id": str(nuevo_id(datos.reloj)),
                        "ejercicio_planificado_id": str(ejercicio),
                        "repeticiones": 10,
                        "carga": 20.5,
                    },
                ).status_code
                == 201
            )
    assert (
        escribir(
            datos.cliente("entrenador"), f"/api/equipos/{equipo}/estado", {"estado": "fuera_de_servicio"}
        ).status_code
        == 200
    )
    siguiente = cliente.get("/api/entrenamiento/propuesta").json
    assert siguiente["sesion_planificada"]["id"] == str(datos.sesiones[1 if series_realizadas == 2 else 0])
    if series_realizadas < 2:
        assert all(e["pendiente"] == 2 - series_realizadas for e in siguiente["ejercicios"])
    assert cliente.get(ruta).json["prescripcion_efectiva"] == congelada


def test_alternativa_por_dolor_no_disponible_conserva_pendiente(dolor_api):
    datos = dolor_api
    cliente, ruta = datos.cliente_dolor, datos.ruta_dolor
    inicial = cliente.get(ruta).json
    primero = inicial["ejercicios"][0]
    cambiar_equipo_dolor(datos, "cajon", "fuera_de_servicio")
    datos.reloj.avanzar(timedelta(seconds=1))
    assert escribir(cliente, ruta + "/dolores", datos.cuerpo_dolor).status_code == 201
    lectura = cliente.get(ruta).json
    assert lectura["ejercicios"][0]["no_disponible"]
    assert lectura["ejercicios"][0]["pendiente"] == primero["pendiente"] > 0
    propuesta = cliente.get("/api/entrenamiento/propuesta").json
    assert propuesta["sesion_planificada"]["id"] == inicial["sesion_planificada"]["id"]
    ejercicio = next(e for e in propuesta["ejercicios"] if e["id"] == primero["id"])
    assert ejercicio["pendiente"] == primero["pendiente"]
    assert cliente.get(ruta).json["prescripcion_efectiva"] == inicial["prescripcion_efectiva"]


def cambiar_equipo_dolor(datos, nombre, estado):
    entrenador = datos.app.test_client()
    assert entrenador.post("/api/sesion/demo/entrenador", headers={"X-Gimnasio": "1"}).status_code == 200
    equipo = next(e for e in entrenador.get("/api/equipos").json["equipos"] if e["nombre"] == nombre)
    datos.reloj.avanzar(timedelta(seconds=1))
    assert escribir(entrenador, f"/api/equipos/{equipo['id']}/estado", {"estado": estado}).status_code == 200


@pytest.mark.parametrize("reparar_primera", [False, True])
def test_dolor_conserva_sustitucion_tras_cambio_equipo(dolor_api, reparar_primera):
    datos = dolor_api
    cliente, ruta = datos.cliente_dolor, datos.ruta_dolor
    if reparar_primera:
        # Dos alternativas seguras, en equipos distintos y con orden explícito.
        with datos.app.app_context(), transaccion() as cursor:
            cursor.execute("SELECT id FROM ejercicios WHERE equipo='mancuernas'")
            primera = cursor.fetchone()["id"]
            cursor.execute("DELETE FROM zonas_ejercicio WHERE ejercicio_id=%s", (primera,))
            cursor.execute(
                "INSERT INTO zonas_ejercicio (ejercicio_id,zona) "
                "SELECT %s,z.zona FROM zonas_ejercicio z JOIN ejercicios e ON e.id=z.ejercicio_id "
                "WHERE e.equipo='cajon'",
                (primera,),
            )
        cambiar_equipo_dolor(datos, "mancuernas", "fuera_de_servicio")
    datos.reloj.avanzar(timedelta(seconds=1))
    assert escribir(cliente, ruta + "/dolores", datos.cuerpo_dolor).status_code == 201
    inicial = cliente.get(ruta).json
    ejercicio = inicial["ejercicios"][0]
    hecho = ejercicio["ejercicio_hecho_id"]
    assert hecho
    serie = {
        "id": str(nuevo_id(datos.reloj)),
        "ejercicio_planificado_id": ejercicio["id"],
        "repeticiones": 10,
        "carga": "20.50",
    }
    assert escribir(cliente, ruta + "/series", serie).status_code == 201
    cambiar_equipo_dolor(
        datos, "mancuernas" if reparar_primera else "cajon", "disponible" if reparar_primera else "fuera_de_servicio"
    )
    lectura = cliente.get(ruta).json
    actual = lectura["ejercicios"][0]
    assert actual["ejercicio_hecho_id"] == hecho
    assert not actual.get("no_disponible", False)
    assert lectura["sustituciones"][ejercicio["id"]] == inicial["sustituciones"][ejercicio["id"]]
    respuesta = escribir(cliente, ruta + "/series", serie | {"id": str(nuevo_id(datos.reloj))})
    assert respuesta.status_code == 201
    assert respuesta.json["serie_realizada"]["ejercicio_hecho_id"] == hecho
    assert cliente.get("/api/entrenamiento/propuesta").status_code == 200


def test_dolor_sin_alternativa_conserva_no_disponible_tras_reparacion(dolor_api):
    datos = dolor_api
    cliente, ruta = datos.cliente_dolor, datos.ruta_dolor
    cambiar_equipo_dolor(datos, "cajon", "fuera_de_servicio")
    datos.reloj.avanzar(timedelta(seconds=1))
    assert escribir(cliente, ruta + "/dolores", datos.cuerpo_dolor).status_code == 201
    inicial = cliente.get(ruta).json["ejercicios"][0]
    assert inicial["no_disponible"]
    cambiar_equipo_dolor(datos, "cajon", "disponible")
    actual = cliente.get(ruta).json["ejercicios"][0]
    assert actual == inicial
    serie = {
        "id": str(nuevo_id(datos.reloj)),
        "ejercicio_planificado_id": inicial["id"],
        "repeticiones": 10,
        "carga": "20.50",
    }
    respuesta = escribir(cliente, ruta + "/series", serie)
    assert respuesta.status_code == 409
    assert respuesta.json["error"]["codigo"] == "ejercicio_no_disponible"
    propuesta = cliente.get("/api/entrenamiento/propuesta").json
    ejercicio = next(e for e in propuesta["ejercicios"] if e["id"] == inicial["id"])
    assert ejercicio["pendiente"] == inicial["pendiente"] > 0
    # Solo un dolor nuevo vuelve a decidir con el equipo reparado.
    datos.reloj.avanzar(timedelta(seconds=1))
    assert (
        escribir(cliente, ruta + "/dolores", datos.cuerpo_dolor | {"id": str(nuevo_id(datos.reloj))}).status_code == 201
    )
    assert not cliente.get(ruta).json["ejercicios"][0].get("no_disponible", False)


def test_dolor_sustitucion_aviso_atomicos_e_idempotentes(dolor_api):
    datos = dolor_api
    cliente, ruta = datos.cliente_dolor, datos.ruta_dolor
    clave = str(uuid4())
    respuesta = escribir(cliente, ruta + "/dolores", datos.cuerpo_dolor, clave)
    assert respuesta.status_code == 201
    assert escribir(cliente, ruta + "/dolores", datos.cuerpo_dolor, clave).data == respuesta.data
    assert escribir(cliente, ruta + "/dolores", datos.cuerpo_dolor).json == respuesta.json
    lectura = cliente.get(ruta).json
    ejercicio = lectura["ejercicios"][0]
    assert ejercicio["objetivos"]["carga"] == "20.50"
    assert ejercicio["ejercicio_hecho_id"] is not None
    assert lectura["sustituciones"][ejercicio["id"]]["nombre"] == "Sentadilla en cajón ficticia"
    assert lectura["sustituciones"][ejercicio["id"]]["sustitucion"]["motivo"] == "dolor_reportado"
    assert any("no involucra" in r["datos"]["explicacion"] for r in ejercicio["explicacion"])
    with datos.app.app_context(), transaccion() as cursor:
        for tabla in ("dolores_reportados", "sustituciones", "avisos_entrenador"):
            cursor.execute(
                f"SELECT COUNT(*) AS cantidad FROM {tabla} WHERE sesion_realizada_id=%s",
                (a_bytes(desde_texto(datos.sesion_dolor)),),
            )
            assert cursor.fetchone()["cantidad"] == 1
    serie = {
        "id": str(nuevo_id(datos.reloj)),
        "ejercicio_planificado_id": ejercicio["id"],
        "repeticiones": 10,
        "carga": "20.50",
    }
    respuesta = escribir(cliente, ruta + "/series", serie)
    assert respuesta.status_code == 201
    assert respuesta.json["serie_realizada"]["ejercicio_hecho_nombre"] == "Sentadilla en cajón ficticia"


@pytest.mark.parametrize("segunda_zona", ["cuadriceps", "cuello"])
def test_dolores_sucesivos_dejan_un_aviso_por_registro(dolor_api, segunda_zona):
    import json

    datos = dolor_api
    cliente, ruta = datos.cliente_dolor, datos.ruta_dolor
    for cantidad, zona in enumerate(("rodillas", segunda_zona), start=1):
        cuerpo = datos.cuerpo_dolor | {"id": str(nuevo_id(datos.reloj)), "zonas": [zona]}
        clave = str(uuid4())
        primera = escribir(cliente, ruta + "/dolores", cuerpo, clave)
        assert primera.status_code == 201
        assert escribir(cliente, ruta + "/dolores", cuerpo, clave).json == primera.json
        assert escribir(cliente, ruta + "/dolores", cuerpo).json == primera.json
        with datos.app.app_context(), transaccion() as cursor:
            cursor.execute(
                "SELECT explicacion FROM avisos_entrenador WHERE sesion_realizada_id=%s AND freno='dolor_reportado'",
                (a_bytes(desde_texto(datos.sesion_dolor)),),
            )
            avisos = cursor.fetchall()
            assert len(avisos) == cantidad
            assert any(zona in r["datos"]["zonas"] for a in avisos for r in json.loads(a["explicacion"]))


def test_alternativa_con_dolor_explicita_y_guarda_el_motivo(dolor_api):
    datos = dolor_api
    cliente, ruta = datos.cliente_dolor, datos.ruta_dolor
    assert escribir(cliente, ruta + "/dolores", datos.cuerpo_dolor).status_code == 201
    ejercicio = datos.cuerpo_dolor["ejercicio_planificado_id"]
    respuesta = cliente.get(ruta + f"/ejercicios/{ejercicio}/alternativas")
    assert respuesta.status_code == 200
    assert [a["nombre"] for a in respuesta.json["alternativas"]] == ["Sentadilla en cajón ficticia"]
    assert respuesta.json["explicacion"]["regla"] == "dolor_reportado"
    assert "no involucra la zona con dolor" in respuesta.json["explicacion"]["datos"]["explicacion"]
    cuerpo = {
        "id": str(nuevo_id(datos.reloj)),
        "ejercicio_planificado_id": ejercicio,
        "ejercicio_hecho_id": respuesta.json["alternativas"][0]["ejercicio_id"],
    }
    guardada = escribir(cliente, ruta + "/sustituciones", cuerpo)
    assert guardada.status_code == 201
    assert guardada.json["sustitucion"]["motivo"] == "dolor_reportado"
    assert escribir(cliente, ruta + "/sustituciones", cuerpo).json == guardada.json
    with datos.app.app_context(), transaccion() as cursor:
        fila = repositorio.obtener_sustitucion(cursor, desde_texto(cuerpo["id"]))
        assert fila["motivo"] == "dolor_reportado"


@pytest.mark.parametrize("con_dolor", [False, True])
def test_consultas_de_propuesta_no_crecen_con_el_historial(dolor_api, monkeypatch, con_dolor):
    from mysql.connector.cursor import MySQLCursor

    datos = dolor_api
    consultas = []
    ejecutar = MySQLCursor.execute

    def contar(cursor, sql, *args, **kwargs):
        consultas.append(sql)
        return ejecutar(cursor, sql, *args, **kwargs)

    monkeypatch.setattr(MySQLCursor, "execute", contar)
    consultas.clear()
    assert datos.cliente_dolor.get("/api/entrenamiento/propuesta").status_code == 200
    cantidad = len(consultas)
    with datos.app.app_context(), transaccion() as cursor:
        sesion = repositorio.obtener_sesion(cursor, desde_texto(datos.sesion_dolor))
        for _ in range(12):
            realizada = nuevo_id(datos.reloj)
            repositorio.insertar_sesion(
                cursor,
                realizada,
                desde_bytes(sesion["socio_id"]),
                desde_bytes(sesion["sesion_planificada_id"]),
                datos.reloj.ahora(),
            )
            repositorio.insertar_prescripcion(
                cursor, nuevo_id(datos.reloj), realizada, datos.propuesta_dolor, datos.reloj.ahora()
            )
            if con_dolor:
                repositorio.insertar_dolor(
                    cursor,
                    nuevo_id(datos.reloj),
                    desde_bytes(sesion["socio_id"]),
                    "rodillas",
                    datos.reloj.ahora(),
                    sesion_id=realizada,
                )
    consultas.clear()
    assert datos.cliente_dolor.get("/api/entrenamiento/propuesta").status_code == 200
    assert len(consultas) <= cantidad + 1
    assert sum("FROM sedes" in sql for sql in consultas) == 1


@pytest.mark.parametrize("revocado", [False, True], ids=["nunca-otorgado", "revocado"])
@pytest.mark.parametrize("origen", ["chequeo", "sesion"])
def test_dolor_exige_consentimiento_de_salud(entrenamiento_api, origen, revocado):
    from gimnasio.permisos.servicio import registrar_consentimiento

    datos = entrenamiento_api
    cliente = datos.cliente()
    sesion = iniciar(datos)
    if revocado:
        with datos.app.app_context(), transaccion() as cursor:
            socio = datos.usuarios["socio"]
            for otorgado in (True, False):
                registrar_consentimiento(cursor, socio, "salud", otorgado, "1", socio)
    if origen == "chequeo":
        ruta = "/api/entrenamiento/chequeos"
        cuerpo = {"id": str(nuevo_id(datos.reloj)), "sueno": 5, "energia": 5, "zonas": ["rodillas"]}
    else:
        ruta = f"/api/entrenamiento/sesiones/{sesion}/dolores"
        cuerpo = {
            "id": str(nuevo_id(datos.reloj)),
            "ejercicio_planificado_id": str(datos.ejercicios[0][0]),
            "zonas": ["rodillas"],
        }
    respuesta = escribir(cliente, ruta, cuerpo)
    assert respuesta.status_code == 403
    assert respuesta.json["error"]["codigo"] == "sin_consentimiento"
    with datos.app.app_context(), transaccion() as cursor:
        for tabla in ("chequeos_dia", "dolores_reportados", "sustituciones", "avisos_entrenador"):
            cursor.execute(f"SELECT COUNT(*) AS cantidad FROM {tabla}")
            assert cursor.fetchone()["cantidad"] == 0


def test_maquina_ocupada_con_dolor_ajeno_conserva_zonas(dolor_api):
    datos = dolor_api
    cliente, ruta = datos.cliente_dolor, datos.ruta_dolor
    assert escribir(cliente, ruta + "/dolores", datos.cuerpo_dolor | {"zonas": ["cuello"]}).status_code == 201
    ejercicio = datos.cuerpo_dolor["ejercicio_planificado_id"]
    respuesta = cliente.get(ruta + f"/ejercicios/{ejercicio}/alternativas")
    assert respuesta.status_code == 200
    assert [a["nombre"] for a in respuesta.json["alternativas"]] == ["Sentadilla con mancuernas ficticia"]
    assert respuesta.json["explicacion"]["regla"] == "maquina_ocupada"
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT id FROM ejercicios WHERE nombre='Sentadilla en cajón ficticia'")
        cajon = str(desde_bytes(cursor.fetchone()["id"]))
    cuerpo = {
        "id": str(nuevo_id(datos.reloj)),
        "ejercicio_planificado_id": ejercicio,
        "ejercicio_hecho_id": cajon,
    }
    rechazo = escribir(cliente, ruta + "/sustituciones", cuerpo)
    assert rechazo.status_code == 422
    assert rechazo.json["error"]["codigo"] == "alternativa_incompatible"
    cuerpo["ejercicio_hecho_id"] = respuesta.json["alternativas"][0]["ejercicio_id"]
    assert escribir(cliente, ruta + "/sustituciones", cuerpo).status_code == 201


def test_fallo_aviso_revierte_dolor_y_sustitucion(dolor_api, monkeypatch):
    datos = dolor_api
    insertar = repositorio.insertar_avisos

    def fallar(*args):
        insertar(*args)
        raise RuntimeError("Fallo ficticio después del aviso")

    monkeypatch.setattr(repositorio, "insertar_avisos", fallar)
    with pytest.raises(RuntimeError, match="Fallo ficticio"):
        escribir(datos.cliente_dolor, datos.ruta_dolor + "/dolores", datos.cuerpo_dolor)
    with datos.app.app_context(), transaccion() as cursor:
        for tabla in ("dolores_reportados", "sustituciones", "avisos_entrenador"):
            cursor.execute(f"SELECT COUNT(*) AS cantidad FROM {tabla}")
            assert cursor.fetchone()["cantidad"] == 0


def test_serie_concurrente_espera_dolor_y_respeta_la_quita(dolor_api, monkeypatch):
    datos = dolor_api
    dolor_insertado, serie_leyendo, continuar = Event(), Event(), Event()
    insertar, obtener = repositorio.insertar_dolor, repositorio.obtener_socio

    def insertar_pausado(*args, **kwargs):
        insertar(*args, **kwargs)
        dolor_insertado.set()
        assert continuar.wait(timeout=10)

    def obtener_observado(*args, **kwargs):
        if kwargs.get("bloqueo_compartido"):
            serie_leyendo.set()
        return obtener(*args, **kwargs)

    monkeypatch.setattr(repositorio, "insertar_dolor", insertar_pausado)
    monkeypatch.setattr(repositorio, "obtener_socio", obtener_observado)
    otro_cliente = datos.app.test_client()
    with datos.cliente_dolor.session_transaction() as origen, otro_cliente.session_transaction() as destino:
        destino.update(origen)
    with ThreadPoolExecutor(max_workers=2) as hilos:
        dolor = hilos.submit(
            escribir,
            datos.cliente_dolor,
            datos.ruta_dolor + "/dolores",
            datos.cuerpo_dolor | {"zonas": ["cuadriceps"]},
        )
        try:
            assert dolor_insertado.wait(timeout=10)
            serie = hilos.submit(
                escribir,
                otro_cliente,
                datos.ruta_dolor + "/series",
                {
                    "id": str(nuevo_id(datos.reloj)),
                    "ejercicio_planificado_id": datos.cuerpo_dolor["ejercicio_planificado_id"],
                    "repeticiones": 10,
                    "carga": "20.50",
                },
            )
            assert serie_leyendo.wait(timeout=10)
        finally:
            continuar.set()
        assert dolor.result(timeout=15).status_code == 201
        assert serie.result(timeout=15).status_code == 409


def test_dolor_sin_alternativa_quita_e_impide_registrar_serie(dolor_api):
    datos = dolor_api
    cliente, ruta = datos.cliente_dolor, datos.ruta_dolor
    assert escribir(cliente, ruta + "/dolores", datos.cuerpo_dolor | {"zonas": ["cuadriceps"]}).status_code == 201
    lectura = cliente.get(ruta).json
    ejercicio = lectura["ejercicios"][0]
    assert ejercicio["objetivos"]["series"] == ejercicio["pendiente"] == 0
    assert any("Se quita" in r["datos"]["explicacion"] for r in ejercicio["explicacion"])
    assert (
        escribir(
            cliente,
            ruta + "/series",
            {
                "id": str(nuevo_id(datos.reloj)),
                "ejercicio_planificado_id": ejercicio["id"],
                "repeticiones": 10,
                "carga": "20.50",
            },
        ).status_code
        == 409
    )


def test_quitadas_en_vivo_no_impiden_avanzar_la_propuesta(dolor_api):
    datos = dolor_api
    cliente, ruta = datos.cliente_dolor, datos.ruta_dolor
    assert escribir(cliente, ruta + "/dolores", datos.cuerpo_dolor | {"zonas": ["cuadriceps"]}).status_code == 201
    lectura = cliente.get(ruta).json
    assert all(e["pendiente"] == 0 for e in lectura["ejercicios"])
    siguiente = cliente.get("/api/entrenamiento/propuesta").json
    assert siguiente["sesion_planificada"]["id"] != lectura["sesion_planificada"]["id"]


@pytest.mark.parametrize(
    ("series_antes", "carga_antes", "carga_esperada", "hubo_suba"),
    [
        (0, "23.00", "23.00", False),
        (1, "20.50", "23.00", False),
        (1, "23.00", "20.50", True),
        (2, "23.00", "23.00", True),
    ],
)
def test_tope_semanal_conserva_suba_realizada_antes_del_dolor(
    dolor_api, series_antes, carga_antes, carga_esperada, hubo_suba
):
    from datetime import timedelta

    datos = dolor_api
    cliente, ruta = datos.cliente_dolor, datos.ruta_dolor
    ejercicio = datos.propuesta_dolor["ejercicios"][0]
    assert ejercicio["objetivos"]["carga"] == "23.00"
    serie = {"ejercicio_planificado_id": ejercicio["id"], "repeticiones": 12, "rir": 2}
    for _ in range(series_antes):
        assert (
            escribir(
                cliente, ruta + "/series", serie | {"id": str(nuevo_id(datos.reloj)), "carga": carga_antes}
            ).status_code
            == 201
        )
    assert escribir(cliente, ruta + "/dolores", datos.cuerpo_dolor).status_code == 201
    for _ in range(ejercicio["objetivos"]["series"] - series_antes):
        assert (
            escribir(
                cliente, ruta + "/series", serie | {"id": str(nuevo_id(datos.reloj)), "carga": "20.50"}
            ).status_code
            == 201
        )
    # Una sesión intermedia sin dolor libera el freno 1, pero no el tope semanal.
    datos.reloj.avanzar(timedelta(days=1))
    intermedia = str(nuevo_id(datos.reloj))
    assert (
        escribir(
            cliente,
            "/api/entrenamiento/sesiones",
            {"id": intermedia, "sesion_planificada_id": datos.propuesta_dolor["sesion_planificada"]["id"]},
        ).status_code
        == 201
    )
    assert (
        "dolor_reportado"
        in cliente.get(f"/api/entrenamiento/sesiones/{intermedia}").json["prescripcion_efectiva"]["frenos"]
    )
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute(
            "SELECT s.id FROM sesiones_planificadas s JOIN sesiones_planificadas anterior "
            "ON s.programa_id=anterior.programa_id WHERE anterior.id=%s AND s.posicion=2",
            (a_bytes(desde_texto(datos.propuesta_dolor["sesion_planificada"]["id"])),),
        )
        siguiente = str(desde_bytes(cursor.fetchone()["id"]))
    datos.reloj.avanzar(timedelta(days=1))
    sesion = str(nuevo_id(datos.reloj))
    assert (
        escribir(cliente, "/api/entrenamiento/sesiones", {"id": sesion, "sesion_planificada_id": siguiente}).status_code
        == 201
    )
    lectura = cliente.get(f"/api/entrenamiento/sesiones/{sesion}").json
    assert lectura["prescripcion_efectiva"]["frenos"] == (["tope_semanal"] if hubo_suba else [])
    assert lectura["ejercicios"][0]["objetivos"]["carga"] == carga_esperada


def test_mysql_dolor_se_libera_en_la_tercera_sesion_realizada(dolor_api):
    from datetime import timedelta

    datos = dolor_api
    cliente = datos.cliente_dolor
    assert escribir(cliente, datos.ruta_dolor + "/dolores", datos.cuerpo_dolor).status_code == 201
    for numero in (2, 3):
        datos.reloj.avanzar(timedelta(weeks=1))
        sesion_id = str(nuevo_id(datos.reloj))
        assert (
            escribir(
                cliente,
                "/api/entrenamiento/sesiones",
                {
                    "id": sesion_id,
                    "sesion_planificada_id": datos.propuesta_dolor["sesion_planificada"]["id"],
                },
            ).status_code
            == 201
        )
        ruta = f"/api/entrenamiento/sesiones/{sesion_id}"
        lectura = cliente.get(ruta).json
        ejercicio = lectura["ejercicios"][0]
        assert ("dolor_reportado" in lectura["prescripcion_efectiva"]["frenos"]) == (numero == 2)
        assert Decimal(ejercicio["objetivos"]["carga"]) == Decimal("20.50" if numero == 2 else "23.00")
        assert not lectura["sustituciones"]
        if numero == 2:
            for _ in range(ejercicio["objetivos"]["series"]):
                assert (
                    escribir(
                        cliente,
                        ruta + "/series",
                        {
                            "id": str(nuevo_id(datos.reloj)),
                            "ejercicio_planificado_id": ejercicio["id"],
                            "repeticiones": 12,
                            "carga": "20.50",
                            "rir": 2,
                        },
                    ).status_code
                    == 201
                )


@pytest.mark.parametrize("zonas", [[], ["otra"], ["rodillas", "rodillas"], "rodillas", [None]])
def test_dolor_valida_zonas_sin_insertar(dolor_api, zonas):
    datos = dolor_api
    assert (
        escribir(datos.cliente_dolor, datos.ruta_dolor + "/dolores", datos.cuerpo_dolor | {"zonas": zonas}).status_code
        == 422
    )
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT COUNT(*) AS cantidad FROM dolores_reportados")
        assert cursor.fetchone()["cantidad"] == 0


def test_chequeo_con_dolor_sustituye_al_iniciar_y_avisa(entrenamiento_api):
    from gimnasio.demo import servicio as demo

    datos = entrenamiento_api
    datos.app.config["MODO_DEMO"] = True
    with datos.app.app_context():
        demo.reiniciar()
    cliente = datos.app.test_client()
    cliente.post("/api/sesion/demo/socio", headers={"X-Gimnasio": "1"})
    cuerpo = {"id": str(nuevo_id(datos.reloj)), "sueno": 5, "energia": 5, "zonas": ["rodillas"]}
    assert escribir(cliente, "/api/entrenamiento/chequeos", cuerpo).status_code == 201
    assert escribir(cliente, "/api/entrenamiento/chequeos", cuerpo).status_code == 201
    propuesta = cliente.get("/api/entrenamiento/propuesta").json
    assert propuesta["frenos"] == ["dolor_reportado"]
    assert propuesta["ejercicios"][0]["objetivos"]["carga"] == "20.50"
    sesion_id = str(nuevo_id(datos.reloj))
    assert (
        escribir(
            cliente,
            "/api/entrenamiento/sesiones",
            {
                "id": sesion_id,
                "sesion_planificada_id": propuesta["sesion_planificada"]["id"],
            },
        ).status_code
        == 201
    )
    lectura = cliente.get(f"/api/entrenamiento/sesiones/{sesion_id}").json
    assert lectura["sustituciones"][propuesta["ejercicios"][0]["id"]]["nombre"] == "Sentadilla en cajón ficticia"
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT origen,chequeo_id FROM dolores_reportados")
        dolores = cursor.fetchall()
        assert len(dolores) == 1
        assert dolores[0]["origen"] == "chequeo" and dolores[0]["chequeo_id"] == a_bytes(desde_texto(cuerpo["id"]))
        cursor.execute("SELECT freno FROM avisos_entrenador")
        assert cursor.fetchall() == [{"freno": "dolor_reportado"}]
    # Reintentar el inicio no duplica el aviso; otro dolor en vivo sí deja otro.
    assert (
        escribir(
            cliente,
            "/api/entrenamiento/sesiones",
            {"id": sesion_id, "sesion_planificada_id": propuesta["sesion_planificada"]["id"]},
        ).status_code
        == 201
    )
    dolor = {
        "id": str(nuevo_id(datos.reloj)),
        "ejercicio_planificado_id": propuesta["ejercicios"][0]["id"],
        "zonas": ["cuadriceps"],
    }
    ruta = f"/api/entrenamiento/sesiones/{sesion_id}/dolores"
    assert escribir(cliente, ruta, dolor).status_code == 201
    assert escribir(cliente, ruta, dolor).status_code == 201
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT freno FROM avisos_entrenador")
        assert cursor.fetchall() == [{"freno": "dolor_reportado"}] * 2


def test_dolores_conjuntos_respetan_chequeo_vigente_y_fecha_local(entrenamiento_api):
    from datetime import date, datetime
    from zoneinfo import ZoneInfo

    from gimnasio.entrenamiento.servicio import preparar_dolores_sesiones

    datos = entrenamiento_api
    zona = ZoneInfo("America/Asuncion")
    socio = datos.usuarios["socio"]
    with datos.app.app_context(), transaccion() as cursor:

        def chequeo(fecha, momento, zonas, socio_id=socio):
            identificador = nuevo_id(datos.reloj)
            repositorio.insertar_chequeo(cursor, identificador, socio_id, fecha, 5, 5, momento.replace(tzinfo=zona))
            for zona_dolor in zonas:
                repositorio.insertar_dolor(
                    cursor,
                    nuevo_id(datos.reloj),
                    socio_id,
                    zona_dolor,
                    datos.reloj.ahora(),
                    chequeo_id=identificador,
                )

        def sesion(momento):
            identificador = nuevo_id(datos.reloj)
            repositorio.insertar_sesion(cursor, identificador, socio, datos.sesiones[0], momento.replace(tzinfo=zona))
            return repositorio.obtener_sesion(cursor, identificador)

        # Las horas son locales: medianoche cambia el chequeo aplicable.
        chequeo(date(2026, 10, 26), datetime(2026, 10, 26, 20), ("rodillas", "hombros"))
        primera = sesion(datetime(2026, 10, 26, 23, 59))
        chequeo(date(2026, 10, 26), datetime(2026, 10, 26, 23, 59), ())
        neutra = sesion(datetime(2026, 10, 26, 23, 59))
        chequeo(date(2026, 10, 27), datetime(2026, 10, 27), ("cuello",))
        chequeo(date(2026, 10, 27), datetime(2026, 10, 27), ("zona_lumbar",), datos.usuarios["ajeno"])
        siguiente = sesion(datetime(2026, 10, 27))
        chequeo(date(2026, 10, 27), datetime(2026, 10, 27, 1), ("cuadriceps",))
        otro_dia = sesion(datetime(2026, 10, 28))
        repositorio.insertar_dolor(
            cursor,
            nuevo_id(datos.reloj),
            socio,
            "gluteos",
            datos.reloj.ahora(),
            sesion_id=desde_bytes(primera["id"]),
        )
        sesiones = [primera, neutra, siguiente, otro_dia]
        efectivas = [{"sesion_realizada_id": s["id"], "sesion_creada_en": s["creada_en"]} for s in sesiones]
        dolores = preparar_dolores_sesiones(efectivas, repositorio.listar_dolores_socio(cursor, socio), zona)
        assert dolores == {primera["id"]: ("gluteos", "hombros", "rodillas"), siguiente["id"]: ("cuello",)}
        for realizada, fecha in zip(
            sesiones, (date(2026, 10, 26), date(2026, 10, 26), date(2026, 10, 27), date(2026, 10, 28)), strict=True
        ):
            assert dolores.get(realizada["id"], ()) == repositorio.dolores_sesion(
                cursor, desde_bytes(realizada["id"]), fecha
            )
