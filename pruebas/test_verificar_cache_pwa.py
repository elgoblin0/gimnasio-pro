"""Pruebas del control del CI que exige subir VERSION del service worker al tocar la PWA."""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import verificar_cache_pwa as control  # noqa: E402  (necesita scripts/ en sys.path, que se agrega arriba)

SW_16 = 'const VERSION = "16";\n'
SW_17 = 'const VERSION = "17";\n'


def test_tocar_la_pwa_sin_subir_version_falla():
    """Fue el primer hallazgo de Codex en #150 y en #155: una vuelta de corrección cada vez."""
    assert control.falta_subir_version(["gimnasio/static/js/recepcion.js"], SW_16, SW_16)
    assert control.falta_subir_version(["gimnasio/static/recepcion.html", control.SERVICE_WORKER], SW_16, SW_16)


def test_con_version_mayor_o_sin_tocar_la_pwa_pasa():
    assert (
        control.falta_subir_version(["gimnasio/static/js/recepcion.js", control.SERVICE_WORKER], SW_16, SW_17) is None
    )
    assert control.falta_subir_version(["gimnasio/visitas/servicio.py"], SW_16, SW_16) is None
    assert control.falta_subir_version(["gimnasio/static/js/modulo.test.js"], SW_16, SW_16) is None


def test_sin_la_constante_lo_dice():
    assert "VERSION" in control.falta_subir_version(["gimnasio/static/js/recepcion.js"], SW_16, "sin constante")
