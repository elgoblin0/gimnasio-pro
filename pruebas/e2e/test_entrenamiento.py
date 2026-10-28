"""Pantalla del socio: propuesta real y estados aislados, en tres anchos y ambos temas."""

import json

import pytest

expect = pytest.importorskip("playwright.sync_api").expect
pytestmark = pytest.mark.e2e


def ingresar(pagina, instancia):
    pagina.goto(instancia.url)
    pagina.get_by_role("button", name="Entrar como socio", exact=True).click()
    pagina.get_by_role("link", name="Ver mi entrenamiento", exact=True).click()


@pytest.mark.parametrize("ancho", [1440, 768, 390])
@pytest.mark.parametrize("tema", ["light", "dark"])
def test_propuesta_explicacion_recarga_y_cierre(pagina_demo, demo_aislada, programa_demo, ancho, tema):
    pagina = pagina_demo
    pagina.set_viewport_size({"width": ancho, "height": 900 if ancho > 390 else 844})
    pagina.emulate_media(color_scheme=tema, reduced_motion="reduce")
    errores = []
    pagina.on("pageerror", lambda error: errores.append(str(error)))
    pagina.on("console", lambda mensaje: errores.append(mensaje.text) if mensaje.type == "error" else None)
    ingresar(pagina, demo_aislada)
    expect(pagina.get_by_role("heading", name="Fuerza y cardio", exact=True)).to_be_visible()
    expect(pagina.get_by_text("2 series · 8–12 reps · 20,50 kg", exact=True)).to_be_visible()
    expect(pagina.get_by_text("1 serie · 120 s · 1.500,25 m", exact=True)).to_be_visible()
    expect(pagina.locator("[data-ajuste]").first).to_contain_text(
        "Se respeta el plan del entrenador sin ajustes de carga, repeticiones, series ni volumen."
    )
    expect(pagina.get_by_text("27/10/2026", exact=True)).to_be_visible()
    expect(pagina.locator("[data-contenido]")).to_have_attribute("data-version-reglas", "2.1.0")
    assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth")
    pagina.get_by_role("button", name="Actualizar propuesta", exact=True).focus()
    pagina.keyboard.press("Enter")
    expect(pagina.get_by_text("Propuesta actualizada.", exact=True)).to_be_visible()
    pagina.reload()
    expect(pagina.get_by_role("heading", name="Fuerza y cardio", exact=True)).to_be_visible()
    pagina.get_by_role("button", name="Cerrar sesión", exact=True).click()
    expect(pagina.get_by_role("heading", name="Ingresar", exact=True)).to_be_visible()
    assert pagina.request.get(demo_aislada.url + "/api/entrenamiento/propuesta").status == 401
    assert errores == []


@pytest.mark.parametrize(
    "regla,titulo,mensaje",
    [
        ("sin_programa", "Sin programa de entrenamiento", "No hay programa de entrenamiento para proponer una sesión."),
        (
            "secuencia_realizada",
            "Secuencia realizada",
            "No queda trabajo pendiente en la secuencia del programa; no se reinicia automáticamente.",
        ),
    ],
)
def test_estados_vacios_con_respuesta_controlada(pagina_demo, demo_aislada, regla, titulo, mensaje):
    datos = {
        "sesion_planificada": None,
        "ejercicios": [],
        "explicacion": [{"regla": regla, "version": "2.1.0", "datos": {"explicacion": mensaje}}],
        "version_reglas": "2.1.0",
        "fecha_local": "2026-10-27",
        "semana_local": "2026-10-26",
    }
    pagina_demo.add_init_script(
        """(() => {
        const original = window.fetch;
        window.fetch = (ruta, opciones) => ruta === '/api/entrenamiento/propuesta'
            ? Promise.resolve(new Response(JSON.stringify(DATOS), {
                status:200,headers:{'Content-Type':'application/json'}
              }))
            : original(ruta, opciones);
    })();""".replace("DATOS", json.dumps(datos))
    )
    ingresar(pagina_demo, demo_aislada)
    expect(pagina_demo.get_by_role("heading", name=titulo, exact=True)).to_be_visible()
    expect(pagina_demo.get_by_text(mensaje, exact=True)).to_be_visible()


def test_error_legible_y_reintento_recupera_propuesta_real(pagina_demo, demo_aislada, programa_demo):
    pagina_demo.add_init_script("""(() => {
        const original = window.fetch;
        let fallar = true;
        window.fetch = (ruta, opciones) => {
            if (ruta === '/api/entrenamiento/propuesta' && fallar) {
                fallar = false;
                const error = {error:{codigo:'prueba',mensaje:'No se pudo leer la propuesta.'}};
                return Promise.resolve(new Response(JSON.stringify(error), {
                    status:503,headers:{'Content-Type':'application/json'}
                }));
            }
            return original(ruta, opciones);
        };
    })();""")
    ingresar(pagina_demo, demo_aislada)
    expect(pagina_demo.get_by_role("alert")).to_have_text("No se pudo leer la propuesta.")
    pagina_demo.get_by_role("button", name="Actualizar propuesta", exact=True).click()
    expect(pagina_demo.get_by_role("heading", name="Fuerza y cardio", exact=True)).to_be_visible()
    expect(pagina_demo.get_by_role("alert")).to_be_empty()
