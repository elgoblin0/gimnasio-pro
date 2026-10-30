"""La figura del cuerpo 3D se elige en la pantalla y queda en la cuenta (ADR 0020)."""

import pytest
from playwright.sync_api import expect

from pruebas.e2e.test_esqueleto_andante import ingresar

pytestmark = pytest.mark.e2e


def abrir_dolor(pagina):
    if pagina.locator("[data-chequeo]").is_visible():
        pagina.get_by_role("button", name="Saltear", exact=True).click()
    if pagina.get_by_role("button", name="Iniciar sesión realizada", exact=True).is_visible():
        pagina.get_by_role("button", name="Iniciar sesión realizada", exact=True).click()
    expect(pagina.locator("[data-sesion-actual]")).to_be_visible()
    pagina.get_by_role("button", name="Me duele durante Sentadilla ficticia", exact=True).click()
    formulario = pagina.locator(
        "[data-ejercicio]", has=pagina.get_by_role("heading", name="Sentadilla ficticia", exact=True)
    ).locator("[data-dolor] form")
    expect(formulario).to_have_attribute("data-cuerpo3d", "listo")
    return formulario


def test_lucia_ve_su_figura_y_puede_cambiarla_sin_perder_lo_marcado(demo_aislada, playwright):
    with (
        playwright.chromium.launch(channel="chromium") as navegador,
        navegador.new_context(locale="es-PY", viewport={"width": 390, "height": 844}) as contexto,
    ):
        pagina = contexto.new_page()
        modelos = []
        pagina.on("response", lambda r: modelos.append(r.url) if "/vendor/cuerpo@2/" in r.url else None)
        errores = []
        pagina.on("pageerror", lambda e: errores.append(str(e)))
        ingresar(pagina, demo_aislada, "socio")
        formulario = abrir_dolor(pagina)
        figura = formulario.get_by_role("group", name="Figura del cuerpo", exact=True)
        expect(figura.get_by_role("button", name="Femenina", exact=True)).to_have_attribute("aria-pressed", "true")
        assert modelos[-1].endswith("/femenina.glb")

        formulario.get_by_role("button", name="Ver todas las zonas", exact=True).click()
        rodillas = formulario.get_by_role("checkbox", name="Rodillas", exact=True)
        rodillas.click()
        figura.get_by_role("button", name="Masculina", exact=True).click()
        expect(figura.get_by_role("button", name="Masculina", exact=True)).to_have_attribute("aria-pressed", "true")
        pagina.wait_for_function(
            "fetch('/api/sesion').then(r => r.json()).then(d => d.usuario.figura_cuerpo === 'masculina')"
        )
        assert modelos[-1].endswith("/masculina.glb")
        expect(rodillas).to_have_attribute("aria-checked", "true")
        expect(formulario.get_by_text("No se pudo cambiar la figura", exact=False)).to_have_count(0)

        pagina.reload()
        formulario = abrir_dolor(pagina)
        expect(
            formulario.get_by_role("group", name="Figura del cuerpo", exact=True).get_by_role(
                "button", name="Masculina", exact=True
            )
        ).to_have_attribute("aria-pressed", "true")
        assert errores == []
