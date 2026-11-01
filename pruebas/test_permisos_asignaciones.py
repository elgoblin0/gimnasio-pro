"""Asignaciones con historial, alcance y conservación del entrenamiento."""

from uuid import UUID

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import desde_bytes, nuevo_id
from gimnasio.permisos import servicio
from pruebas.test_bandeja_api import socios
from pruebas.test_entrenador import vista as vista
from pruebas.test_entrenamiento_api import entrenamiento_api as entrenamiento_api
from pruebas.test_pagos import escribir, filas

pytestmark = pytest.mark.bd


def asignar(datos, entrenador="otro", socio="socio"):
    return escribir(
        datos.cliente("administracion"),
        f"/api/socios/{datos.usuarios[socio]}/entrenador",
        {"entrenador_id": str(datos.usuarios[entrenador])},
        metodo="put",
    )


def test_cambio_conserva_programa_sesion_historial_y_avisos(vista):
    datos = vista
    tablas = (
        "programas_entrenamiento",
        "sesiones_planificadas",
        "ejercicios_planificados",
        "sesiones_realizadas",
        "avisos_entrenador",
    )
    antes = {tabla: filas(datos.app, tabla) for tabla in tablas}
    anterior, nuevo = datos.cliente("entrenador"), datos.cliente("otro")
    assert socios(anterior.get("/api/entrenador/bandeja"))
    assert not socios(nuevo.get("/api/entrenador/bandeja"))
    respuesta = asignar(datos)
    assert respuesta.status_code == 200, respuesta.json
    assert not socios(anterior.get("/api/entrenador/bandeja"))
    assert socios(nuevo.get("/api/entrenador/bandeja"))[0]["id"] == datos.socio
    assert anterior.get(datos.ruta).status_code == 403
    assert nuevo.get(datos.ruta).status_code == 200
    assert antes == {tabla: filas(datos.app, tabla) for tabla in tablas}
    assert asignar(datos).json["error"]["codigo"] == "asignacion_sin_cambio"
    assert asignar(datos, "entrenador").status_code == 200
    historial = [f for f in filas(datos.app, "asignaciones_entrenador") if f["socio_id"] == UUID(datos.socio).bytes]
    assert len(historial) == 3
    assert sum(f["hasta"] is None for f in historial) == 1
    original = next(f for f in historial if desde_bytes(f["id"]) == datos.asignacion)
    assert original["hasta"] is not None
    vigente = next(f for f in historial if f["hasta"] is None)
    assert vigente["id"] != original["id"] and vigente["entrenador_id"] == original["entrenador_id"]


def test_socios_sin_entrenador_y_validacion(entrenamiento_api):
    datos = entrenamiento_api
    cliente = datos.cliente("administracion")
    ruta = "/api/socios/sin-entrenador"
    assert [s["id"] for s in cliente.get(ruta).json["socios"]] == [str(datos.usuarios["ajeno"])]
    assert asignar(datos, "recepcion", "ajeno").status_code == 422
    assert asignar(datos, "otro", "ajeno").status_code == 200
    assert cliente.get(ruta).json == {"socios": []}
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("UPDATE usuarios SET activo=FALSE WHERE id=%s", (datos.usuarios["otro"].bytes,))
    assert [s["id"] for s in cliente.get(ruta).json["socios"]] == [str(datos.usuarios["ajeno"])]
    assert asignar(datos).status_code == 422
    assert asignar(datos, socio="recepcion").status_code == 404


def test_editor_abierto_pierde_permiso_al_publicar(entrenamiento_api):
    datos = entrenamiento_api
    entrenador = datos.cliente("entrenador")
    ruta = f"/api/socios/{datos.usuarios['socio']}"
    # El editor ya pudo leer y conserva su versión antes del cambio.
    lectura = entrenador.get(ruta + "/programa")
    assert lectura.status_code == 200, lectura.json
    assert asignar(datos).status_code == 200
    assert escribir(entrenador, ruta + "/programas", {}, metodo="post").status_code == 403


@pytest.fixture
def asignacion(app_con_bd, reloj_fijo):
    with app_con_bd.app_context(), transaccion() as cursor:
        usuarios = {}
        for numero, (nombre, rol) in enumerate(
            [("socio", "socio"), ("ajeno", "socio"), ("entrenador", "entrenador"), ("otro", "entrenador")]
        ):
            usuarios[nombre] = servicio.crear_usuario(
                cursor, {"nombre": nombre, "apellido": "Prueba", "cedula": str(1_000_000 + numero)}, rol
            )
        asignacion_id = nuevo_id(reloj_fijo)
        cursor.execute(
            """INSERT INTO asignaciones_entrenador (id, socio_id, entrenador_id, desde, hasta)
               VALUES (%s, %s, %s, %s, NULL)""",
            (asignacion_id.bytes, usuarios["socio"].bytes, usuarios["entrenador"].bytes, reloj_fijo.ahora()),
        )
    return usuarios, asignacion_id


def test_consulta_asignacion_vigente_sin_importar_otro_repositorio(app_con_bd, asignacion):
    usuarios, _ = asignacion
    with app_con_bd.app_context(), transaccion() as cursor:
        assert servicio.tiene_asignacion_vigente(cursor, usuarios["socio"], usuarios["entrenador"]) is True
        assert servicio.tiene_asignacion_vigente(cursor, usuarios["ajeno"], usuarios["entrenador"]) is False
        assert servicio.tiene_asignacion_vigente(cursor, usuarios["socio"], usuarios["otro"]) is False


def test_asignacion_terminada_no_da_alcance(app_con_bd, asignacion, reloj_fijo):
    usuarios, asignacion_id = asignacion
    with app_con_bd.app_context():
        with transaccion() as cursor:
            cursor.execute(
                "UPDATE asignaciones_entrenador SET hasta = %s WHERE id = %s",
                (reloj_fijo.ahora(), asignacion_id.bytes),
            )
        with transaccion() as cursor:
            assert servicio.tiene_asignacion_vigente(cursor, usuarios["socio"], usuarios["entrenador"]) is False


@pytest.mark.parametrize("inactivo", ["socio", "entrenador"])
def test_asignacion_con_usuario_inactivo_no_da_alcance(app_con_bd, asignacion, inactivo):
    usuarios, _ = asignacion
    with app_con_bd.app_context():
        with transaccion() as cursor:
            cursor.execute("UPDATE usuarios SET activo = FALSE WHERE id = %s", (usuarios[inactivo].bytes,))
        with transaccion() as cursor:
            assert servicio.tiene_asignacion_vigente(cursor, usuarios["socio"], usuarios["entrenador"]) is False


@pytest.mark.parametrize("usuario,rol", [("socio", "recepcion"), ("entrenador", "administracion")])
def test_asignacion_no_amplia_el_alcance_de_otros_roles(app_con_bd, asignacion, usuario, rol):
    usuarios, _ = asignacion
    with app_con_bd.app_context():
        with transaccion() as cursor:
            cursor.execute("UPDATE usuarios SET rol = %s WHERE id = %s", (rol, usuarios[usuario].bytes))
        with transaccion() as cursor:
            assert servicio.tiene_asignacion_vigente(cursor, usuarios["socio"], usuarios["entrenador"]) is False
