"""Vigencia de acceso por fecha local, independiente del historial de visitas (#36)."""

import ast
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from mysql.connector import DatabaseError

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import a_bytes, nuevo_id
from gimnasio.comun.migrar import aplicar, dividir_sentencias, leer_migraciones
from gimnasio.comun.reloj import fecha_local
from gimnasio.permisos import servicio as permisos
from gimnasio.socios.servicio import consultar_membresia

RAIZ = Path(__file__).resolve().parents[1]
DESDE = date(2026, 10, 27)
HASTA = date(2026, 10, 29)


@pytest.fixture
def socio_con_membresia(app_con_bd, reloj_fijo):
    with app_con_bd.app_context(), transaccion() as cursor:
        socio_id = permisos.crear_usuario(
            cursor, {"nombre": "Socio", "apellido": "Ficticio", "cedula": "9900001"}, "socio"
        )
        membresia_id = nuevo_id(reloj_fijo)
        cursor.execute(
            """INSERT INTO membresias (id, socio_id, desde, hasta, actualizada_en)
               VALUES (%s, %s, %s, %s, %s)""",
            (a_bytes(membresia_id), a_bytes(socio_id), DESDE, HASTA, reloj_fijo.ahora()),
        )
    return socio_id, membresia_id


@pytest.mark.bd
def test_migracion_vacia_repetida_y_esquema_minimo(bd_vacia):
    assert "0006" in aplicar(bd_vacia, salida=lambda _: None)
    assert aplicar(bd_vacia, salida=lambda _: None) == []
    from gimnasio import crear_app

    app = crear_app({"ENTORNO": "prueba", "BD": bd_vacia})
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SHOW COLUMNS FROM membresias")
        assert {fila["Field"]: fila["Type"] for fila in cursor.fetchall()} == {
            "id": "binary(16)",
            "socio_id": "binary(16)",
            "desde": "date",
            "hasta": "date",
            "actualizada_en": "datetime(6)",
            "pago_id": "binary(16)",
            "tipo_id": "binary(16)",
        }
        # También es seguro repetir el DDL, sin pasar por el registro del aplicador.
        migracion = next(m for m in leer_migraciones() if m.version == "0006")
        for sentencia in dividir_sentencias(migracion.sql):
            cursor.execute(sentencia)


@pytest.mark.bd
def test_consulta_membresia_vigente_sin_datos_de_salud(app_con_bd, reloj_fijo, socio_con_membresia):
    socio_id, membresia_id = socio_con_membresia
    with app_con_bd.app_context():
        assert consultar_membresia(socio_id, fecha_local(reloj_fijo.ahora())) == {
            "id": str(membresia_id),
            "socio_id": str(socio_id),
            "desde": DESDE,
            "hasta": HASTA,
        }
    assert membresia_id.version == socio_id.version == 7


@pytest.mark.bd
def test_consulta_ausente_y_usuario_inexistente(app_con_bd, reloj_fijo):
    with app_con_bd.app_context():
        with transaccion() as cursor:
            socio_id = permisos.crear_usuario(
                cursor, {"nombre": "Socio", "apellido": "Ficticio", "cedula": "9900001"}, "socio"
            )
        assert consultar_membresia(socio_id, DESDE) is None
        assert consultar_membresia(nuevo_id(reloj_fijo), DESDE) is None


@pytest.mark.bd
@pytest.mark.parametrize(
    ("momento", "vigente"),
    [
        (datetime(2026, 10, 27, 2, 59, 59, 999999, tzinfo=UTC), False),
        (datetime(2026, 10, 27, 3, 0, tzinfo=UTC), True),
        (datetime(2026, 10, 28, 2, 59, 59, 999999, tzinfo=UTC), True),
        (datetime(2026, 10, 29, 3, 0, tzinfo=UTC), True),
        (datetime(2026, 10, 30, 2, 59, 59, 999999, tzinfo=UTC), True),
        (datetime(2026, 10, 30, 3, 0, tzinfo=UTC), False),
    ],
)
def test_extremos_inclusivos_y_medianoche_local(app_con_bd, reloj_fijo, socio_con_membresia, momento, vigente):
    socio_id, _ = socio_con_membresia
    reloj_fijo.fijar(momento)
    with app_con_bd.app_context():
        assert (consultar_membresia(socio_id, fecha_local(reloj_fijo.ahora())) is not None) == vigente


