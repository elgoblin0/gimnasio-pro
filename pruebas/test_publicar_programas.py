"""Publicación de una semana tipo: límites, transacción, versiones e historial."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.ids import a_bytes, desde_bytes, desde_texto, nuevo_id
from gimnasio.demo import servicio as demo
from gimnasio.entrenamiento import servicio as entrenamiento
from gimnasio.programas import servicio

EJERCICIO = "019a2747-3600-7000-8000-000000000001"


def publicacion(ejercicio=EJERCICIO, version=1):
    return {
        "version_base": version,
        "semanas": 8,
        "sesiones": [
            {
                "nombre": "Fuerza",
                "ejercicios": [
                    {
                        "ejercicio_id": ejercicio,
                        "series": 3,
                        "repeticiones_minimas": 8,
                        "repeticiones_maximas": 12,
                        "rir_objetivo": 2,
                        "descanso": 90,
                        "carga": 20,
                    }
                ],
            }
        ],
    }


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("semanas", 3),
        ("semanas", 13),
        ("semanas", True),
        ("semanas", 4.5),
        ("sesiones", []),
        ("sesiones", [publicacion()["sesiones"][0]] * 7),
        ("version_base", True),
        ("version_base", 0),
    ],
)
def test_limites_del_programa(campo, valor):
    datos = publicacion()
    datos[campo] = valor
    with pytest.raises(ErrorDeDominio) as error:
        servicio._validar_publicacion(datos, {EJERCICIO: {"medidas_aplicables": ["repeticiones", "carga"]}}, {})
    assert (error.value.codigo, error.value.estado_http) == ("programa_invalido", 422)


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("series", 0),
        ("series", 11),
        ("series", True),
        ("repeticiones_minimas", 0),
        ("repeticiones_minimas", 13),
        ("repeticiones_maximas", 0),
        ("repeticiones_maximas", 1.5),
        ("carga", None),
        ("carga", -1),
        ("carga", "NaN"),
        ("duracion", 30),
        ("distancia", 2),
        ("rir_objetivo", -1),
        ("rir_objetivo", 6),
        ("descanso", -1),
        ("ejercicio_id", "inexistente"),
    ],
)
def test_limites_y_medidas_del_ejercicio(campo, valor):
    datos = publicacion()
    datos["sesiones"][0]["ejercicios"][0][campo] = valor
    with pytest.raises(ErrorDeDominio) as error:
        servicio._validar_publicacion(datos, {EJERCICIO: {"medidas_aplicables": ["repeticiones", "carga"]}}, {})
    assert (error.value.codigo, error.value.estado_http) == ("programa_invalido", 422)


@pytest.mark.parametrize("cantidad", [0, 13])
def test_limite_de_ejercicios(cantidad):
    datos = publicacion()
    datos["sesiones"][0]["ejercicios"] *= cantidad
    with pytest.raises(ErrorDeDominio, match="entre 1 y 12 ejercicios"):
        servicio._validar_publicacion(datos, {}, {})


@pytest.mark.parametrize("semanas,sesiones,ejercicios,series", [(4, 1, 1, 1), (12, 6, 12, 10)])
def test_extremos_validos(semanas, sesiones, ejercicios, series):
    datos = publicacion()
    datos["semanas"] = semanas
    datos["sesiones"][0]["ejercicios"][0]["series"] = series
    datos["sesiones"][0]["ejercicios"] *= ejercicios
    datos["sesiones"] *= sesiones
    assert servicio._validar_publicacion(datos, {EJERCICIO: {"medidas_aplicables": ["repeticiones", "carga"]}}, {})


def test_carga_omitida_usa_historial_sin_cambiar_el_cuerpo():
    datos = publicacion()
    del datos["sesiones"][0]["ejercicios"][0]["carga"]
    antes = deepcopy(datos)
    sesiones = servicio._validar_publicacion(
        datos, {EJERCICIO: {"medidas_aplicables": ["repeticiones", "carga"]}}, {EJERCICIO: 17}
    )
    assert sesiones[0]["ejercicios"][0]["carga"] == 17
    assert datos == antes


def test_menor_carga_de_la_ultima_sesion_por_ejercicio(monkeypatch, reloj_fijo):
    ejercicio, otro = a_bytes(nuevo_id(reloj_fijo)), a_bytes(nuevo_id(reloj_fijo))
    primera, ultima = a_bytes(nuevo_id(reloj_fijo)), a_bytes(nuevo_id(reloj_fijo))
    filas = [
        {
            "ejercicio_hecho_resuelto_id": identificador,
            "sesion_creada_en": momento,
            "sesion_realizada_id": sesion,
            "carga": carga,
        }
        for identificador, momento, sesion, carga in (
            (ejercicio, reloj_fijo.ahora(), primera, 10),
            (ejercicio, reloj_fijo.ahora() + timedelta(days=1), ultima, 25),
            (ejercicio, reloj_fijo.ahora() + timedelta(days=1), ultima, 20),
            (otro, reloj_fijo.ahora(), primera, 30),
        )
    ]
    monkeypatch.setattr(entrenamiento.repositorio, "listar_series_vigentes", lambda *_: filas)
    assert entrenamiento.cargas_ultima_sesion(None, nuevo_id(reloj_fijo)) == {
        str(desde_bytes(ejercicio)): 20,
        str(desde_bytes(otro)): 30,
    }


def test_medidas_de_duracion_y_distancia():
    datos = publicacion()
    datos["sesiones"][0]["ejercicios"] = [{"ejercicio_id": EJERCICIO, "series": 1, "duracion": 60, "distancia": 0.5}]
    catalogo = {EJERCICIO: {"medidas_aplicables": ["duracion", "distancia"]}}
    assert servicio._validar_publicacion(datos, catalogo, {})
    datos["sesiones"][0]["ejercicios"][0]["duracion"] = 0
    with pytest.raises(ErrorDeDominio):
        servicio._validar_publicacion(datos, catalogo, {})


@pytest.fixture
def programas_api(app_con_bd, sembrar_demo):
    app_con_bd.config["MODO_DEMO"] = True
    sembrar_demo(app_con_bd)
    with app_con_bd.app_context(), transaccion() as cursor:
        cursor.execute("SELECT id FROM usuarios WHERE rol='socio' AND es_demo=TRUE ORDER BY id LIMIT 1")
        socio = str(desde_bytes(cursor.fetchone()["id"]))
    cliente = app_con_bd.test_client()
    cliente.post("/api/sesion/demo/entrenador", headers={"X-Gimnasio": "1"})
    ejercicios = cliente.get("/api/ejercicios").json["ejercicios"]
    fuerza = next(e["id"] for e in ejercicios if e["nombre"] == "Sentadilla ficticia")
    return app_con_bd, cliente, socio, fuerza


def publicar(cliente, socio, datos, clave=None):
    return cliente.post(
        f"/api/socios/{socio}/programas",
        json=datos,
        headers={"X-Gimnasio": "1", "Idempotency-Key": clave or str(uuid4())},
    )


def escribir_plantilla(cliente, datos=None, identificador=None, *, archivar=False, clave=None):
    ruta = "/api/programas/plantillas"
    if identificador:
        ruta += f"/{identificador}"
    if archivar:
        ruta += "/archivar"
    return cliente.open(
        ruta,
        method="PUT" if identificador and not archivar else "POST",
        json=datos or {},
        headers={"X-Gimnasio": "1", "Idempotency-Key": clave or str(uuid4())},
    )


def datos_plantilla(ejercicio=EJERCICIO):
    sesiones = publicacion(ejercicio)["sesiones"]
    del sesiones[0]["ejercicios"][0]["carga"]
    return {"nombre": "Fuerza ficticia", "descripcion": "Semana tipo ficticia", "sesiones": sesiones}


@pytest.mark.bd
def test_administracion_crea_edita_archiva_y_filtra_plantillas(programas_api):
    _, cliente, _, fuerza = programas_api
    cliente.post("/api/sesion/demo/administracion", headers={"X-Gimnasio": "1"})
    datos = datos_plantilla(fuerza)
    clave = str(uuid4())
    respuesta = escribir_plantilla(cliente, datos, clave=clave)
    assert respuesta.status_code == 201, respuesta.json
    assert escribir_plantilla(cliente, datos, clave=clave).json == respuesta.json
    plantilla = respuesta.json["plantilla"]
    assert plantilla["archivada"] is False
    identificador = plantilla["id"]
    datos["sesiones"][0]["ejercicios"][0]["series"] = 5
    datos["sesiones"].append(deepcopy(datos["sesiones"][0]))
    editada = escribir_plantilla(cliente, datos, identificador)
    assert editada.status_code == 200, editada.json
    assert len(editada.json["plantilla"]["sesiones"]) == 2
    assert editada.json["plantilla"]["sesiones"][0]["ejercicios"][0]["series"] == 5
    assert escribir_plantilla(cliente, identificador=identificador, archivar=True).json["plantilla"]["archivada"]
    assert next(p for p in cliente.get("/api/programas/plantillas").json["plantillas"] if p["id"] == identificador)[
        "archivada"
    ]
    cliente.post("/api/sesion/demo/entrenador", headers={"X-Gimnasio": "1"})
    assert identificador not in {p["id"] for p in cliente.get("/api/programas/plantillas").json["plantillas"]}


@pytest.mark.bd
@pytest.mark.parametrize("rol", ["socio", "recepcion", "entrenador"])
def test_solo_administracion_modifica_plantillas(programas_api, rol):
    _, cliente, _, fuerza = programas_api
    identificador = cliente.get("/api/programas/plantillas").json["plantillas"][0]["id"]
    cliente.post(f"/api/sesion/demo/{rol}", headers={"X-Gimnasio": "1"})
    assert escribir_plantilla(cliente, datos_plantilla(fuerza)).status_code == 403
    assert escribir_plantilla(cliente, datos_plantilla(fuerza), identificador).status_code == 403
    assert escribir_plantilla(cliente, identificador=identificador, archivar=True).status_code == 403


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("series", 11),
        ("repeticiones_minimas", 13),
        ("rir_objetivo", 6),
        ("descanso", -1),
        ("ejercicio_id", "inexistente"),
        ("carga", 20),
        ("carga_partida", 10),
    ],
)
def test_plantilla_respeta_limites_sin_carga(campo, valor):
    datos = datos_plantilla()
    datos["sesiones"][0]["ejercicios"][0][campo] = valor
    with pytest.raises(ErrorDeDominio):
        servicio._validar_plantilla(datos, {EJERCICIO: {"medidas_aplicables": ["repeticiones", "carga"]}})


def test_plantilla_no_necesita_carga_ni_socio():
    sesiones = servicio._validar_plantilla(
        datos_plantilla(), {EJERCICIO: {"medidas_aplicables": ["repeticiones", "carga"]}}
    )
    assert sesiones[0]["ejercicios"][0]["series"] == 3


@pytest.mark.bd
def test_ultima_plantilla_activa_no_se_archiva(programas_api):
    _, cliente, _, _ = programas_api
    cliente.post("/api/sesion/demo/administracion", headers={"X-Gimnasio": "1"})
    plantillas = cliente.get("/api/programas/plantillas").json["plantillas"]
    for plantilla in plantillas[:-1]:
        assert escribir_plantilla(cliente, identificador=plantilla["id"], archivar=True).status_code == 200
    respuesta = escribir_plantilla(cliente, identificador=plantillas[-1]["id"], archivar=True)
    assert respuesta.status_code == 409
    assert respuesta.json["error"]["codigo"] == "ultima_plantilla_activa"


@pytest.mark.bd
def test_reemplazo_plantilla_es_atomico(programas_api, monkeypatch):
    _, cliente, _, fuerza = programas_api
    cliente.post("/api/sesion/demo/administracion", headers={"X-Gimnasio": "1"})
    anterior = cliente.get("/api/programas/plantillas").json["plantillas"]

    def fallar(*argumentos):
        raise ErrorDeDominio("prueba", "Fallo ficticio.", 503)

    monkeypatch.setattr(servicio.repositorio, "insertar_ejercicio_plantilla", fallar)
    assert escribir_plantilla(cliente, datos_plantilla(fuerza), anterior[0]["id"]).status_code == 503
    assert cliente.get("/api/programas/plantillas").json["plantillas"] == anterior


@pytest.mark.bd
def test_editar_y_archivar_conserva_versiones_secuencia_y_prescripcion(programas_api, reloj_fijo):
    app, cliente, socio, fuerza = programas_api
    plantilla = cliente.get("/api/programas/plantillas").json["plantillas"][0]
    datos = publicacion(fuerza)
    datos["plantilla_id"] = plantilla["id"]
    assert publicar(cliente, socio, datos).status_code == 201
    with app.app_context():
        antes = servicio.listar_programas(desde_texto(socio))
    cliente.post("/api/sesion/demo/socio", headers={"X-Gimnasio": "1"})
    propuesta = cliente.get("/api/entrenamiento/propuesta").json
    sesion_id = str(nuevo_id(reloj_fijo))
    assert (
        escribir(
            cliente,
            "/api/entrenamiento/sesiones",
            {"id": sesion_id, "sesion_planificada_id": propuesta["sesion_planificada"]["id"]},
        ).status_code
        == 201
    )
    ruta = f"/api/entrenamiento/sesiones/{sesion_id}"
    efectiva = cliente.get(ruta).json["prescripcion_efectiva"]
    cliente.post("/api/sesion/demo/administracion", headers={"X-Gimnasio": "1"})
    cambio = datos_plantilla(fuerza)
    cambio["sesiones"][0]["ejercicios"][0]["series"] = 1
    assert escribir_plantilla(cliente, cambio, plantilla["id"]).status_code == 200
    assert escribir_plantilla(cliente, identificador=plantilla["id"], archivar=True).status_code == 200
    with app.app_context():
        assert servicio.listar_programas(desde_texto(socio)) == antes
    cliente.post("/api/sesion/demo/socio", headers={"X-Gimnasio": "1"})
    assert cliente.get(ruta).json["prescripcion_efectiva"] == efectiva
    cliente.post("/api/sesion/demo/entrenador", headers={"X-Gimnasio": "1"})
    datos["version_base"] = 2
    rechazada = publicar(cliente, socio, datos)
    assert rechazada.status_code == 409
    assert rechazada.json["error"]["codigo"] == "plantilla_archivada"
    del datos["plantilla_id"]
    assert publicar(cliente, socio, datos).json["programa"]["version"] == 3


@pytest.mark.bd
def test_publica_24_sesiones_idempotentes_e_inmutables(programas_api):
    app, cliente, socio, fuerza = programas_api
    anterior = cliente.get(f"/api/socios/{socio}/programa").json["programa"]
    assert anterior["duracion_semanas"] is None
    datos = publicacion(fuerza)
    datos["sesiones"] *= 3
    clave = str(uuid4())
    respuesta = publicar(cliente, socio, datos, clave)
    assert respuesta.status_code == 201, respuesta.json
    assert publicar(cliente, socio, datos, clave).data == respuesta.data
    con_otra_duracion = {**datos, "semanas": 4}
    reutilizada = publicar(cliente, socio, con_otra_duracion, clave)
    assert reutilizada.status_code == 422 and reutilizada.json["error"]["codigo"] == "clave_reutilizada"
    programa = respuesta.json["programa"]
    assert programa["version"] == 2 and programa["duracion_semanas"] == 8
    assert len(programa["sesiones"]) == 3
    assert cliente.get(f"/api/socios/{socio}/programa").json["programa"] == programa
    with app.app_context():
        versiones = servicio.listar_programas(desde_texto(socio))
        assert app.json.loads(app.json.dumps(servicio._semana_tipo(versiones[0]))) == anterior
        sesiones = versiones[1]["sesiones_planificadas"]
        assert [s["posicion"] for s in sesiones] == list(range(1, 25))
        assert [s["nombre"] for s in sesiones] == [f"Semana {n} · Fuerza" for n in range(1, 9) for _ in range(3)]
        assert [s["semana"] for s in sesiones] == [n for n in range(1, 9) for _ in range(3)]
    assert publicar(cliente, socio, datos).status_code == 409
    datos["version_base"] = None
    assert publicar(cliente, socio, datos).json["error"]["codigo"] == "version_desactualizada"


@pytest.mark.bd
def test_plantillas_catalogo_y_reinicio(programas_api):
    app, cliente, _, _ = programas_api
    plantillas = cliente.get("/api/programas/plantillas").json["plantillas"]
    assert {p["nombre"] for p in plantillas} == {"Inicial de cuerpo completo", "3 días", "4 días"}
    assert sorted(len(p["sesiones"]) for p in plantillas) == [2, 3, 4]
    catalogo = {e["id"]: e for e in cliente.get("/api/ejercicios").json["ejercicios"]}
    for plantilla in plantillas:
        for sesion in plantilla["sesiones"]:
            for ejercicio in sesion["ejercicios"]:
                entrada = catalogo[ejercicio["ejercicio_id"]]
                assert entrada["zonas"] and entrada["patron_movimiento"] and entrada["equipo"]
                assert entrada["incremento_carga"]
    with app.app_context():
        demo.reiniciar()
    assert len(cliente.get("/api/programas/plantillas").json["plantillas"]) == 3


@pytest.mark.bd
def test_rechaza_socio_no_asignado_y_lectura(programas_api):
    app, cliente, socio, fuerza = programas_api
    with app.app_context(), transaccion() as cursor:
        cursor.execute(
            "UPDATE asignaciones_entrenador SET hasta=desde WHERE socio_id=%s", (a_bytes(desde_texto(socio)),)
        )
    assert publicar(cliente, socio, publicacion(fuerza)).status_code == 403
    assert cliente.get(f"/api/socios/{socio}/programa").status_code == 403


@pytest.mark.bd
def test_publicacion_invalida_no_deja_escrituras(programas_api):
    app, cliente, socio, fuerza = programas_api
    datos = publicacion(fuerza)
    datos["sesiones"].append({"nombre": "Sin ejercicios", "ejercicios": []})
    respuesta = publicar(cliente, socio, datos)
    assert respuesta.status_code == 422 and respuesta.json["error"]["codigo"] == "programa_invalido"
    with app.app_context():
        assert len(servicio.listar_programas(desde_texto(socio))) == 1


@pytest.mark.bd
def test_carga_omitida_se_guarda_desde_ultima_sesion(programas_api):
    app, cliente, socio, fuerza = programas_api
    datos = publicacion(fuerza)
    del datos["sesiones"][0]["ejercicios"][0]["carga"]
    respuesta = publicar(cliente, socio, datos)
    assert respuesta.status_code == 201, respuesta.json
    with app.app_context():
        assert {
            e["carga"]
            for s in servicio.obtener_programa(desde_texto(socio), 2)["sesiones_planificadas"]
            for e in s["ejercicios_planificados"]
        } == {20.50}


@pytest.mark.bd
@pytest.mark.parametrize("con_programa", [True, False])
def test_dos_publicaciones_simultaneas_no_duplican_version(programas_api, con_programa):
    app, _, socio, fuerza = programas_api
    if not con_programa:
        with app.app_context(), transaccion() as cursor:
            cursor.execute("""SELECT u.id FROM usuarios u LEFT JOIN programas_entrenamiento p ON p.socio_id=u.id
                              WHERE u.rol='socio' AND p.id IS NULL ORDER BY u.id LIMIT 1""")
            socio = str(desde_bytes(cursor.fetchone()["id"]))
    barrera = Barrier(2)

    def intentar():
        cliente = app.test_client()
        cliente.post("/api/sesion/demo/entrenador", headers={"X-Gimnasio": "1"})
        barrera.wait(timeout=10)
        return publicar(cliente, socio, publicacion(fuerza, version=1 if con_programa else None)).status_code

    with ThreadPoolExecutor(max_workers=2) as hilos:
        assert sorted(hilos.map(lambda _: intentar(), range(2))) == [201, 409]
    with app.app_context():
        assert [p["version"] for p in servicio.listar_programas(desde_texto(socio))] == (
            [1, 2] if con_programa else [1]
        )


@pytest.mark.bd
def test_nueva_secuencia_y_progresion_del_historial_anterior(programas_api, reloj_fijo):
    _, cliente, socio, fuerza = programas_api
    cliente.post("/api/sesion/demo/socio", headers={"X-Gimnasio": "1"})
    anterior = cliente.get("/api/entrenamiento/propuesta").json
    assert anterior["ejercicios"][0]["objetivos"]["carga"] == "23.00"
    cliente.post("/api/sesion/demo/entrenador", headers={"X-Gimnasio": "1"})
    datos = publicacion(fuerza)
    datos["sesiones"][0]["ejercicios"][0]["series"] = 2
    datos["sesiones"][0]["ejercicios"][0]["carga"] = 20
    assert publicar(cliente, socio, datos).status_code == 201
    cliente.post("/api/sesion/demo/socio", headers={"X-Gimnasio": "1"})
    nueva = cliente.get("/api/entrenamiento/propuesta").json
    assert nueva["sesion_planificada"]["nombre"] == "Semana 1 · Fuerza"
    assert nueva["ejercicios"][0]["realizado"] == 0
    assert nueva["ejercicios"][0]["objetivos"]["carga"] == "23.00"
    reloj_fijo.avanzar(timedelta(weeks=2))
    pendiente = cliente.get("/api/entrenamiento/propuesta").json
    assert pendiente["sesion_planificada"] == nueva["sesion_planificada"]


def escribir(cliente, ruta, datos):
    return cliente.post(ruta, json=datos, headers={"X-Gimnasio": "1", "Idempotency-Key": str(uuid4())})


@pytest.mark.bd
def test_publicar_conserva_prescripcion_de_sesion_en_curso(programas_api, reloj_fijo):
    _, cliente, socio, fuerza = programas_api
    cliente.post("/api/sesion/demo/socio", headers={"X-Gimnasio": "1"})
    propuesta = cliente.get("/api/entrenamiento/propuesta").json
    sesion_id = str(nuevo_id(reloj_fijo))
    respuesta = escribir(
        cliente,
        "/api/entrenamiento/sesiones",
        {
            "id": sesion_id,
            "sesion_planificada_id": propuesta["sesion_planificada"]["id"],
        },
    )
    assert respuesta.status_code == 201, respuesta.json
    ruta = f"/api/entrenamiento/sesiones/{sesion_id}"
    antes = cliente.get(ruta).json
    cliente.post("/api/sesion/demo/entrenador", headers={"X-Gimnasio": "1"})
    assert publicar(cliente, socio, publicacion(fuerza)).status_code == 201
    cliente.post("/api/sesion/demo/socio", headers={"X-Gimnasio": "1"})
    despues = cliente.get(ruta).json
    assert despues["prescripcion_efectiva"] == antes["prescripcion_efectiva"]
    assert despues["ejercicios"] == antes["ejercicios"]


@pytest.mark.bd
def test_semana_realizada_y_ausencia_no_acumulan_trabajo(programas_api, reloj_fijo):
    _, cliente, socio, fuerza = programas_api
    datos = publicacion(fuerza)
    datos["sesiones"][0]["ejercicios"][0]["series"] = 1
    datos["sesiones"] *= 3
    assert publicar(cliente, socio, datos).status_code == 201
    cliente.post("/api/sesion/demo/socio", headers={"X-Gimnasio": "1"})
    for _ in range(3):
        propuesta = cliente.get("/api/entrenamiento/propuesta").json
        sesion_id = str(nuevo_id(reloj_fijo))
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
        assert (
            escribir(
                cliente,
                f"/api/entrenamiento/sesiones/{sesion_id}/series",
                {
                    "id": str(nuevo_id(reloj_fijo)),
                    "ejercicio_planificado_id": propuesta["ejercicios"][0]["id"],
                    "repeticiones": 10,
                    "carga": "20.50",
                    "rir": 2,
                },
            ).status_code
            == 201
        )
        reloj_fijo.avanzar(timedelta(days=1))
    pendiente = cliente.get("/api/entrenamiento/propuesta").json
    assert pendiente["sesion_planificada"]["nombre"] == "Semana 2 · Fuerza"
    reloj_fijo.avanzar(timedelta(weeks=1))
    despues = cliente.get("/api/entrenamiento/propuesta").json
    assert despues["sesion_planificada"] == pendiente["sesion_planificada"]
    assert len(despues["ejercicios"]) == 1
    assert despues["ejercicios"][0]["pendiente"] == 1


@pytest.mark.bd
def test_primera_publicacion_y_carga_obligatoria_sin_historial(programas_api):
    app, cliente, _, fuerza = programas_api
    with app.app_context(), transaccion() as cursor:
        cursor.execute("""SELECT u.id FROM usuarios u LEFT JOIN programas_entrenamiento p ON p.socio_id=u.id
                          WHERE u.rol='socio' AND p.id IS NULL ORDER BY u.id LIMIT 1""")
        socio = str(desde_bytes(cursor.fetchone()["id"]))
    assert cliente.get(f"/api/socios/{socio}/programa").json == {"programa": None}
    datos = publicacion(fuerza, version=None)
    datos["sesiones"][0]["ejercicios"][0]["carga"] = None
    respuesta = publicar(cliente, socio, datos)
    assert respuesta.status_code == 422
    assert respuesta.json["error"]["codigo"] == "programa_invalido"
    datos["sesiones"][0]["ejercicios"][0]["carga"] = 0
    respuesta = publicar(cliente, socio, datos)
    assert respuesta.status_code == 201 and respuesta.json["programa"]["version"] == 1
    assert publicar(cliente, socio, datos).status_code == 409


@pytest.mark.bd
@pytest.mark.parametrize("rol", ["socio", "recepcion"])
def test_permiso_para_publicar_y_leer(programas_api, rol):
    _, cliente, socio, fuerza = programas_api
    cliente.post(f"/api/sesion/demo/{rol}", headers={"X-Gimnasio": "1"})
    assert cliente.get("/api/programas/plantillas").status_code == 403
    assert cliente.get(f"/api/socios/{socio}/programa").status_code == 403
    assert publicar(cliente, socio, publicacion(fuerza)).status_code == 403


@pytest.mark.bd
def test_publicar_exige_idempotencia_y_csrf(programas_api):
    _, cliente, socio, fuerza = programas_api
    ruta = f"/api/socios/{socio}/programas"
    assert cliente.post(ruta, json=publicacion(fuerza), headers={"X-Gimnasio": "1"}).status_code == 428
    assert cliente.post(ruta, json=publicacion(fuerza), headers={"Idempotency-Key": str(uuid4())}).status_code == 403


@pytest.mark.bd
def test_error_durante_generacion_revierte_toda_la_version(programas_api, monkeypatch):
    app, cliente, socio, fuerza = programas_api
    insertar = servicio.repositorio.insertar_sesion
    llamadas = 0

    def fallar(*argumentos):
        nonlocal llamadas
        llamadas += 1
        if llamadas == 2:
            raise ErrorDeDominio("prueba", "Fallo ficticio.", 503)
        return insertar(*argumentos)

    monkeypatch.setattr(servicio.repositorio, "insertar_sesion", fallar)
    assert publicar(cliente, socio, publicacion(fuerza)).status_code == 503
    with app.app_context():
        assert [p["version"] for p in servicio.listar_programas(desde_texto(socio))] == [1]


@pytest.mark.bd
def test_publicacion_sin_consentimiento_de_salud_no_usa_restricciones(programas_api, reloj_fijo):
    from gimnasio.permisos.servicio import registrar_consentimiento

    app, cliente, socio, fuerza = programas_api
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT id FROM usuarios WHERE rol='entrenador' LIMIT 1")
        autor = desde_bytes(cursor.fetchone()["id"])
        for otorgado in (True, False):
            registrar_consentimiento(cursor, desde_texto(socio), "salud", otorgado, "1", autor)
        cursor.execute(
            "INSERT INTO restricciones_salud (id,socio_id,ejercicio_id,descripcion,registrada_en,autor_id) "
            "VALUES (%s,%s,%s,'Detalle ficticio reservado',%s,%s)",
            (
                a_bytes(nuevo_id(reloj_fijo)),
                a_bytes(desde_texto(socio)),
                a_bytes(desde_texto(fuerza)),
                reloj_fijo.ahora(),
                a_bytes(autor),
            ),
        )
    assert publicar(cliente, socio, publicacion(fuerza)).status_code == 201


@pytest.mark.bd
@pytest.mark.parametrize("tipo", ["ejercicio", "patron", "zona"])
def test_publicacion_restricciones_y_levantamiento(programas_api, reloj_fijo, tipo):
    from gimnasio.permisos.servicio import registrar_consentimiento

    consentimiento = True

    app, cliente, socio, fuerza = programas_api
    catalogo = cliente.get("/api/ejercicios").json["ejercicios"]
    original = next(e for e in catalogo if e["id"] == fuerza)
    restriccion = nuevo_id(reloj_fijo)
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT id FROM usuarios WHERE rol='entrenador' LIMIT 1")
        autor = desde_bytes(cursor.fetchone()["id"])
        registrar_consentimiento(cursor, desde_texto(socio), "salud", consentimiento, "1", autor)
        cursor.execute(
            """INSERT INTO restricciones_salud
               (id,socio_id,ejercicio_id,patron_movimiento,zona,descripcion,registrada_en,autor_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                a_bytes(restriccion),
                a_bytes(desde_texto(socio)),
                a_bytes(desde_texto(fuerza)) if tipo == "ejercicio" else None,
                original["patron_movimiento"] if tipo == "patron" else None,
                original["zonas"][0] if tipo == "zona" else None,
                "Detalle ficticio reservado",
                reloj_fijo.ahora(),
                a_bytes(autor),
            ),
        )
        antes = servicio.listar_programas(desde_texto(socio), cursor=cursor)
    respuesta = publicar(cliente, socio, publicacion(fuerza))
    assert respuesta.status_code == 409, respuesta.json
    error = respuesta.json["error"]
    assert error["codigo"] == "choque_restriccion"
    choque = error["choques"][0]
    assert choque["ejercicio_id"] == fuerza
    assert original["nombre"] in choque["mensaje"]
    assert ("Detalle ficticio reservado" in str(respuesta.json)) == consentimiento
    if tipo == "ejercicio":
        assert choque["alternativas"]
        with app.app_context(), transaccion() as cursor:
            for equipo in {e["equipo"] for e in catalogo if e["id"] in original["alternativas"]}:
                cursor.execute("SELECT id FROM equipos WHERE nombre=%s", (equipo,))
                equipo_id = desde_bytes(cursor.fetchone()["id"])
                servicio.repositorio.insertar_cambio_estado(
                    cursor, nuevo_id(reloj_fijo), equipo_id, "fuera_de_servicio", None, autor, reloj_fijo.ahora()
                )
        sin_equipos = publicar(cliente, socio, publicacion(fuerza))
        assert sin_equipos.status_code == 409
        assert sin_equipos.json["error"]["choques"][0]["alternativas"] == []
    if tipo == "patron":
        assert choque["alternativas"] == []
    with app.app_context(), transaccion() as cursor:
        assert servicio.listar_programas(desde_texto(socio), cursor=cursor) == antes
        cursor.execute(
            """INSERT INTO restricciones_salud
               (id,socio_id,zona,descripcion,registrada_en,autor_id,levanta_a)
               VALUES (%s,%s,'rodillas','Levantada',%s,%s,%s)""",
            (
                a_bytes(nuevo_id(reloj_fijo)),
                a_bytes(desde_texto(socio)),
                reloj_fijo.ahora(),
                a_bytes(autor),
                a_bytes(restriccion),
            ),
        )
    assert publicar(cliente, socio, publicacion(fuerza)).status_code == 201

    # Una restricción nueva después de publicar sigue actuando en la propuesta.
    with app.app_context(), transaccion() as cursor:
        cursor.execute(
            """INSERT INTO restricciones_salud
               (id,socio_id,ejercicio_id,patron_movimiento,zona,descripcion,registrada_en,autor_id)
               SELECT %s,socio_id,ejercicio_id,patron_movimiento,zona,descripcion,%s,autor_id
               FROM restricciones_salud WHERE id=%s""",
            (a_bytes(nuevo_id(reloj_fijo)), reloj_fijo.ahora(), a_bytes(restriccion)),
        )
    propuesta = cliente.get(f"/api/entrenamiento/socios/{socio}/propuesta")
    assert propuesta.status_code == 200, propuesta.json
    assert "restriccion_salud" in propuesta.json["frenos"]
    assert "Detalle ficticio reservado" not in str(propuesta.json)


