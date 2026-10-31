"""Ficha del socio: alcance, formatos y conservación de hechos y entrenamiento."""

from datetime import timedelta
from uuid import uuid4

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import a_bytes, nuevo_id
from gimnasio.permisos.servicio import registrar_consentimiento
from pruebas.test_entrenamiento_api import entrenamiento_api as entrenamiento_api
from pruebas.test_entrenamiento_api import registrar

pytestmark = pytest.mark.bd


def guardar(cliente, ruta="/api/yo/ficha", datos=None):
    return cliente.put(ruta, json=datos or {}, headers={"X-Gimnasio": "1", "Idempotency-Key": str(uuid4())})


def test_socio_edita_contacto_y_perfil_sin_consentimiento(entrenamiento_api):
    datos = entrenamiento_api
    cliente = datos.cliente()
    inicial = cliente.get("/api/yo/ficha")
    assert inicial.status_code == 200
    assert all(valor is None for valor in inicial.json["perfil_entrenamiento"].values())
    respuesta = guardar(
        cliente,
        datos={
            "telefono": "0981 123 456",
            "correo": " SOCIO@ejemplo.test ",
            "perfil_entrenamiento": {
                "objetivo": "Fuerza",
                "experiencia": "inicial",
                "disponibilidad_semanal": 3,
                "tiempo_por_sesion": 60,
                "preferencias": "Por la mañana",
            },
        },
    )
    assert respuesta.status_code == 200, respuesta.json
    assert respuesta.json["datos_personales"]["telefono"] == "+595981123456"
    assert respuesta.json["datos_personales"]["correo"] == "socio@ejemplo.test"
    assert respuesta.json["perfil_entrenamiento"]["objetivo"] == "Fuerza"
    assert guardar(cliente, datos={"cedula": "1234567"}).status_code == 422
    assert guardar(cliente, datos={"nombre": "Otro"}).status_code == 422
    assert cliente.get("/api/yo/ficha").json["datos_personales"]["cedula"] == "9900600"
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT actualizado_por, actualizado_en FROM perfiles_entrenamiento")
        fila = cursor.fetchone()
        assert fila["actualizado_por"] == a_bytes(datos.usuarios["socio"])
        assert fila["actualizado_en"] == datos.reloj.ahora().replace(tzinfo=None)
        cursor.execute("SELECT COUNT(*) AS cantidad FROM consentimientos")
        assert cursor.fetchone()["cantidad"] == 0


@pytest.mark.parametrize("rol", ["recepcion", "administracion"])
def test_datos_personales_sin_salud_ni_perfil_y_sin_repetidos_propios(entrenamiento_api, rol):
    datos = entrenamiento_api
    socio = str(datos.usuarios["socio"])
    cliente = datos.cliente(rol)
    ruta = f"/api/socios/{socio}/ficha"
    guardar(datos.cliente(), datos={"correo": "socio@ejemplo.test", "perfil_entrenamiento": {"objetivo": "Fuerza"}})
    respuesta = guardar(
        cliente,
        ruta,
        {
            "nombre": "Nombre",
            "apellido": "Apellido",
            "cedula": "9.900.600",
            "correo": "socio@ejemplo.test",
            "fecha_nacimiento": "1995-01-02",
        },
    )
    assert respuesta.status_code == 200, respuesta.json
    assert set(respuesta.json) == {"datos_personales"}
    assert respuesta.json["datos_personales"]["fecha_nacimiento"] == "1995-01-02"
    assert cliente.get(ruta).json == respuesta.json
    assert guardar(cliente, ruta, {"perfil_entrenamiento": {}}).status_code == 422
    assert guardar(datos.cliente(), datos={"correo": "socio@ejemplo.test"}).status_code == 200


@pytest.mark.parametrize(
    "campo,valor,codigo",
    [
        ("cedula", "9900601", "cedula_repetida"),
        ("correo", "ajeno@ejemplo.test", "correo_repetido"),
    ],
)
def test_repetidos_son_conflictos(entrenamiento_api, campo, valor, codigo):
    datos = entrenamiento_api
    assert guardar(datos.cliente("ajeno"), datos={"correo": "ajeno@ejemplo.test"}).status_code == 200
    ruta = f"/api/socios/{datos.usuarios['socio']}/ficha"
    respuesta = guardar(datos.cliente("recepcion"), ruta, {campo: valor})
    assert respuesta.status_code == 409
    assert respuesta.json["error"]["codigo"] == codigo


