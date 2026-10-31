"""Mi ficha, tarjeta contextual y perfil de entrenamiento en sus pantallas."""

import pytest

expect = pytest.importorskip("playwright.sync_api").expect
pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("ancho", [390, 1280])
def test_socio_guarda_contacto_y_perfil(pagina_demo, demo_aislada, ancho):
    pagina = pagina_demo
    pagina.set_viewport_size({"width": ancho, "height": 900})
    pagina.goto(demo_aislada.url)
    pagina.get_by_role("button", name="Entrar como socio", exact=True).click()
    pagina.get_by_role("link", name="Mi ficha", exact=True).click()
    expect(pagina.get_by_role("heading", name="Mi ficha", exact=True)).to_be_visible()
    pagina.get_by_label("Teléfono (+595)", exact=True).fill("+595981123456")
    pagina.get_by_label("Correo", exact=True).fill("ficticio@ejemplo.test")
    pagina.get_by_role("button", name="Guardar datos personales", exact=True).click()
    expect(pagina.locator("[data-estado]")).to_have_text("Datos personales guardados.")
    pagina.get_by_label("Objetivo", exact=True).fill("Fuerza")
    pagina.get_by_label("Experiencia", exact=True).select_option("inicial")
    pagina.get_by_label("Disponibilidad semanal (días)", exact=True).fill("3")
    pagina.get_by_role("button", name="Guardar perfil de entrenamiento", exact=True).click()
    expect(pagina.locator("[data-perfil] [role=status]")).to_have_text("Perfil de entrenamiento guardado.")
    pagina.reload()
    expect(pagina.get_by_label("Correo", exact=True)).to_have_value("ficticio@ejemplo.test")
    expect(pagina.get_by_label("Objetivo", exact=True)).to_have_value("Fuerza")
    assert pagina.locator('input[name="cedula"]').count() == 0
    assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_recepcion_abre_ficha_desde_tarjeta_sin_perfil(pagina_demo, demo_aislada):
    pagina = pagina_demo
    pagina.goto(demo_aislada.url)
    pagina.get_by_role("button", name="Entrar como recepción", exact=True).click()
    pagina.get_by_role("link", name="Ir a recepción", exact=True).click()
    expect(pagina.get_by_text("Recepción lista.", exact=True)).to_be_visible()
    opciones = pagina.locator("#socio option").evaluate_all(
        "opciones => opciones.filter(o => o.value).map(o => ({id:o.value,nombre:o.textContent}))"
    )
    socio = next(opcion for opcion in opciones if "Lucía Benítez" in opcion["nombre"])
    pagina.get_by_label("Socio", exact=True).select_option(socio["id"])
    pagina.get_by_role("button", name="Registrar entrada", exact=True).click()
    pagina.get_by_role("link", name="Ver ficha del socio", exact=True).click()
    expect(pagina.get_by_label("Nombre", exact=True)).to_be_visible()
    expect(pagina.locator("[data-perfil]")).to_be_hidden()
    pagina.get_by_label("Nombre", exact=True).fill("Nombre ficticio")
    pagina.get_by_role("button", name="Guardar datos personales", exact=True).click()
    expect(pagina.locator("[data-estado]")).to_have_text("Datos personales guardados.")


def test_entrenador_edita_perfil_en_vista_del_socio(pagina_demo, demo_aislada):
    pagina = pagina_demo
    pagina.goto(demo_aislada.url)
    pagina.get_by_role("button", name="Entrar como entrenador", exact=True).click()
    pagina.wait_for_url("**/bandeja.html")
    socios = pagina.request.get(demo_aislada.url + "/api/entrenador/socios").json()["socios"]
    pagina.goto(demo_aislada.url + "/bandeja.html?socio=" + socios[0]["id"])
    pagina.get_by_label("Preferencias", exact=True).fill("Por la mañana")
    pagina.get_by_role("button", name="Guardar perfil de entrenamiento", exact=True).click()
    expect(pagina.locator("[data-perfil] [role=status]")).to_have_text("Perfil de entrenamiento guardado.")
    pagina.reload()
    expect(pagina.get_by_label("Preferencias", exact=True)).to_have_value("Por la mañana")
