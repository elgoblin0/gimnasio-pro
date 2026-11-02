"""Portada de espera de la demo: abre la app cuando despierta, sin servidor propio."""

# Sin ficha: se publica aparte de la app y no cambia ninguna de sus capacidades.

from pathlib import Path

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

DEMO = "https://gimnasio-pro-demo.onrender.com"
ARCHIVO = Path(__file__).resolve().parents[2] / "demo-espera" / "index.html"
PORTADA = ARCHIVO.as_uri()
# PNG de 1×1: la portada solo necesita que la imagen cargue.
PIXEL = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082"
)


def responder_dormida(ruta):
    ruta.fulfill(status=503, content_type="text/html", body="<title>Render</title>")


def test_abre_la_demo_cuando_la_imagen_ya_carga(page):
    intentos = []

    def atender(ruta):
        if "/iconos/" not in ruta.request.url:
            ruta.fulfill(status=200, content_type="text/html", body="<title>Demo lista</title>")
        elif len(intentos) < 2:
            intentos.append(ruta.request.url)
            responder_dormida(ruta)
        else:
            ruta.fulfill(status=200, content_type="image/png", body=PIXEL)

    page.route(f"{DEMO}/**", atender)
    page.goto(PORTADA)
    expect(page.get_by_role("status")).to_contain_text("demo")
    expect(page).to_have_url(f"{DEMO}/", timeout=15_000)
    expect(page).to_have_title("Demo lista")
    assert len(set(intentos)) == 2, "cada intento evita la caché del anterior"


def test_si_tarda_mucho_avisa_y_ofrece_abrirla(page):
    page.clock.install()
    page.route(f"{DEMO}/**", responder_dormida)
    page.goto(PORTADA)
    enlace = page.get_by_role("link", name="Abrir la demo ahora")
    expect(enlace).to_be_hidden()
    page.clock.fast_forward(5_000)
    expect(page.get_by_role("status")).to_have_text("Despertando la demo…")
    page.clock.fast_forward(90_000)
    expect(page.get_by_role("status")).to_have_text("Está tardando más de lo habitual. Seguimos intentando.")
    expect(enlace).to_be_visible()
    expect(enlace).to_have_attribute("href", f"{DEMO}/")


def test_no_depende_de_nada_fuera_de_su_carpeta():
    html = ARCHIVO.read_text(encoding="utf-8")
    assert "<link" not in html
    assert "<script src" not in html
