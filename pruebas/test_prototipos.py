"""Chequeos estáticos de los prototipos visuales: son descartables, pero no pueden contradecir los frenos."""

import re
from pathlib import Path

import pytest

PROTOTIPOS = Path(__file__).resolve().parent.parent / "prototipos"
DIRECCIONES = sorted(PROTOTIPOS.glob("direccion-*/index.html"))


def leer(archivo):
    return archivo.read_text(encoding="utf-8")


def tokens_semanticos(html):
    bloque = html.split("/* Semánticos */", 1)[1].split("}", 1)[0]
    return set(re.findall(r"(--[a-z0-9-]+)\s*:", bloque))


def test_hay_dos_direcciones():
    assert [d.parent.name for d in DIRECCIONES] == ["direccion-a", "direccion-b"]


def test_las_direcciones_comparten_los_tokens_semanticos():
    conjuntos = [tokens_semanticos(leer(d)) for d in DIRECCIONES]
    assert conjuntos[0] == conjuntos[1]
    assert {"--superficie", "--texto", "--acento", "--freno", "--foco"} <= conjuntos[0]


@pytest.mark.parametrize("archivo", DIRECCIONES, ids=lambda d: d.parent.name)
def test_sin_recursos_externos_y_con_movimiento_reducido(archivo):
    html = leer(archivo)
    assert not re.search(r"""(src|href)=["']https?:|url\(["']?https?:""", html)
    assert "prefers-reduced-motion: reduce" in html
    assert "Demo · datos ficticios" in html


@pytest.mark.parametrize("archivo", DIRECCIONES, ids=lambda d: d.parent.name)
def test_con_dolor_no_se_propone_ninguna_suba_frenada(archivo):
    html = leer(archivo)
    con_dolor = re.findall(r"<li[^>]*data-con-dolor[^>]*>(.*?)</li>", html, re.S)
    sin_dolor = re.findall(r"<li[^>]*data-sin-dolor[^>]*>(.*?)</li>", html, re.S)
    assert con_dolor and sin_dolor
    # Lo que el freno reemplaza o mantiene nunca muestra una suba de carga.
    assert all('class="delta"' not in item for item in con_dolor)
    # El estado inicial es "con dolor": esas filas se ven y las alternativas sin dolor arrancan ocultas.
    assert all("hidden" not in tag for tag in re.findall(r"<li[^>]*data-con-dolor[^>]*>", html))
    assert all("hidden" in tag for tag in re.findall(r"<li[^>]*data-sin-dolor[^>]*>", html))
