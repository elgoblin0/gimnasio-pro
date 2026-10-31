"""Cerrar sesión no deja consultas periódicas que el servidor rechace con 401."""

# Sin ficha: corrige una carrera al cerrar sesión; no cambia ninguna capacidad.

from urllib.parse import urlparse

import pytest

from pruebas.e2e.test_esqueleto_andante import ingresar, preparar

expect = pytest.importorskip("playwright.sync_api").expect
pytestmark = pytest.mark.e2e

PERIODICAS = {"recepcion": {"/api/ocupacion", "/api/visitas"}, "socio": {"/api/ocupacion"}}


@pytest.fixture
def pagina_sin_sw(pagina_demo):
    # Con un service worker activo, Playwright no intercepta los pedidos de la página.
    with pagina_demo.context.browser.new_context(locale="es-PY", service_workers="block") as contexto:
        yield contexto.new_page()


def retener_cierre(pagina):
    """El servidor cierra la sesión, pero la pantalla recibe la respuesta recién cuando se la entrega."""
    retenidos = []

    def retener(ruta):
        if ruta.request.method == "DELETE":
            retenidos.append((ruta, ruta.fetch()))
        else:
            ruta.fallback()

    pagina.route("**/api/sesion", retener)
    return retenidos


def esperar_retencion(pagina, retenidos):
    for _ in range(200):
        if retenidos:
            return
        pagina.wait_for_timeout(25)
    raise AssertionError("El cierre de sesión no llegó al servidor.")


@pytest.mark.parametrize("rol", ["recepcion", "socio"])
def test_un_turno_del_sondeo_durante_el_cierre_no_consulta(pagina_sin_sw, demo_aislada, rol):
    pagina = pagina_sin_sw
    errores = preparar(pagina, 1440, 900)
    pagina.clock.install()
    ingresar(pagina, demo_aislada, rol)
    retenidos = retener_cierre(pagina)
    consultas = []
    pagina.on(
        "request",
        lambda pedido: consultas.append(pedido.url) if urlparse(pedido.url).path in PERIODICAS[rol] else None,
    )
    pagina.get_by_role("button", name="Cerrar sesión", exact=True).click()
    esperar_retencion(pagina, retenidos)
    consultas.clear()
    # Le toca el turno a todos los temporizadores del sondeo; la sesión ya no existe en el servidor.
    pagina.clock.fast_forward(6000)
    # El evento del pedido llega antes que este resultado, así que la lista ya está completa.
    assert pagina.evaluate("fetch('/api/estado').then((respuesta) => respuesta.status)") == 200
    assert consultas == []
    ruta, respuesta = retenidos[0]
    ruta.fulfill(response=respuesta)
    expect(pagina.get_by_role("heading", name="Ingresar", exact=True)).to_be_visible()
    assert errores == []


def test_una_consulta_en_curso_al_cerrar_no_termina_en_error(pagina_sin_sw, demo_aislada):
    pagina = pagina_sin_sw
    errores = preparar(pagina, 1440, 900)
    pagina.clock.install()
    ingresar(pagina, demo_aislada, "socio")
    retenidas = []
    pagina.route("**/api/ocupacion", lambda ruta: retenidas.append(ruta))
    pagina.clock.fast_forward(6000)
    esperar_retencion(pagina, retenidas)
    retenidos = retener_cierre(pagina)
    # El cierre sigue retenido: solo la pantalla, y no la navegación, puede cancelar la consulta.
    with pagina.expect_event("requestfailed", lambda p: urlparse(p.url).path == "/api/ocupacion", timeout=3000):
        pagina.get_by_role("button", name="Cerrar sesión", exact=True).click()
    esperar_retencion(pagina, retenidos)
    ruta, respuesta = retenidos[0]
    ruta.fulfill(response=respuesta)
    expect(pagina.get_by_role("heading", name="Ingresar", exact=True)).to_be_visible()
    assert errores == []
