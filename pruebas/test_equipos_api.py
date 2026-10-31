"""Equipos del catálogo, permisos e historial idempotente de estados."""

from datetime import timedelta
from uuid import uuid4

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import a_bytes, desde_texto, nuevo_id
from gimnasio.demo import servicio as demo
from gimnasio.programas import servicio

pytestmark = pytest.mark.bd


@pytest.fixture
def equipos(app_con_bd):
    app_con_bd.config["MODO_DEMO"] = True
    with app_con_bd.app_context():
        demo.reiniciar()
    cliente = app_con_bd.test_client()
    cliente.post("/api/sesion/demo/entrenador", headers={"X-Gimnasio": "1"})
    equipo = next(e for e in cliente.get("/api/equipos").get_json()["equipos"] if e["estado"] == "disponible")
    return app_con_bd, cliente, equipo


def cambiar(cliente, equipo, estado, *, clave=None, **datos):
    return cliente.post(
        f"/api/equipos/{equipo['id']}/estado",
        json={"estado": estado, **datos},
        headers={"X-Gimnasio": "1", "Idempotency-Key": clave or str(uuid4())},
    )


def test_cambios_estado_equipo_idempotentes(equipos):
    app, cliente, equipo = equipos
    assert equipo["estado"] == "disponible"
    assert equipo["ultimo_cambio"] is equipo["autor_id"] is equipo["motivo"] is None
    with app.app_context(), transaccion() as cursor:
        base = servicio.equipos_fuera_de_servicio(cursor)
    clave = str(uuid4())
    primera = cambiar(cliente, equipo, "fuera_de_servicio", clave=clave, motivo="Revisión ficticia")
    assert primera.status_code == 200
    assert cambiar(cliente, equipo, "fuera_de_servicio", clave=clave, motivo="Revisión ficticia").data == primera.data
    assert cambiar(cliente, equipo, "disponible", clave=clave).status_code == 422
    with app.app_context(), transaccion() as cursor:
        assert servicio.equipos_fuera_de_servicio(cursor) == base | {equipo["nombre"]}
        assert servicio.equipos_fuera_de_servicio() == base | {equipo["nombre"]}
    repetida = cambiar(cliente, equipo, "fuera_de_servicio")
    assert repetida.status_code == 409
    assert repetida.get_json()["error"]["codigo"] == "estado_sin_cambio"
    segunda = cambiar(cliente, equipo, "disponible", motivo="Listo")
    assert segunda.status_code == 200
    actual = next(e for e in cliente.get("/api/equipos").get_json()["equipos"] if e["id"] == equipo["id"])
    assert actual == segunda.get_json()["equipo"]
    assert actual["autor_id"] == primera.get_json()["equipo"]["autor_id"]
    assert actual["ultimo_cambio"].endswith("+00:00")
    assert actual["motivo"] == "Listo"
    with app.app_context(), transaccion() as cursor:
        cursor.execute(
            "SELECT estado, motivo FROM cambios_estado_equipo WHERE equipo_id=%s ORDER BY registrado_en, id",
            (a_bytes(desde_texto(equipo["id"])),),
        )
        assert cursor.fetchall() == [
            {"estado": "fuera_de_servicio", "motivo": "Revisión ficticia"},
            {"estado": "disponible", "motivo": "Listo"},
        ]
        assert servicio.equipos_fuera_de_servicio(cursor) == base
    with app.app_context():
        demo.reiniciar()
        assert servicio.equipos_fuera_de_servicio() == base


