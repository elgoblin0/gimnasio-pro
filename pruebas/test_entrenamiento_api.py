"""Propuesta real, programa intacto y alcance por rol/asignación sobre MySQL."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import a_bytes, nuevo_id
from gimnasio.entrenamiento import repositorio
from gimnasio.permisos.servicio import crear_usuario

pytestmark = pytest.mark.bd


@pytest.fixture
def entrenamiento_api(app_con_bd, reloj_fijo):
    datos = SimpleNamespace(app=app_con_bd, reloj=reloj_fijo, usuarios={}, sesiones=[], ejercicios=[])
    with datos.app.app_context(), transaccion() as cursor:
        datos.sede = nuevo_id(reloj_fijo)
        cursor.execute(
            "INSERT INTO sedes (id,nombre,aforo_maximo,actualizada_en) VALUES (%s,'Sede ficticia',60,%s)",
            (a_bytes(datos.sede), reloj_fijo.ahora()),
        )
        for indice, (nombre, rol) in enumerate(
            (
                ("socio", "socio"),
                ("ajeno", "socio"),
                ("entrenador", "entrenador"),
                ("otro", "entrenador"),
                ("recepcion", "recepcion"),
                ("administracion", "administracion"),
            )
        ):
            datos.usuarios[nombre] = crear_usuario(
                cursor, {"nombre": nombre, "apellido": "Ficticio", "cedula": str(9900600 + indice)}, rol
            )
        datos.asignacion = nuevo_id(reloj_fijo)
        cursor.execute(
            "INSERT INTO asignaciones_entrenador (id,socio_id,entrenador_id,desde) VALUES (%s,%s,%s,%s)",
            (
                a_bytes(datos.asignacion),
                a_bytes(datos.usuarios["socio"]),
                a_bytes(datos.usuarios["entrenador"]),
                reloj_fijo.ahora(),
            ),
        )
        datos.programa = nuevo_id(reloj_fijo)
        cursor.execute(
            "INSERT INTO programas_entrenamiento (id,socio_id,version,creado_en) VALUES (%s,%s,1,%s)",
            (a_bytes(datos.programa), a_bytes(datos.usuarios["socio"]), reloj_fijo.ahora()),
        )
        catalogo = nuevo_id(reloj_fijo)
        cursor.execute(
            "INSERT INTO ejercicios (id,nombre,medidas_aplicables,actualizada_en) "
            "VALUES (%s,'Sentadilla ficticia','[\"repeticiones\",\"carga\"]',%s)",
            (a_bytes(catalogo), reloj_fijo.ahora()),
        )
        for posicion in (1, 2):
            sesion = nuevo_id(reloj_fijo)
            datos.sesiones.append(sesion)
            cursor.execute(
                "INSERT INTO sesiones_planificadas (id,programa_id,posicion,nombre) "
                "VALUES (%s,%s,%s,'Sesión ficticia')",
                (a_bytes(sesion), a_bytes(datos.programa), posicion),
            )
            ejercicios = []
            for orden in (1, 2):
                ejercicio = nuevo_id(reloj_fijo)
                ejercicios.append(ejercicio)
                cursor.execute(
                    "INSERT INTO ejercicios_planificados "
                    "(id,sesion_planificada_id,ejercicio_id,posicion,series,repeticiones,carga) "
                    "VALUES (%s,%s,%s,%s,2,10,20.50)",
                    (a_bytes(ejercicio), a_bytes(sesion), a_bytes(catalogo), orden),
                )
            datos.ejercicios.append(ejercicios)

    def cliente(nombre="socio"):
        cliente = datos.app.test_client()
        with cliente.session_transaction() as sesion:
            sesion["usuario_id"] = str(datos.usuarios[nombre])
        return cliente

    datos.cliente = cliente
    return datos


def registrar(datos, sesion, ejercicio, cantidad=1):
    with datos.app.app_context(), transaccion() as cursor:
        realizada = nuevo_id(datos.reloj)
        repositorio.insertar_sesion(
            cursor, realizada, datos.usuarios["socio"], datos.sesiones[sesion], datos.reloj.ahora()
        )
        for _ in range(cantidad):
            repositorio.insertar_serie(
                cursor,
                nuevo_id(datos.reloj),
                realizada,
                datos.ejercicios[sesion][ejercicio],
                datos.usuarios["socio"],
                datos.reloj.ahora(),
                repeticiones=8,
                carga=Decimal("15.25"),
            )


def test_propuesta_conserva_plan_y_distingue_posiciones_del_mismo_ejercicio(entrenamiento_api):
    datos = entrenamiento_api
    antes = datos.cliente().get("/api/entrenamiento/propuesta")
    assert antes.status_code == 200
    antes = antes.json
    assert antes["sesion_planificada"]["id"] == str(datos.sesiones[0])
    assert [e["pendiente"] for e in antes["ejercicios"]] == [2, 2]
    registrar(datos, 0, 0)
    despues = datos.cliente().get("/api/entrenamiento/propuesta").json
    assert [e["objetivos"] for e in despues["ejercicios"]] == [e["objetivos"] for e in antes["ejercicios"]]
    assert [e["realizado"] for e in despues["ejercicios"]] == [1, 0]
    assert [e["pendiente"] for e in despues["ejercicios"]] == [1, 2]
    assert despues["ejercicios"][0]["objetivos"]["carga"] == "20.50"
    assert despues["version_reglas"] == "1.0.0"
    assert "sin ajustes" in despues["explicacion"][-1]["datos"]["explicacion"]
    assert despues == datos.cliente().get("/api/entrenamiento/propuesta").json
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT COUNT(*) AS cantidad FROM series_realizadas")
        assert cursor.fetchone()["cantidad"] == 1
        cursor.execute("SELECT carga FROM ejercicios_planificados ORDER BY id")
        assert all(fila["carga"] == Decimal("20.50") for fila in cursor.fetchall())
        cursor.execute("SELECT COUNT(*) AS cantidad FROM consentimientos")
        assert cursor.fetchone()["cantidad"] == 0


def test_secuencia_terminada_no_reinicia_y_sin_programa_no_inventa(entrenamiento_api):
    datos = entrenamiento_api
    for sesion in (0, 1):
        for ejercicio in (0, 1):
            registrar(datos, sesion, ejercicio, 2)
        propuesta = datos.cliente().get("/api/entrenamiento/propuesta").json
        assert (
            propuesta["sesion_planificada"] is None
            if sesion == 1
            else propuesta["sesion_planificada"]["id"] == str(datos.sesiones[1])
        )
    assert propuesta["explicacion"][0]["regla"] == "secuencia_realizada"
    sin_programa = datos.cliente("ajeno").get("/api/entrenamiento/propuesta").json
    assert sin_programa["sesion_planificada"] is None
    assert sin_programa["explicacion"][0]["regla"] == "sin_programa"


@pytest.mark.parametrize("rol", ["recepcion", "administracion", "entrenador"])
def test_propuesta_propia_rechaza_otros_roles(entrenamiento_api, rol):
    assert entrenamiento_api.cliente(rol).get("/api/entrenamiento/propuesta").status_code == 403


def test_entrenador_solo_ve_asignacion_vigente_y_recursos_existentes(entrenamiento_api):
    datos = entrenamiento_api
    ruta = f"/api/entrenamiento/socios/{datos.usuarios['socio']}/propuesta"
    assert datos.cliente("entrenador").get(ruta).status_code == 200
    for nombre in ("otro", "socio", "recepcion", "administracion"):
        assert datos.cliente(nombre).get(ruta).status_code == 403
    assert (
        datos.cliente("entrenador").get(f"/api/entrenamiento/socios/{nuevo_id(datos.reloj)}/propuesta").status_code
        == 404
    )
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute(
            "UPDATE asignaciones_entrenador SET hasta=%s WHERE id=%s", (datos.reloj.ahora(), a_bytes(datos.asignacion))
        )
    assert datos.cliente("entrenador").get(ruta).status_code == 403


def test_visita_sin_series_no_cambia_propuesta(entrenamiento_api):
    from gimnasio.visitas import repositorio as visitas

    datos = entrenamiento_api
    antes = datos.cliente().get("/api/entrenamiento/propuesta").json
    with datos.app.app_context(), transaccion() as cursor:
        entrada = nuevo_id(datos.reloj)
        visitas.insertar_entrada(
            cursor, entrada, datos.usuarios["socio"], datos.sede, datos.usuarios["recepcion"], datos.reloj.ahora()
        )
        visitas.insertar_salida(
            cursor, nuevo_id(datos.reloj), entrada, datos.usuarios["recepcion"], datos.reloj.ahora()
        )
    assert datos.cliente().get("/api/entrenamiento/propuesta").json == antes


def test_version_nueva_con_cardio_no_mezcla_hechos_de_version_anterior(entrenamiento_api):
    datos = entrenamiento_api
    registrar(datos, 0, 0)
    with datos.app.app_context(), transaccion() as cursor:
        programa, sesion, ejercicio, planificado = (nuevo_id(datos.reloj) for _ in range(4))
        cursor.execute(
            "INSERT INTO programas_entrenamiento (id,socio_id,version,creado_en) VALUES (%s,%s,2,%s)",
            (a_bytes(programa), a_bytes(datos.usuarios["socio"]), datos.reloj.ahora()),
        )
        cursor.execute(
            "INSERT INTO sesiones_planificadas (id,programa_id,posicion,nombre) VALUES (%s,%s,1,'Cardio ficticio')",
            (a_bytes(sesion), a_bytes(programa)),
        )
        cursor.execute(
            "INSERT INTO ejercicios (id,nombre,medidas_aplicables,actualizada_en) "
            "VALUES (%s,'Carrera ficticia','[\"duracion\",\"distancia\"]',%s)",
            (a_bytes(ejercicio), datos.reloj.ahora()),
        )
        cursor.execute(
            "INSERT INTO ejercicios_planificados "
            "(id,sesion_planificada_id,ejercicio_id,posicion,series,duracion,distancia) "
            "VALUES (%s,%s,%s,1,1,120,1500.25)",
            (a_bytes(planificado), a_bytes(sesion), a_bytes(ejercicio)),
        )
    propuesta = datos.cliente().get("/api/entrenamiento/propuesta").json
    assert propuesta["sesion_planificada"]["id"] == str(sesion)
    ejercicio = propuesta["ejercicios"][0]
    assert ejercicio["realizado"] == 0
    assert ejercicio["pendiente"] == 1
    assert ejercicio["objetivos"] == {
        "series": 1,
        "repeticiones": None,
        "carga": None,
        "duracion": 120,
        "distancia": "1500.25",
    }