@pytest.mark.parametrize(
    "datos",
    [
        {"telefono": "+5491112345678"},
        {"correo": "sin-arroba"},
        {"correo": 123},
        {"perfil_entrenamiento": {"objetivo": "x" * 501}},
        {"perfil_entrenamiento": {"preferencias": "x" * 501}},
        {"perfil_entrenamiento": {"experiencia": "experto"}},
        {"perfil_entrenamiento": {"experiencia": []}},
        *[{"perfil_entrenamiento": {"disponibilidad_semanal": n}} for n in (0, 8, True, 2.5)],
        *[{"perfil_entrenamiento": {"tiempo_por_sesion": n}} for n in (14, 241, True)],
        {"perfil_entrenamiento": None},
        {"perfil_entrenamiento": {"salud": "no"}},
    ],
)
def test_rechaza_datos_invalidos(entrenamiento_api, datos):
    respuesta = guardar(entrenamiento_api.cliente(), datos=datos)
    assert respuesta.status_code == 422
    assert respuesta.json["error"]["mensaje"]


@pytest.mark.parametrize("rol", ["socio", "ajeno", "recepcion", "administracion", "otro"])
@pytest.mark.parametrize("metodo", ["get", "put"])
def test_perfil_solo_para_entrenador_asignado(entrenamiento_api, rol, metodo):
    datos = entrenamiento_api
    ruta = f"/api/socios/{datos.usuarios['socio']}/perfil"
    respuesta = getattr(datos.cliente(rol), metodo)(
        ruta, json={}, headers={"X-Gimnasio": "1", "Idempotency-Key": str(uuid4())}
    )
    assert respuesta.status_code == 403


def test_cambiar_entrenador_conserva_perfil_y_revocacion_no_lo_oculta(entrenamiento_api):
    datos = entrenamiento_api
    socio = datos.usuarios["socio"]
    ruta = f"/api/socios/{socio}/perfil"
    cliente = datos.cliente("entrenador")
    respuesta = guardar(cliente, ruta, {"objetivo": "Fuerza", "experiencia": "avanzada"})
    assert respuesta.status_code == 200, respuesta.json
    with datos.app.app_context(), transaccion() as cursor:
        registrar_consentimiento(cursor, socio, "salud", False, "1", socio)
        cursor.execute(
            "UPDATE asignaciones_entrenador SET hasta=%s WHERE id=%s", (datos.reloj.ahora(), a_bytes(datos.asignacion))
        )
        cursor.execute(
            "INSERT INTO asignaciones_entrenador (id,socio_id,entrenador_id,desde) VALUES (%s,%s,%s,%s)",
            (
                a_bytes(nuevo_id()),
                a_bytes(socio),
                a_bytes(datos.usuarios["otro"]),
                datos.reloj.ahora() + timedelta(seconds=1),
            ),
        )
    assert cliente.get(ruta).status_code == 403
    assert datos.cliente("otro").get(ruta).json == respuesta.json
    assert datos.cliente().get("/api/yo/ficha").json["perfil_entrenamiento"] == respuesta.json["perfil_entrenamiento"]


def test_editar_ficha_conserva_hechos_y_perfil_no_altera_propuesta(entrenamiento_api):
    datos = entrenamiento_api
    registrar(datos, 0, 0)
    cliente = datos.cliente()
    antes = cliente.get("/api/entrenamiento/propuesta").json
    tablas = ("sesiones_realizadas", "series_realizadas", "programas_entrenamiento", "consentimientos")
    with datos.app.app_context(), transaccion() as cursor:
        hechos = {}
        for tabla in tablas:
            cursor.execute(f"SELECT * FROM {tabla} ORDER BY id")
            hechos[tabla] = cursor.fetchall()
    assert (
        guardar(
            cliente, datos={"perfil_entrenamiento": {"objetivo": "Otro objetivo", "tiempo_por_sesion": 240}}
        ).status_code
        == 200
    )
    ruta = f"/api/socios/{datos.usuarios['socio']}/ficha"
    assert guardar(datos.cliente("recepcion"), ruta, {"nombre": "Nuevo", "cedula": "1234567"}).status_code == 200
    assert cliente.get("/api/entrenamiento/propuesta").json == antes
    with datos.app.app_context(), transaccion() as cursor:
        for tabla in tablas:
            cursor.execute(f"SELECT * FROM {tabla} ORDER BY id")
            assert cursor.fetchall() == hechos[tabla]


