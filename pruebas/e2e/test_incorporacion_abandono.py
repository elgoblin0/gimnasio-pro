"""Etapa 6: incorporación y riesgo de abandono en recepción, bandeja e inicio del socio, con la semilla."""

import pytest
from playwright.sync_api import expect

from gimnasio.demo.servicio import DIAS_DE_ALTA_LUCIA

pytestmark = pytest.mark.e2e


def entrar_como(contexto, demo, boton):
    pagina = contexto.new_page()
    pagina.goto(demo.url)
    pagina.get_by_role("button", name=boton, exact=True).click()
    return pagina


def test_el_socio_ve_su_incorporacion_y_no_el_riesgo(navegador, demo_aislada):
    with navegador.new_context(locale="es-PY") as contexto:
        pagina = entrar_como(contexto, demo_aislada, "Entrar como Lucía Benítez")
        seccion = pagina.locator("[data-incorporacion]")
        expect(seccion).to_contain_text(f"Día {DIAS_DE_ALTA_LUCIA + 1} de 90")
        expect(seccion).to_contain_text("Primera visita")
        expect(pagina.locator("body")).not_to_contain_text("abandono")


def test_el_entrenador_ve_el_riesgo_ultimo_en_la_bandeja_con_sus_razones(navegador, demo_aislada):
    with navegador.new_context(locale="es-PY") as contexto:
        pagina = entrar_como(contexto, demo_aislada, "Entrar como entrenador")
        grupo = pagina.locator('[data-grupo="riesgo_abandono"]')
        expect(grupo).to_contain_text("Riesgo de abandono")
        expect(pagina.locator("[data-grupo]").last).to_have_attribute("data-grupo", "riesgo_abandono")
        ver_todos = grupo.locator("[data-ver-grupo]")
        if ver_todos.count():
            ver_todos.click()
        grupo.get_by_role("link", name="Darío Vera").click()
        vista = pagina.locator("[data-acompanamiento]")
        expect(vista).to_contain_text("Incorporación: Día 31 de 90")
        expect(vista).to_contain_text("○ Primera sesión realizada")
        expect(vista).to_contain_text("días sin venir")


def test_recepcion_ve_incorporacion_y_riesgo_en_la_tarjeta(navegador, demo_aislada):
    with navegador.new_context(locale="es-PY") as contexto:
        pagina = entrar_como(contexto, demo_aislada, "Entrar como recepción")
        pagina.get_by_role("link", name="Ir a recepción").click()
        opcion = pagina.locator("#socio option").filter(has_text="Darío Vera")
        expect(opcion).to_have_count(1)
        pagina.locator("#socio").select_option(label=opcion.text_content())
        tarjeta = pagina.locator("[data-tarjeta-datos]")
        expect(tarjeta).to_contain_text("Incorporación: Día 31 de 90")
        expect(tarjeta).to_contain_text("Riesgo de abandono:")
        expect(tarjeta).not_to_contain_text("Primera sesión")
