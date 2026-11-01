"""API, permisos, validación y consultas de la agenda."""

from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from gimnasio.clases import servicio
from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.ids import a_bytes, desde_bytes, desde_texto, nuevo_id
from gimnasio.demo import servicio as demo

DATOS = {
    "nombre": "Clase ficticia",
    "dia_semana": 2,
    "hora_inicio": "18:00",
    "duracion_minutos": 60,
    "cupo": 10,
    "entrenador_id": "019a2700-0000-7000-8000-000000000001",
}


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("nombre", ""),
        ("nombre", " " * 3),
        ("nombre", "x" * 121),
        ("nombre", None),
        ("dia_semana", 0),
        ("dia_semana", 8),
        ("dia_semana", True),
        ("duracion_minutos", 14),
        ("duracion_minutos", 241),
        ("duracion_minutos", 30.5),
        ("cupo", 0),
        ("cupo", -1),
        ("cupo", True),
        ("cupo", "10"),
        ("cupo", 1.5),
        ("hora_inicio", "24:00"),
        ("hora_inicio", "8:00"),
        ("hora_inicio", None),
        ("entrenador_id", None),
        ("entrenador_id", "019a2700-0000-4000-8000-000000000001"),
    ],
)
def test_validacion(campo, valor):
    with pytest.raises(ErrorDeDominio) as error:
        servicio.validar(DATOS | {campo: valor})
    assert error.value.estado_http == 422


@pytest.fixture
def clases(app_con_bd, sembrar_demo):
    app_con_bd.config["MODO_DEMO"] = True
    sembrar_demo(app_con_bd)
    cliente = app_con_bd.test_client()
    cliente.post("/api/sesion/demo/administracion", headers={"X-Gimnasio": "1"})
    entrenador = cliente.get("/api/clases").get_json()["entrenadores"][0]["id"]
    return app_con_bd, cliente, DATOS | {"entrenador_id": entrenador}


def escribir(cliente, ruta="/api/clases", datos=None, metodo="POST", clave=None):
    return cliente.open(
        ruta, method=metodo, json=datos, headers={"X-Gimnasio": "1", "Idempotency-Key": clave or str(uuid4())}
    )


@pytest.mark.bd
@pytest.mark.parametrize("caso", ["horario", "dia", "archivar"])
def test_conserva_fila_ante_cambios(clases, caso):
    app, cliente, datos = clases
    creada = escribir(cliente, datos=datos)
    assert creada.status_code == 201
    clase_id = creada.get_json()["id"]
    original = cliente.get("/api/clases/agenda").get_json()["ocurrencias"]
    assert len(original) == 2
    assert original[0]["identificador"] == {"clase_id": clase_id, "fecha": "2026-10-27"}
    with app.app_context(), transaccion() as cursor:
        cursor.execute(
            "INSERT INTO ocurrencias_clase (id,clase_id,fecha,hora_inicio,duracion_minutos,creada_en) "
            "VALUES (%s,%s,'2026-10-27','18:00',60,%s)",
            (a_bytes(nuevo_id()), a_bytes(desde_texto(clase_id)), app.extensions["reloj"].ahora().replace(tzinfo=None)),
        )
    if caso == "archivar":
        assert escribir(cliente, f"/api/clases/{clase_id}/archivar").status_code == 200
    else:
        cambio = {"hora_inicio": "19:00", "duracion_minutos": 90} if caso == "horario" else {"dia_semana": 3}
        assert escribir(cliente, f"/api/clases/{clase_id}", datos | cambio, "PUT").status_code == 200
    agenda = cliente.get("/api/clases/agenda").get_json()["ocurrencias"]
    assert agenda[0] == original[0]
    if caso == "horario":
        assert agenda[1]["hora_inicio"] == "19:00"
        assert agenda[1]["duracion_minutos"] == 90
    elif caso == "dia":
        assert [fila["fecha"] for fila in agenda] == ["2026-10-27", "2026-10-28", "2026-11-04"]
    else:
        assert len(agenda) == 1
    # La agenda y los cambios de configuración no fijan ocurrencias nuevas.
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT COUNT(*) AS cantidad FROM ocurrencias_clase")
        assert cursor.fetchone()["cantidad"] == 1
    # Reiniciar la demo también debe poder borrar clases y ocurrencias.
    with app.app_context():
        demo.reiniciar()


