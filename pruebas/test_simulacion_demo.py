"""Integración transaccional de visitas simuladas sobre MySQL."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import desde_bytes, nuevo_id
from gimnasio.demo import servicio
from gimnasio.visitas.servicio import (
    consultar_ocupacion,
    consultar_tarjeta,
    listar_visitas,
    registrar_entrada,
    registrar_entrada_en_transaccion,
)

pytestmark = pytest.mark.bd


def preparar(app, reloj):
    app.config["MODO_DEMO"] = True
    reloj.fijar(datetime(2026, 10, 27, 9, tzinfo=UTC))
    with app.app_context():
        servicio.reiniciar()
    reloj.fijar(datetime(2026, 10, 27, 22, tzinfo=UTC))  # 19:00 local.


def hechos(app):
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT (SELECT COUNT(*) FROM entradas) + (SELECT COUNT(*) FROM salidas) AS cantidad")
        return cursor.fetchone()["cantidad"]


def test_reloj_fijo_no_duplica_y_avanza(app_con_bd, reloj_fijo):
    preparar(app_con_bd, reloj_fijo)
    anteriores = hechos(app_con_bd)
    with app_con_bd.app_context():
        servicio.poner_al_dia()
        ocupacion = consultar_ocupacion()
        visitas = listar_visitas()
    assert hechos(app_con_bd) > anteriores
    cantidad = hechos(app_con_bd)
    with app_con_bd.app_context():
        servicio.poner_al_dia()
    assert hechos(app_con_bd) == cantidad
    assert 0 < ocupacion["ocupacion_registrada"] <= 48
    assert visitas and all(visita["simulada"] for visita in visitas)
    reloj_fijo.avanzar(timedelta(minutes=30))
    with app_con_bd.app_context():
        servicio.poner_al_dia()
        assert consultar_ocupacion()["ocupacion_registrada"] <= 48
    assert hechos(app_con_bd) > cantidad


def test_fuera_de_demo_no_consulta_la_base(app_con_bd, reloj_fijo):
    preparar(app_con_bd, reloj_fijo)
    anteriores = hechos(app_con_bd)
    app_con_bd.config["MODO_DEMO"] = False
    with app_con_bd.app_context():
        servicio.poner_al_dia()
    assert hechos(app_con_bd) == anteriores


def test_dos_llamadas_simultaneas_equivalen_a_una(app_con_bd, reloj_fijo):
    preparar(app_con_bd, reloj_fijo)
    with app_con_bd.app_context():
        servicio.poner_al_dia()
    esperados = hechos(app_con_bd)
    preparar(app_con_bd, reloj_fijo)
    barrera = Barrier(2)

    def ejecutar():
        with app_con_bd.app_context():
            barrera.wait(timeout=10)
            servicio.poner_al_dia()

    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        futuros = [ejecutor.submit(ejecutar) for _ in range(2)]
        for futuro in futuros:
            futuro.result(timeout=30)
    assert hechos(app_con_bd) == esperados


def test_error_revierte_hechos_y_marca(app_con_bd, reloj_fijo, monkeypatch):
    preparar(app_con_bd, reloj_fijo)
    anteriores = hechos(app_con_bd)

    def fallar(*argumentos):
        raise RuntimeError("fallo al avanzar")

    monkeypatch.setattr(servicio.repositorio, "avanzar_simulacion", fallar)
    with app_con_bd.app_context(), pytest.raises(RuntimeError, match="fallo al avanzar"):
        servicio.poner_al_dia()
    assert hechos(app_con_bd) == anteriores


def test_simulados_identificados_y_entrada_real_disponible(app_con_bd, reloj_fijo):
    preparar(app_con_bd, reloj_fijo)
    with app_con_bd.app_context():
        ocupacion = consultar_ocupacion()
        simulada = listar_visitas()[0]
        assert consultar_tarjeta(simulada["socio_id"])["socio"]["simulada"]
        with transaccion() as cursor:
            cursor.execute("SELECT id FROM usuarios WHERE es_demo=TRUE AND rol='socio' ORDER BY id LIMIT 1")
            socio = str(desde_bytes(cursor.fetchone()["id"]))
            cursor.execute("SELECT id FROM usuarios WHERE es_demo=TRUE AND rol='recepcion'")
            autor = str(desde_bytes(cursor.fetchone()["id"]))
            cursor.execute("SELECT COUNT(*) AS cantidad FROM personas WHERE simulada=TRUE")
            assert cursor.fetchone()["cantidad"] == 60
            cursor.execute(
                "SELECT u.es_demo, u.rol, p.nombre, p.apellido FROM usuarios u "
                "JOIN personas p ON p.id=u.persona_id WHERE p.correo='simulacion@demo.gimnasio.invalid'"
            )
            sistema = cursor.fetchone()
            assert not sistema["es_demo"] and sistema["rol"] == "recepcion"
            assert sistema["nombre"] + " " + sistema["apellido"] == "Simulación demo"
            # Completar exactamente el 80 % antes de probar la entrada real.
            presentes = {visita["socio_id"] for visita in listar_visitas()}
            for fila in servicio.repositorio.listar_simulados(cursor):
                identificador = desde_bytes(fila["id"])
                if len(presentes) == 48:
                    break
                if str(identificador) not in presentes:
                    registrar_entrada_en_transaccion(
                        cursor,
                        {
                            "id": nuevo_id(),
                            "socio_id": identificador,
                            "sede_id": servicio.desde_texto(ocupacion["sede_id"]),
                        },
                        {"id": autor},
                        reloj_fijo.ahora(),
                    )
                    presentes.add(str(identificador))
        assert consultar_ocupacion()["ocupacion_registrada"] == 48
        registrar_entrada({"id": str(nuevo_id()), "socio_id": socio, "sede_id": ocupacion["sede_id"]}, {"id": autor})
        assert consultar_ocupacion()["ocupacion_registrada"] == 49


def test_atraso_se_limita_a_veinticuatro_horas(app_con_bd, reloj_fijo):
    preparar(app_con_bd, reloj_fijo)
    reloj_fijo.avanzar(timedelta(days=4))
    limite = (reloj_fijo.ahora() - timedelta(hours=24)).replace(tzinfo=None)
    with app_con_bd.app_context():
        servicio.poner_al_dia()
        with transaccion() as cursor:
            cursor.execute(
                "SELECT MIN(e.registrada_en) AS primera FROM entradas e JOIN usuarios u ON u.id=e.socio_id "
                "JOIN personas p ON p.id=u.persona_id WHERE p.simulada=TRUE"
            )
            assert cursor.fetchone()["primera"] > limite
