"""Sondeo HTTP y cierre de lectura sin depender de la disponibilidad de MySQL."""

from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from flask import g

from gimnasio import crear_app
from gimnasio.comun.ids import nuevo_id
from gimnasio.entrenador import servicio


@pytest.fixture
def sondeo(monkeypatch, reloj_fijo):
    app = crear_app({"ENTORNO": "prueba", "MODO_DEMO": False})
    socio_id, entrenador_id, aviso_id = str(nuevo_id(reloj_fijo)), str(nuevo_id(reloj_fijo)), str(nuevo_id(reloj_fijo))
    estado = {"abierta": False, "avisos": [], "rol": "entrenador"}

    @app.before_request
    def autenticar():
        g.usuario = {"id": entrenador_id, "rol": estado["rol"]}

    @contextmanager
    def lectura():
        estado["abierta"] = True
        try:
            yield object()
        finally:
            estado["abierta"] = False

    monkeypatch.setattr(servicio, "transaccion", lectura)
    monkeypatch.setattr(servicio, "listar_equipos", lambda **opciones: [])
    monkeypatch.setattr(servicio, "socios_asignados", lambda *args: [{"id": socio_id}])
    monkeypatch.setattr(servicio, "avisos_para_entrenador", lambda *args: estado["avisos"])
    monkeypatch.setattr(servicio.repositorio, "listar_revisiones", lambda *args: [])
    monkeypatch.setattr(servicio, "listar_programas", lambda *args, **opciones: [])
    monkeypatch.setattr(
        servicio.repositorio, "fecha_asignacion_vigente", lambda *args: datetime(2026, 10, 30, tzinfo=UTC)
    )
    return app.test_client(), estado, aviso_id


def test_sondeo_cierra_lectura_en_200_y_304_y_cambia_tras_aviso(sondeo):
    cliente, estado, aviso_id = sondeo
    primera = cliente.get("/api/entrenador/bandeja")
    assert primera.status_code == 200 and not estado["abierta"]
    assert "private" in primera.headers["Cache-Control"]
    assert "no-cache" in primera.headers["Cache-Control"]
    segunda = cliente.get("/api/entrenador/bandeja", headers={"If-None-Match": primera.headers["ETag"]})
    assert segunda.status_code == 304 and segunda.data == b"" and not estado["abierta"]
    estado["avisos"].append({"id": aviso_id, "freno": "dolor_reportado", "creado_en": "2026-10-30T00:00:00+00:00"})
    nueva = cliente.get("/api/entrenador/bandeja", headers={"If-None-Match": primera.headers["ETag"]})
    assert nueva.status_code == 200 and not estado["abierta"]
    assert nueva.headers["ETag"] != primera.headers["ETag"]
    motivos = nueva.json["grupos"][0]["socios"][0]["motivos"]
    assert [m["tipo"] for m in motivos] == ["aviso_seguridad", "sin_programa"]


@pytest.mark.parametrize("rol", ["socio", "recepcion", "administracion"])
def test_permiso_se_aplica_antes_de_leer(sondeo, rol):
    cliente, estado, _ = sondeo
    estado["rol"] = rol
    assert cliente.get("/api/entrenador/bandeja").status_code == 403
    assert not estado["abierta"]


def test_error_tambien_cierra_lectura(sondeo, monkeypatch):
    cliente, estado, _ = sondeo

    def fallar(*argumentos, **opciones):
        raise RuntimeError("Error de lectura ficticio")

    monkeypatch.setattr(servicio, "listar_programas", fallar)
    with pytest.raises(RuntimeError, match="Error de lectura ficticio"):
        cliente.get("/api/entrenador/bandeja")
    assert not estado["abierta"]
