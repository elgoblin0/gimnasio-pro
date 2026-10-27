"""Ingreso real y modo demo con Cuaderno de entrenamiento, teclado y movimiento reducido."""

from pathlib import Path
from threading import Thread

import pytest
from werkzeug.serving import make_server

from gimnasio.comun.bd import transaccion
from gimnasio.permisos.servicio import crear_usuario

expect = pytest.importorskip("playwright.sync_api", reason="sin Playwright: instalá requirements-dev.txt").expect

pytestmark = [pytest.mark.bd, pytest.mark.e2e]


@pytest.fixture
def url_ingreso(app_con_bd, modo_demo):
    """Cada recorrido tiene su propia base y servidor, incluidos los límites de uso de la demo."""
    app_con_bd.config["MODO_DEMO"] = modo_demo
    with app_con_bd.app_context(), transaccion() as cursor:
        crear_usuario(
            cursor,
            {"nombre": "Lucía" if modo_demo else "Ana", "apellido": "Prueba", "cedula": "9900001"},
            "socio",
            clave=None if modo_demo else "clave-solo-e2e",
            es_demo=modo_demo,
        )
    with make_server("127.0.0.1", 0, app_con_bd) as servidor:
        hilo = Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        try:
            yield f"http://127.0.0.1:{servidor.server_port}"
        finally:
            servidor.shutdown()
            hilo.join()


@pytest.fixture(scope="session")
def navegador_ingreso(playwright):
    if not Path(playwright.chromium.executable_path).is_file():
        pytest.skip("sin Chromium: ejecutá playwright install chromium")
    with playwright.chromium.launch(channel="chromium") as navegador:
        yield navegador


def sin_desborde(pagina):
    assert pagina.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


def avanzar_con_foco(pagina, control):
    pagina.keyboard.press("Tab")
    expect(control).to_be_focused()
    expect(control).to_have_css("outline-style", "solid")
    expect(control).to_have_css("outline-width", "3px")


@pytest.mark.parametrize("modo_demo", [False, True], ids=["real", "demo"])
@pytest.mark.parametrize("esquema", ["light", "dark"], ids=["claro", "oscuro"])
@pytest.mark.parametrize("ancho", [1440, 768, 390])
def test_ingreso_en_b_claro_y_oscuro_con_teclado_sin_desborde(
    navegador_ingreso, url_ingreso, modo_demo, esquema, ancho
):
    with navegador_ingreso.new_context(
        locale="es-PY", viewport={"width": ancho, "height": 900}, color_scheme=esquema, reduced_motion="reduce"
    ) as contexto:
        pagina = contexto.new_page()
        errores = []
        pagina.on("console", lambda mensaje: errores.append(mensaje.text) if mensaje.type == "error" else None)
        pagina.on("pageerror", lambda error: errores.append(str(error)))
        pagina.goto(url_ingreso)
        expect(pagina.locator("html")).to_have_attribute("data-direccion", "b")
        expect(pagina.locator("html")).to_have_css("color-scheme", esquema)
        fondo = "rgb(22, 19, 15)" if esquema == "dark" else "rgb(251, 247, 240)"
        expect(pagina.locator("body")).to_have_css("background-color", fondo)
        expect(pagina.get_by_role("heading", name="Ingresar", exact=True)).to_be_visible()
        sin_desborde(pagina)

        identificador = pagina.get_by_label("Cédula o correo")
        clave = pagina.get_by_label("Clave", exact=True)
        avanzar_con_foco(pagina, identificador)
        foco = "rgb(124, 196, 160)" if esquema == "dark" else "rgb(31, 90, 67)"
        expect(identificador).to_have_css("outline-color", foco)
        if not modo_demo:
            pagina.keyboard.insert_text("9900001")
        avanzar_con_foco(pagina, clave)
        if not modo_demo:
            pagina.keyboard.insert_text("clave-solo-e2e")
        avanzar_con_foco(pagina, pagina.get_by_role("button", name="Entrar", exact=True))
        if modo_demo:
            avanzar_con_foco(pagina, pagina.get_by_role("button", name="Entrar como socio", exact=True))
        else:
            expect(pagina.get_by_role("button", name="Entrar como socio", exact=True)).to_be_hidden()
        pagina.keyboard.press("Enter")
        nombre = "Lucía" if modo_demo else "Ana"
        expect(pagina.get_by_role("heading", name=f"Hola, {nombre}", exact=True)).to_be_visible()
        sin_desborde(pagina)
        salir = pagina.get_by_role("button", name="Salir", exact=True)
        avanzar_con_foco(pagina, salir)
        pagina.keyboard.press("Enter")
        expect(pagina.get_by_role("heading", name="Ingresar", exact=True)).to_be_visible()
        sin_desborde(pagina)

        duraciones = pagina.locator("html").evaluate(
            "elemento => [1, 2, 3].map(n => getComputedStyle(elemento).getPropertyValue(`--duracion-${n}`).trim())"
        )
        assert duraciones == ["0ms", "0ms", "0ms"]
        assert errores == [], "Errores del navegador: " + "\n".join(errores)
