"""Primer recorrido de la demo con la semilla ficticia."""

import pytest

expect = pytest.importorskip("playwright.sync_api", reason="sin Playwright: instalá requirements-dev.txt").expect

pytestmark = pytest.mark.e2e


def test_entrar_como_socio_saluda_a_lucia_sin_errores(pagina, url_base):
    errores = []
    pagina.on("console", lambda mensaje: errores.append(mensaje.text) if mensaje.type == "error" else None)
    pagina.on("pageerror", lambda error: errores.append(str(error)))

    pagina.goto(f"{url_base}/")
    pagina.get_by_role("button", name="Entrar como socio", exact=True).click()
    expect(pagina.get_by_role("heading", name="Hola, Lucía", exact=True)).to_be_visible()

    assert errores == [], "Errores del navegador: " + "\n".join(errores)
