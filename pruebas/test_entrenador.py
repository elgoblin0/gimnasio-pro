"""Vista del socio asignado, privacidad al leer y avisos revisados inmutables."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import a_bytes, desde_bytes, nuevo_id
from gimnasio.entrenador.servicio import _sin_datos_salud
from gimnasio.entrenamiento import repositorio
from gimnasio.entrenamiento import servicio as entrenamiento
from gimnasio.permisos.servicio import registrar_consentimiento
from pruebas.test_entrenamiento_api import entrenamiento_api as entrenamiento_api


def razones():
    return [
        {
            "regla": regla,
            "version": "1",
            "datos": {
                "ejercicio_id": "ejercicio",
                "ejercicio_hecho_id": "hecho",
                "zonas": ["rodillas"],
                "explicacion": "Detalle de salud ficticio",
            },
        }
        for regla in ("dolor_reportado", "restriccion_salud", "tope_suba_semanal")
    ]


def test_filtro_recursivo_conserva_razones_ajenas_e_identificadores_sin_mutar():
    original = {
        "explicacion": razones(),
        "frenos": [{"explicacion": razones()}],
        "ejercicios": [{"explicacion": razones()}],
    }
    antes = deepcopy(original)
    filtrado = _sin_datos_salud(original)
    assert original == antes
    for lista in (
        filtrado["explicacion"],
        filtrado["frenos"][0]["explicacion"],
        filtrado["ejercicios"][0]["explicacion"],
    ):
        assert lista[2] == original["explicacion"][2]
        for razon in lista[:2]:
            assert razon == {
                "regla": razon["regla"],
                "version": "1",
                "datos": {"ejercicio_id": "ejercicio", "ejercicio_hecho_id": "hecho"},
            }


@pytest.fixture
def vista(entrenamiento_api):
    datos = entrenamiento_api
    datos.socio = str(datos.usuarios["socio"])
    datos.ruta = f"/api/entrenador/socios/{datos.socio}"
    datos.avisos = []
    with datos.app.app_context(), transaccion() as cursor:
        registrar_consentimiento(cursor, datos.usuarios["socio"], "salud", True, "1", datos.usuarios["socio"])
        propuesta = entrenamiento.consultar_propuesta(
            datos.socio, {"id": datos.socio, "rol": "socio"}, datos.sesiones[0], cursor=cursor
        )
        propuesta["explicacion"].extend(razones())
        for ejercicio in propuesta["ejercicios"]:
            ejercicio["explicacion"].extend(razones())
        propuesta["frenos"] = ["dolor_reportado", "tope_suba_semanal"]
        datos.realizada = nuevo_id()
        repositorio.insertar_sesion(
            cursor, datos.realizada, datos.usuarios["socio"], datos.sesiones[0], datos.reloj.ahora()
        )
        repositorio.insertar_prescripcion(cursor, nuevo_id(), datos.realizada, propuesta, datos.reloj.ahora())
        repositorio.insertar_avisos(cursor, datos.usuarios["socio"], datos.realizada, propuesta, datos.reloj.ahora())
        repositorio.insertar_dolor(
            cursor, nuevo_id(), datos.usuarios["socio"], "rodillas", datos.reloj.ahora(), sesion_id=datos.realizada
        )
        cursor.execute(
            "INSERT INTO restricciones_salud (id,socio_id,zona,descripcion,registrada_en,autor_id) "
            "VALUES (%s,%s,'rodillas','Restricción ficticia',%s,%s)",
            (
                a_bytes(nuevo_id()),
                a_bytes(datos.usuarios["socio"]),
                datos.reloj.ahora(),
                a_bytes(datos.usuarios["entrenador"]),
            ),
        )
        for fila in repositorio.listar_avisos(cursor, datos.usuarios["socio"]):
            datos.avisos.append(str(desde_bytes(fila["id"])))
    return datos


def revisar(datos, cliente, ids=None, nota="Nota de salud ficticia", clave=None):
    return cliente.post(
        datos.ruta + "/avisos/revision",
        json={"aviso_ids": datos.avisos if ids is None else ids, "nota": nota},
        headers={"X-Gimnasio": "1", "Idempotency-Key": clave or str(uuid4())},
    )


def consentimiento(datos, otorgado):
    with datos.app.app_context(), transaccion() as cursor:
        registrar_consentimiento(cursor, datos.usuarios["socio"], "salud", otorgado, "1", datos.usuarios["socio"])


@pytest.mark.bd
def test_revocar_filtra_todos_los_avisos_y_prescripciones_y_otorgar_restaura(vista):
    cliente = vista.cliente("entrenador")
    assert revisar(vista, cliente).status_code == 200
    completa = cliente.get(vista.ruta).json
    assert completa["salud"]["dolores_reportados"] and completa["salud"]["restricciones_salud"]
    consentimiento(vista, False)
    respuesta = cliente.get(vista.ruta)
    assert respuesta.status_code == 200
    filtrada = respuesta.json
    assert filtrada["salud"] is None and filtrada["sin_consentimiento"] is True
    assert filtrada["figura_cuerpo"] == completa["figura_cuerpo"]
    for aviso, original in zip(filtrada["avisos"], completa["avisos"], strict=True):
        assert aviso["freno"] == original["freno"]
        assert aviso["revision"] == {**original["revision"], "nota": None}

    def comprobar(valor):
        if isinstance(valor, dict):
            if valor.get("regla") in ("dolor_reportado", "restriccion_salud"):
                assert set(valor["datos"]) == {"ejercicio_id", "ejercicio_hecho_id"}
            for dato in valor.values():
                comprobar(dato)
        elif isinstance(valor, list):
            for dato in valor:
                comprobar(dato)

    comprobar(filtrada)
    consentimiento(vista, True)
    assert cliente.get(vista.ruta).json == completa


@pytest.mark.bd
def test_revisar_sin_consentimiento_es_idempotente_y_no_cambia_propuesta(vista):
    consentimiento(vista, False)
    cliente = vista.cliente("entrenador")
    with vista.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT * FROM avisos_entrenador ORDER BY id")
        avisos_antes = cursor.fetchall()
        cursor.execute("SELECT * FROM prescripciones_efectivas ORDER BY id")
        efectivas_antes = cursor.fetchall()
    with vista.app.app_context():
        usuario = {"id": vista.socio, "rol": "socio"}
        antes = entrenamiento.consultar_propuesta(vista.socio, usuario)
    clave = str(uuid4())
    primera = revisar(vista, cliente, vista.avisos[:1], clave=clave)
    assert primera.status_code == 200, primera.json
    assert revisar(vista, cliente, vista.avisos[:1], clave=clave).data == primera.data
    assert revisar(vista, cliente, vista.avisos[:1]).status_code == 200
    with vista.app.app_context():
        assert entrenamiento.consultar_propuesta(vista.socio, usuario) == antes
        with transaccion() as cursor:
            cursor.execute("SELECT * FROM revisiones_aviso")
            filas = cursor.fetchall()
            assert len(filas) == 1 and filas[0]["nota"] == "Nota de salud ficticia"
            cursor.execute("SELECT * FROM avisos_entrenador ORDER BY id")
            assert cursor.fetchall() == avisos_antes
            cursor.execute("SELECT * FROM prescripciones_efectivas ORDER BY id")
            assert cursor.fetchall() == efectivas_antes
    avisos = cliente.get(vista.ruta).json["avisos"]
    assert sum(a["revisado"] for a in avisos) == 1
    assert revisar(vista, cliente).status_code == 200


@pytest.mark.bd
def test_id_ajeno_rechaza_todo_sin_insertar(vista):
    with vista.app.app_context(), transaccion() as cursor:
        realizada = nuevo_id()
        programa, planificada = nuevo_id(), nuevo_id()
        cursor.execute(
            "INSERT INTO programas_entrenamiento (id,socio_id,version,creado_en) VALUES (%s,%s,1,%s)",
            (a_bytes(programa), a_bytes(vista.usuarios["ajeno"]), vista.reloj.ahora()),
        )
        cursor.execute(
            "INSERT INTO sesiones_planificadas (id,programa_id,posicion,nombre) VALUES (%s,%s,1,'Sesión ficticia')",
            (a_bytes(planificada), a_bytes(programa)),
        )
        repositorio.insertar_sesion(cursor, realizada, vista.usuarios["ajeno"], planificada, vista.reloj.ahora())
        repositorio.insertar_avisos(
            cursor,
            vista.usuarios["ajeno"],
            realizada,
            {"frenos": ["dolor_reportado"], "explicacion": razones()},
            vista.reloj.ahora(),
        )
        ajeno = repositorio.listar_avisos(cursor, vista.usuarios["ajeno"])[0]
        ajeno_id = str(desde_bytes(ajeno["id"]))
    respuesta = revisar(vista, vista.cliente("entrenador"), [vista.avisos[0], ajeno_id])
    assert respuesta.status_code == 422 and respuesta.json["error"]["codigo"] == "aviso_ajeno"
    with vista.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT COUNT(*) AS cantidad FROM revisiones_aviso")
        assert cursor.fetchone()["cantidad"] == 0


@pytest.mark.bd
def test_cambio_de_entrenador_cambia_ambas_rutas_y_lista(vista):
    anterior, nuevo = vista.cliente("entrenador"), vista.cliente("otro")
    assert nuevo.get(vista.ruta).status_code == 403
    assert revisar(vista, nuevo).status_code == 403
    assert anterior.get("/api/entrenador/socios").json["socios"][0]["id"] == vista.socio
    with vista.app.app_context(), transaccion() as cursor:
        cursor.execute("UPDATE asignaciones_entrenador SET hasta=desde WHERE id=%s", (a_bytes(vista.asignacion),))
        cursor.execute(
            "INSERT INTO asignaciones_entrenador (id,socio_id,entrenador_id,desde) VALUES (%s,%s,%s,%s)",
            (
                a_bytes(nuevo_id()),
                a_bytes(vista.usuarios["socio"]),
                a_bytes(vista.usuarios["otro"]),
                vista.reloj.ahora(),
            ),
        )
    assert anterior.get(vista.ruta).status_code == 403
    assert revisar(vista, anterior).status_code == 403
    assert anterior.get("/api/entrenador/socios").json == {"socios": []}
    assert nuevo.get(vista.ruta).status_code == 200
    assert revisar(vista, nuevo).status_code == 200
    assert nuevo.get("/api/entrenador/socios").json["socios"][0]["id"] == vista.socio


@pytest.mark.bd
@pytest.mark.parametrize("rol", ["socio", "recepcion", "administracion"])
def test_rutas_denegadas_por_rol(vista, rol):
    cliente = vista.cliente(rol)
    assert cliente.get("/api/entrenador/socios").status_code == 403
    assert cliente.get(vista.ruta).status_code == 403
    assert revisar(vista, cliente).status_code == 403


@pytest.mark.bd
@pytest.mark.parametrize("nota", ["a" * 501, 42, [], {}])
def test_nota_invalida_no_se_guarda(vista, nota):
    assert revisar(vista, vista.cliente("entrenador"), nota=nota).status_code == 422


@pytest.mark.bd
def test_ultimas_diez_sesiones_y_programa_vigente(vista):
    with vista.app.app_context(), transaccion() as cursor:
        ids = []
        for numero in range(12):
            identificador = nuevo_id()
            ids.append(str(identificador))
            repositorio.insertar_sesion(
                cursor,
                identificador,
                vista.usuarios["socio"],
                vista.sesiones[0],
                vista.reloj.ahora() + timedelta(minutes=numero + 1),
            )
    respuesta = vista.cliente("entrenador").get(vista.ruta)
    assert respuesta.status_code == 200, respuesta.json
    assert [s["id"] for s in respuesta.json["sesiones_realizadas"]] == list(reversed(ids[-10:]))
    assert respuesta.json["programa_vigente"]["id"] == str(vista.programa)


@pytest.mark.bd
def test_revisiones_concurrentes_no_duplican_filas(vista):
    barrera = Barrier(2)

    def enviar():
        cliente = vista.cliente("entrenador")
        barrera.wait(timeout=10)
        return revisar(vista, cliente).status_code

    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        assert list(ejecutor.map(lambda _: enviar(), range(2))) == [200, 200]
    with vista.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT COUNT(*) AS cantidad FROM revisiones_aviso")
        assert cursor.fetchone()["cantidad"] == len(vista.avisos)


@pytest.mark.bd
def test_un_aviso_posterior_no_queda_revisado_y_la_demo_se_puede_vaciar(vista):
    from gimnasio.demo.repositorio import vaciar_datos

    cliente = vista.cliente("entrenador")
    vistos = [a["id"] for a in cliente.get(vista.ruta).json["avisos"]]
    with vista.app.app_context(), transaccion() as cursor:
        repositorio.insertar_avisos(
            cursor,
            vista.usuarios["socio"],
            vista.realizada,
            {"frenos": ["restriccion_salud"], "explicacion": razones()},
            vista.reloj.ahora(),
        )
    assert revisar(vista, cliente, vistos, nota="a" * 500).status_code == 200
    avisos = cliente.get(vista.ruta).json["avisos"]
    assert len(avisos) == 3
    assert all(a["revisado"] is (a["id"] in vistos) for a in avisos)
    with vista.app.app_context(), transaccion() as cursor:
        vaciar_datos(cursor)
        cursor.execute("SELECT COUNT(*) AS cantidad FROM revisiones_aviso")
        assert cursor.fetchone()["cantidad"] == 0


@pytest.mark.bd
def test_revision_exige_encabezados_y_admite_nota_omitida(vista):
    cliente = vista.cliente("entrenador")
    ruta = vista.ruta + "/avisos/revision"
    cuerpo = {"aviso_ids": vista.avisos}
    assert cliente.post(ruta, json=cuerpo, headers={"X-Gimnasio": "1"}).status_code == 428
    assert cliente.post(ruta, json=cuerpo, headers={"Idempotency-Key": str(uuid4())}).status_code == 403
    assert (
        cliente.post(ruta, json=cuerpo, headers={"X-Gimnasio": "1", "Idempotency-Key": str(uuid4())}).status_code == 200
    )
    assert all(a["revision"]["nota"] is None for a in cliente.get(vista.ruta).json["avisos"])
