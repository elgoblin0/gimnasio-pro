"""Consulta pública del alcance del entrenador sobre MySQL (ADR 0001 y 0006)."""

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import nuevo_id
from gimnasio.permisos import servicio

pytestmark = pytest.mark.bd


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
