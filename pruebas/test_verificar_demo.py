"""verificar_demo contra una demo simulada, sin red."""

import importlib.util
import json
from pathlib import Path

ARCHIVO = Path(__file__).resolve().parent.parent / "scripts" / "verificar_demo.py"
ESPECIFICACION = importlib.util.spec_from_file_location("verificar_demo", ARCHIVO)
verificar_demo = importlib.util.module_from_spec(ESPECIFICACION)
ESPECIFICACION.loader.exec_module(verificar_demo)


def demo_simulada(modo_demo=True, limite=60, rechaza_grande=True, retry_after="12"):
    llamadas = []

    def abrir(metodo, url, cuerpo=None):
        llamadas.append(metodo)
        if cuerpo is not None and len(cuerpo) > verificar_demo.MAXIMO_BYTES:
            return (413, {}, "") if rechaza_grande else (200, {}, "{}")
        if len(llamadas) > limite:
            return 429, {"Retry-After": retry_after}, ""
        return 200, {}, json.dumps({"modo_demo": modo_demo})

    return abrir


def test_una_demo_correcta_no_da_fallas():
    assert verificar_demo.verificar("https://demo.test/", demo_simulada()) == []


def test_detecta_cada_incumplimiento():
    assert any("modo_demo" in f for f in verificar_demo.verificar("https://demo.test", demo_simulada(modo_demo=False)))
    assert any("413" in f for f in verificar_demo.verificar("https://demo.test", demo_simulada(rechaza_grande=False)))
    assert any("429" in f for f in verificar_demo.verificar("https://demo.test", demo_simulada(limite=10_000)))
    assert any("Retry-After" in f for f in verificar_demo.verificar("https://demo.test", demo_simulada(retry_after="")))
