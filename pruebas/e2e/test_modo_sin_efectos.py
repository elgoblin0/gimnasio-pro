"""Modo sin efectos: el interruptor manda sobre la detección, se recuerda y conserva información y acciones."""

import pytest
from playwright.sync_api import expect

from pruebas.e2e.test_recepcion import ingresar

pytestmark = pytest.mark.e2e


def test_interruptor_apaga_el_3d_conserva_las_acciones_y_se_recuerda(pagina_demo, demo_aislada):
    pagina = pagina_demo
    errores = []
    pagina.on("pageerror", lambda error: errores.append(str(error)))
    # Se parte de los efectos elegidos: el CI dibuja sin GPU y la detección ya activaría el modo.
    pagina.goto(demo_aislada.url)
    pagina.evaluate("localStorage.setItem('gimnasio-sin-efectos', 'no')")
    interruptor = pagina.get_by_role("button", name="Modo sin efectos", exact=True)
    expect(interruptor).to_have_attribute("aria-pressed", "false")

    ingresar(pagina, demo_aislada)
    expect(pagina.locator('[data-escena-ocupacion][data-lista="true"]')).to_be_visible()
    expect(pagina.locator("[data-escena-ocupacion] canvas")).to_be_visible()

    interruptor.click()
    pagina.wait_for_load_state("load")
    expect(interruptor).to_have_attribute("aria-pressed", "true")
    expect(pagina.locator("canvas:visible")).to_have_count(0)
    expect(pagina.locator("[data-alternativa-escena]")).to_be_visible()
    expect(pagina.get_by_role("heading", name="Por zona", exact=True)).to_be_visible()
    expect(pagina.locator("[data-ocupacion-cifra]")).to_have_text("0")

    # Las mismas acciones: registrar la entrada y elegir la visita por zona.
    socio = pagina.locator("#socio option").filter(has_text="Lucía Benítez").first.get_attribute("value")
    pagina.get_by_label("Socio", exact=True).select_option(socio)
    pagina.locator("[data-entrada]").get_by_role("button", name="Registrar entrada", exact=True).click()
    expect(pagina.locator("[data-ocupacion-cifra]")).to_have_text("1")
    pagina.keyboard.press("Escape")
    pagina.locator('[data-elegir-zona="en_la_sede"]').click()
    pagina.locator("[data-visita-zona]").click()
    expect(pagina.locator("[data-tarjeta-contextual]")).to_contain_text("Lucía Benítez")

    # Se recuerda al recargar y en las demás páginas.
    pagina.reload()
    expect(interruptor).to_have_attribute("aria-pressed", "true")
    expect(pagina.locator("canvas:visible")).to_have_count(0)
    pagina.goto(f"{demo_aislada.url}/clases.html")
    expect(interruptor).to_have_attribute("aria-pressed", "true")
    assert pagina.evaluate("document.documentElement.dataset.sinEfectos") == "si"

    # Apagarlo devuelve la escena.
    pagina.goto(f"{demo_aislada.url}/recepcion.html")
    interruptor.click()
    pagina.wait_for_load_state("load")
    expect(interruptor).to_have_attribute("aria-pressed", "false")
    expect(pagina.locator('[data-escena-ocupacion][data-lista="true"]')).to_be_visible()
    assert errores == []
