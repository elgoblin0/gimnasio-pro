"""Etapa 4 completa: el ciclo entre socio y entrenador con la semilla, la API y MySQL reales."""

import re

import pytest
from playwright.sync_api import expect

from pruebas.e2e.test_esqueleto_andante import ingresar, preparar, tiempo_de_recorrido

pytestmark = pytest.mark.e2e


def abrir_contexto(navegador):
    """Cada persona con su sesión; sin service worker, como las demás pantallas del entrenador."""
    return navegador.new_context(locale="es-PY", service_workers="block")


def tarjeta(pagina, nombre):
    return pagina.locator("[data-ejercicio]").filter(has=pagina.get_by_role("heading", name=nombre, exact=True))


def test_recorrido_lucia_marcos_lucia(navegador, demo_aislada):
    demo_aislada.app.add_url_rule("/favicon.ico", view_func=lambda: ("", 204))
    with abrir_contexto(navegador) as contexto_socio, abrir_contexto(navegador) as contexto_entrenador:
        lucia = contexto_socio.new_page()
        marcos = contexto_entrenador.new_page()
        errores_socio = preparar(lucia, 1440, 900)
        errores_entrenador = preparar(marcos, 1440, 900)

        # Marcos deja la bandeja abierta antes de que Lucía reporte el dolor.
        marcos.goto(demo_aislada.url)
        marcos.get_by_role("button", name="Entrar como entrenador", exact=True).click()
        marcos.wait_for_url("**/bandeja.html")
        grupo = marcos.locator('[data-grupo="aviso_seguridad"]')
        expect(grupo).to_be_visible()
        marcos.evaluate("window.sinRecargar = true")
        fila = grupo.locator("[data-enlace-socio]").filter(has_text="Lucía Benítez")
        expect(fila).to_have_count(0)

        ingresar(lucia, demo_aislada, "socio")
        lucia.get_by_label("Sueño", exact=True).select_option("4")
        lucia.get_by_label("Energía", exact=True).select_option("4")
        lucia.get_by_role("button", name="Guardar chequeo del día", exact=True).click()
        expect(lucia.locator("[data-chequeo]")).to_be_hidden()
        lucia.get_by_role("button", name="Iniciar sesión realizada", exact=True).click()
        expect(lucia.locator("[data-sesion-actual]")).to_be_visible()
        sentadilla = tarjeta(lucia, "Sentadilla ficticia")
        lucia.get_by_role("button", name="Me duele durante Sentadilla ficticia", exact=True).click()
        dolor = sentadilla.locator("[data-dolor] form")
        # El 3D reemplaza los controles de la silueta al terminar de cargar.
        expect(dolor).to_have_attribute("data-cuerpo3d", "listo", timeout=30000)
        dolor.get_by_role("button", name="Ver todas las zonas", exact=True).click()
        dolor.get_by_role("checkbox", name="Rodillas", exact=True).click()
        expect(dolor.get_by_role("checkbox", name="Rodillas", exact=True)).to_be_checked()
        sentadilla.get_by_role("button", name="Guardar dolor reportado", exact=True).click()
        expect(lucia.get_by_text("Dolor reportado guardado. Se avisó al entrenador.", exact=True)).to_be_visible()
        lucia.get_by_role("button", name="Terminar sesión", exact=True).click()
        expect(lucia.get_by_text("Resumen actualizado.", exact=True)).to_be_visible()

        # El aviso llega por el sondeo: la bandeja no se recargó.
        expect(fila).to_be_visible(timeout=15000)
        assert marcos.evaluate("window.sinRecargar") is True
        fila.click()
        expect(marcos.locator("[data-socio-nombre]")).to_have_text("Lucía Benítez")
        expect(marcos.locator('[data-avisos-sin-revisar] [data-freno="dolor_reportado"]')).to_have_count(1)
        marcos.get_by_label("Nota opcional").fill("Bajamos la carga de partida.")
        marcos.get_by_role("button", name="Marcar como revisado", exact=True).click()
        expect(marcos.locator("[data-avisos-revisados]")).to_contain_text("Bajamos la carga de partida.")
        expect(fila).to_have_count(0, timeout=15000)
        assert marcos.evaluate("window.sinRecargar") is True

        # Marcos publica una versión nueva con una carga de partida más baja que la del motor.
        tiempo_de_recorrido(demo_aislada)
        socios = marcos.evaluate("fetch('/api/entrenador/socios').then(r => r.json())")["socios"]
        socio = next(s["id"] for s in socios if s["nombre"] == "Lucía" and s["apellido"] == "Benítez")
        marcos.goto(f"{demo_aislada.url}/editor-programa.html?socio={socio}")
        fila_plan = marcos.locator(".fila-plan").filter(has_text="Sentadilla ficticia").first
        expect(fila_plan).to_be_visible()
        fila_plan.locator('[data-campo="carga_partida"]').fill("15")
        marcos.get_by_role("button", name=re.compile("^Publicar versión")).click()
        expect(marcos.locator("[data-publicado-titulo]")).to_have_text("Publicaste la versión 2")

        # Al día siguiente Lucía recibe esa versión con su explicación.
        tiempo_de_recorrido(demo_aislada, dias=1)
        lucia.goto(f"{demo_aislada.url}/entrenamiento.html")
        expect(lucia.get_by_text("Propuesta actualizada.", exact=True)).to_be_visible()
        sentadilla = tarjeta(lucia, "Sentadilla ficticia")
        expect(sentadilla).to_contain_text("Tu entrenador fijó 15")
        expect(sentadilla).to_contain_text("15,00 kg")

        assert errores_socio == []
        assert errores_entrenador == []
