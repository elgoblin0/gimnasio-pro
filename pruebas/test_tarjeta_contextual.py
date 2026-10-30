"""Tarjeta de recepción con visitas y membresía, sin datos sensibles."""

from datetime import timedelta

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import a_bytes, nuevo_id
from gimnasio.comun.reloj import fecha_local
from gimnasio.socios.servicio import consultar_membresia, membresia_para_tarjeta
from gimnasio.visitas import repositorio
from pruebas import test_visitas_api

pytestmark = pytest.mark.bd


@pytest.fixture
def visitas_api(app_con_bd, reloj_fijo):
    return test_visitas_api.visitas_api.__wrapped__(app_con_bd, reloj_fijo)


@pytest.mark.parametrize("estado", ["abierta", "cerrada", "sin_visitas"])
def test_tarjeta_con_historial(visitas_api, estado):
    datos = visitas_api
    socio = datos.socios[0]
    ahora = datos.reloj.ahora()
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute(
            "INSERT INTO restricciones_salud (id,socio_id,zona,descripcion,registrada_en,autor_id) "
            "VALUES (%s,%s,'rodillas','Restricción ficticia confidencial',%s,%s)",
            (a_bytes(nuevo_id(datos.reloj)), a_bytes(socio), ahora, a_bytes(datos.usuarios["entrenador"])),
        )
        chequeo = nuevo_id(datos.reloj)
        cursor.execute(
            "INSERT INTO chequeos_dia (id,socio_id,fecha_local,sueno,energia,registrado_en) VALUES (%s,%s,%s,3,3,%s)",
            (a_bytes(chequeo), a_bytes(socio), fecha_local(ahora), ahora),
        )
        cursor.execute(
            "INSERT INTO dolores_reportados (id,socio_id,zona,origen,chequeo_id,registrado_en) "
            "VALUES (%s,%s,'rodillas','chequeo',%s,%s)",
            (a_bytes(nuevo_id(datos.reloj)), a_bytes(socio), a_bytes(chequeo), ahora),
        )
        if estado != "sin_visitas":
            entrada = nuevo_id(datos.reloj)
            repositorio.insertar_entrada(
                cursor, entrada, socio, datos.sede, datos.usuarios["recepcion"], ahora - timedelta(hours=2)
            )
            if estado == "cerrada":
                repositorio.insertar_salida(
                    cursor, nuevo_id(datos.reloj), entrada, datos.usuarios["recepcion"], ahora - timedelta(hours=1)
                )
    respuesta = datos.cliente().get(f"/api/socios/{socio}/tarjeta")
    assert respuesta.status_code == 200
    tarjeta = respuesta.json
    for clave in ("salud", "restricciones", "dolores", "rodillas", "confidencial", "pagos", "incorporacion", "riesgo"):
        assert clave not in respuesta.get_data(as_text=True)
    assert set(tarjeta) == {
        "socio",
        "membresia",
        "visita_abierta",
        "ultima_visita",
        "visitas_ultimas_4_semanas",
        "permanencia_habitual",
    }
    assert set(tarjeta["socio"]) == {"id", "nombre", "apellido", "cedula", "simulada"}
    assert tarjeta["socio"]["simulada"] is False
    assert tarjeta["socio"]["cedula"] == "9.900.503"
    assert tarjeta["membresia"] == {"vigente": True, "hasta": "2026-10-27", "dias_restantes": 0}
    assert (tarjeta["visita_abierta"] is not None) == (estado == "abierta")
    assert (tarjeta["ultima_visita"] is not None) == (estado == "cerrada")
    assert tarjeta["visitas_ultimas_4_semanas"] == (estado != "sin_visitas")
    assert tarjeta["permanencia_habitual"]["observaciones"] == (estado == "cerrada")
    if estado == "abierta":
        assert tarjeta["visita_abierta"]["minutos"] == 120


@pytest.mark.parametrize("rol,estado", [("socio", 403), ("entrenador", 403), ("administracion", 200)])
def test_permiso_tarjeta(visitas_api, rol, estado):
    assert visitas_api.cliente(rol).get(f"/api/socios/{visitas_api.socios[0]}/tarjeta").status_code == estado


