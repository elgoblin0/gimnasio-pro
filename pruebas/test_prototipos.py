"""Chequeos de los prototipos visuales: son descartables, pero no pueden contradecir los frenos de VISION.md."""

import json
import re
import runpy
import shutil
import subprocess
from pathlib import Path

import pytest

PROTOTIPOS = Path(__file__).resolve().parent.parent / "prototipos"
DIRECCIONES = sorted(PROTOTIPOS.glob("direccion-*/index.html"))
CUERPOS = sorted(PROTOTIPOS.glob("cuerpo-3d/*/index.html"))
ESCENAS = sorted(PROTOTIPOS.glob("escena-ocupacion/*/index.html"))
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


def test_permanece_b_y_se_retiro_a():
    assert [d.parent.name for d in DIRECCIONES] == ["direccion-b"]
    assert not (PROTOTIPOS / "direccion-a").exists()
    b = leer(DIRECCIONES[0])
    assert motor(b)
    assert {"--superficie", "--texto", "--acento", "--freno", "--foco"} <= tokens_semanticos(b)


@pytest.mark.parametrize("archivo", DIRECCIONES + CUERPOS + ESCENAS, ids=lambda d: d.parent.name)
def test_sin_recursos_externos_y_con_movimiento_reducido(archivo):
    html = leer(archivo)
    assert not re.search(r"""(src|href)=["']https?:|url\(["']?https?:""", html)
    assert (
        "prefers-reduced-motion: reduce" in html
        or (archivo in CUERPOS and "prefers-reduced-motion: reduce" in leer(PROTOTIPOS / "cuerpo-3d/cuerpo.css"))
        or (archivo in ESCENAS and "prefers-reduced-motion: reduce" in leer(PROTOTIPOS / "escena-ocupacion/escena.css"))
    )
    assert "Demo · datos ficticios" in html


def test_escena_ocupacion_compara_dos_direcciones_con_los_mismos_datos():
    assert {p.parent.name for p in ESCENAS} == {"a", "b"}
    datos = json.loads(leer(PROTOTIPOS / "escena-ocupacion/personas.json"))
    assert len(datos["personas"]) == 40
    assert datos["aforo_maximo"] >= 40
    assert len({p["id"] for p in datos["personas"]}) == 40
    assert {p["zona"] for p in datos["personas"]} == {"Musculación", "Peso libre", "Cardio", "Funcional", "En la sede"}
    assert {p["simulada"] for p in datos["personas"]} == {True, False}
    assert all(p["minutos"] >= 0 for p in datos["personas"])
    for archivo in ESCENAS:
        assert 'src="../escena.js"' in leer(archivo)


def test_cuerpo_3d_tiene_dos_versiones_y_las_zonas_del_catalogo():
    from gimnasio.comun.tipos import ZONAS_CUERPO

    assert {p.parent.name for p in CUERPOS} == {"modelo", "estilizado"}
    codigo = leer(PROTOTIPOS / "cuerpo-3d/cuerpo.js")
    declaradas = re.search(r"export const zonas = (\[.*?\]);", codigo).group(1)
    assert json.loads(declaradas.replace("'", '"')) == list(ZONAS_CUERPO)
    assert "zona-seleccionada" in codigo
    assert (PROTOTIPOS / "cuerpo-3d/recursos/cuerpo.glb").read_bytes()[:4] == b"glTF"
    assert "CC0" in leer(PROTOTIPOS / "cuerpo-3d/recursos/LICENCIA.txt")


@pytest.mark.e2e
def test_cuerpo_3d_carga_y_emite_zonas_en_chromium(tmp_path, playwright):
    if not Path(playwright.chromium.executable_path).is_file():
        pytest.skip("sin Chromium: ejecutá playwright install chromium")
    verificar = runpy.run_path(str(PROTOTIPOS / "cuerpo-3d/verificar.py"))["verificar"]
    verificar(tmp_path, playwright)


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


def test_un_chequeo_desfavorable_nunca_sube_y_baja_el_volumen(propuestas):
    for caso in ("sueno", "energia", "dolorYCansancio"):
        assert all(p["delta"] <= 0 and p["freno"] for p in propuestas[caso]), caso
    # VISION.md, frenos §5: todo freno sustituye o baja. Con el chequeo desfavorable baja el volumen.
    for caso in ("sueno", "energia"):
        assert all(p["series"] < 3 for p in propuestas[caso]), caso


def test_todo_freno_sustituye_o_baja(propuestas):
    for caso, lista in propuestas.items():
        if caso == "zonas":
            continue
        for p in lista:
            if p["freno"]:
                assert p.get("reemplaza") or p["delta"] < 0 or p["series"] < 3, (caso, p)


def test_todo_freno_avisa_al_entrenador(propuestas):
    # VISION.md, frenos de seguridad, punto 5.
    frenadas = [p for caso, lista in propuestas.items() if caso != "zonas" for p in lista if p["freno"]]
    assert frenadas
    assert all("Avisamos a Marcos" in p["porque"] for p in frenadas)


def test_sin_frenos_hay_subas_explicadas(propuestas):
    assert all(p["delta"] > 0 and not p["freno"] and p["porque"].startswith("Subís") for p in propuestas["bien"])
