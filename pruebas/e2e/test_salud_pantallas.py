"""Condiciones de salud y acciones del entrenador desde sus pantallas."""

import pytest

expect = pytest.importorskip("playwright.sync_api").expect
pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("ancho", [390, 1280])
def test_condicion_restriccion_y_levantamiento(pagina_demo, demo_aislada, ancho):
    pagina = pagina_demo
    pagina.set_viewport_size({"width": ancho, "height": 900})
    pagina.goto(demo_aislada.url)
    pagina.get_by_role("button", name="Entrar como socio", exact=True).click()
    expect(pagina.get_by_role("link", name="Ver mi entrenamiento", exact=True)).to_be_visible()
    socio = pagina.request.get(demo_aislada.url + "/api/sesion").json()["usuario"]["id"]
    pagina.goto(demo_aislada.url + "/ficha.html")
    salud = pagina.locator("[data-salud]")
    salud.get_by_label("Condición de salud", exact=True).fill("Condición ficticia para revisar")
    salud.get_by_role("button", name="Declarar condición", exact=True).click()
    expect(salud.get_by_text("Condición ficticia para revisar", exact=True)).to_be_visible()
    assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth")
    pagina.get_by_role("button", name="Cerrar sesión", exact=True).click()
    pagina.get_by_role("button", name="Entrar como entrenador", exact=True).click()
    pagina.wait_for_url(demo_aislada.url + "/bandeja.html")
    pagina.goto(demo_aislada.url + "/bandeja.html?socio=" + socio)
    salud = pagina.locator("[data-salud]")
    expect(salud.locator("article").get_by_text("Condición ficticia para revisar", exact=True)).to_be_visible()
    salud.get_by_label("Objetivo", exact=True).select_option("zona")
    salud.get_by_label("Buscar ejercicio, patrón o zona", exact=True).fill("Rodillas")
    salud.get_by_label("Resultado", exact=True).select_option("rodillas")
    salud.get_by_label("Descripción de la restricción", exact=True).fill("Restricción ficticia de prueba")
    salud.get_by_label("Condición que se revisa", exact=True).select_option(label="Condición ficticia para revisar")
    salud.get_by_role("button", name="Registrar restricción", exact=True).click()
    expect(salud.get_by_text("Rodillas: Restricción ficticia de prueba", exact=True)).to_be_visible()
    expect(salud.get_by_role("button", name="Marcar condición revisada", exact=True)).to_have_count(0)
    fila = salud.locator("article").filter(has_text="Restricción ficticia de prueba")
    fila.get_by_role("button", name="Levantar restricción", exact=True).click()
    expect(salud.get_by_text("Rodillas: Restricción ficticia de prueba", exact=True)).to_have_count(0)
    assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_borrado_solo_con_revocacion_y_con_la_palabra_exacta(pagina_demo, demo_aislada):
    pagina = pagina_demo
    pagina.set_viewport_size({"width": 390, "height": 900})
    pagina.goto(demo_aislada.url)
    pagina.get_by_role("button", name="Entrar como socio", exact=True).click()
    expect(pagina.get_by_role("link", name="Ver mi entrenamiento", exact=True)).to_be_visible()
    pagina.goto(demo_aislada.url + "/ficha.html")
    seccion = pagina.locator("[data-consentimientos]")
    boton = seccion.get_by_role("button", name="Borrar mis datos de salud", exact=True)
    revocar = seccion.get_by_role("button", name="Revocar consentimiento de salud", exact=True)
    expect(revocar).to_be_visible()
    expect(boton).to_have_count(0)
    pagina.on("dialog", lambda dialogo: dialogo.accept())
    revocar.click()
    expect(boton).to_be_disabled()
    campo = seccion.get_by_label("Escribí BORRAR para confirmar", exact=True)
    campo.fill("borrar")
    expect(boton).to_be_disabled()
    campo.fill("BORRAR")
    expect(boton).to_be_enabled()
    assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth")
    # En la demo, el socio del recorrido no es el dedicado al borrado: la pantalla explica el límite.
    boton.click()
    expect(seccion.get_by_text("En la demo, el borrado solo funciona", exact=False)).to_be_visible()
    expect(boton).to_be_enabled()
