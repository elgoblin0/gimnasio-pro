"""El reparto de pruebas en fragmentos que usa el CI (pruebas/conftest.py)."""

import os
import subprocess
import sys
from pathlib import Path

from fragmentos import fragmento_de

RAIZ = Path(__file__).resolve().parent.parent
MUESTRA = "pruebas/test_cadena.py"


def test_cada_prueba_cae_en_un_solo_fragmento():
    ids = [f"pruebas/test_x.py::test_{n}[{m}]" for n in range(60) for m in (0, 1)]
    for total in (2, 3, 4):
        cuenta = [0] * total
        for identificador in ids:
            fragmento = fragmento_de(identificador, total)
            assert 1 <= fragmento <= total
            assert fragmento == fragmento_de(identificador, total)  # estable
            cuenta[fragmento - 1] += 1
        assert sum(cuenta) == len(ids)
        assert min(cuenta) > len(ids) / total * 0.6  # reparto parejo, sin fragmentos vacíos


def _recolectar(fragmento):
    comando = [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", MUESTRA]
    salida = subprocess.run(
        comando,
        cwd=RAIZ,
        env={**os.environ, "GIMNASIO_FRAGMENTO": fragmento},
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
    return {linea for linea in salida.splitlines() if "::" in linea}


def test_los_fragmentos_juntos_son_toda_la_suite_sin_repetir():
    todas = _recolectar("")
    uno, dos = _recolectar("1/2"), _recolectar("2/2")
    assert todas and uno and dos
    assert uno | dos == todas and not uno & dos
