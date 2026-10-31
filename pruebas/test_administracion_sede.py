"""Configuración de sede, historial y entradas con el aforo vigente."""

from datetime import timedelta
from uuid import uuid4

import pytest

from gimnasio.administracion import servicio
from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.ids import desde_bytes, nuevo_id
from gimnasio.demo import servicio as demo
from gimnasio.visitas import servicio as visitas


@pytest.fixture
def sede(app_con_bd):
    app_con_bd.config["MODO_DEMO"] = True
    with app_con_bd.app_context():
        demo.reiniciar()
    cliente = app_con_bd.test_client()
    ingreso = cliente.post("/api/sesion/demo/administracion", headers={"X-Gimnasio": "1"})
    return app_con_bd, cliente, ingreso.get_json()["usuario"]


def cambiar(cliente, aforo=60, *, clave=None, **datos):
    return cliente.put(
        "/api/administracion/sede",
        json={
            "aforo_maximo": aforo,
            "horario": {"1": [["07:00", "21:00"]]},
            "motivo": "Cambio ficticio",
            **datos,
        },
        headers={"X-Gimnasio": "1", "Idempotency-Key": clave or str(uuid4())},
    )


@pytest.mark.bd
def test_historial_idempotente_y_correccion(sede):
    app, cliente, usuario = sede
    inicial = cliente.get("/api/administracion/sede").get_json()
    assert inicial["aforo_maximo"] == 60
    assert inicial["historial"] == []
    clave = str(uuid4())
    primera = cambiar(cliente, 50, clave=clave)
    assert primera.status_code == 200
    assert cambiar(cliente, 50, clave=clave).data == primera.data
    assert cambiar(cliente, 51, clave=clave).status_code == 422
    anterior = primera.get_json()["historial"][0]
    assert anterior["autor_id"] == usuario["id"]
    assert anterior["autor"]
    assert anterior["motivo"] == "Cambio ficticio"
    assert anterior["registrado_en"].endswith("+00:00")
    segunda = cambiar(cliente, 70, motivo="Corrección ficticia").get_json()
    assert segunda["historial"][1] == anterior
    assert len(segunda["historial"]) == 2
    assert cliente.get("/api/administracion/sede").get_json() == segunda
    cliente.post("/api/sesion/demo/recepcion", headers={"X-Gimnasio": "1"})
    assert cliente.get("/api/ocupacion").get_json()["aforo_maximo"] == 70
    with app.app_context():
        demo.reiniciar()


@pytest.mark.bd
@pytest.mark.parametrize("rol", ["socio", "recepcion", "entrenador"])
def test_solo_administracion(sede, rol):
    _, cliente, _ = sede
    cliente.post(f"/api/sesion/demo/{rol}", headers={"X-Gimnasio": "1"})
    assert cliente.get("/api/administracion/sede").status_code == 403
    assert cambiar(cliente).status_code == 403


@pytest.mark.parametrize(
    "datos",
    [
        {"motivo": ""},
        {"motivo": "  "},
        {"motivo": None},
        {"motivo": "x" * 501},
        {"aforo_maximo": True},
        {"aforo_maximo": 0},
        {"aforo_maximo": -1},
        {"aforo_maximo": 1.5},
        {"aforo_maximo": "60"},
        {"aforo_maximo": 65536},
        {"horario": None},
        {"horario": {"8": []}},
        {"horario": {"1": [["22:00", "06:00"]]}},
        {"horario": {"1": [["06:00", "25:00"]]}},
        {"horario": {"1": [["0٦:00", "21:00"]]}},
        {"horario": {"1": [["06:0٠", "21:00"]]}},
        {"horario": {"1": [["06:00", "2１:00"]]}},
        {"horario": {"1": [["06:00", "21:0１"]]}},
        {"horario": {"1": [["06:00", "12:00"], ["11:00", "15:00"]]}},
    ],
)
def test_validacion(datos):
    with pytest.raises(ErrorDeDominio) as error:
        servicio.validar_cambio({"aforo_maximo": 60, "horario": {}, "motivo": "Prueba", **datos})
    assert error.value.estado_http == 422


