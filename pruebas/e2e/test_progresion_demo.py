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
    expect(pagina.locator("[data-contenido]")).to_have_attribute("data-version-reglas", "3.2.0")
    subir = pagina.locator("[data-ejercicio]").filter(
        has=pagina.get_by_role("heading", name="Sentadilla ficticia", exact=True)
    )
    mantener = pagina.locator("[data-ejercicio]").filter(
        has=pagina.get_by_role("heading", name="Sentadilla con mancuernas ficticia", exact=True)
    )
    expect(subir).to_contain_text("23,00 kg")
    expect(subir.locator("[data-ajuste]")).to_contain_text("Subís 2,5 kg")
    expect(mantener.locator("[data-ajuste]")).to_contain_text("Mantenés 20,5 kg")
    expect(mantener.locator("[data-ajuste]")).to_contain_text("buscás 11 repeticiones")
    assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("movimiento", ["reduce", "no-preference"])
def test_lucia_celebra_record_de_la_prescripcion(pagina_demo, demo_aislada, movimiento):
    pagina = pagina_demo
    pagina.emulate_media(reduced_motion=movimiento)
    pagina.goto(demo_aislada.url)
    pagina.get_by_role("button", name="Entrar como socio", exact=True).click()
    pagina.get_by_role("link", name="Ver mi entrenamiento", exact=True).click()
    pagina.get_by_role("button", name="Saltear", exact=True).click()
    pagina.get_by_role("button", name="Iniciar sesión realizada", exact=True).click()
    pagina.get_by_role("button", name="Registrar serie de Sentadilla ficticia", exact=True).click()
    expect(pagina.locator("[data-record]")).to_have_text("Récord: 23,00 kg en Sentadilla ficticia")
    expect(pagina.locator("[data-record]")).to_have_attribute("aria-live", "polite")
    if movimiento == "reduce":
        assert pagina.locator("[data-record]").evaluate("elemento => elemento.getAnimations().length") == 0
    pagina.reload()
    expect(pagina.locator("[data-record]")).to_be_empty()


def test_sesion_en_vivo_conserva_objetivos_guardados(pagina_demo, demo_aislada):
    from gimnasio.comun.bd import transaccion

    pagina = pagina_demo
    pagina.goto(demo_aislada.url)
    pagina.get_by_role("button", name="Entrar como socio", exact=True).click()
    pagina.get_by_role("link", name="Ver mi entrenamiento", exact=True).click()
    pagina.get_by_role("button", name="Saltear", exact=True).click()
    pagina.get_by_role("button", name="Iniciar sesión realizada", exact=True).click()
    expect(pagina.locator("[data-sesion-actual]")).to_be_visible()
    with demo_aislada.app.app_context(), transaccion() as cursor:
        cursor.execute("UPDATE ejercicios_planificados SET carga=99,series=8 WHERE carga IS NOT NULL")
    pagina.reload()
    sentadilla = pagina.locator("[data-ejercicio]").filter(
        has=pagina.get_by_role("heading", name="Sentadilla ficticia", exact=True)
    )
    expect(sentadilla).to_contain_text("2 series")
    expect(sentadilla).to_contain_text("Pendientes: 2")
    expect(sentadilla).to_contain_text("23,00 kg")
    expect(sentadilla.locator("[data-ajuste]")).to_contain_text("Subís 2,5 kg")
