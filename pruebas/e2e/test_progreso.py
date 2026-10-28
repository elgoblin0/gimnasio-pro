"""Progreso visible, tabla equivalente y adaptación a celular."""

import json

import pytest
from playwright.sync_api import expect

from pruebas.e2e.test_entrenamiento import ingresar

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("ancho", [390, 1440])
def test_progreso_selector_tabla_y_vacio(pagina_demo, demo_aislada, ancho):
    pagina = pagina_demo
    pagina.set_viewport_size({"width": ancho, "height": 900})
    datos = {
        "ejercicios": [
            {
                "id": "primero",
                "nombre": "Sentadilla ficticia",
                "puntos": [
                    {"fecha_local": "2026-10-01", "carga": "20.00", "repeticiones": 10},
                    {"fecha_local": "2026-10-03", "carga": "25.00", "repeticiones": 8},
                ],
            },
            {
                "id": "segundo",
                "nombre": "Remo ficticio",
                "puntos": [
                    {"fecha_local": "2026-10-02", "carga": "15.00", "repeticiones": 12},
                ],
            },
        ]
    }
    pagina.add_init_script(
        """(() => {
        const original = window.fetch;
        window.progresoPrueba = DATOS;
        window.fetch = (ruta, opciones) => ruta === '/api/entrenamiento/progreso'
            ? Promise.resolve(new Response(JSON.stringify(window.progresoPrueba), {
                status: window.errorProgreso ? 500 : 200,
                headers: {'Content-Type': 'application/json'}
              }))
            : original(ruta, opciones);
    })();""".replace("DATOS", json.dumps(datos))
    )
    ingresar(pagina, demo_aislada)
    pagina.get_by_role("button", name="Ver progreso", exact=True).click()
    seccion = pagina.locator("[data-progreso]")
    expect(seccion.locator("circle")).to_have_count(2)
    expect(seccion.locator("tbody tr")).to_have_count(2)
    expect(seccion.locator("tbody")).to_contain_text("25")
    pagina.get_by_label("Ejercicio de progreso").select_option("segundo")
    expect(seccion.locator("circle")).to_have_count(1)
    expect(seccion.locator("tbody")).to_contain_text("12")
    assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth")
    pagina.evaluate("window.progresoPrueba = {ejercicios: []}")
    pagina.get_by_role("button", name="Actualizar propuesta", exact=True).click()
    expect(seccion.get_by_role("status")).to_contain_text("Todavía no hay cargas")
    expect(seccion.locator("svg")).to_be_hidden()
    expect(pagina.get_by_label("Ejercicio de progreso")).to_be_disabled()
    pagina.evaluate("window.errorProgreso = true")
    pagina.get_by_role("button", name="Actualizar propuesta", exact=True).click()
    expect(seccion.get_by_role("status")).to_contain_text("No se pudo cargar el progreso")

    pagina.set_viewport_size({"width": ancho + 20, "height": 900})
    expect(seccion.get_by_role("status")).to_contain_text("No se pudo cargar el progreso")
    expect(seccion.locator("svg")).to_be_hidden()
