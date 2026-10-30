"""Equipo realmente usado, correcciones y ocupación por zona sobre MySQL."""

from datetime import timedelta

import pytest
from flask import g

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import a_bytes, desde_bytes, nuevo_id
from gimnasio.demo.servicio import reiniciar
from gimnasio.entrenamiento.repositorio import insertar_serie
from gimnasio.reglas.zonas_sede import ZONA_POR_EQUIPO
from gimnasio.visitas import repositorio, servicio

pytestmark = pytest.mark.bd


def test_zonas_de_la_semilla_y_ejercicio_hecho(app_con_bd, reloj_fijo):
    app_con_bd.config["MODO_DEMO"] = True
    with app_con_bd.app_context():
        reiniciar()
        with transaccion() as cursor:
            cursor.execute("SELECT DISTINCT equipo FROM ejercicios")
            assert {fila["equipo"] for fila in cursor.fetchall()} <= ZONA_POR_EQUIPO.keys()
            cursor.execute("SELECT id FROM usuarios WHERE rol='socio' AND es_demo=TRUE")
            socio = desde_bytes(cursor.fetchone()["id"])
            cursor.execute("SELECT id FROM usuarios WHERE rol='recepcion'")
            autor = desde_bytes(cursor.fetchone()["id"])
            sede = desde_bytes(repositorio.obtener_sede(cursor)["id"])
            repositorio.insertar_entrada(cursor, nuevo_id(reloj_fijo), socio, sede, autor, reloj_fijo.ahora())
            cursor.execute(
                """SELECT ep.id, ep.sesion_planificada_id FROM ejercicios_planificados ep
                   JOIN ejercicios e ON e.id=ep.ejercicio_id WHERE e.equipo='cinta' LIMIT 1"""
            )
            ejercicio = cursor.fetchone()
            sesion = nuevo_id(reloj_fijo)
            cursor.execute(
                "INSERT INTO sesiones_realizadas (id,socio_id,sesion_planificada_id,creada_en) VALUES (%s,%s,%s,%s)",
                (a_bytes(sesion), a_bytes(socio), ejercicio["sesion_planificada_id"], reloj_fijo.ahora()),
            )
            serie = nuevo_id(reloj_fijo)
            insertar_serie(
                cursor,
                serie,
                sesion,
                desde_bytes(ejercicio["id"]),
                socio,
                reloj_fijo.ahora(),
                duracion=60,
                distancia=100,
            )
        assert servicio.listar_visitas()[0]["zona"] == "cardio"
        cliente = app_con_bd.test_client()
        with cliente.session_transaction() as sesion_cliente:
            sesion_cliente["usuario_id"] = str(autor)
        anterior = cliente.get("/api/ocupacion")
        assert anterior.json["por_zona"]["cardio"] == 1
        with transaccion() as cursor:
            cursor.execute("SELECT id FROM ejercicios WHERE equipo='sin equipo'")
            hecho = desde_bytes(cursor.fetchone()["id"])
            correccion = nuevo_id(reloj_fijo)
            insertar_serie(
                cursor,
                correccion,
                sesion,
                desde_bytes(ejercicio["id"]),
                socio,
                reloj_fijo.ahora(),
                duracion=60,
                distancia=100,
                corrige_a=serie,
                motivo="Máquina ocupada",
                ejercicio_hecho_id=hecho,
            )
        nueva = cliente.get("/api/ocupacion", headers={"If-None-Match": anterior.headers["ETag"]})
        assert nueva.status_code == 200
        assert nueva.json["por_zona"]["funcional"] == 1
        assert servicio.listar_visitas()[0]["zona"] == "funcional"
        reloj_fijo.avanzar(timedelta(minutes=20))
        vigente = cliente.get("/api/ocupacion")
        assert vigente.json["por_zona"]["funcional"] == 1
        reloj_fijo.avanzar(timedelta(microseconds=1))
        vencida = cliente.get("/api/ocupacion", headers={"If-None-Match": vigente.headers["ETag"]})
        assert vencida.status_code == 200
        assert vencida.json["por_zona"]["en_la_sede"] == 1
        reloj_fijo.avanzar(-timedelta(minutes=20, microseconds=1))
        with cliente.session_transaction() as sesion_cliente:
            sesion_cliente["usuario_id"] = str(socio)
        # Este caso conserva el contexto de app entre solicitudes de distintos roles.
        g.pop("usuario", None)
        assert "por_zona" not in cliente.get("/api/ocupacion").json
        with transaccion() as cursor:
            insertar_serie(
                cursor,
                nuevo_id(reloj_fijo),
                sesion,
                desde_bytes(ejercicio["id"]),
                socio,
                reloj_fijo.ahora(),
                duracion=60,
                distancia=100,
                corrige_a=correccion,
                motivo="Serie anulada",
                anulada=True,
            )
        assert servicio.listar_visitas()[0]["zona"] == "en_la_sede"
