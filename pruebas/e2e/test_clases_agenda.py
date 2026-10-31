"""Configuración de una clase y consulta de la agenda con la semilla ficticia."""

import pytest

expect = pytest.importorskip("playwright.sync_api", reason="sin Playwright").expect
pytestmark = pytest.mark.e2e


def test_configurar_clase_y_ver_agenda_como_socio(pagina_demo, demo_aislada):
    pagina = pagina_demo
    pagina.goto(demo_aislada.url)
    pagina.get_by_role("button", name="Entrar como administración", exact=True).click()
    expect(pagina).to_have_url(f"{demo_aislada.url}/administracion.html")
    pagina.get_by_role("link", name="Clases", exact=True).click()
    expect(pagina.get_by_text("No hay ocurrencias de clase en estas dos semanas.")).to_be_visible()
    pagina.get_by_label("Nombre", exact=True).fill("Clase ficticia de prueba")
    pagina.get_by_label("Día").select_option("2")
    pagina.get_by_label("Hora", exact=True).fill("18:00")
    pagina.get_by_label("Duración en minutos").fill("60")
    pagina.get_by_label("Cupo", exact=True).fill("12")
    pagina.get_by_role("button", name="Guardar clase", exact=True).click()
    expect(pagina.locator("[data-agenda] li")).to_have_count(2)
    expect(pagina.locator("[data-agenda]")).to_contain_text("Cupo: 12")
    pagina.get_by_role("button", name="Cerrar sesión", exact=True).click()
    pagina.get_by_role("button", name="Entrar como socio", exact=True).click()
    expect(pagina.get_by_role("heading", name="Hola, Lucía", exact=True)).to_be_visible()
    pagina.goto(f"{demo_aislada.url}/entrenamiento.html")
    pagina.get_by_role("link", name="Clases", exact=True).click()
    expect(pagina.locator("[data-agenda] li")).to_have_count(2)
    expect(pagina.get_by_role("heading", name="Configurar clases", exact=True)).not_to_be_visible()


def test_reservar_cancelar_y_ver_lista_por_rol(pagina_demo, demo_aislada):
    pagina = pagina_demo

    def entrar(rol):
        pagina.goto(demo_aislada.url)
        pagina.get_by_role("button", name=f"Entrar como {rol}", exact=True).click()
        destino = {"administración": "/administracion.html", "entrenador": "/bandeja.html"}.get(rol)
        if destino:
            expect(pagina).to_have_url(f"{demo_aislada.url}{destino}")
        else:
            expect(pagina.locator("[data-bienvenida]")).to_be_visible()
        pagina.goto(f"{demo_aislada.url}/clases.html")
        expect(pagina.locator("[data-estado]")).to_be_empty()

    def salir():
        pagina.get_by_role("button", name="Cerrar sesión", exact=True).click()
        expect(pagina.get_by_role("button", name="Entrar como socio", exact=True)).to_be_visible()

    entrar("administración")
    pagina.get_by_label("Nombre", exact=True).fill("Clase ficticia con reservas")
    pagina.get_by_label("Día").select_option("2")
    pagina.get_by_label("Hora", exact=True).fill("18:00")
    pagina.get_by_label("Duración en minutos").fill("60")
    pagina.get_by_label("Cupo", exact=True).fill("1")
    pagina.get_by_role("button", name="Guardar clase", exact=True).click()
    expect(pagina.locator("[data-agenda] > li")).to_have_count(2)
    salir()

    entrar("socio")
    primera = pagina.locator("[data-agenda] > li").first
    primera.get_by_role("button", name="Reservar", exact=True).click()
    expect(primera).to_contain_text("Con lugar")
    primera.get_by_role("button", name="Cancelar reserva", exact=True).click()
    expect(primera).to_contain_text("Libres: 1")
    salir()

    entrar("recepción")
    pagina.get_by_label("Buscar socio", exact=True).fill("Lucía")
    pagina.get_by_label("Socio", exact=True).select_option(label="Lucía Benítez")
    expect(primera.get_by_role("button", name="Reservar", exact=True)).to_be_enabled()
    primera.get_by_role("button", name="Reservar", exact=True).click()
    expect(primera).to_contain_text("Con lugar")
    salir()

    entrar("entrenador")
    primera.get_by_role("button", name="Ver reservas", exact=True).click()
    lista = pagina.locator("[data-lista-reservas]")
    expect(lista).to_contain_text("Lucía · Con lugar")
    expect(lista.get_by_role("link")).to_have_count(0)
