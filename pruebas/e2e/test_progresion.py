"""La semilla muestra la doble progresión con movimiento reducido."""

import pytest

expect = pytest.importorskip("playwright.sync_api").expect
pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("ancho", [1440, 390])
def test_demo_explica_subir_y_mantener(pagina_demo, demo_aislada, ancho):
    pagina = pagina_demo
    pagina.set_viewport_size({"width": ancho, "height": 900})
    pagina.emulate_media(reduced_motion="reduce")
    pagina.goto(demo_aislada.url)
    pagina.get_by_role("button", name="Entrar como socio", exact=True).click()
    pagina.get_by_role("link", name="Ver mi entrenamiento", exact=True).click()
    expect(pagina.locator("[data-contenido]")).to_have_attribute("data-version-reglas", "2.0.0")
    subir = pagina.locator("[data-ejercicio]").filter(
        has=pagina.get_by_role("heading", name="Sentadilla ficticia", exact=True)
    )
    mantener = pagina.locator("[data-ejercicio]").filter(
        has=pagina.get_by_role("heading", name="Sentadilla con mancuernas ficticia", exact=True)
    )
    expect(subir).to_contain_text("23 kg")
    expect(subir.locator("[data-ajuste]")).to_contain_text("Subís 2,5 kg")
    expect(mantener.locator("[data-ajuste]")).to_contain_text("Mantenés 20,5 kg")
    expect(mantener.locator("[data-ajuste]")).to_contain_text("buscás 11 repeticiones")
    assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth")
