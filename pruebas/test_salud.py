"""Restricciones ficticias, bajas por inserción, privacidad y aviso transaccional."""

import json

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.ids import desde_bytes, nuevo_id
from gimnasio.demo.servicio import reiniciar
from gimnasio.entrenamiento.servicio import (
    consultar_propuesta,
    consultar_sesion,
    crear_sesion,
    registrar_dolor,
    registrar_serie,
)
from gimnasio.salud.servicio import restricciones_vigentes


@pytest.mark.bd
@pytest.mark.parametrize("con_alternativa", [False, True])
def test_iniciar_sesion_restringida_deja_aviso_sin_exponer_descripcion(app_con_bd, con_alternativa):
    app_con_bd.config["MODO_DEMO"] = True
    with app_con_bd.app_context():
        reiniciar()
        with transaccion() as cursor:
            cursor.execute("SELECT * FROM restricciones_salud WHERE levanta_a IS NULL")
            restriccion = cursor.fetchone()
            if not con_alternativa:
                cursor.execute(
                    """INSERT INTO restricciones_salud
                       (id,socio_id,patron_movimiento,descripcion,registrada_en,autor_id)
                       VALUES (%s,%s,'sentadilla',%s,%s,%s)""",
                    (
                        nuevo_id().bytes,
                        restriccion["socio_id"],
                        restriccion["descripcion"],
                        restriccion["registrada_en"],
                        restriccion["autor_id"],
                    ),
                )
        socio = {"id": str(desde_bytes(restriccion["socio_id"])), "rol": "socio"}
        propuesta = consultar_propuesta(socio["id"], socio)
        assert "restriccion_salud" in propuesta["frenos"]
        assert restriccion["descripcion"] not in json.dumps(propuesta, ensure_ascii=False, default=str)
        identificador = str(nuevo_id())
        datos = {"id": identificador, "sesion_planificada_id": propuesta["sesion_planificada"]["id"]}
        crear_sesion(datos, socio)
        crear_sesion(datos, socio)
        sesion = consultar_sesion(identificador, socio)
        assert restriccion["descripcion"] not in json.dumps(sesion, ensure_ascii=False, default=str)
        with transaccion() as cursor:
            cursor.execute(
                "SELECT * FROM avisos_entrenador WHERE freno='restriccion_salud' AND socio_id=%s",
                (restriccion["socio_id"],),
            )
            avisos = cursor.fetchall()
        assert len(avisos) == 1
        assert avisos[0]["entrenador_id"] == restriccion["autor_id"]
        assert restriccion["descripcion"] in avisos[0]["explicacion"]
        entrenador = {"id": str(desde_bytes(restriccion["autor_id"])), "rol": "entrenador"}
        assert consultar_propuesta(socio["id"], entrenador)["frenos"] == propuesta["frenos"]
        with pytest.raises(ErrorDeDominio):
            consultar_propuesta(socio["id"], {"id": str(nuevo_id()), "rol": "entrenador"})
        afectado = next(
            e for e in sesion["ejercicios"] if any(r["regla"] == "restriccion_salud" for r in e["explicacion"])
        )
        assert bool(afectado["objetivos"]["series"]) == con_alternativa
        if con_alternativa:
            assert sesion["sustituciones"][afectado["id"]]["sustitucion"]["motivo"] == "restriccion_salud"
        with pytest.raises(ErrorDeDominio):
            registrar_serie(
                identificador,
                {
                    "id": str(nuevo_id()),
                    "ejercicio_planificado_id": afectado["id"],
                    "ejercicio_hecho_id": afectado["ejercicio_id"],
                    "repeticiones": 8,
                    "carga": "20.50",
                },
                socio,
            )
        for rol in ("recepcion", "administracion"):
            with pytest.raises(ErrorDeDominio):
                consultar_propuesta(socio["id"], {"id": socio["id"], "rol": rol})
        if con_alternativa:
            registrar_dolor(
                identificador,
                {
                    "id": str(nuevo_id()),
                    "ejercicio_planificado_id": afectado["id"],
                    "zonas": ["cuadriceps"],
                },
                socio,
            )
            assert restriccion["descripcion"] not in json.dumps(
                consultar_sesion(identificador, socio),
                ensure_ascii=False,
                default=str,
            )
            with transaccion() as cursor:
                cursor.execute(
                    "SELECT explicacion FROM avisos_entrenador WHERE freno='restriccion_salud' AND socio_id=%s",
                    (restriccion["socio_id"],),
                )
                assert all(restriccion["descripcion"] in f["explicacion"] for f in cursor.fetchall())


@pytest.mark.bd
def test_baja_por_insercion_no_borra_la_restriccion(app_con_bd):
    app_con_bd.config["MODO_DEMO"] = True
    with app_con_bd.app_context():
        reiniciar()
        with transaccion() as cursor:
            cursor.execute("SELECT * FROM restricciones_salud LIMIT 1")
            original = cursor.fetchone()
            cursor.execute(
                """INSERT INTO restricciones_salud
                   (id,socio_id,zona,descripcion,registrada_en,autor_id,levanta_a)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (
                    nuevo_id().bytes,
                    original["socio_id"],
                    original["zona"],
                    "Baja ficticia",
                    original["registrada_en"],
                    original["autor_id"],
                    original["id"],
                ),
            )
        assert restricciones_vigentes(desde_bytes(original["socio_id"])) == ()
        reiniciar()
        assert len(restricciones_vigentes(desde_bytes(original["socio_id"]))) == 1
