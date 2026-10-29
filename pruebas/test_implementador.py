"""Pruebas de la lógica pura del implementador local (sin gh, git ni Codex)."""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import implementador  # noqa: E402  (necesita scripts/ en sys.path, que se agrega arriba)

HECHO = implementador.MARCA_HECHO
FALLO = implementador.MARCA_FALLO


def test_distingue_los_pedidos_de_trabajo_de_la_revision():
    assert implementador.es_pedido("@codex implementá el issue #5")
    assert implementador.es_pedido("<!-- cadena:corregir -->\n@codex el CI falló")
    assert not implementador.es_pedido("<!-- cadena:revisar abc -->\n@codex review")
    assert not implementador.es_pedido("Resumen del CI: ✅")
    assert not implementador.es_pedido(None)


def test_toma_el_ultimo_pedido_sin_atender():
    comentarios = ["@codex implementá #5", "respuesta del bot", f"{HECHO}\nlisto", "@codex corregí"]
    assert implementador.pedido_pendiente(comentarios) == ("@codex corregí", 0)


def test_un_pedido_atendido_no_queda_pendiente():
    assert implementador.pedido_pendiente(["@codex implementá #5", f"{HECHO}\nlisto"]) == (None, 0)


def test_cuenta_los_fallos_del_pedido_vigente():
    comentarios = ["@codex implementá #5", f"{FALLO}\nuno", f"{FALLO}\ndos"]
    assert implementador.pedido_pendiente(comentarios) == ("@codex implementá #5", 2)
    assert implementador.pedido_pendiente([*comentarios, "@codex corregí"]) == ("@codex corregí", 0)


def test_el_prompt_quita_la_mencion_y_las_marcas():
    prompt = implementador.prompt_para_codex("<!-- cadena:corregir -->\n@codex el CI falló: arreglalo")
    assert prompt.endswith("el CI falló: arreglalo")
    assert "@codex" not in prompt and "<!--" not in prompt
