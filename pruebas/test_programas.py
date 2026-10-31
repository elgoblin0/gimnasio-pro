"""Programa de entrenamiento versionado, orden de lectura y medidas aplicables."""

import json
from contextlib import contextmanager
from datetime import UTC
from decimal import Decimal

import pytest
from mysql.connector import IntegrityError

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import a_bytes, nuevo_id
from gimnasio.demo import servicio as demo
from gimnasio.permisos.servicio import crear_usuario
from gimnasio.programas import servicio


@pytest.mark.parametrize(
    "medidas",
    [[], ["repeticiones", "carga"], ["duracion", "distancia"], list(servicio.MEDIDAS)],
)
def test_valida_las_medidas_del_catalogo(medidas):
    servicio.validar_medidas_aplicables(medidas)


@pytest.mark.parametrize("medidas", [None, "carga", {}, [1], [["carga"]], ["peso"], ["duración"]])
def test_rechaza_medidas_que_no_son_una_lista_de_nombres_aplicables(medidas):
    with pytest.raises(ValueError, match="medidas aplicables"):
        servicio.validar_medidas_aplicables(medidas)


@pytest.fixture
def lectura_simulada(monkeypatch, reloj_fijo):
    identificadores = [a_bytes(nuevo_id(reloj_fijo)) for _ in range(5)]
    programa, socio, sesion, planificado, ejercicio = identificadores
    filas = [
        {
            "programa_id": programa,
            "socio_id": socio,
            "version": 2,
            "creado_en": reloj_fijo.ahora().replace(tzinfo=None),
            "sesion_id": sesion,
            "sesion_nombre": "Fuerza",
            "sesion_posicion": 1,
            "planificado_id": planificado,
            "ejercicio_id": ejercicio,
            "ejercicio_nombre": "Sentadilla",
            "ejercicio_posicion": 1,
            "medidas_aplicables": '["repeticiones", "carga"]',
            "series": 3,
            "repeticiones_minimas": 12,
            "repeticiones_maximas": 12,
            "rir_objetivo": None,
            "descanso": None,
            "patron_movimiento": "sentadilla",
            "equipo": "barra",
            "incremento_carga": Decimal("2.50"),
            "zonas": "[]",
            "alternativas": "[]",
            "carga": Decimal("30.50"),
            "duracion": None,
            "distancia": None,
        }
    ]

    @contextmanager
    def transaccion_simulada():
        yield None

    monkeypatch.setattr(servicio, "transaccion", transaccion_simulada)
    monkeypatch.setattr(servicio.repositorio, "leer_por_socio", lambda *argumentos: filas)
    return filas


def test_estructura_la_lectura_con_utc_y_decimales(lectura_simulada, reloj_fijo):
    programa = servicio.obtener_programa(nuevo_id(reloj_fijo), 2)
    assert programa["version"] == 2
    assert programa["creado_en"] == reloj_fijo.ahora()
    assert programa["creado_en"].tzinfo is UTC
    ejercicio = programa["sesiones_planificadas"][0]["ejercicios_planificados"][0]
    assert ejercicio["medidas_aplicables"] == ["repeticiones", "carga"]
    assert ejercicio["carga"] == Decimal("30.50")
    assert ejercicio["duracion"] is ejercicio["distancia"] is None


def test_la_lectura_valida_el_catalogo(lectura_simulada, reloj_fijo):
    lectura_simulada[0]["medidas_aplicables"] = '["peso"]'
    with pytest.raises(ValueError, match="medidas aplicables"):
        servicio.listar_programas(nuevo_id(reloj_fijo))


def test_la_lectura_rechaza_una_medida_no_aplicable(lectura_simulada, reloj_fijo):
    lectura_simulada[0]["duracion"] = 60
    with pytest.raises(ValueError, match="no aplicables"):
        servicio.listar_programas(nuevo_id(reloj_fijo))


@pytest.mark.parametrize("version", [None, True, "2", 2.0])
def test_la_version_de_lectura_debe_ser_explicita_y_entera(version, reloj_fijo):
    with pytest.raises(ValueError, match="versión"):
        servicio.obtener_programa(nuevo_id(reloj_fijo), version)


def insertar(cursor, tabla, **datos):
    columnas = ", ".join(datos)
    parametros = ", ".join("%s" for _ in datos)
    cursor.execute(f"INSERT INTO {tabla} ({columnas}) VALUES ({parametros})", tuple(datos.values()))


