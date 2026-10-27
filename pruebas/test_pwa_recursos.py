"""Recursos públicos para instalar la PWA; no necesitan MySQL."""

import json
import struct
from pathlib import Path

from gimnasio import crear_app

ESTATICOS = Path(__file__).resolve().parents[1] / "gimnasio" / "static"


def test_manifest_iconos_y_sw_se_sirven_con_tipo_y_alcance_correctos():
    cliente = crear_app({"ENTORNO": "prueba", "SECRET_KEY": "solo-pruebas"}).test_client()
    respuesta = cliente.get("/manifest.webmanifest")
    assert respuesta.status_code == 200
    assert respuesta.mimetype == "application/manifest+json"
    manifiesto = json.loads(respuesta.data)
    assert manifiesto["name"] == manifiesto["short_name"] == "Gimnasio Pro"
    assert manifiesto["id"] == manifiesto["start_url"] == manifiesto["scope"] == "/"
    assert manifiesto["display"] == "standalone"
    assert manifiesto["lang"] == "es"
    tokens = (ESTATICOS / "estilos/tokens.css").read_text(encoding="utf-8")
    for color in (manifiesto["theme_color"], manifiesto["background_color"]):
        assert color in tokens

    assert {icono["purpose"] for icono in manifiesto["icons"]} == {"any", "maskable"}
    assert {icono["sizes"] for icono in manifiesto["icons"] if icono["purpose"] == "any"} == {
        "192x192",
        "512x512",
    }
    for icono in manifiesto["icons"]:
        assert icono["src"].startswith("/iconos/")
        respuesta = cliente.get(icono["src"])
        assert respuesta.status_code == 200
        assert respuesta.mimetype == icono["type"] == "image/png"
        assert respuesta.data[:8] == b"\x89PNG\r\n\x1a\n"
        ancho, alto = struct.unpack(">II", respuesta.data[16:24])
        assert icono["sizes"] == f"{ancho}x{alto}"

    respuesta = cliente.get("/sw.js")
    assert respuesta.status_code == 200
    assert respuesta.mimetype == "text/javascript"
    assert respuesta.headers["Service-Worker-Allowed"] == "/"
    assert respuesta.cache_control.no_cache


def test_todas_las_paginas_enlazan_el_manifest():
    for pagina in ESTATICOS.rglob("*.html"):
        assert '<link rel="manifest" href="/manifest.webmanifest">' in pagina.read_text(encoding="utf-8")