@pytest.mark.bd
def test_sin_motivo(sede):
    _, cliente, _ = sede
    assert cambiar(cliente, motivo="").status_code == 422
    assert cliente.get("/api/administracion/sede").get_json()["historial"] == []


@pytest.mark.bd
def test_hora_con_digitos_no_ascii_no_modifica_sede(sede):
    _, cliente, _ = sede
    anterior = cliente.get("/api/administracion/sede").get_json()
    respuesta = cambiar(cliente, 50, horario={"1": [["0٦:00", "21:00"]]})
    assert respuesta.status_code == 422
    assert cliente.get("/api/administracion/sede").get_json() == anterior


@pytest.mark.bd
def test_bajar_y_subir_conserva_visitas_y_permanencia(sede):
    app, cliente, _ = sede
    app.config["MODO_DEMO"] = False
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT id FROM sedes LIMIT 1")
        sede_id = desde_bytes(cursor.fetchone()["id"])
        cursor.execute("SELECT id FROM usuarios WHERE rol='recepcion' LIMIT 1")
        autor = {"id": str(desde_bytes(cursor.fetchone()["id"]))}
        cursor.execute("SELECT id FROM usuarios WHERE rol='socio' AND activo=TRUE ORDER BY id LIMIT 3")
        socios = [desde_bytes(fila["id"]) for fila in cursor.fetchall()]
    with app.app_context():
        entrada = visitas.registrar_entrada(
            {"id": str(nuevo_id()), "socio_id": str(socios[0]), "sede_id": str(sede_id)}, autor
        )
        visitas.registrar_entrada({"id": str(nuevo_id()), "socio_id": str(socios[2]), "sede_id": str(sede_id)}, autor)
        anteriores = visitas.listar_visitas()
        assert len(anteriores) >= 2
    assert cambiar(cliente, 1).status_code == 200
    with app.app_context():
        assert visitas.listar_visitas() == anteriores
        datos = {"id": str(nuevo_id()), "socio_id": str(socios[1]), "sede_id": str(sede_id)}
        with pytest.raises(ErrorDeDominio) as error:
            visitas.registrar_entrada(datos, autor)
        assert error.value.codigo == "aforo_alcanzado"
    assert cambiar(cliente, 60).status_code == 200
    with app.app_context():
        assert visitas.listar_visitas() == anteriores
        assert visitas.registrar_entrada(datos, autor)["id"] != entrada["id"]


@pytest.mark.bd
def test_simulacion_respeta_nuevo_aforo(sede, reloj_fijo):
    app, cliente, _ = sede
    assert cambiar(cliente, 30, horario=demo.HORARIO_SEDE).status_code == 200
    for _ in range(8):
        reloj_fijo.avanzar(timedelta(minutes=15))
        with app.app_context():
            demo.poner_al_dia()
            ocupacion = visitas.consultar_ocupacion()
        assert ocupacion["aforo_maximo"] == 30
        assert ocupacion["ocupacion_registrada"] <= 30 * 4 // 5


@pytest.mark.bd
@pytest.mark.parametrize("aforo", [30, 120])
def test_limites_demo_inclusivos(sede, aforo):
    _, cliente, _ = sede
    assert cambiar(cliente, aforo).status_code == 200


@pytest.mark.bd
def test_error_revierte_historial_y_valor_vigente(sede, monkeypatch):
    app, cliente, _ = sede
    anterior = cliente.get("/api/administracion/sede").get_json()
    original = servicio.repositorio.registrar_cambio

    def fallar(*argumentos):
        original(*argumentos)
        raise RuntimeError("Fallo ficticio")

    monkeypatch.setattr(servicio.repositorio, "registrar_cambio", fallar)
    with pytest.raises(RuntimeError, match="Fallo ficticio"):
        cambiar(cliente, 50)
    assert cliente.get("/api/administracion/sede").get_json() == anterior
