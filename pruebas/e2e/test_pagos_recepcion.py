"""Administración configura un tipo y recepción registra el pago desde el navegador."""

import re

import pytest

expect = pytest.importorskip("playwright.sync_api").expect
pytestmark = [pytest.mark.e2e, pytest.mark.sin_pagos_ni_clases]


@pytest.mark.parametrize("ancho", [1280, 390])
def test_tipo_de_membresia_y_pago(pagina_demo, demo_aislada, ancho):
    pagina = pagina_demo
    errores = []
    pagina.on("pageerror", lambda error: errores.append(str(error)))
    pagina.set_viewport_size({"width": ancho, "height": 900})
    pagina.goto(demo_aislada.url)
    pagina.get_by_role("button", name="Entrar como administración", exact=True).click()
    pagina.wait_for_url("**/administracion.html")
    tipos = pagina.locator("#tipos-membresia")
    expect(tipos.locator("[data-tipos-estado]")).to_contain_text("No hay tipos")
    tipos.get_by_label("Nombre", exact=True).fill("Mensual ficticia")
    tipos.get_by_label("Duración en días").fill("30")
    tipos.get_by_label("Precio en guaraníes").fill("250000")
    tipos.get_by_role("button", name="Crear tipo de membresía", exact=True).click()
    expect(tipos.locator("[data-tipos-lista]")).to_contain_text("Mensual ficticia · 30 días · ₲ 250.000")
    tipos.get_by_role("button", name="Editar", exact=True).click()
    tipos.get_by_label("Precio en guaraníes").fill("270000")
    tipos.get_by_role("button", name="Guardar tipo de membresía", exact=True).click()
    expect(tipos.locator("[data-tipos-lista]")).to_contain_text("₲ 270.000")
    pagina.get_by_role("button", name="Cerrar sesión").click()
    pagina.get_by_role("button", name="Entrar como recepción", exact=True).click()
    pagina.get_by_role("link", name="Ir a recepción").click()
    pagina.get_by_role("link", name="Pagos", exact=True).click()
    expect(pagina.locator("[data-pago]")).to_be_visible()
    pagina.get_by_label("Buscar socio por nombre o cédula").fill("xxxxxxxx")
    expect(pagina.locator("[data-socios-estado]")).to_have_text("No hay socios para esa búsqueda.")
    pagina.get_by_label("Buscar socio por nombre o cédula").fill("Lucía")
    pagina.get_by_label("Socio", exact=True).select_option(index=1)
    pagina.get_by_label("Tipo de membresía", exact=True).select_option(index=1)
    expect(pagina.locator("[data-precio]")).to_contain_text("₲ 270.000")
    pagina.get_by_label("Medio de pago").select_option("transferencia")
    pagina.get_by_role("button", name="Registrar pago y renovar").click()
    expect(pagina.locator("[data-resultado]")).to_have_text(
        re.compile(r"Pago registrado: ₲ 270\.000\. Membresía del \d{2}/\d{2}/\d{4} al \d{2}/\d{2}/\d{4}\.")
    )
    assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert errores == []