@pytest.fixture
def programas_con_bd(app_con_bd, reloj_fijo):
    with app_con_bd.app_context(), transaccion() as cursor:
        socios = [
            crear_usuario(cursor, {"nombre": "Socio", "apellido": "Ficticio", "cedula": str(9900010 + i)}, "socio")
            for i in range(2)
        ]
        ahora = reloj_fijo.ahora()
        fuerza, cardio = (a_bytes(nuevo_id(reloj_fijo)) for _ in range(2))
        for identificador, nombre, medidas in (
            (fuerza, "Sentadilla", ["repeticiones", "carga"]),
            (cardio, "Carrera", ["duracion", "distancia"]),
        ):
            insertar(
                cursor,
                "ejercicios",
                id=identificador,
                nombre=nombre,
                medidas_aplicables=json.dumps(medidas),
                actualizada_en=ahora,
            )
        programas = []
        sesiones = []
        # Se insertan versiones, sesiones y ejercicios en orden inverso al de lectura.
        for socio, version in ((socios[0], 2), (socios[1], 1), (socios[0], 1)):
            programa = a_bytes(nuevo_id(reloj_fijo))
            programas.append(programa)
            insertar(
                cursor,
                "programas_entrenamiento",
                id=programa,
                socio_id=a_bytes(socio),
                version=version,
                creado_en=ahora,
            )
            for posicion in (2, 1):
                sesion = a_bytes(nuevo_id(reloj_fijo))
                sesiones.append(sesion)
                insertar(
                    cursor, "sesiones_planificadas", id=sesion, programa_id=programa, posicion=posicion, nombre="Sesión"
                )
                for orden, ejercicio in ((2, cardio), (1, fuerza)):
                    insertar(
                        cursor,
                        "ejercicios_planificados",
                        id=a_bytes(nuevo_id(reloj_fijo)),
                        sesion_planificada_id=sesion,
                        ejercicio_id=ejercicio,
                        posicion=orden,
                        series=3,
                        repeticiones_minimas=12 if ejercicio == fuerza else None,
                        repeticiones_maximas=12 if ejercicio == fuerza else None,
                        carga=Decimal("30.50")
                        if ejercicio == fuerza and version == 2
                        else (Decimal("0.00") if ejercicio == fuerza else None),
                        duracion=120 if ejercicio == cardio else None,
                        distancia=Decimal("1500.25") if ejercicio == cardio else None,
                    )
    return {"socios": socios, "programas": programas, "sesiones": sesiones, "fuerza": fuerza}


@pytest.mark.bd
def test_lee_la_version_del_socio_sin_mezclar_y_con_orden_estable(app_con_bd, programas_con_bd):
    socio, otro_socio = programas_con_bd["socios"]
    with app_con_bd.app_context():
        versiones = servicio.listar_programas(socio)
        assert [programa["version"] for programa in versiones] == [1, 2]
        segunda = servicio.obtener_programa(socio, 2)
        assert segunda == versiones[1] == servicio.obtener_programa(socio, 2)
        assert segunda["socio_id"] == str(socio)
        assert servicio.obtener_programa(otro_socio, 2) is None
        assert servicio.obtener_programa(socio, 3) is None
        assert len(servicio.listar_programas(otro_socio)) == 1
        for programa in versiones:
            sesiones = programa["sesiones_planificadas"]
            assert [sesion["posicion"] for sesion in sesiones] == [1, 2]
            for sesion in sesiones:
                ejercicios = sesion["ejercicios_planificados"]
                assert [ejercicio["posicion"] for ejercicio in ejercicios] == [1, 2]
                fuerza, cardio = ejercicios
                assert fuerza["repeticiones_minimas"] == 12
                assert fuerza["carga"] == (Decimal("30.50") if programa["version"] == 2 else Decimal("0.00"))
                assert fuerza["duracion"] is fuerza["distancia"] is None
                assert fuerza["medidas_aplicables"] == ["repeticiones", "carga"]
                assert cardio["repeticiones_minimas"] is cardio["carga"] is None
                assert cardio["duracion"] == 120
                assert cardio["distancia"] == Decimal("1500.25")
                assert cardio["medidas_aplicables"] == ["duracion", "distancia"]
        # Leer y agregar una versión no modifica las medidas ni las sesiones de la anterior.
        assert servicio.obtener_programa(socio, 1) == versiones[0]


@pytest.mark.bd
def test_lectura_sin_programas_y_con_sesiones_sin_ejercicios(app_con_bd, programas_con_bd, reloj_fijo):
    socio = programas_con_bd["socios"][0]
    with app_con_bd.app_context():
        assert servicio.listar_programas(nuevo_id(reloj_fijo)) == []
        with transaccion() as cursor:
            programa = a_bytes(nuevo_id(reloj_fijo))
            insertar(
                cursor,
                "programas_entrenamiento",
                id=programa,
                socio_id=a_bytes(socio),
                version=3,
                creado_en=reloj_fijo.ahora(),
            )
        assert servicio.obtener_programa(socio, 3)["sesiones_planificadas"] == []
        with transaccion() as cursor:
            insertar(
                cursor,
                "sesiones_planificadas",
                id=a_bytes(nuevo_id(reloj_fijo)),
                programa_id=programa,
                posicion=1,
                nombre="Sesión",
            )
        assert servicio.obtener_programa(socio, 3)["sesiones_planificadas"][0]["ejercicios_planificados"] == []


