"""Catálogo y reemplazo transaccional de alternativas por rol."""

from uuid import uuid4

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.ids import a_bytes, nuevo_id
from gimnasio.demo import servicio as demo
from gimnasio.programas import repositorio

pytestmark = pytest.mark.bd


@pytest.fixture
def catalogo(app_con_bd, reloj_fijo):
    app_con_bd.config["MODO_DEMO"] = True
    with app_con_bd.app_context():
        demo.reiniciar()
    cliente = app_con_bd.test_client()
    cliente.post("/api/sesion/demo/entrenador", headers={"X-Gimnasio": "1"})
    identificadores = []
    with app_con_bd.app_context(), transaccion() as cursor:
        for indice in range(11):
            identificador = nuevo_id(reloj_fijo)
            identificadores.append(str(identificador))
            cursor.execute(
                "INSERT INTO ejercicios (id,nombre,medidas_aplicables,actualizada_en,equipo,patron_movimiento) "
                'VALUES (%s,%s,\'["repeticiones","carga"]\',%s,%s,%s)',
                (
                    a_bytes(identificador),
                    f"Ejercicio ficticio {indice}",
                    reloj_fijo.ahora(),
                    "barra" if indice in (0, 10) else "mancuernas",
                    "empuje" if indice == 9 else "sentadilla",
                ),
            )
    return app_con_bd, cliente, identificadores


def reemplazar(cliente, ejercicio, alternativas, clave=None):
    return cliente.post(
        f"/api/ejercicios/{ejercicio}/alternativas",
        json={"alternativas": alternativas},
        headers={"X-Gimnasio": "1", "Idempotency-Key": clave or str(uuid4())},
    )


def test_reemplazo_orden_vacio_e_idempotencia(catalogo):
    _, cliente, ids = catalogo
    clave = str(uuid4())
    primera = reemplazar(cliente, ids[0], [ids[2], ids[1]], clave)
    assert primera.status_code == 200
    assert primera.json["ejercicio"]["alternativas"] == [ids[2], ids[1]]
    assert reemplazar(cliente, ids[0], ids[1:9]).status_code == 200
    assert reemplazar(cliente, ids[0], [ids[2], ids[1]], clave).data == primera.data
    actual = next(e for e in cliente.get("/api/ejercicios").json["ejercicios"] if e["id"] == ids[0])
    assert actual["alternativas"] == ids[1:9]
    assert {
        "id",
        "nombre",
        "medidas_aplicables",
        "patron_movimiento",
        "equipo",
        "estado_equipo",
        "zonas",
        "incremento_carga",
        "alternativas",
    } == set(actual)
    assert actual["medidas_aplicables"] == ["repeticiones", "carga"]
    assert reemplazar(cliente, ids[0], [], clave).status_code == 422
    assert reemplazar(cliente, ids[0], []).json["ejercicio"]["alternativas"] == []


@pytest.mark.parametrize("indice,motivo", [(0, "mismo"), (9, "patrón"), (10, "equipo")])
def test_rechaza_incompatibles_sin_reemplazo_parcial(catalogo, indice, motivo):
    _, cliente, ids = catalogo
    assert reemplazar(cliente, ids[0], [ids[2]]).status_code == 200
    respuesta = reemplazar(cliente, ids[0], [ids[1], ids[indice]])
    assert respuesta.status_code == 422
    assert respuesta.json["error"]["codigo"] == "alternativa_invalida"
    assert ids[indice] in respuesta.json["error"]["mensaje"]
    assert motivo in respuesta.json["error"]["mensaje"]
    actual = next(e for e in cliente.get("/api/ejercicios").json["ejercicios"] if e["id"] == ids[0])
    assert actual["alternativas"] == [ids[2]]