def test_estado_equipo_al_momento_del_dolor(equipos, reloj_fijo):
    app, cliente, equipo = equipos
    with app.app_context(), transaccion() as cursor:
        base = servicio.equipos_fuera_de_servicio(cursor)
    inicio = reloj_fijo.ahora().replace(tzinfo=None)
    reloj_fijo.avanzar(timedelta(seconds=1))
    assert cambiar(cliente, equipo, "fuera_de_servicio").status_code == 200
    dolor = reloj_fijo.ahora().replace(tzinfo=None)
    reloj_fijo.avanzar(timedelta(seconds=1))
    assert cambiar(cliente, equipo, "disponible").status_code == 200
    reparacion = reloj_fijo.ahora().replace(tzinfo=None)
    with app.app_context(), transaccion() as cursor:
        assert servicio.equipos_fuera_de_servicio(cursor, momento=inicio) == base
        assert servicio.equipos_fuera_de_servicio(cursor, momento=dolor) == base | {equipo["nombre"]}
        assert servicio.equipos_fuera_de_servicio(momento=dolor) == base | {equipo["nombre"]}
        assert servicio.equipos_fuera_de_servicio(cursor) == base
        assert servicio.equipos_fuera_de_servicio_en_momentos(cursor, [inicio, dolor, reparacion]) == {
            inicio: base,
            dolor: base | {equipo["nombre"]},
            reparacion: base,
        }


@pytest.mark.parametrize(
    "rol,esperado", [("socio", 403), ("recepcion", 403), ("entrenador", 200), ("administracion", 200)]
)
def test_permisos_equipos(equipos, rol, esperado):
    _, cliente, equipo = equipos
    cliente.post(f"/api/sesion/demo/{rol}", headers={"X-Gimnasio": "1"})
    assert cliente.get("/api/equipos").status_code == esperado
    assert cambiar(cliente, equipo, "fuera_de_servicio").status_code == esperado


def test_catalogo_consistente_con_equipos(equipos):
    app, _, _ = equipos
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT DISTINCT equipo FROM ejercicios WHERE equipo NOT IN ('', 'sin equipo')")
        nombres = {fila["equipo"] for fila in cursor.fetchall()}
        cursor.execute("SELECT nombre FROM equipos")
        assert {fila["nombre"] for fila in cursor.fetchall()} == nombres
        assert nombres


@pytest.mark.parametrize(
    "datos",
    [
        None,
        [],
        {},
        {"estado": "otro"},
        {"estado": []},
        {"estado": "disponible", "extra": 1},
        {"estado": "fuera_de_servicio", "motivo": 3},
        {"estado": "fuera_de_servicio", "motivo": "a" * 501},
    ],
)
def test_validacion_estado(equipos, datos):
    app, cliente, equipo = equipos
    respuesta = cliente.post(
        f"/api/equipos/{equipo['id']}/estado", json=datos, headers={"X-Gimnasio": "1", "Idempotency-Key": str(uuid4())}
    )
    assert respuesta.status_code == 422
    with app.app_context(), transaccion() as cursor:
        cursor.execute(
            "SELECT COUNT(*) AS cantidad FROM cambios_estado_equipo WHERE equipo_id=%s",
            (a_bytes(desde_texto(equipo["id"])),),
        )
        assert cursor.fetchone()["cantidad"] == 0


def test_limites_identificadores_y_encabezados(equipos):
    app, cliente, equipo = equipos
    assert cambiar(cliente, equipo, "disponible").status_code == 409
    assert cambiar(cliente, equipo, "fuera_de_servicio", motivo="a" * 500).status_code == 200
    assert cambiar(cliente, {"id": "invalido"}, "disponible").status_code == 422
    with app.app_context():
        inexistente = str(nuevo_id())
    assert cambiar(cliente, {"id": inexistente}, "disponible").status_code == 404
    ruta = f"/api/equipos/{equipo['id']}/estado"
    assert cliente.post(ruta, json={"estado": "disponible"}, headers={"X-Gimnasio": "1"}).status_code == 428
    assert cliente.post(ruta, json={"estado": "disponible"}).status_code == 403
    cliente.delete("/api/sesion", headers={"X-Gimnasio": "1"})
    assert cliente.get("/api/equipos").status_code == 401
    assert cambiar(cliente, equipo, "disponible").status_code == 401