@pytest.mark.bd
@pytest.mark.parametrize(
    ("rol", "activo"), [("socio", False), ("recepcion", True), ("entrenador", True), ("administracion", True)]
)
def test_no_autoriza_usuario_inactivo_o_no_socio(app_con_bd, socio_con_membresia, rol, activo):
    socio_id, _ = socio_con_membresia
    with app_con_bd.app_context():
        with transaccion() as cursor:
            cursor.execute("UPDATE usuarios SET rol = %s, activo = %s WHERE id = %s", (rol, activo, a_bytes(socio_id)))
        assert consultar_membresia(socio_id, DESDE) is None


@pytest.mark.bd
def test_visitas_con_salida_no_consumen_vigencia_y_el_vencimiento_impide_reingresar(
    app_con_bd, reloj_fijo, socio_con_membresia
):
    socio_id, _ = socio_con_membresia
    with app_con_bd.app_context():
        # Historial aislado de prueba: no anticipa el esquema ni la apertura efectiva de #40.
        with transaccion() as cursor:
            cursor.execute(
                """CREATE TEMPORARY TABLE visitas (
                       id BINARY(16) PRIMARY KEY, socio_id BINARY(16),
                       entrada_en DATETIME(6), salida_en DATETIME(6))"""
            )
            cursor.execute("SELECT * FROM membresias")
            membresias_antes = cursor.fetchall()
        antes = consultar_membresia(socio_id, fecha_local(reloj_fijo.ahora()))
        assert antes is not None
        for _ in range(3):
            entrada = reloj_fijo.ahora()
            reloj_fijo.avanzar(timedelta(hours=1))
            with transaccion() as cursor:
                cursor.execute(
                    "INSERT INTO visitas (id, socio_id, entrada_en, salida_en) VALUES (%s, %s, %s, %s)",
                    (a_bytes(nuevo_id(reloj_fijo)), a_bytes(socio_id), entrada, reloj_fijo.ahora()),
                )
            assert consultar_membresia(socio_id, fecha_local(reloj_fijo.ahora())) == antes
        with transaccion() as cursor:
            cursor.execute("SELECT COUNT(*) AS cantidad FROM visitas WHERE salida_en IS NOT NULL")
            assert cursor.fetchone()["cantidad"] == 3
            cursor.execute("SELECT * FROM membresias")
            assert cursor.fetchall() == membresias_antes
        reloj_fijo.fijar(datetime(2026, 10, 30, 3, 0, tzinfo=UTC))
        assert consultar_membresia(socio_id, fecha_local(reloj_fijo.ahora())) is None


@pytest.mark.bd
def test_restricciones_de_fechas_y_clave_foranea(app_con_bd, reloj_fijo, socio_con_membresia):
    socio_id, _ = socio_con_membresia
    with app_con_bd.app_context():
        for socio, desde, hasta, codigo in [
            (socio_id, HASTA, DESDE, 3819),
            (nuevo_id(reloj_fijo), DESDE, HASTA, 1452),
        ]:
            with pytest.raises(DatabaseError) as error, transaccion() as cursor:
                cursor.execute(
                    """INSERT INTO membresias (id, socio_id, desde, hasta, actualizada_en)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (a_bytes(nuevo_id(reloj_fijo)), a_bytes(socio), desde, hasta, reloj_fijo.ahora()),
                )
            assert error.value.errno == codigo
        # Un solo día es un intervalo válido, con ambos extremos incluidos.
        with transaccion() as cursor:
            cursor.execute(
                """INSERT INTO membresias (id, socio_id, desde, hasta, actualizada_en)
                   VALUES (%s, %s, %s, %s, %s)""",
                (
                    a_bytes(nuevo_id(reloj_fijo)),
                    a_bytes(socio_id),
                    DESDE - timedelta(days=1),
                    DESDE - timedelta(days=1),
                    reloj_fijo.ahora(),
                ),
            )
        assert consultar_membresia(socio_id, DESDE - timedelta(days=1)) is not None


def test_socios_solo_accede_a_sus_tablas_sin_repositorios_ajenos():
    from pruebas.test_dependencias import violaciones

    assert not [v for v in violaciones(RAIZ) if v.startswith("gimnasio.socios.")]
    tablas = set()
    for archivo in (RAIZ / "gimnasio" / "socios").glob("*.py"):
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                # UPDATE al inicio evita confundir FOR UPDATE y ON DUPLICATE KEY UPDATE con tablas.
                tablas.update(re.findall(r"(?:\b(?:FROM|JOIN|INTO)|^\s*UPDATE)\s+(\w+)", nodo.value, re.IGNORECASE))
    # ADR 0027: socios ignora la vigencia derivada de pagos anulados.
    assert tablas == {"membresias", "usuarios", "personas", "perfiles_entrenamiento", "anulaciones_pago"}