@pytest.mark.parametrize("caso", ["inexistente", "original_inexistente", "repetida", "limite", "uuid", "tipo"])
def test_rechazos(catalogo, caso, reloj_fijo):
    _, cliente, ids = catalogo
    original = ids[0]
    alternativas = [ids[1]]
    motivo = {
        "inexistente": "no existe",
        "original_inexistente": "no existe",
        "repetida": "repetida",
        "limite": "hasta 8",
        "uuid": "UUIDv7",
        "tipo": "UUIDv7",
    }[caso]
    if caso == "inexistente":
        alternativas = [str(nuevo_id(reloj_fijo))]
    elif caso == "original_inexistente":
        original = str(nuevo_id(reloj_fijo))
    elif caso == "repetida":
        alternativas *= 2
    elif caso == "limite":
        alternativas = ids[1:10]
    elif caso == "uuid":
        alternativas = ["invalido"]
    elif caso == "tipo":
        alternativas = [{}]
    respuesta = reemplazar(cliente, original, alternativas)
    assert respuesta.status_code == 422
    assert respuesta.json["error"]["codigo"] == "alternativa_invalida"
    assert motivo in respuesta.json["error"]["mensaje"]


@pytest.mark.parametrize("datos", [None, [], {}, {"alternativas": None}, {"alternativas": [], "otro": 1}])
def test_cuerpo_invalido(catalogo, datos):
    _, cliente, ids = catalogo
    respuesta = cliente.post(
        f"/api/ejercicios/{ids[0]}/alternativas",
        json=datos,
        headers={"X-Gimnasio": "1", "Idempotency-Key": str(uuid4())},
    )
    assert respuesta.status_code == 422
    assert respuesta.json["error"]["codigo"] == "alternativa_invalida"


@pytest.mark.parametrize(
    "rol,estado", [("socio", 403), ("recepcion", 403), ("entrenador", 200), ("administracion", 200)]
)
def test_permisos_catalogo_y_reemplazo(catalogo, rol, estado):
    _, cliente, ids = catalogo
    cliente.post(f"/api/sesion/demo/{rol}", headers={"X-Gimnasio": "1"})
    assert cliente.get("/api/ejercicios").status_code == estado
    assert reemplazar(cliente, ids[0], []).status_code == estado


def test_encabezados_y_sesion(catalogo):
    _, cliente, ids = catalogo
    ruta = f"/api/ejercicios/{ids[0]}/alternativas"
    assert cliente.post(ruta, json={"alternativas": []}).status_code == 403
    assert cliente.post(ruta, json={"alternativas": []}, headers={"X-Gimnasio": "1"}).status_code == 428
    cliente.delete("/api/sesion", headers={"X-Gimnasio": "1"})
    assert cliente.get("/api/ejercicios").status_code == 401
    assert reemplazar(cliente, ids[0], []).status_code == 401


def test_fallo_de_escritura_revierte_reemplazo(catalogo, monkeypatch):
    _, cliente, ids = catalogo
    assert reemplazar(cliente, ids[0], [ids[1]]).status_code == 200
    reemplazo = repositorio.reemplazar_alternativas

    def fallar(*argumentos):
        reemplazo(*argumentos)
        raise ErrorDeDominio("fallo_de_prueba", "Fallo ficticio después de escribir.", 503)

    monkeypatch.setattr(repositorio, "reemplazar_alternativas", fallar)
    assert reemplazar(cliente, ids[0], [ids[2]]).status_code == 503
    actual = next(e for e in cliente.get("/api/ejercicios").json["ejercicios"] if e["id"] == ids[0])
    assert actual["alternativas"] == [ids[1]]


def test_catalogo_refleja_estado_del_equipo_y_zonas(catalogo):
    _, cliente, _ = catalogo
    equipo = cliente.get("/api/equipos").json["equipos"][0]
    assert (
        cliente.post(
            f"/api/equipos/{equipo['id']}/estado",
            json={"estado": "fuera_de_servicio"},
            headers={"X-Gimnasio": "1", "Idempotency-Key": str(uuid4())},
        ).status_code
        == 200
    )
    ejercicios = cliente.get("/api/ejercicios").json["ejercicios"]
    afectados = [e for e in ejercicios if e["equipo"] == equipo["nombre"]]
    assert afectados
    assert all(e["estado_equipo"] == "fuera_de_servicio" for e in afectados)
    assert any(e["zonas"] for e in ejercicios)
