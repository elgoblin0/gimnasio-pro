"""Etapa 5: clases, recepción y administración con la semilla de la etapa, en varios contextos de navegador."""

import pytest
from playwright.sync_api import expect

from gimnasio.comun.bd import transaccion
from gimnasio.demo.servicio import CLASE_LLENA

pytestmark = pytest.mark.e2e


def entrar_como(contexto, demo, boton):
    pagina = contexto.new_page()
    pagina.goto(demo.url)
    pagina.get_by_role("button", name=boton, exact=True).click()
    return pagina


def elegir_socio(recepcion, nombre):
    opcion = recepcion.locator("#socio option").filter(has_text=nombre)
    expect(opcion).to_have_count(1)
    recepcion.locator("#socio").select_option(label=opcion.text_content())


def posicion_en_la_agenda(pagina, estado):
    """La clase llena aparece dos semanas seguidas; la que tiene a este socio en `estado` es una sola."""
    expect(pagina.locator("[data-agenda] li").first).to_be_visible()
    return pagina.locator("[data-agenda] li").evaluate_all(
        "(tarjetas, [clase, estado]) => "
        "tarjetas.findIndex(t => t.textContent.includes(clase) && t.textContent.includes(estado))",
        [CLASE_LLENA, estado],
    )


def contar(demo, consulta):
    with demo.app.app_context(), transaccion() as cursor:
        cursor.execute(consulta)
        return cursor.fetchone()["n"]


def test_lucia_cancela_y_hugo_ve_su_lugar_sin_recargar(navegador, demo_aislada):
    with (
        navegador.new_context(locale="es-PY") as contexto_lucia,
        navegador.new_context(locale="es-PY") as contexto_hugo,
    ):
        hugo = entrar_como(contexto_hugo, demo_aislada, "Entrar como Hugo Rolón")
        expect(hugo.locator("[data-bienvenida]")).to_be_visible()
        hugo.goto(f"{demo_aislada.url}/clases.html")
        indice = posicion_en_la_agenda(hugo, "En espera")
        assert indice >= 0
        clase_de_hugo = hugo.locator("[data-agenda] li").nth(indice)
        expect(clase_de_hugo).to_contain_text("En espera · Posición 1")

        lucia = entrar_como(contexto_lucia, demo_aislada, "Entrar como socio")
        expect(lucia.locator("[data-bienvenida]")).to_be_visible()
        lucia.goto(f"{demo_aislada.url}/clases.html")
        assert posicion_en_la_agenda(lucia, "Con lugar") == indice
        clase_de_lucia = lucia.locator("[data-agenda] li").nth(indice)
        expect(clase_de_lucia).to_contain_text("Con lugar")
        clase_de_lucia.get_by_role("button", name="Cancelar reserva", exact=True).click()
        expect(clase_de_lucia).not_to_contain_text("Con lugar")

        # Hugo no recarga: el sondeo de su agenda trae el cambio.
        expect(clase_de_hugo).to_contain_text("Con lugar", timeout=15000)
        reservas = "SELECT COUNT(*) AS n FROM reservas"
        total = contar(demo_aislada, reservas)
        hugo.reload()
        expect(clase_de_hugo).to_contain_text("Con lugar")
        assert contar(demo_aislada, reservas) == total

        hugo.goto(demo_aislada.url)
        expect(hugo.locator("[data-avisos-lista] li").filter(has_text="Pasaste a tener lugar")).to_be_visible()


def test_recepcion_rechaza_la_entrada_vencida_cobra_y_registra_la_entrada(navegador, demo_aislada):
    with demo_aislada.app.app_context(), transaccion() as cursor:
        cursor.execute(
            "SELECT p.nombre, p.apellido FROM membresias m JOIN usuarios u ON u.id=m.socio_id "
            "JOIN personas p ON p.id=u.persona_id WHERE NOT p.simulada AND m.hasta < DATE(%s)",
            (demo_aislada.app.extensions["reloj"].ahora(),),
        )
        vencidos = cursor.fetchall()
    assert len(vencidos) == 1
    nombre = f"{vencidos[0]['nombre']} {vencidos[0]['apellido']}"

    with navegador.new_context(locale="es-PY") as contexto:
        rocio = entrar_como(contexto, demo_aislada, "Entrar como recepción")
        rocio.get_by_role("link", name="Ir a recepción", exact=True).click()
        expect(rocio.get_by_text("Recepción lista.", exact=True)).to_be_visible()
        elegir_socio(rocio, nombre)
        tarjeta = rocio.locator("[data-tarjeta-contextual]")
        expect(tarjeta).to_contain_text("Membresía vencida")
        expect(tarjeta).to_contain_text("Pago pendiente")
        rocio.locator("[data-entrada]").get_by_role("button", name="Registrar entrada", exact=True).click()
        expect(rocio.locator("[data-error]")).to_contain_text("membresía vigente")
        expect(rocio.locator("[data-estado]")).to_have_text("La operación fue rechazada.")
        entradas = "SELECT COUNT(*) AS n FROM entradas"
        antes = contar(demo_aislada, entradas)

        tarjeta.get_by_role("button", name="Registrar pago", exact=True).click()
        formulario = rocio.frame_locator("[data-pago-tarjeta]")
        formulario.get_by_label("Tipo de membresía", exact=True).select_option(index=1)
        formulario.get_by_role("button", name="Registrar pago y renovar").click()
        expect(tarjeta).to_contain_text("Membresía vigente")
        expect(tarjeta).not_to_contain_text("Pago pendiente")
        pagos = contar(demo_aislada, "SELECT COUNT(*) AS n FROM pagos")
        rocio.reload()
        assert contar(demo_aislada, "SELECT COUNT(*) AS n FROM pagos") == pagos

        # La tarjeta ya no está abierta tras recargar; el socio sigue elegible sin volver a buscarlo en la lista.
        elegir_socio(rocio, nombre)
        tarjeta.get_by_role("button", name="Registrar entrada", exact=True).click()
        expect(rocio.get_by_text("Entrada registrada.", exact=True)).to_be_visible()
        expect(rocio.get_by_role("button", name=f"Registrar salida de {nombre}")).to_be_visible()
        assert contar(demo_aislada, entradas) == antes + 1


