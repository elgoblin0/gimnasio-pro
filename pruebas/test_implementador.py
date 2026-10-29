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


def test_las_revisiones_posteriores_al_ultimo_hecho_entran_al_prompt():
    resenas = [
        {"user": {"login": "claude"}, "body": "Quitá la deduplicación.", "submitted_at": "2026-10-29T12:50:00Z"},
        {"user": {"login": "claude"}, "body": "Vieja.", "submitted_at": "2026-10-29T10:00:00Z"},
        {
            "user": {"login": "bot"},
            "body": "<!-- codex-review-receipt:v1 --> ruido",
            "submitted_at": "2026-10-29T12:51:00Z",
        },
    ]
    en_linea = [
        {
            "user": {"login": "bot"},
            "path": "a.py",
            "line": 7,
            "body": "P1 falta consentimiento",
            "created_at": "2026-10-29T12:49:00Z",
        }
    ]
    texto = implementador.texto_de_revisiones(resenas, en_linea, "2026-10-29T11:00:00Z")
    assert "Quitá la deduplicación." in texto
    assert "a.py:7" in texto and "P1 falta consentimiento" in texto
    assert "Vieja." not in texto and "ruido" not in texto
    prompt = implementador.prompt_para_codex("@codex atendé la revisión", texto)
    assert "Quitá la deduplicación." in prompt
    assert implementador.prompt_para_codex("@codex hacé algo").endswith("hacé algo")


def test_el_cuerpo_del_pr_empieza_con_closes():
    assert implementador.cuerpo_del_pr("Closes #89\n\nNotas", 89) == "Closes #89\n\nNotas"
    assert implementador.cuerpo_del_pr("Notas", 90) == "Closes #90\n\nNotas"
    assert implementador.cuerpo_del_pr("  \n", 90) is None
    assert implementador.cuerpo_del_pr(None, 90) is None
    assert implementador.ARCHIVO_CUERPO in implementador.prompt_para_codex("@codex hacé algo")


def test_reconoce_la_falta_de_cupo_de_codex():
    assert implementador.es_falta_de_cupo("ERROR: You've hit your usage limit. Upgrade to Pro")
    assert not implementador.es_falta_de_cupo("Codex terminó con código 1")
    assert not implementador.es_falta_de_cupo(None)
