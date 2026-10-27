"""Chequeos de los prototipos visuales: son descartables, pero no pueden contradecir los frenos de VISION.md."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

PROTOTIPOS = Path(__file__).resolve().parent.parent / "prototipos"
DIRECCIONES = sorted(PROTOTIPOS.glob("direccion-*/index.html"))
CASOS = """
const chequeo = (sueno, energia, dolor) => ({ sueno, energia, dolor });
console.log(JSON.stringify({
  zonas: SESION.map((e) => e.zona),
  dolor: SESION.map((e) => proponer(e, chequeo("bien", "normal", "rodilla"))),
  dolorYCansancio: SESION.map((e) => proponer(e, chequeo("mal", "baja", "rodilla"))),
  sueno: SESION.map((e) => proponer(e, chequeo("mal", "normal", null))),
  energia: SESION.map((e) => proponer(e, chequeo("bien", "baja", null))),
  bien: SESION.map((e) => proponer(e, chequeo("bien", "normal", null))),
}));
"""


def leer(archivo):
    return archivo.read_text(encoding="utf-8")


def motor(html):
    return re.search(r'<script id="motor">(.*?)</script>', html, re.S).group(1)


def tokens_semanticos(html):
    bloque = html.split("/* Semánticos */", 1)[1].split("}", 1)[0]
    return set(re.findall(r"(--[a-z0-9-]+)\s*:", bloque))


def test_hay_dos_direcciones_con_el_mismo_motor_y_los_mismos_tokens():
    assert [d.parent.name for d in DIRECCIONES] == ["direccion-a", "direccion-b"]
    a, b = (leer(d) for d in DIRECCIONES)
    assert motor(a) == motor(b)
    assert tokens_semanticos(a) == tokens_semanticos(b)
    assert {"--superficie", "--texto", "--acento", "--freno", "--foco"} <= tokens_semanticos(a)


@pytest.mark.parametrize("archivo", DIRECCIONES, ids=lambda d: d.parent.name)
def test_sin_recursos_externos_y_con_movimiento_reducido(archivo):
    html = leer(archivo)
    assert not re.search(r"""(src|href)=["']https?:|url\(["']?https?:""", html)
    assert "prefers-reduced-motion: reduce" in html
    assert "Demo · datos ficticios" in html


@pytest.fixture(scope="module")
def propuestas():
    node = shutil.which("node")
    if not node:
        pytest.skip("sin Node")
    salida = subprocess.run(
        [node, "-e", motor(leer(DIRECCIONES[0])) + CASOS], capture_output=True, text=True, encoding="utf-8", check=True
    )
    return json.loads(salida.stdout)


def test_con_dolor_se_baja_o_se_sustituye_y_se_avisa(propuestas):
    for caso in ("dolor", "dolorYCansancio"):
        for zona, p in zip(propuestas["zonas"], propuestas[caso], strict=True):
            if zona != "rodilla":
                continue
            assert p["freno"]
            assert p["delta"] < 0 or p.get("reemplaza"), p
            assert "Marcos" in p["porque"]


def test_un_chequeo_desfavorable_nunca_sube(propuestas):
    for caso in ("sueno", "energia", "dolorYCansancio"):
        assert all(p["delta"] <= 0 and p["freno"] for p in propuestas[caso]), caso


def test_todo_freno_avisa_al_entrenador(propuestas):
    # VISION.md, frenos de seguridad, punto 5.
    frenadas = [p for caso, lista in propuestas.items() if caso != "zonas" for p in lista if p["freno"]]
    assert frenadas
    assert all("Avisamos a Marcos" in p["porque"] for p in frenadas)


def test_sin_frenos_hay_subas_explicadas(propuestas):
    assert all(p["delta"] > 0 and not p["freno"] and p["porque"].startswith("Subís") for p in propuestas["bien"])
