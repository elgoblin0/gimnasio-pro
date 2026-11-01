"""Prevision desde la semilla ficticia y el permiso de ocupacion."""

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import desde_bytes

pytestmark = pytest.mark.bd


@pytest.fixture
def app_horarios(app_con_bd, sembrar_demo):
    app_con_bd.config["MODO_DEMO"] = True
    sembrar_demo(app_con_bd)
    return app_con_bd


@pytest.mark.parametrize("rol", ["socio", "recepcion", "entrenador", "administracion"])
def test_prevision_martes_desde_semilla(app_horarios, rol):
    with app_horarios.app_context(), transaccion() as cursor:
        cursor.execute("SELECT id FROM usuarios WHERE rol = %s AND es_demo = TRUE ORDER BY id LIMIT 1", (rol,))
        usuario_id = str(desde_bytes(cursor.fetchone()["id"]))
    cliente = app_horarios.test_client()
    with cliente.session_transaction() as sesion:
        sesion["usuario_id"] = usuario_id
    respuesta = cliente.get("/api/mejores-horarios")
    assert respuesta.status_code == 200
    for dia in respuesta.json.values():
        assert set(dia) == {"franjas", "cerrado", "datos_insuficientes"}
        assert len(dia["franjas"]) == 3
        assert not dia["cerrado"] and not dia["datos_insuficientes"]
        for franja in dia["franjas"]:
            assert set(franja) == {"desde", "hasta", "prevision", "observaciones"}
            assert franja["desde"] not in {"18:00", "19:00"}
            assert franja["observaciones"] >= 4
    assert all(f["hasta"] > "09:00" for f in respuesta.json["hoy"]["franjas"])