@pytest.mark.parametrize("partida", [-1, True, "NaN", "0.001", "1000000"])
def test_carga_partida_invalida(partida):
    datos = publicacion()
    datos["sesiones"][0]["ejercicios"][0]["carga_partida"] = partida
    with pytest.raises(ErrorDeDominio):
        servicio._validar_publicacion(datos, {EJERCICIO: {"medidas_aplicables": ["carga", "repeticiones"]}}, {})


@pytest.mark.bd
def test_carga_partida_publicada_y_segunda_sesion(programas_api, reloj_fijo):
    app, cliente, socio, fuerza = programas_api
    datos = publicacion(fuerza)
    datos["sesiones"][0]["ejercicios"][0].update(series=1, carga_partida=10)
    assert publicar(cliente, socio, datos).status_code == 201
    with app.app_context():
        programa = servicio.listar_programas(desde_texto(socio))[-1]
        assert {
            e["carga_partida"] for s in programa["sesiones_planificadas"] for e in s["ejercicios_planificados"]
        } == {10}
    cliente.post("/api/sesion/demo/socio", headers={"X-Gimnasio": "1"})
    propuesta = cliente.get("/api/entrenamiento/propuesta").json
    ejercicio = propuesta["ejercicios"][0]
    assert float(ejercicio["objetivos"]["carga"]) == 10
    assert any(r["regla"] == "carga_partida_entrenador" for r in ejercicio["explicacion"])
    sesion_id = str(nuevo_id(reloj_fijo))
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
    assert (
        escribir(
            cliente,
            f"/api/entrenamiento/sesiones/{sesion_id}/series",
            {
                "id": str(nuevo_id(reloj_fijo)),
                "ejercicio_planificado_id": ejercicio["id"],
                "repeticiones": 12,
                "carga": 10,
                "rir": 2,
            },
        ).status_code
        == 201
    )
    reloj_fijo.avanzar(timedelta(days=1))
    segunda = cliente.get("/api/entrenamiento/propuesta").json["ejercicios"][0]
    assert float(segunda["objetivos"]["carga"]) == 12.5
    assert not any(r["regla"] == "carga_partida_entrenador" for r in segunda["explicacion"])


