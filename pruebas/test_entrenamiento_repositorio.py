"""Hechos de entrenamiento independientes de las visitas y del programa."""

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from mysql.connector import IntegrityError

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import a_bytes, nuevo_id
from gimnasio.demo import servicio as demo
from gimnasio.entrenamiento import repositorio
from gimnasio.permisos.servicio import crear_usuario


def insertar(cursor, tabla, **datos):
    columnas = ", ".join(datos)
    parametros = ", ".join("%s" for _ in datos)
    cursor.execute(f"INSERT INTO {tabla} ({columnas}) VALUES ({parametros})", tuple(datos.values()))


@pytest.fixture
def entrenamiento(app_con_bd, reloj_fijo):
    with app_con_bd.app_context(), transaccion() as cursor:
        datos = SimpleNamespace(app=app_con_bd, cursor=cursor, reloj=reloj_fijo, momento=reloj_fijo.ahora())
        datos.socio = crear_usuario(cursor, {"nombre": "Socio", "apellido": "Ficticio", "cedula": "9900301"}, "socio")
        datos.otro_socio = crear_usuario(
            cursor, {"nombre": "Otro", "apellido": "Ficticio", "cedula": "9900302"}, "socio"
        )
        datos.programa, datos.planificada = (nuevo_id(reloj_fijo) for _ in range(2))
        insertar(
            cursor,
            "programas_entrenamiento",
            id=a_bytes(datos.programa),
            socio_id=a_bytes(datos.socio),
            version=1,
            creado_en=datos.momento,
        )
        insertar(
            cursor,
            "sesiones_planificadas",
            id=a_bytes(datos.planificada),
            programa_id=a_bytes(datos.programa),
            posicion=1,
            nombre="Sesión ficticia",
        )
        for posicion, nombre, medidas in (
            (1, "fuerza", '["repeticiones", "carga"]'),
            (2, "cardio", '["duracion", "distancia"]'),
        ):
            ejercicio, planificado = (nuevo_id(reloj_fijo) for _ in range(2))
            insertar(
                cursor,
                "ejercicios",
                id=a_bytes(ejercicio),
                nombre=nombre,
                medidas_aplicables=medidas,
                actualizada_en=datos.momento,
            )
            insertar(
                cursor,
                "ejercicios_planificados",
                id=a_bytes(planificado),
                sesion_planificada_id=a_bytes(datos.planificada),
                ejercicio_id=a_bytes(ejercicio),
                posicion=posicion,
                series=2,
                repeticiones=10 if posicion == 1 else None,
                carga=Decimal("20.50") if posicion == 1 else None,
                duracion=120 if posicion == 2 else None,
                distancia=Decimal("1500.25") if posicion == 2 else None,
            )
            setattr(datos, nombre, planificado)
        datos.sesion = nuevo_id(reloj_fijo)
        repositorio.insertar_sesion(cursor, datos.sesion, datos.socio, datos.planificada, datos.momento)
        yield datos


def serie(datos, **cambios):
    argumentos = {
        "serie_id": nuevo_id(datos.reloj),
        "sesion_realizada_id": datos.sesion,
        "ejercicio_planificado_id": datos.fuerza,
        "autor_id": datos.socio,
        "registrada_en": datos.momento,
        "repeticiones": 10,
        "carga": Decimal("20.50"),
    } | cambios
    repositorio.insertar_serie(datos.cursor, **argumentos)
    return argumentos["serie_id"]


