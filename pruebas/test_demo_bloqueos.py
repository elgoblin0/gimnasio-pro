"""Orden de los bloqueos compartidos por la simulación y recepción."""

from contextlib import nullcontext
from datetime import UTC, datetime

import pytest
from flask import Flask

from gimnasio.demo import servicio


@pytest.mark.parametrize("con_simulacion", [False, True])
def test_sede_se_bloquea_antes_de_simulacion(monkeypatch, reloj_fijo, con_simulacion):
    app = Flask(__name__)
    app.config["MODO_DEMO"] = True
    cursor = object()
    sede_bloqueada = False

    def estado_para_simulacion(cursor_recibido):
        nonlocal sede_bloqueada
        assert cursor_recibido is cursor
        sede_bloqueada = True
        return {"id": b"sede"}, []

    def bloquear_simulacion(cursor_recibido):
        assert cursor_recibido is cursor
        assert sede_bloqueada, "Recepción bloquea primero la sede: la simulación debe seguir el mismo orden"
        return {"generada_hasta": datetime(2026, 10, 27, 12, tzinfo=UTC)} if con_simulacion else None

    monkeypatch.setattr(servicio, "transaccion", lambda: nullcontext(cursor))
    monkeypatch.setattr(servicio, "reloj_actual", lambda: reloj_fijo)
    monkeypatch.setattr(servicio.visitas, "estado_para_simulacion", estado_para_simulacion)
    monkeypatch.setattr(servicio.repositorio, "bloquear_simulacion", bloquear_simulacion)
    with app.app_context():
        servicio.poner_al_dia()
