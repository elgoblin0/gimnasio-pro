"""Bandeja por sondeo con propuestas de solo lectura sobre MySQL."""

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import a_bytes, nuevo_id
from gimnasio.entrenamiento import repositorio
from pruebas.test_entrenador import revisar
from pruebas.test_entrenador import vista as vista
from pruebas.test_entrenamiento_api import entrenamiento_api as entrenamiento_api
from pruebas.test_entrenamiento_api import registrar

pytestmark = pytest.mark.bd
RUTA = "/api/entrenador/bandeja"


def socios(respuesta):
    return [s for grupo in respuesta.json["grupos"] for s in grupo["socios"]]


def test_etag_aviso_nuevo_y_revisado(vista):
    cliente = vista.cliente("entrenador")
    primera = cliente.get(RUTA)
    assert primera.status_code == 200
    assert primera.json["grupos"][0]["socios"][0]["id"] == vista.socio
    assert cliente.get(RUTA, headers={"If-None-Match": primera.headers["ETag"]}).status_code == 304
    assert revisar(vista, cliente).status_code == 200
    revisada = cliente.get(RUTA, headers={"If-None-Match": primera.headers["ETag"]})
    assert revisada.status_code == 200 and socios(revisada) == []
    with vista.app.app_context(), transaccion() as cursor:
        repositorio.insertar_avisos(
            cursor,
            vista.usuarios["socio"],
            vista.realizada,
            {"frenos": ["chequeo_desfavorable"], "explicacion": []},
            vista.reloj.ahora(),
        )
    nueva = cliente.get(RUTA, headers={"If-None-Match": revisada.headers["ETag"]})
    assert nueva.status_code == 200
    assert nueva.json["grupos"][-1]["socios"][0]["motivos"][0]["tipo"] == "aviso_progresion"
    assert "zonas" not in str(nueva.json)


def test_solo_asignacion_vigente_incluso_aviso_de_otro_entrenador(vista):
    anterior, nuevo = vista.cliente("entrenador"), vista.cliente("otro")
    assert socios(nuevo.get(RUTA)) == []
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
    assert socios(anterior.get(RUTA)) == []
    assert socios(nuevo.get(RUTA))[0]["id"] == vista.socio


@pytest.mark.parametrize("rol", ["socio", "recepcion", "administracion"])
def test_permiso(entrenamiento_api, rol):
    assert entrenamiento_api.cliente(rol).get(RUTA).status_code == 403


def test_sin_programa_fecha_asignacion(entrenamiento_api):
    datos = entrenamiento_api
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute(
            "INSERT INTO asignaciones_entrenador (id,socio_id,entrenador_id,desde) VALUES (%s,%s,%s,%s)",
            (
                a_bytes(nuevo_id()),
                a_bytes(datos.usuarios["ajeno"]),
                a_bytes(datos.usuarios["entrenador"]),
                datos.reloj.ahora(),
            ),
        )
    respuesta = datos.cliente("entrenador").get(RUTA)
    assert socios(respuesta)[0]["id"] == str(datos.usuarios["ajeno"])
    assert socios(respuesta)[0]["motivos"] == [{"tipo": "sin_programa", "fecha": datos.reloj.ahora().isoformat()}]


def test_secuencia_terminada_fecha_ultima_serie(entrenamiento_api):
    datos = entrenamiento_api
    for sesion in (0, 1):
        for ejercicio in (0, 1):
            registrar(datos, sesion, ejercicio, 2)
    respuesta = datos.cliente("entrenador").get(RUTA)
    assert socios(respuesta)[0]["motivos"] == [
        {"tipo": "secuencia_terminada", "fecha": datos.reloj.ahora().isoformat()}
    ]


def test_equipo_solo_en_proxima_sesion_y_lectura_sin_escrituras(entrenamiento_api):
    datos = entrenamiento_api
    with datos.app.app_context(), transaccion() as cursor:
        equipo, catalogo = nuevo_id(), nuevo_id()
        cursor.execute(
            "INSERT INTO equipos (id,nombre,creado_en) VALUES (%s,'Equipo ficticio',%s)",
            (a_bytes(equipo), datos.reloj.ahora()),
        )
        cursor.execute(
            "INSERT INTO cambios_estado_equipo (id,equipo_id,estado,autor_id,registrado_en) "
            "VALUES (%s,%s,'fuera_de_servicio',%s,%s)",
            (a_bytes(nuevo_id()), a_bytes(equipo), a_bytes(datos.usuarios["entrenador"]), datos.reloj.ahora()),
        )
        cursor.execute(
            "INSERT INTO ejercicios (id,nombre,equipo,medidas_aplicables,actualizada_en) "
            "VALUES (%s,'Ejercicio ficticio','Equipo ficticio',%s,%s)",
            (a_bytes(catalogo), '["repeticiones","carga"]', datos.reloj.ahora()),
        )
        cursor.execute(
            "UPDATE ejercicios_planificados SET ejercicio_id=%s WHERE id=%s",
            (a_bytes(catalogo), a_bytes(datos.ejercicios[1][0])),
        )
    cliente = datos.cliente("entrenador")
    assert socios(cliente.get(RUTA)) == []
    for ejercicio in (0, 1):
        registrar(datos, 0, ejercicio, 2)
    respuesta = cliente.get(RUTA)
    motivos = socios(respuesta)[0]["motivos"]
    assert motivos == [
        {
            "tipo": "ejercicio_sin_alternativa",
            "fecha": datos.reloj.ahora().isoformat(),
            "ejercicio_id": str(datos.ejercicios[1][0]),
        }
    ]
    assert cliente.get(RUTA, headers={"If-None-Match": respuesta.headers["ETag"]}).status_code == 304
    with datos.app.app_context(), transaccion() as cursor:
        for tabla in ("avisos_entrenador", "prescripciones_efectivas"):
            cursor.execute(f"SELECT COUNT(*) AS cantidad FROM {tabla}")
            assert cursor.fetchone()["cantidad"] == 0


def test_bandeja_no_consulta_chequeo_del_dia(entrenamiento_api, monkeypatch):
    def no_consultar(*argumentos, **opciones):
        pytest.fail("La bandeja no debe consultar el chequeo del día")

    monkeypatch.setattr(repositorio, "obtener_chequeo", no_consultar)
    assert entrenamiento_api.cliente("entrenador").get(RUTA).status_code == 200