def test_limites_nulos_guardado_parcial_y_reintento(entrenamiento_api):
    datos = entrenamiento_api
    cliente = datos.cliente()
    for disponibilidad, minutos, experiencia in [(1, 15, "inicial"), (7, 240, "intermedia"), (3, 60, "avanzada")]:
        respuesta = guardar(
            cliente,
            datos={
                "perfil_entrenamiento": {
                    "objetivo": "x" * 500,
                    "preferencias": "x" * 500,
                    "experiencia": experiencia,
                    "disponibilidad_semanal": disponibilidad,
                    "tiempo_por_sesion": minutos,
                }
            },
        )
        assert respuesta.status_code == 200, respuesta.json
    respuesta = guardar(cliente, datos={"perfil_entrenamiento": {"objetivo": None}})
    assert respuesta.json["perfil_entrenamiento"]["objetivo"] is None
    assert respuesta.json["perfil_entrenamiento"]["experiencia"] == "avanzada"
    encabezados = {"X-Gimnasio": "1", "Idempotency-Key": str(uuid4())}
    cuerpo = {"telefono": None, "correo": None, "perfil_entrenamiento": {"preferencias": None}}
    primera = cliente.put("/api/yo/ficha", json=cuerpo, headers=encabezados)
    assert primera.status_code == 200
    assert cliente.put("/api/yo/ficha", json=cuerpo, headers=encabezados).json == primera.json
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT COUNT(*) AS cantidad FROM perfiles_entrenamiento")
        assert cursor.fetchone()["cantidad"] == 1


def test_datos_personales_invalidos_y_errores_no_guardan_perfil(entrenamiento_api):
    datos = entrenamiento_api
    ruta = f"/api/socios/{datos.usuarios['socio']}/ficha"
    cliente = datos.cliente("recepcion")
    for cuerpo in [
        {"cedula": "123"},
        {"nombre": ""},
        {"apellido": "x" * 81},
        {"fecha_nacimiento": "2020-02-30"},
        {"fecha_nacimiento": "9999-01-01"},
        {"fecha_nacimiento": 123},
        {"salud": "no"},
    ]:
        respuesta = guardar(cliente, ruta, cuerpo)
        assert respuesta.status_code == 422, respuesta.json
    assert guardar(datos.cliente("ajeno"), datos={"correo": "ajeno@ejemplo.test"}).status_code == 200
    respuesta = guardar(
        datos.cliente(), datos={"correo": "ajeno@ejemplo.test", "perfil_entrenamiento": {"objetivo": "No guardar"}}
    )
    assert respuesta.status_code == 409
    assert datos.cliente().get("/api/yo/ficha").json["perfil_entrenamiento"]["objetivo"] is None


def test_alcance_de_ficha_por_rol_y_sesion(entrenamiento_api):
    datos = entrenamiento_api
    ruta = f"/api/socios/{datos.usuarios['socio']}/ficha"
    for rol in ("socio", "ajeno", "entrenador", "otro"):
        cliente = datos.cliente(rol)
        assert cliente.get(ruta).status_code == 403
        assert guardar(cliente, ruta).status_code == 403
    for rol in ("recepcion", "administracion", "entrenador"):
        cliente = datos.cliente(rol)
        assert cliente.get("/api/yo/ficha").status_code == 403
        assert guardar(cliente).status_code == 403
    for camino in ("/api/yo/ficha", ruta, ruta.replace("/ficha", "/perfil")):
        assert datos.app.test_client().get(camino).status_code == 401
        assert guardar(datos.app.test_client(), camino).status_code == 401
    assert cliente.get("/api/socios/invalido/ficha").status_code == 403
    recepcion = datos.cliente("recepcion")
    assert recepcion.get("/api/socios/invalido/ficha").status_code == 422
    assert recepcion.get(f"/api/socios/{nuevo_id(datos.reloj)}/ficha").status_code == 404