@pytest.mark.bd
def test_las_claves_foraneas_y_las_posiciones_son_obligatorias_y_unicas(app_con_bd, programas_con_bd, reloj_fijo):
    datos = programas_con_bd
    inexistente = a_bytes(nuevo_id(reloj_fijo))
    casos = [
        ("programas_entrenamiento", {"socio_id": inexistente, "version": 1, "creado_en": reloj_fijo.ahora()}, 1452),
        (
            "programas_entrenamiento",
            {"socio_id": a_bytes(datos["socios"][0]), "version": 2, "creado_en": reloj_fijo.ahora()},
            1062,
        ),
        ("sesiones_planificadas", {"programa_id": inexistente, "posicion": 1, "nombre": "Sesión"}, 1452),
        ("sesiones_planificadas", {"programa_id": datos["programas"][0], "posicion": 1, "nombre": "Sesión"}, 1062),
        (
            "ejercicios_planificados",
            {"sesion_planificada_id": inexistente, "ejercicio_id": datos["fuerza"], "posicion": 3, "series": 1},
            1452,
        ),
        (
            "ejercicios_planificados",
            {"sesion_planificada_id": datos["sesiones"][0], "ejercicio_id": inexistente, "posicion": 3, "series": 1},
            1452,
        ),
        (
            "ejercicios_planificados",
            {
                "sesion_planificada_id": datos["sesiones"][0],
                "ejercicio_id": datos["fuerza"],
                "posicion": 1,
                "series": 1,
            },
            1062,
        ),
    ]
    with app_con_bd.app_context(), transaccion() as cursor:
        for tabla, columnas, codigo in casos:
            with pytest.raises(IntegrityError) as error:
                insertar(cursor, tabla, id=a_bytes(nuevo_id(reloj_fijo)), **columnas)
            assert error.value.errno == codigo


@pytest.mark.bd
def test_mysql_rechaza_medidas_fuera_de_rango(app_con_bd, programas_con_bd, reloj_fijo):
    from mysql.connector import DatabaseError

    with app_con_bd.app_context(), transaccion() as cursor:
        for medida, valor in (
            ("series", 0),
            ("series", -1),
            ("repeticiones_minimas", 0),
            ("repeticiones_maximas", -1),
            ("carga", -1),
            ("duracion", 0),
            ("duracion", -1),
            ("distancia", 0),
            ("distancia", -1),
        ):
            columnas = {
                "sesion_planificada_id": programas_con_bd["sesiones"][0],
                "ejercicio_id": programas_con_bd["fuerza"],
                "posicion": 3,
                "series": 1,
                medida: valor,
            }
            with pytest.raises(DatabaseError) as error:
                insertar(cursor, "ejercicios_planificados", id=a_bytes(nuevo_id(reloj_fijo)), **columnas)
            assert error.value.errno == 3819


@pytest.mark.bd
def test_reiniciar_demo_borra_programas_antes_de_los_socios(app_con_bd, programas_con_bd):
    app_con_bd.config["MODO_DEMO"] = True
    with app_con_bd.app_context():
        demo.reiniciar()
        with transaccion() as cursor:
            # #185 agrega siete programas y tres ejercicios a la semilla anterior.
            for tabla, cantidad in (
                ("ejercicios_planificados", 13 + 7),
                ("sesiones_planificadas", 7 + 7),
                ("programas_entrenamiento", 2 + 7),
                ("ejercicios", 7 + 3),
            ):
                cursor.execute(f"SELECT COUNT(*) AS cantidad FROM {tabla}")
                assert cursor.fetchone()["cantidad"] == cantidad
            for tabla, ids in (
                ("programas_entrenamiento", programas_con_bd["programas"]),
                ("sesiones_planificadas", programas_con_bd["sesiones"]),
            ):
                for identificador in ids:
                    cursor.execute(f"SELECT COUNT(*) AS cantidad FROM {tabla} WHERE id=%s", (identificador,))
                    assert cursor.fetchone()["cantidad"] == 0


@pytest.mark.parametrize("nombre", ["Semana 1 \u00b7 Fuerza", "Fuerza"])
def test_semana_tipo_conserva_nombre_sin_separador(nombre):
    programa = {
        "id": "programa",
        "version": 1,
        "duracion_semanas": 4,
        "sesiones_planificadas": [{"nombre": nombre, "semana": 1, "ejercicios_planificados": []}],
    }
    assert servicio._semana_tipo(programa)["sesiones"] == [{"nombre": "Fuerza", "ejercicios": []}]