@pytest.mark.bd
def test_cargas_sugeridas_sin_chequeo_y_asignacion(programas_api):
    app, cliente, socio, fuerza = programas_api
    ruta = f"/api/socios/{socio}/programa/cargas-sugeridas?ejercicios={fuerza}"
    respuesta = cliente.get(ruta)
    assert respuesta.status_code == 200
    assert respuesta.json["cargas"][fuerza] is not None
    datos = publicacion(fuerza)
    datos["sesiones"][0]["ejercicios"][0]["carga_partida"] = 0
    assert publicar(cliente, socio, datos).status_code == 201
    assert float(cliente.get(ruta).json["cargas"][fuerza]) > 0
    with app.app_context(), transaccion() as cursor:
        cursor.execute(
            "UPDATE asignaciones_entrenador SET hasta=desde WHERE socio_id=%s", (a_bytes(desde_texto(socio)),)
        )
    assert cliente.get(ruta).status_code == 403


@pytest.mark.bd
def test_cargas_sugeridas_null_sin_historial(programas_api):
    app, cliente, _, fuerza = programas_api
    with app.app_context(), transaccion() as cursor:
        cursor.execute("""SELECT u.id FROM usuarios u LEFT JOIN programas_entrenamiento p ON p.socio_id=u.id
                          WHERE u.rol='socio' AND p.id IS NULL ORDER BY u.id LIMIT 1""")
        socio = str(desde_bytes(cursor.fetchone()["id"]))
    respuesta = cliente.get(f"/api/socios/{socio}/programa/cargas-sugeridas?ejercicios={fuerza}")
    assert respuesta.status_code == 200 and respuesta.json == {"cargas": {fuerza: None}}