@pytest.mark.bd
def test_sesion_sin_visita_y_parcial_acredita_solo_series_vigentes(entrenamiento):
    datos = entrenamiento
    assert repositorio.listar_series_vigentes(datos.cursor, datos.socio) == []
    assert repositorio.obtener_sesion(datos.cursor, datos.sesion)["socio_id"] == a_bytes(datos.socio)
    identificador = serie(datos)
    vigente = repositorio.listar_series_vigentes(datos.cursor, datos.socio)
    assert len(vigente) == 1
    assert vigente[0]["id"] == a_bytes(identificador)
    assert vigente[0]["sesion_planificada_id"] == a_bytes(datos.planificada)
    assert vigente[0]["carga"] == Decimal("20.50")
    assert vigente[0]["registrada_en"] == datos.momento.replace(tzinfo=None)
    assert repositorio.listar_series_vigentes(datos.cursor, datos.otro_socio) == []
    datos.cursor.execute("SELECT COUNT(*) AS cantidad FROM entradas")
    assert datos.cursor.fetchone()["cantidad"] == 0
    datos.cursor.execute("SELECT series, carga FROM ejercicios_planificados WHERE id = %s", (a_bytes(datos.fuerza),))
    assert datos.cursor.fetchone() == {"series": 2, "carga": Decimal("20.50")}


@pytest.mark.bd
def test_correccion_y_anulacion_conservan_original_y_cambian_lectura(entrenamiento):
    datos = entrenamiento
    original = serie(datos)
    corregida = serie(
        datos,
        corrige_a=original,
        motivo="Carga corregida",
        carga=Decimal("21.25"),
        registrada_en=datos.momento + timedelta(seconds=1),
    )
    assert [fila["id"] for fila in repositorio.listar_series_vigentes(datos.cursor, datos.socio)] == [
        a_bytes(corregida)
    ]
    serie(
        datos,
        corrige_a=corregida,
        motivo="Anulación ficticia",
        anulada=True,
        registrada_en=datos.momento + timedelta(seconds=2),
    )
    assert repositorio.listar_series_vigentes(datos.cursor, datos.socio) == []
    datos.cursor.execute("SELECT COUNT(*) AS cantidad FROM series_realizadas")
    assert datos.cursor.fetchone()["cantidad"] == 3


@pytest.mark.bd
def test_cardio_conserva_decimales_y_nulos(entrenamiento):
    datos = entrenamiento
    serie(
        datos,
        ejercicio_planificado_id=datos.cardio,
        repeticiones=None,
        carga=None,
        duracion=121,
        distancia=Decimal("1500.27"),
    )
    fila = repositorio.listar_series_vigentes(datos.cursor, datos.socio, datos.sesion)[0]
    assert fila["duracion"] == 121
    assert fila["distancia"] == Decimal("1500.27")
    assert fila["repeticiones"] is fila["carga"] is None


@pytest.mark.bd
def test_rechaza_ejercicio_de_otra_sesion_y_correccion_ajena(entrenamiento):
    datos = entrenamiento
    with pytest.raises(ValueError, match="ejercicio planificado"):
        serie(datos, ejercicio_planificado_id=nuevo_id(datos.reloj))
    original = serie(datos)
    with pytest.raises(ValueError, match="corrección"):
        serie(
            datos,
            ejercicio_planificado_id=datos.cardio,
            repeticiones=None,
            carga=None,
            duracion=100,
            distancia=Decimal("100"),
            corrige_a=original,
            motivo="Inválida",
        )
    with pytest.raises(ValueError, match="socio"):
        repositorio.insertar_sesion(
            datos.cursor, nuevo_id(datos.reloj), datos.otro_socio, datos.planificada, datos.momento
        )


@pytest.mark.bd
def test_ids_repetidos_no_sobrescriben_hechos_y_fk_rechaza_autor_inexistente(entrenamiento):
    datos = entrenamiento
    identificador = serie(datos)
    serie(datos, serie_id=identificador, carga=Decimal("99"))
    assert repositorio.listar_series_vigentes(datos.cursor, datos.socio)[0]["carga"] == Decimal("20.50")
    repositorio.insertar_sesion(datos.cursor, datos.sesion, datos.socio, datos.planificada, datos.momento)
    with pytest.raises(IntegrityError):
        serie(datos, autor_id=nuevo_id(datos.reloj))


