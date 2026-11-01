"""Etapa 6: resumen semanal en el inicio del socio y en la vista del socio del entrenador, con la semilla."""

import pytest
from playwright.sync_api import expect

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import desde_bytes

pytestmark = pytest.mark.e2e


def entrar_como(contexto, demo, boton):
    pagina = contexto.new_page()
    pagina.goto(demo.url)
    pagina.get_by_role("button", name=boton, exact=True).click()
    return pagina


def test_el_socio_ve_su_ultima_semana_cerrada_y_navega_a_las_anteriores(navegador, demo_aislada):
    with navegador.new_context(locale="es-PY") as contexto:
        pagina = entrar_como(contexto, demo_aislada, "Entrar como Lucía Benítez")
        resumen = pagina.locator("[data-resumen-semanal]")
        expect(resumen).to_contain_text("Tu semana")
        expect(resumen).to_contain_text("4 series")
        expect(resumen).to_contain_text("buscás 12 repeticiones")
        expect(resumen).to_contain_text("sesiones planificadas sin realizar")
        semana = resumen.locator("[data-resumen-semana]")
        cerrada = semana.get_attribute("data-resumen-semana")
        expect(resumen.get_by_role("button", name="Semana siguiente")).to_be_disabled()
        resumen.get_by_role("button", name="Semana anterior").click()
        expect(semana).not_to_have_attribute("data-resumen-semana", cerrada)
        expect(resumen).to_contain_text("Sin ajustes ni frenos en la semana.")
        resumen.get_by_role("button", name="Semana siguiente").click()
        expect(semana).to_have_attribute("data-resumen-semana", cerrada)


def test_el_entrenador_ve_el_resumen_del_socio_asignado(navegador, demo_aislada):
    with navegador.new_context(locale="es-PY") as contexto:
        with demo_aislada.app.app_context(), transaccion() as cursor:
            cursor.execute("SELECT id FROM usuarios WHERE rol='socio' AND es_demo=TRUE ORDER BY id LIMIT 1")
            lucia = desde_bytes(cursor.fetchone()["id"])
        pagina = entrar_como(contexto, demo_aislada, "Entrar como entrenador")
        pagina.wait_for_url("**/bandeja.html")
        # Lucía no está en ningún grupo de la bandeja: el entrenador la abre desde su enlace.
        pagina.goto(f"{demo_aislada.url}/bandeja.html?socio={lucia}")
        resumen = pagina.locator("[data-resumen-semanal]")
        expect(resumen).to_contain_text("4 series")
        expect(resumen).to_contain_text("buscás 12 repeticiones")
        expect(resumen.get_by_role("button", name="Semana anterior")).to_be_enabled()
