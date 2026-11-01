"""ADR 0031: el cuerpo saneado sustituye solo lo persistido."""

import json
from base64 import b64decode
from unittest.mock import MagicMock

import pytest
from flask import Flask, g

from gimnasio.comun import idempotencia


@pytest.mark.parametrize("sanear", [False, True])
def test_guarda_cuerpo_saneado_o_real(monkeypatch, sanear):
    app = Flask(__name__)
    conexion = MagicMock()
    monkeypatch.setattr(idempotencia, "conexion_actual", lambda: conexion)
    idempotencia.registrar_idempotencia(app, lambda: None)
    with app.test_request_context("/"):
        g.solicitud_idempotente = (b"clave", b"usuario", b"huella", "ahora")
        if sanear:
            g.respuesta_para_reintento = {"clave_ya_entregada": True}
        respuesta = app.make_response(({"clave_provisional": "secreto-ficticio"}, 201, {"Location": "/api/socios/1"}))
        guardada = app.process_response(respuesta)
        parametros = conexion.cursor.return_value.__enter__.return_value.execute.call_args.args[1]
        persistida = json.loads(parametros[-1])
        cuerpo = b64decode(persistida["cuerpo"])
        assert json.loads(cuerpo) == ({"clave_ya_entregada": True} if sanear else respuesta.json)
        assert parametros[-2] == 201
        assert ["Location", "/api/socios/1"] in persistida["encabezados"]
        assert guardada.json == {"clave_provisional": "secreto-ficticio"}
        assert "respuesta_para_reintento" not in g