def test_administracion_da_de_alta_asigna_a_marcos_y_marcos_lo_ve(navegador, demo_aislada):
    with (
        navegador.new_context(locale="es-PY") as contexto_admin,
        navegador.new_context(locale="es-PY") as contexto_marcos,
    ):
        admin = entrar_como(contexto_admin, demo_aislada, "Entrar como administración")
        admin.wait_for_url("**/administracion.html")
        admin.goto(f"{demo_aislada.url}/pagos.html?alta=1")
        formulario = admin.locator("[data-pago]")
        formulario.get_by_label("Nombre", exact=True).fill("Socia")
        formulario.get_by_label("Apellido", exact=True).fill("Nueva Ficticia")
        formulario.get_by_label("Cédula", exact=True).fill("8899900")
        formulario.get_by_label("El socio otorga su consentimiento", exact=False).check()
        formulario.get_by_label("Registrar primer pago (opcional)", exact=False).check()
        formulario.get_by_label("Tipo de membresía", exact=True).select_option(index=1)
        formulario.get_by_role("button", name="Dar de alta socio", exact=True).click()
        expect(admin.locator("[data-resultado]")).to_contain_text("Socio dado de alta")
        altas = "SELECT COUNT(*) AS n FROM personas WHERE cedula='8899900'"
        assert contar(demo_aislada, altas) == 1
        pagos = "SELECT COUNT(*) AS n FROM pagos"
        total_pagos = contar(demo_aislada, pagos)
        admin.reload()
        assert contar(demo_aislada, altas) == 1
        assert contar(demo_aislada, pagos) == total_pagos

        admin.goto(f"{demo_aislada.url}/administracion.html")
        panel = admin.locator("#usuarios")
        socio = panel.locator("[data-sin-entrenador] li").filter(has_text="Socia Nueva Ficticia")
        socio.get_by_role("combobox").select_option(label="Marcos Giménez")
        socio.get_by_role("button", name="Asignar entrenador").click()
        expect(panel).to_contain_text("Entrenador asignado.")

        marcos = entrar_como(contexto_marcos, demo_aislada, "Entrar como entrenador")
        marcos.wait_for_url("**/bandeja.html")
        socios = marcos.evaluate("fetch('/api/entrenador/socios').then(r => r.json())")["socios"]
        assert "Socia Nueva Ficticia" in {f"{s['nombre']} {s['apellido']}" for s in socios}


def test_agenda_con_movimiento_reducido_sin_animar_la_subida_de_hugo(navegador, demo_aislada):
    with (
        navegador.new_context(locale="es-PY", reduced_motion="reduce") as contexto_hugo,
        navegador.new_context(locale="es-PY") as contexto_lucia,
    ):
        hugo = entrar_como(contexto_hugo, demo_aislada, "Entrar como Hugo Rolón")
        expect(hugo.locator("[data-bienvenida]")).to_be_visible()
        hugo.goto(f"{demo_aislada.url}/clases.html")
        indice = posicion_en_la_agenda(hugo, "En espera")
        clase_de_hugo = hugo.locator("[data-agenda] li").nth(indice)
        lucia = entrar_como(contexto_lucia, demo_aislada, "Entrar como socio")
        expect(lucia.locator("[data-bienvenida]")).to_be_visible()
        lucia.goto(f"{demo_aislada.url}/clases.html")
        expect(lucia.locator("[data-agenda] li").nth(indice)).to_contain_text("Con lugar")
        lucia.locator("[data-agenda] li").nth(indice).get_by_role("button", name="Cancelar reserva", exact=True).click()
        expect(clase_de_hugo).to_contain_text("Con lugar", timeout=15000)
        expect(hugo.locator("[data-anuncio]")).to_contain_text("Ya tenés lugar")
        assert hugo.evaluate("document.getAnimations().length") == 0


@pytest.mark.parametrize("pantalla", ["/clases.html", "/ficha.html"])
def test_agenda_y_mi_ficha_en_celular_sin_desborde(navegador, demo_aislada, pantalla):
    with navegador.new_context(locale="es-PY", viewport={"width": 360, "height": 740}) as contexto:
        hugo = entrar_como(contexto, demo_aislada, "Entrar como Hugo Rolón")
        expect(hugo.locator("[data-bienvenida]")).to_be_visible()
        hugo.goto(demo_aislada.url + pantalla)
        if pantalla == "/clases.html":
            expect(hugo.locator("[data-agenda] li").first).to_be_visible()
        else:
            expect(hugo.locator("[data-consentimientos]")).to_contain_text("Consentimiento otorgado.")
            expect(hugo.locator("[data-consultas-ficha]")).to_contain_text("Consultas de ficha")
        assert hugo.evaluate("document.documentElement.scrollWidth <= innerWidth")