def test_membresia_vencida_y_futura(visitas_api):
    datos = visitas_api
    socio = datos.socios[0]
    with datos.app.app_context():
        with transaccion() as cursor:
            for desde, hasta in (("2026-09-01", "2026-09-30"), ("2026-11-01", "2026-11-30")):
                cursor.execute(
                    "INSERT INTO membresias (id,socio_id,desde,hasta,actualizada_en) VALUES (%s,%s,%s,%s,%s)",
                    (a_bytes(nuevo_id(datos.reloj)), a_bytes(socio), desde, hasta, datos.reloj.ahora()),
                )
        datos.reloj.avanzar(timedelta(days=2))
        dia = fecha_local(datos.reloj.ahora())
        assert membresia_para_tarjeta(socio, dia) == {
            "vigente": False,
            "hasta": "2026-10-27",
            "dias_restantes": -2,
        }
        assert consultar_membresia(socio, dia) is None
        assert membresia_para_tarjeta(socio, dia - timedelta(days=90)) is None
        assert membresia_para_tarjeta(datos.socios[1], dia - timedelta(days=3)) is None


def test_tarjeta_sin_sesion(reloj_fijo):
    from gimnasio import crear_app

    cliente = crear_app({"ENTORNO": "prueba"}).test_client()
    assert cliente.get(f"/api/socios/{nuevo_id(reloj_fijo)}/tarjeta").status_code == 401


@pytest.mark.parametrize("activo", [True, False])
def test_membresia_ultimo_dia_y_socio_activo(visitas_api, activo):
    datos = visitas_api
    with datos.app.app_context():
        with transaccion() as cursor:
            cursor.execute("UPDATE usuarios SET activo = %s WHERE id = %s", (activo, a_bytes(datos.socios[0])))
        tarjeta = membresia_para_tarjeta(datos.socios[0], fecha_local(datos.reloj.ahora()))
        assert tarjeta == {"vigente": activo, "hasta": "2026-10-27", "dias_restantes": 0}


def test_tarjeta_fecha_local_de_sede(visitas_api):
    from datetime import UTC, datetime

    datos = visitas_api
    datos.reloj.fijar(datetime(2026, 10, 28, 2, 59, tzinfo=UTC))
    ruta = f"/api/socios/{datos.socios[0]}/tarjeta"
    assert datos.cliente().get(ruta).json["membresia"]["dias_restantes"] == 0
    datos.reloj.avanzar(timedelta(minutes=1))
    assert datos.cliente().get(ruta).json["membresia"]["dias_restantes"] == -1


def test_historial_excluye_anuladas_y_cuenta_cuatro_semanas(visitas_api):
    datos = visitas_api
    ahora = datos.reloj.ahora()
    with datos.app.app_context(), transaccion() as cursor:
        for dias in (1, 28, 29):
            entrada = nuevo_id(datos.reloj)
            momento = ahora - timedelta(days=dias)
            repositorio.insertar_entrada(
                cursor, entrada, datos.socios[0], datos.sede, datos.usuarios["recepcion"], momento
            )
            repositorio.insertar_salida(
                cursor, nuevo_id(datos.reloj), entrada, datos.usuarios["recepcion"], momento + timedelta(minutes=60)
            )
        repositorio.insertar_entrada(
            cursor,
            nuevo_id(datos.reloj),
            datos.socios[0],
            datos.sede,
            datos.usuarios["recepcion"],
            ahora - timedelta(days=29, minutes=-1),
            corrige_a=entrada,
            motivo="Anulación ficticia",
            anulada=True,
        )
    tarjeta = datos.cliente().get(f"/api/socios/{datos.socios[0]}/tarjeta").json
    assert tarjeta["visitas_ultimas_4_semanas"] == 2
    assert tarjeta["permanencia_habitual"]["observaciones"] == 2
    assert tarjeta["ultima_visita"]["desde"] == (ahora - timedelta(days=1)).isoformat()