@pytest.mark.parametrize("carga,cantidad", [("10", 0), ("41", 1)])
def test_partida_solo_consume_tope_si_conserva_suba(carga, cantidad, reloj_fijo):
    import json
    from datetime import UTC
    from zoneinfo import ZoneInfo

    fecha = reloj_fijo.ahora()
    ejercicio_id = str(nuevo_id(reloj_fijo))
    explicacion = [
        {"regla": "subir_carga", "datos": {"ejercicio_id": ejercicio_id, "carga_base": "40"}},
        {"regla": "carga_partida_entrenador", "datos": {"ejercicio_id": ejercicio_id, "carga": carga}},
    ]
    efectiva = {
        "creada_en": fecha.astimezone(UTC).replace(tzinfo=None),
        "sesion_planificada_id": a_bytes(nuevo_id(reloj_fijo)),
        "ejercicios": json.dumps(
            [{"id": ejercicio_id, "ejercicio_id": EJERCICIO, "objetivos": {"carga": carga}, "explicacion": explicacion}]
        ),
        "explicacion": json.dumps(explicacion),
    }
    local = fecha.astimezone(ZoneInfo("America/Asuncion")).date()
    assert len(entrenamiento.preparar_subas([efectiva], [], ZoneInfo("America/Asuncion"), local)) == cantidad


