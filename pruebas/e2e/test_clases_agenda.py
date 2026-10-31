"""Configuración de una clase y consulta de la agenda con la semilla ficticia."""

import pytest

expect = pytest.importorskip("playwright.sync_api", reason="sin Playwright").expect
pytestmark = pytest.mark.e2e


def test_configurar_clase_y_ver_agenda_como_socio(pagina_demo, demo_aislada):
    pagina = pagina_demo
    pagina.goto(demo_aislada.url)
    pagina.get_by_role("button", name="Entrar como administración", exact=True).click()
    expect(pagina).to_have_url(f"{demo_aislada.url}/administracion.html")
    pagina.get_by_role("link", name="Clases", exact=True).click()
    expect(pagina.get_by_text("No hay ocurrencias de clase en estas dos semanas.")).to_be_visible()
    pagina.get_by_label("Nombre", exact=True).fill("Clase ficticia de prueba")
    pagina.get_by_label("Día", exact=True).select_option("2")
    pagina.get_by_label("Hora", exact=True).fill("18:00")
    pagina.get_by_label("Duración en minutos").fill("60")
    pagina.get_by_label("Cupo", exact=True).fill("12")
    pagina.get_by_role("button", name="Guardar clase", exact=True).click()
    expect(pagina.locator("[data-agenda] li")).to_have_count(2)
    expect(pagina.locator("[data-agenda]")).to_contain_text("Cupo: 12")
    pagina.get_by_role("button", name="Cerrar sesión", exact=True).click()
    pagina.get_by_role("button", name="Entrar como socio", exact=True).click()
    expect(pagina.get_by_role("heading", name="Hola, Lucía", exact=True)).to_be_visible()
    pagina.goto(f"{demo_aislada.url}/entrenamiento.html")
    pagina.get_by_role("link", name="Clases", exact=True).click()
    expect(pagina.locator("[data-agenda] li")).to_have_count(2)
    expect(pagina.get_by_role("heading", name="Configurar clases", exact=True)).not_to_be_visible()
