"""Historial de visitas: hechos conservados y lectura vigente sobre MySQL."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from mysql.connector import IntegrityError

from gimnasio.comun.bd import conectar
from gimnasio.comun.ids import a_bytes, nuevo_id
from gimnasio.demo import repositorio as repositorio_demo
from gimnasio.visitas import repositorio


@pytest.fixture
def historial(bd_limpia, reloj_fijo):
    conexion = conectar(bd_limpia)
    cursor = conexion.cursor(dictionary=True)
    datos = SimpleNamespace(cursor=cursor, reloj=reloj_fijo, momento=reloj_fijo.ahora())
    for indice, nombre in enumerate(("socio_id", "otro_socio_id", "autor_id")):
        persona_id, usuario_id = nuevo_id(reloj_fijo), nuevo_id(reloj_fijo)
        cursor.execute(
            """INSERT INTO personas (id, nombre, apellido, cedula, creada_en, actualizada_en)
               VALUES (%s, 'Persona ficticia', 'Demo', %s, %s, %s)""",
            (a_bytes(persona_id), str(9900000 + indice), datos.momento, datos.momento),
        )
        cursor.execute(
            """INSERT INTO usuarios (id, persona_id, rol, creado_en, actualizado_en)
               VALUES (%s, %s, %s, %s, %s)""",
            (
                a_bytes(usuario_id),
                a_bytes(persona_id),
                "recepcion" if nombre == "autor_id" else "socio",
                datos.momento,
                datos.momento,
            ),
        )
        setattr(datos, nombre, usuario_id)
    for nombre in ("sede_id", "otra_sede_id"):
        sede_id = nuevo_id(reloj_fijo)
        cursor.execute(
            """INSERT INTO sedes (id, nombre, aforo_maximo, actualizada_en)
               VALUES (%s, 'Sede ficticia', 60, %s)""",
            (a_bytes(sede_id), datos.momento),
        )
        setattr(datos, nombre, sede_id)
    try:
        yield datos
    finally:
        conexion.rollback()
        cursor.close()
        conexion.close()


def entrada(datos, **cambios):
    campos = {
        "entrada_id": nuevo_id(datos.reloj),
        "socio_id": datos.socio_id,
        "sede_id": datos.sede_id,
        "autor_id": datos.autor_id,
        "registrada_en": datos.momento,
    } | cambios
    repositorio.insertar_entrada(datos.cursor, **campos)
    return campos["entrada_id"]


def salida(datos, entrada_id, **cambios):
    campos = {
        "salida_id": nuevo_id(datos.reloj),
        "entrada_id": entrada_id,
        "autor_id": datos.autor_id,
        "registrada_en": datos.momento + timedelta(hours=1),
    } | cambios
    repositorio.insertar_salida(datos.cursor, **campos)
    return campos["salida_id"]


@pytest.mark.bd
def test_entrada_sin_salida_permanece_abierta_y_salida_confirmada_la_cierra(historial):
    datos = historial
    entrada_id = entrada(datos, registrada_en=datos.momento - timedelta(days=30))
    estado = repositorio.obtener_estado_vigente(datos.cursor, entrada_id)
    assert estado["entrada_id"] == a_bytes(entrada_id)
    assert estado["abierta"]
    assert estado["salida_id"] is None
    assert estado["salida_registrada_en"] is None
    salida_id = salida(datos, entrada_id)
    estado = repositorio.obtener_estado_vigente(datos.cursor, entrada_id)
    assert not estado["abierta"]
    assert estado["salida_id"] == a_bytes(salida_id)
    assert estado["salida_registrada_en"] == (datos.momento + timedelta(hours=1)).replace(tzinfo=None)
    assert repositorio.obtener_estado_vigente(datos.cursor, nuevo_id(datos.reloj)) is None


@pytest.mark.bd
def test_ultima_correccion_de_entrada_conserva_la_visita_y_los_originales(historial):
    datos = historial
    original = entrada(datos)
    primera = entrada(
        datos,
        corrige_a=original,
        motivo="Corrección de sede",
        sede_id=datos.otra_sede_id,
        registrada_en=datos.momento + timedelta(minutes=1),
    )
    ultima = entrada(
        datos,
        corrige_a=primera,
        motivo="Corrección de socio",
        socio_id=datos.otro_socio_id,
        registrada_en=datos.momento + timedelta(minutes=2),
    )
    estado = repositorio.obtener_estado_vigente(datos.cursor, original)
    assert estado["entrada_id"] == a_bytes(original)
    assert estado["registro_entrada_id"] == a_bytes(ultima)
    assert estado["socio_id"] == a_bytes(datos.otro_socio_id)
    assert estado["sede_id"] == a_bytes(datos.sede_id)
    assert estado["corrige_a"] == a_bytes(primera)
    assert estado["motivo"] == "Corrección de socio"
    assert estado["abierta"]
    datos.cursor.execute("SELECT id, socio_id, sede_id, corrige_a FROM entradas ORDER BY registrada_en, id")
    filas = datos.cursor.fetchall()
    assert len(filas) == 3
    assert filas[0] == {
        "id": a_bytes(original),
        "socio_id": a_bytes(datos.socio_id),
        "sede_id": a_bytes(datos.sede_id),
        "corrige_a": None,
    }
    # Una salida ligada a una versión de la entrada sigue cerrando la visita original.
    salida(datos, primera)
    assert not repositorio.obtener_estado_vigente(datos.cursor, original)["abierta"]


@pytest.mark.bd
def test_correcciones_a_la_original_se_ordenan_por_fecha_y_por_id(historial):
    datos = historial
    original = entrada(datos)
    momento = datos.momento + timedelta(minutes=1)
    menor, mayor = nuevo_id(datos.reloj), nuevo_id(datos.reloj)
    entrada(datos, entrada_id=mayor, corrige_a=original, motivo="Última corrección", registrada_en=momento)
    entrada(datos, entrada_id=menor, corrige_a=original, motivo="Corrección anterior", registrada_en=momento)
    entrada(datos, corrige_a=original, motivo="Registro anterior", registrada_en=datos.momento)
    assert repositorio.obtener_estado_vigente(datos.cursor, original)["registro_entrada_id"] == a_bytes(mayor)


@pytest.mark.bd
def test_correccion_y_anulacion_de_salida_reabren_sin_borrar_el_historial(historial):
    datos = historial
    original = entrada(datos)
    primera = salida(datos, original)
    correccion = salida(
        datos,
        original,
        corrige_a=primera,
        motivo="Corrección de salida",
        registrada_en=datos.momento + timedelta(hours=2),
    )
    estado = repositorio.obtener_estado_vigente(datos.cursor, original)
    assert estado["salida_id"] == a_bytes(correccion)
    assert not estado["abierta"]
    anulacion = salida(
        datos,
        original,
        corrige_a=correccion,
        motivo="Salida registrada por error",
        anulada=True,
        registrada_en=datos.momento + timedelta(hours=3),
    )
    estado = repositorio.obtener_estado_vigente(datos.cursor, original)
    assert estado["abierta"]
    assert estado["salida_id"] is None
    assert repositorio.contar_ocupacion_registrada(datos.cursor, datos.sede_id) == 1
    datos.cursor.execute("SELECT id, corrige_a, anulada FROM salidas ORDER BY registrada_en, id")
    assert datos.cursor.fetchall() == [
        {"id": a_bytes(primera), "corrige_a": None, "anulada": 0},
        {"id": a_bytes(correccion), "corrige_a": a_bytes(primera), "anulada": 0},
        {"id": a_bytes(anulacion), "corrige_a": a_bytes(correccion), "anulada": 1},
    ]
    salida(
        datos,
        original,
        corrige_a=anulacion,
        motivo="Salida confirmada nuevamente",
        registrada_en=datos.momento + timedelta(hours=4),
    )
    assert not repositorio.obtener_estado_vigente(datos.cursor, original)["abierta"]


@pytest.mark.bd
def test_anular_una_entrada_excluye_la_visita_de_la_ocupacion(historial):
    datos = historial
    original = entrada(datos)
    entrada(
        datos,
        corrige_a=original,
        motivo="Entrada registrada por error",
        anulada=True,
        registrada_en=datos.momento + timedelta(minutes=1),
    )
    estado = repositorio.obtener_estado_vigente(datos.cursor, original)
    assert estado["anulada"]
    assert not estado["abierta"]
    assert repositorio.contar_ocupacion_registrada(datos.cursor, datos.sede_id) == 0
    datos.cursor.execute("SELECT COUNT(*) AS cantidad FROM entradas")
    assert datos.cursor.fetchone()["cantidad"] == 2


@pytest.mark.bd
def test_ocupacion_registrada_cuenta_solo_visitas_abiertas_por_sede(historial):
    datos = historial
    assert repositorio.contar_ocupacion_registrada(datos.cursor, datos.sede_id) == 0
    # La presencia se registra aunque no haya ninguna sesión realizada.
    abierta = entrada(datos)
    cerrada = entrada(datos, socio_id=datos.otro_socio_id)
    salida(datos, cerrada)
    salida(datos, cerrada)  # Dos salidas no duplican ni restan visitas.
    otra_sede = entrada(datos, sede_id=datos.otra_sede_id, socio_id=datos.otro_socio_id)
    assert repositorio.contar_ocupacion_registrada(datos.cursor, datos.sede_id) == 1
    assert repositorio.contar_ocupacion_registrada(datos.cursor, datos.otra_sede_id) == 1
    entrada(
        datos,
        corrige_a=abierta,
        motivo="Corrección de sede",
        sede_id=datos.otra_sede_id,
        registrada_en=datos.momento + timedelta(minutes=1),
    )
    assert repositorio.contar_ocupacion_registrada(datos.cursor, datos.sede_id) == 0
    assert repositorio.contar_ocupacion_registrada(datos.cursor, datos.otra_sede_id) == 2
    salida(datos, otra_sede)
    assert repositorio.contar_ocupacion_registrada(datos.cursor, datos.otra_sede_id) == 1


@pytest.mark.bd
def test_anular_una_salida_no_anula_otras_salidas_vigentes(historial):
    datos = historial
    original = entrada(datos)
    salida(datos, original)
    otra = salida(datos, original)
    salida(
        datos,
        original,
        corrige_a=otra,
        motivo="Salida duplicada",
        anulada=True,
        registrada_en=datos.momento + timedelta(hours=2),
    )
    assert not repositorio.obtener_estado_vigente(datos.cursor, original)["abierta"]
    assert repositorio.contar_ocupacion_registrada(datos.cursor, datos.sede_id) == 0


@pytest.mark.bd
@pytest.mark.parametrize(
    "tabla, campo",
    [
        ("entradas", "socio_id"),
        ("entradas", "sede_id"),
        ("entradas", "autor_id"),
        ("entradas", "corrige_a"),
        ("salidas", "entrada_id"),
        ("salidas", "autor_id"),
        ("salidas", "corrige_a"),
    ],
)
def test_claves_foraneas_rechazan_referencias_inexistentes(historial, tabla, campo):
    datos = historial
    original = entrada(datos)
    cambios = {campo: nuevo_id(datos.reloj)}
    if campo == "corrige_a":
        cambios["motivo"] = "Corrección de prueba"
    with pytest.raises(IntegrityError) as error:
        if tabla == "entradas":
            entrada(datos, **cambios)
        else:
            salida(datos, **({"entrada_id": original} | cambios))
    assert error.value.errno == 1452


@pytest.mark.bd
def test_reintentar_ids_no_duplica_ni_reescribe_hechos(historial):
    datos = historial
    original = entrada(datos)
    entrada(datos, entrada_id=original, socio_id=datos.otro_socio_id)
    salida_id = salida(datos, original)
    salida(datos, original, salida_id=salida_id, registrada_en=datos.momento + timedelta(days=1))
    datos.cursor.execute("SELECT COUNT(*) AS cantidad FROM entradas")
    assert datos.cursor.fetchone()["cantidad"] == 1
    datos.cursor.execute("SELECT COUNT(*) AS cantidad FROM salidas")
    assert datos.cursor.fetchone()["cantidad"] == 1
    estado = repositorio.obtener_estado_vigente(datos.cursor, original)
    assert estado["socio_id"] == a_bytes(datos.socio_id)
    assert estado["salida_registrada_en"] == (datos.momento + timedelta(hours=1)).replace(tzinfo=None)


@pytest.mark.bd
def test_reinicio_demo_borra_correcciones_antes_que_originales_sin_desactivar_fk(historial):
    datos = historial
    original = entrada(datos)
    correccion = entrada(datos, corrige_a=original, motivo="Corrección de entrada")
    entrada(datos, corrige_a=correccion, motivo="Anulación de entrada", anulada=True)
    primera_salida = salida(datos, original)
    correccion_salida = salida(datos, original, corrige_a=primera_salida, motivo="Corrección de salida")
    salida(datos, original, corrige_a=correccion_salida, motivo="Anulación de salida", anulada=True)
    repositorio_demo.vaciar_datos(datos.cursor)
    for tabla in ("entradas", "salidas", "usuarios", "personas", "sedes"):
        datos.cursor.execute(f"SELECT COUNT(*) AS cantidad FROM {tabla}")
        assert datos.cursor.fetchone()["cantidad"] == 0
    datos.cursor.execute("SELECT @@FOREIGN_KEY_CHECKS AS activas")
    assert datos.cursor.fetchone()["activas"] == 1
    datos.cursor.execute("SELECT COUNT(*) AS cantidad FROM migraciones_aplicadas")
    assert datos.cursor.fetchone()["cantidad"] > 0


@pytest.mark.bd
def test_columnas_e_indices_de_visitas(historial):
    datos = historial
    for tabla in ("entradas", "salidas"):
        datos.cursor.execute(f"SHOW COLUMNS FROM {tabla}")
        columnas = {fila["Field"]: fila["Type"] for fila in datos.cursor.fetchall()}
        assert columnas["id"] == columnas["autor_id"] == columnas["corrige_a"] == "binary(16)"
        assert columnas["registrada_en"] == "datetime(6)"
        if tabla == "entradas":
            assert columnas["socio_id"] == columnas["sede_id"] == "binary(16)"
            indice, esperadas = "ix_entradas_socio_fecha", ["socio_id", "registrada_en"]
        else:
            assert columnas["entrada_id"] == "binary(16)"
            indice, esperadas = "ix_salidas_entrada_fecha", ["entrada_id", "registrada_en"]
        datos.cursor.execute(f"SHOW INDEX FROM {tabla}")
        filas = sorted(datos.cursor.fetchall(), key=lambda fila: fila["Seq_in_index"])
        assert [fila["Column_name"] for fila in filas if fila["Key_name"] == indice] == esperadas


@pytest.mark.parametrize("tipo", ["entrada", "salida"])
def test_reintentar_un_id_duplicado_es_un_exito_sin_otra_escritura(reloj_fijo, tipo):
    cursor = Mock()
    cursor.execute.side_effect = IntegrityError(msg="Id ya registrado", errno=1062)
    identificadores = [nuevo_id(reloj_fijo) for _ in range(4)]
    if tipo == "entrada":
        repositorio.insertar_entrada(cursor, *identificadores, registrada_en=reloj_fijo.ahora())
    else:
        repositorio.insertar_salida(cursor, *identificadores[:3], registrada_en=reloj_fijo.ahora())
    cursor.execute.assert_called_once()


@pytest.mark.parametrize("tipo", ["entrada", "salida"])
def test_convierte_fechas_a_utc_antes_de_insertar(reloj_fijo, tipo):
    cursor = Mock()
    momento = datetime(2026, 10, 27, 9, 15, 0, 123456, tzinfo=timezone(timedelta(hours=-3)))
    identificadores = [nuevo_id(reloj_fijo) for _ in range(4)]
    if tipo == "entrada":
        repositorio.insertar_entrada(cursor, *identificadores, registrada_en=momento)
    else:
        repositorio.insertar_salida(cursor, *identificadores[:3], registrada_en=momento)
    assert datetime(2026, 10, 27, 12, 15, 0, 123456) in cursor.execute.call_args.args[1]
    with pytest.raises(ValueError, match="zona horaria"):
        if tipo == "entrada":
            repositorio.insertar_entrada(cursor, *identificadores, registrada_en=momento.replace(tzinfo=None))
        else:
            repositorio.insertar_salida(cursor, *identificadores[:3], registrada_en=momento.replace(tzinfo=None))


@pytest.mark.parametrize("tipo", ["entrada", "salida"])
def test_los_errores_de_integridad_no_se_ocultan(reloj_fijo, tipo):
    cursor = Mock()
    cursor.execute.side_effect = IntegrityError(msg="Referencia inexistente", errno=1452)
    identificadores = [nuevo_id(reloj_fijo) for _ in range(4)]
    with pytest.raises(IntegrityError):
        if tipo == "entrada":
            repositorio.insertar_entrada(cursor, *identificadores, registrada_en=reloj_fijo.ahora())
        else:
            repositorio.insertar_salida(cursor, *identificadores[:3], registrada_en=reloj_fijo.ahora())


@pytest.mark.bd
def test_visitas_confiables_para_prevision_respetan_estado_sede_y_rango(historial):
    datos = historial
    desde = datos.momento - timedelta(hours=1)
    hasta = datos.momento + timedelta(hours=1)
    # Una visita que empieza antes del rango sigue presente dentro de este.
    vigente = entrada(datos, registrada_en=desde - timedelta(minutes=30))
    anterior = salida(datos, vigente, registrada_en=datos.momento)
    salida(datos, vigente, corrige_a=anterior, motivo="Salida corregida", registrada_en=hasta)
    entrada(datos)  # La visita abierta no es confiable para la prevision.
    anulada = entrada(datos)
    salida(datos, anulada)
    entrada(datos, corrige_a=anulada, motivo="Entrada anulada", anulada=True)
    ajena = entrada(datos, sede_id=datos.otra_sede_id)
    salida(datos, ajena)
    futura = entrada(datos)
    salida(datos, futura, registrada_en=hasta + timedelta(minutes=1))
    filas = repositorio.listar_visitas_confiables(datos.cursor, datos.sede_id, desde, hasta)
    assert filas == [
        {
            "registrada_en": (desde - timedelta(minutes=30)).replace(tzinfo=None),
            "salida_registrada_en": hasta.replace(tzinfo=None),
        }
    ]