def test_partida_sin_historial_reemplaza_carga_omitida():
    datos = publicacion()
    datos["sesiones"][0]["ejercicios"][0].update(carga=None, carga_partida=0)
    sesiones = servicio._validar_publicacion(datos, {EJERCICIO: {"medidas_aplicables": ["carga", "repeticiones"]}}, {})
    assert sesiones[0]["ejercicios"][0]["carga"] == 0


def test_partida_se_repite_y_rechaza_valores_distintos():
    datos = publicacion()
    datos["sesiones"][0]["ejercicios"][0]["carga_partida"] = 10
    datos["sesiones"].append(deepcopy(datos["sesiones"][0]))
    del datos["sesiones"][1]["ejercicios"][0]["carga_partida"]
    catalogo = {EJERCICIO: {"medidas_aplicables": ["carga", "repeticiones"]}}
    sesiones = servicio._validar_publicacion(datos, catalogo, {})
    assert all(s["ejercicios"][0]["carga_partida"] == 10 for s in sesiones)
    datos["sesiones"][1]["ejercicios"][0]["carga_partida"] = 15
    with pytest.raises(ErrorDeDominio):
        servicio._validar_publicacion(datos, catalogo, {})


@pytest.mark.bd
@pytest.mark.parametrize("consumida", [False, True])
def test_partida_al_iniciar_version_anterior(programas_api, reloj_fijo, consumida):
    app, cliente, socio, fuerza = programas_api
    datos = publicacion(fuerza)
    datos["sesiones"][0]["ejercicios"][0].update(series=1, carga_partida=10)
    assert publicar(cliente, socio, datos).status_code == 201
    with app.app_context():
        anterior = servicio.listar_programas(desde_texto(socio))[-1]

    def registrar(programa):
        sesion = programa["sesiones_planificadas"][0]
        sesion_id = str(nuevo_id(reloj_fijo))
        assert (
            escribir(
                cliente,
                "/api/entrenamiento/sesiones",
                {
                    "id": sesion_id,
                    "sesion_planificada_id": sesion["id"],
                },
            ).status_code
            == 201
        )
        assert (
            escribir(
                cliente,
                f"/api/entrenamiento/sesiones/{sesion_id}/series",
                {
                    "id": str(nuevo_id(reloj_fijo)),
                    "ejercicio_planificado_id": sesion["ejercicios_planificados"][0]["id"],
                    "repeticiones": 12,
                    "carga": 40,
                    "rir": 2,
                },
            ).status_code
            == 201
        )

    cliente.post("/api/sesion/demo/socio", headers={"X-Gimnasio": "1"})
    if consumida:
        registrar(anterior)
    cliente.post("/api/sesion/demo/entrenador", headers={"X-Gimnasio": "1"})
    datos["version_base"] = anterior["version"]
    assert publicar(cliente, socio, datos).status_code == 201
    with app.app_context():
        nueva = servicio.listar_programas(desde_texto(socio))[-1]
    cliente.post("/api/sesion/demo/socio", headers={"X-Gimnasio": "1"})
    if not consumida:
        registrar(nueva)
    sesion_id = str(nuevo_id(reloj_fijo))
    assert (
        escribir(
            cliente,
            "/api/entrenamiento/sesiones",
            {
                "id": sesion_id,
                "sesion_planificada_id": anterior["sesiones_planificadas"][1]["id"],
            },
        ).status_code
        == 201
    )
    efectiva = cliente.get(f"/api/entrenamiento/sesiones/{sesion_id}").json
    assert float(efectiva["prescripcion_efectiva"]["ejercicios"][0]["objetivos"]["carga"]) == (
        42.5 if consumida else 10
    )


