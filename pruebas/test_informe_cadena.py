"""Pruebas del informe de la cadena por etapa (lógica pura, sin gh)."""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import informe_cadena as informe  # noqa: E402  (necesita scripts/ en sys.path, que se agrega arriba)

HALLAZGO = (
    "**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  "
    "Incrementá la versión del caché al actualizar recepción**\n\nPara quienes ya abrieron la aplicación…"
)


def test_lee_prioridad_y_titulo_del_hallazgo_de_codex():
    assert informe.titulo_de_hallazgo(HALLAZGO) == "P1 Incrementá la versión del caché al actualizar recepción"
    assert informe.titulo_de_hallazgo("Comentario sin formato\nmás texto") == "Comentario sin formato"


def test_resume_un_pr_de_la_cadena():
    cadena = informe.cadena
    pr = {
        "number": 150,
        "title": "Permanencia habitual",
        "headRefName": "codex/issue-143",
        "createdAt": "2026-10-29T22:50:00Z",
        "mergedAt": "2026-10-29T23:16:00Z",
    }
    comentarios = [
        cadena.prompt_implementar({"number": 143, "title": "t", "body": "b"}),
        f"{cadena.MARCA_HECHO}\nCodex tiene una duda de criterio; quedó en el issue #143.",
        f"{cadena.MARCA_HECHO}\n<!-- implementador:codex minutos=4.0 tokens=1000 esfuerzo=low -->\nImplementado",
        cadena.prompt_corregir("corregí los hallazgos de tu revisión.", "revision"),
        "<!-- cadena:corregir -->\nPedido de antes, sin origen",
        f"{cadena.MARCA_HECHO}\n<!-- implementador:codex minutos=2.5 tokens=500 esfuerzo=low -->\nCorregido",
        f"{cadena.MARCA_AVISO}\nNadie tomó el pedido",
    ]
    fila = informe.fila(pr, comentarios, [HALLAZGO])
    assert fila["issue"] == 143 and fila["minutos"] == 26
    assert fila["codex_minutos"] == 6.5 and fila["tokens"] == 1500
    assert fila["correcciones"] == {"ci": 0, "revision": 1, "opus": 0, "conflicto": 0, "sin-origen": 1}
    assert fila["dudas"] == 1 and fila["avisos"] == 1 and not fila["bloqueado"]
    assert fila["hallazgos"] == ["P1 Incrementá la versión del caché al actualizar recepción"]


def test_el_informe_marca_los_hallazgos_que_se_repiten():
    filas = [
        {**informe.FILA_VACIA, "numero": 150, "issue": 143, "hallazgos": ["P1 Incrementá la versión del caché"]},
        {**informe.FILA_VACIA, "numero": 155, "issue": 144, "hallazgos": ["P2 Incrementá la versión del caché"]},
    ]
    texto = informe.informe_markdown("Etapa 3", filas)
    assert "| #150 | #143 |" in texto and "| #155 | #144 |" in texto
    assert "Se repite (2 PR): Incrementá la versión del caché" in texto
