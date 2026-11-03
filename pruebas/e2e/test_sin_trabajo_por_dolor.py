"""El dolor que deja una sesión sin ejercicios no abre una sesión vacía: avisa al entrenador."""

# Sin ficha: corrige un estado de la pantalla de entrenamiento; no cambia ninguna capacidad.

import pytest
from playwright.sync_api import expect

from gimnasio.comun.bd import transaccion
from pruebas.e2e.test_esqueleto_andante import ingresar, preparar

pytestmark = pytest.mark.e2e

# Sin WebGL queda la silueta SVG, con todas las zonas a mano: el 3D no es lo que se prueba acá.
SIN_WEBGL = (
    "const original = HTMLCanvasElement.prototype.getContext;"
    "HTMLCanvasElement.prototype.getContext = function(tipo, ...opciones) {"
    "return tipo.startsWith('webgl') ? null : original.call(this, tipo, ...opciones); };"
)


def entrar_como_socio(pagina, demo):
    errores = preparar(pagina, 1440, 900)
    pagina.add_init_script(SIN_WEBGL)
    ingresar(pagina, demo, "socio")
    return errores


def guardar_chequeo_con_dolor(pagina, *zonas):
    pagina.get_by_role("group", name="Sueño", exact=True).get_by_role("radio", name="4", exact=True).check()
    pagina.get_by_role("group", name="Energía", exact=True).get_by_role("radio", name="4", exact=True).check()
    selector = pagina.locator("[data-zonas-chequeo]")
    for zona in zonas:
        selector.get_by_role("checkbox", name=zona, exact=True).locator("text").click()
    pagina.get_by_role("button", name="Guardar chequeo del día", exact=True).click()
    expect(pagina.get_by_text("Chequeo guardado.", exact=True)).to_be_visible()


def contar_avisos(demo):
    with demo.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT COUNT(*) AS total FROM avisos_entrenador WHERE freno='dolor_reportado'")
        return cursor.fetchone()["total"]


def test_con_dolor_en_las_piernas_queda_el_tren_superior(pagina_demo, demo_aislada):
    pagina = pagina_demo
    errores = entrar_como_socio(pagina, demo_aislada)
    guardar_chequeo_con_dolor(pagina, "Cuádriceps")

    expect(pagina.locator("[data-ejercicio]").filter(has_text="Quitado por hoy")).to_have_count(3)
    expect(pagina.locator("[data-ejercicio]").filter(has_text="Press con mancuernas ficticio")).to_contain_text(
        "2 series"
    )
    expect(pagina.get_by_role("button", name="Empezar sesión", exact=True)).to_be_visible()
    expect(pagina.locator("[data-sin-trabajo]")).to_be_hidden()
    assert errores == []


def test_sin_ningun_ejercicio_se_avisa_al_entrenador(pagina_demo, demo_aislada):
    pagina = pagina_demo
    errores = entrar_como_socio(pagina, demo_aislada)
    avisos_antes = contar_avisos(demo_aislada)
    guardar_chequeo_con_dolor(pagina, "Cuádriceps", "Pecho")

    expect(pagina.locator("[data-ejercicio]").filter(has_text="Quitado por hoy")).to_have_count(4)
    expect(pagina.locator("[data-ejercicio]").first).not_to_contain_text("0 series")
    expect(pagina.locator("[data-ejercicio]").filter(has_text="Se respeta el plan")).to_have_count(0)
    expect(pagina.locator("[data-ejercicio]").filter(has_text="Se quita el ejercicio")).to_have_count(4)
    expect(pagina.get_by_role("button", name="Empezar sesión", exact=True)).to_be_hidden()
    expect(pagina.locator("[data-sin-trabajo]")).to_contain_text("Hoy no hay ejercicios")
    # Todavía nadie avisó: el aviso nace al abrir la sesión.
    assert contar_avisos(demo_aislada) == avisos_antes

    pagina.get_by_role("button", name="Avisar a mi entrenador", exact=True).click()
    expect(pagina.get_by_text("Aviso enviado a tu entrenador.", exact=True)).to_be_visible()
    expect(pagina.locator("[data-sin-trabajo]")).to_contain_text("Tu entrenador ya tiene el aviso")
    expect(pagina.get_by_role("button", name="Avisar a mi entrenador", exact=True)).to_be_hidden()
    expect(pagina.locator("[data-registro]")).to_be_hidden()
    assert contar_avisos(demo_aislada) == avisos_antes + 1

    pagina.reload()
    expect(pagina.locator("[data-sin-trabajo]")).to_contain_text("Tu entrenador ya tiene el aviso")
    expect(pagina.locator("[data-registro]")).to_be_hidden()
    expect(pagina.get_by_role("button", name="Empezar sesión", exact=True)).to_be_hidden()
    assert errores == []