@pytest.mark.bd
def test_visita_sin_series_no_acredita_entrenamiento(entrenamiento):
    datos = entrenamiento
    sede = nuevo_id(datos.reloj)
    insertar(
        datos.cursor, "sedes", id=a_bytes(sede), nombre="Sede ficticia", aforo_maximo=3, actualizada_en=datos.momento
    )
    insertar(
        datos.cursor,
        "entradas",
        id=a_bytes(nuevo_id(datos.reloj)),
        socio_id=a_bytes(datos.socio),
        sede_id=a_bytes(sede),
        autor_id=a_bytes(datos.socio),
        registrada_en=datos.momento,
    )
    assert repositorio.listar_series_vigentes(datos.cursor, datos.socio) == []


@pytest.mark.bd
def test_fk_de_sesion_y_serie_rechazan_referencias_inexistentes(entrenamiento):
    datos = entrenamiento
    with pytest.raises(IntegrityError):
        insertar(
            datos.cursor,
            "sesiones_realizadas",
            id=a_bytes(nuevo_id(datos.reloj)),
            socio_id=a_bytes(datos.socio),
            sesion_planificada_id=a_bytes(nuevo_id(datos.reloj)),
            creada_en=datos.momento,
        )
    with pytest.raises(IntegrityError):
        insertar(
            datos.cursor,
            "series_realizadas",
            id=a_bytes(nuevo_id(datos.reloj)),
            sesion_realizada_id=a_bytes(nuevo_id(datos.reloj)),
            ejercicio_planificado_id=a_bytes(datos.fuerza),
            autor_id=a_bytes(datos.socio),
            registrada_en=datos.momento,
        )


@pytest.mark.bd
def test_reinicio_demo_borra_correcciones_y_sesiones_antes_del_programa(entrenamiento):
    datos = entrenamiento
    datos.app.config["MODO_DEMO"] = True
    original = serie(datos)
    correccion = serie(datos, corrige_a=original, motivo="Corrección ficticia")
    demo.reiniciar()
    assert repositorio.obtener_sesion(datos.cursor, datos.sesion) is None
    assert repositorio.obtener_serie(datos.cursor, original) is None
    assert repositorio.obtener_serie(datos.cursor, correccion) is None
    for tabla, cantidad in (("series_realizadas", 1), ("sesiones_realizadas", 1), ("programas_entrenamiento", 2)):
        datos.cursor.execute(f"SELECT COUNT(*) AS cantidad FROM {tabla}")
        assert datos.cursor.fetchone()["cantidad"] == cantidad
    datos.cursor.execute("SELECT COUNT(*) AS cantidad FROM migraciones_aplicadas")
    assert datos.cursor.fetchone()["cantidad"] == 9


@pytest.mark.parametrize(
    "medidas,valores",
    [
        (["carga"], {"carga": float("nan")}),
        (["carga"], {"carga": "Infinity"}),
        (["carga"], {"carga": -1}),
        (["carga"], {"carga": "1.001"}),
        (["repeticiones"], {"repeticiones": True}),
        (["repeticiones"], {"repeticiones": 1.5}),
        (["duracion"], {"duracion": 0}),
        (["distancia"], {"distancia": 0}),
        (["carga"], {"carga": 1, "duracion": 10}),
        (["carga"], {}),
    ],
)
def test_rechaza_medidas_invalidas_sin_redondear(medidas, valores):
    with pytest.raises(ValueError):
        repositorio.validar_medidas(medidas, valores)


def test_valida_medidas_de_fuerza_y_cardio_sin_perder_precision():
    assert repositorio.validar_medidas(["repeticiones", "carga"], {"repeticiones": 10, "carga": "20.50"}) == {
        "repeticiones": 10,
        "carga": Decimal("20.50"),
        "duracion": None,
        "distancia": None,
    }
    assert repositorio.validar_medidas(["duracion", "distancia"], {"duracion": 120, "distancia": "1500.25"})[
        "distancia"
    ] == Decimal("1500.25")