@pytest.mark.bd
@pytest.mark.parametrize("rol", ["socio", "recepcion", "administracion"])
def test_entrenador_debe_tener_rol_entrenador(clases, rol):
    app, cliente, datos = clases
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT id FROM usuarios WHERE rol=%s LIMIT 1", (rol,))
        usuario_id = str(desde_bytes(cursor.fetchone()["id"]))
    respuesta = escribir(cliente, datos=datos | {"entrenador_id": usuario_id})
    assert respuesta.status_code == 422


@pytest.mark.bd
def test_entrenador_inactivo(clases):
    app, cliente, datos = clases
    with app.app_context(), transaccion() as cursor:
        cursor.execute("UPDATE usuarios SET activo=FALSE WHERE id=%s", (a_bytes(desde_texto(datos["entrenador_id"])),))
    assert escribir(cliente, datos=datos).status_code == 422


@pytest.mark.bd
@pytest.mark.parametrize("rol", ["socio", "recepcion", "entrenador", "administracion"])
def test_permisos_de_rutas(clases, rol):
    _, cliente, datos = clases
    clase_id = escribir(cliente, datos=datos).get_json()["id"]
    cliente.post(f"/api/sesion/demo/{rol}", headers={"X-Gimnasio": "1"})
    assert cliente.get("/api/clases/agenda").status_code == 200
    esperado = 200 if rol == "administracion" else 403
    assert cliente.get("/api/clases").status_code == esperado
    assert escribir(cliente, datos=datos).status_code == (201 if rol == "administracion" else 403)
    assert escribir(cliente, f"/api/clases/{clase_id}", datos, "PUT").status_code == esperado
    assert escribir(cliente, f"/api/clases/{clase_id}/archivar").status_code == esperado


@pytest.mark.bd
def test_creacion_idempotente_y_encabezados(clases):
    _, cliente, datos = clases
    assert cliente.post("/api/clases", json=datos).status_code == 403
    assert cliente.post("/api/clases", json=datos, headers={"X-Gimnasio": "1"}).status_code == 428
    clave = str(uuid4())
    respuesta = escribir(cliente, datos=datos, clave=clave)
    assert respuesta.status_code == 201
    assert escribir(cliente, datos=datos, clave=clave).data == respuesta.data
    assert len(cliente.get("/api/clases").get_json()["clases"]) == 1


@pytest.mark.bd
def test_semana_cambia_al_lunes_local(clases):
    app, cliente, _ = clases
    reloj = app.extensions["reloj"]
    reloj.fijar(datetime(2026, 11, 2, 2, 59, tzinfo=UTC))
    assert cliente.get("/api/clases/agenda").get_json()["desde"] == "2026-10-26"
    reloj.fijar(datetime(2026, 11, 2, 3, 0, tzinfo=UTC))
    agenda = cliente.get("/api/clases/agenda").get_json()
    assert (agenda["desde"], agenda["hasta"]) == ("2026-11-02", "2026-11-15")


@pytest.mark.bd
def test_semana_usa_zona_horaria_de_sede(clases):
    app, cliente, _ = clases
    app.extensions["reloj"].fijar(datetime(2026, 11, 2, 2, 59, tzinfo=UTC))
    agenda = cliente.get("/api/clases/agenda").get_json()
    assert (agenda["desde"], agenda["zona_horaria"]) == ("2026-10-26", "America/Asuncion")
    with app.app_context(), transaccion() as cursor:
        cursor.execute("UPDATE sedes SET zona_horaria=%s", ("UTC",))
    agenda = cliente.get("/api/clases/agenda").get_json()
    assert (agenda["desde"], agenda["hasta"], agenda["zona_horaria"]) == ("2026-11-02", "2026-11-15", "UTC")


@pytest.mark.bd
def test_agenda_consultas_constantes(clases, monkeypatch):
    app, cliente, datos = clases
    for numero in range(12):
        assert escribir(cliente, datos=datos | {"nombre": f"Clase ficticia {numero}"}).status_code == 201
    consultas = []
    # Contar las consultas SQL reales del servicio, sin la consulta de sesión.

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
        assert len(servicio.agenda()["ocurrencias"]) == 24
    assert len(consultas) == 4