@pytest.mark.bd
def test_partida_se_conserva_al_retomar_pendiente(programas_api, reloj_fijo):
    _, cliente, socio, fuerza = programas_api
    datos = publicacion(fuerza)
    datos["sesiones"][0]["ejercicios"][0]["carga_partida"] = 10
    assert publicar(cliente, socio, datos).status_code == 201
    cliente.post("/api/sesion/demo/socio", headers={"X-Gimnasio": "1"})
    propuesta = cliente.get("/api/entrenamiento/propuesta").json
    ejercicio = propuesta["ejercicios"][0]
    assert float(ejercicio["objetivos"]["carga"]) == 10
    sesion_id = str(nuevo_id(reloj_fijo))
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
    assert (
        escribir(
            cliente,
            f"/api/entrenamiento/sesiones/{sesion_id}/series",
            {
                "id": str(nuevo_id(reloj_fijo)),
                "ejercicio_planificado_id": ejercicio["id"],
                "repeticiones": 12,
                "carga": 10,
                "rir": 2,
            },
        ).status_code
        == 201
    )
    retomada = cliente.get("/api/entrenamiento/propuesta").json
    assert float(retomada["ejercicios"][0]["objetivos"]["carga"]) == 10
    otra_id = str(nuevo_id(reloj_fijo))
    assert (
        escribir(
            cliente,
            "/api/entrenamiento/sesiones",
            {
                "id": otra_id,
                "sesion_planificada_id": retomada["sesion_planificada"]["id"],
            },
        ).status_code
        == 201
    )
    efectiva = cliente.get(f"/api/entrenamiento/sesiones/{otra_id}").json
    assert float(efectiva["prescripcion_efectiva"]["ejercicios"][0]["objetivos"]["carga"]) == 10
