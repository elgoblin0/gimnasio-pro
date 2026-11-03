"""La silueta sin 3D sale de los mismos músculos que el mapa del cuerpo 3D (ADR 0034)."""

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import silueta_cuerpo  # noqa: E402  (necesita scripts/ en sys.path, que se agrega arriba)
from musculos_cuerpo import MUSCULOS  # noqa: E402


def test_el_modulo_de_la_silueta_esta_al_dia_con_los_musculos():
    assert silueta_cuerpo.DESTINO.read_text(encoding="utf-8") == silueta_cuerpo.generar()


def test_cada_zona_del_motor_tiene_su_trazo_con_un_poligono_por_lado_de_cada_musculo():
    zonas = json.loads((RAIZ / "pruebas/vectores/zonas_cuerpo.json").read_text(encoding="utf-8"))
    modulo = silueta_cuerpo.DESTINO.read_text(encoding="utf-8")
    trazos = dict(re.findall(r'^  (\w+): "([^"]+)",$', modulo, re.MULTILINE))
    assert list(trazos) == zonas
    for zona, trazo in trazos.items():
        musculos = sum(1 for _, z, *_ in MUSCULOS if z == zona)
        assert trazo.count("M") == 2 * musculos, zona


def test_la_silueta_entra_en_el_viewbox_y_deja_libre_la_columna_de_nombres():
    modulo = silueta_cuerpo.DESTINO.read_text(encoding="utf-8")
    absolutos = re.findall(r"[ML](-?[\d.]+) (-?[\d.]+)", modulo)
    xs = [float(x) for x, _ in absolutos]
    ys = [float(y) for _, y in absolutos]
    assert min(xs) >= 0 and max(xs) < 392  # Los nombres de zona empiezan en x = 392 (zonas.js).
    assert min(ys) >= 0 and max(ys) <= 400
