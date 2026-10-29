"""Cuerpo del chequeo y del resumen con las mismas zonas y alternativa SVG."""

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("alternativa", ["ninguna", "sin_webgl", "movimiento_reducido"])
def test_cuerpo_3d_y_silueta(page, url_base, alternativa):
    errores = []
    page.on("pageerror", lambda error: errores.append(str(error)))
    page.on("console", lambda mensaje: errores.append(mensaje.text) if mensaje.type == "error" else None)
    page.emulate_media(reduced_motion="reduce" if alternativa == "movimiento_reducido" else "no-preference")
    if alternativa == "sin_webgl":
        page.add_init_script(
            "const original = HTMLCanvasElement.prototype.getContext;"
            "HTMLCanvasElement.prototype.getContext = function(tipo, ...opciones) {"
            "return tipo.startsWith('webgl') ? null : original.call(this, tipo, ...opciones); };"
        )
    page.route(
        "**/prueba-cuerpo",
        lambda ruta: ruta.fulfill(
            content_type="text/html",
            body='<html><head><script type="importmap">'
            '{"imports":{"three":"/vendor/three@0.186.0/three.module.js"}}'
            "</script></head><body></body></html>",
        ),
    )
    page.goto(f"{url_base}/prueba-cuerpo")
    page.evaluate("""async () => {
      const zonas = await import('/js/comun/zonas.js');
      document.body.replaceChildren();
      const chequeo = document.createElement('div'); chequeo.id = 'chequeo';
      const resumen = document.createElement('div'); resumen.id = 'resumen';
      document.body.append(chequeo, resumen);
      window.selector = zonas.crearSelectorZonas(chequeo);
      zonas.crearResumenZonas(resumen, ['pecho'], ['pecho', 'rodillas']);
    }""")
    chequeo = page.locator("#chequeo")
    if alternativa == "ninguna":
        expect(chequeo).to_have_attribute("data-cuerpo3d", "listo")
        expect(page.locator("#resumen")).to_have_attribute("data-cuerpo3d", "listo")
        lienzo = chequeo.locator("canvas")
        rectangulo = lienzo.bounding_box()
        lienzo.click(position={"x": rectangulo["width"] / 2, "y": 152})
        assert page.evaluate("selector.zonas()") == ["abdomen"]
    else:
        expect(chequeo.locator("svg")).to_be_visible()
        expect(chequeo.locator("canvas")).to_have_count(0)
    rodillas = chequeo.get_by_role("checkbox", name="Rodillas", exact=True)
    rodillas.focus()
    page.keyboard.press("Space")
    expect(rodillas).to_have_attribute("aria-checked", "true")
    assert "rodillas" in page.evaluate("selector.zonas()")
    page.evaluate("selector.deshabilitar(true)")
    expect(rodillas).to_be_disabled() if alternativa == "ninguna" else expect(rodillas).to_have_attribute(
        "aria-disabled", "true"
    )
    assert errores == []
