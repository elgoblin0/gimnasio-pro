"""Caché pública, red obligatoria y actualización sin perder formularios, sin MySQL."""

import json
import re
from pathlib import Path
from threading import Thread

import pytest
from flask import request
from werkzeug.serving import make_server

from gimnasio import crear_app

expect = pytest.importorskip("playwright.sync_api", reason="sin Playwright: instalá requirements-dev.txt").expect

pytestmark = pytest.mark.e2e
ESTATICOS = Path(__file__).resolve().parents[2] / "gimnasio/static"


@pytest.fixture
def servidor_pwa():
    app = crear_app({"ENTORNO": "prueba", "SECRET_KEY": "solo-e2e-pwa", "MODO_DEMO": False})
    escrituras = []

    @app.before_request
    def contar_escrituras():
        if request.path == "/api/sesion" and request.method != "GET":
            escrituras.append(request.method)

    @app.after_request
    def version_del_sw(respuesta):
        if request.path == "/sw.js":
            # La versión cambia en memoria: simula un archivo nuevo incluso ante una petición condicional.
            respuesta.direct_passthrough = False
            respuesta.status_code = 200
            respuesta.set_data(
                (ESTATICOS / "sw.js")
                .read_text(encoding="utf-8")
                .replace('const VERSION = "1";', f'const VERSION = "{app.config["VERSION_PWA"]}";')
            )
            respuesta.headers.pop("ETag", None)
            respuesta.headers.pop("Last-Modified", None)
        return respuesta

    app.config["VERSION_PWA"] = "1"
    with make_server("127.0.0.1", 0, app) as servidor:
        hilo = Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        try:
            yield f"http://127.0.0.1:{servidor.server_port}", app, escrituras
        finally:
            servidor.shutdown()
            hilo.join()


@pytest.fixture
def contexto_pwa(playwright):
    if not Path(playwright.chromium.executable_path).is_file():
        pytest.skip("sin Chromium: ejecutá playwright install chromium")
    with playwright.chromium.launch(channel="chromium") as navegador, navegador.new_context(locale="es-PY") as contexto:
        yield contexto


def abrir_controlada(contexto, url):
    pagina = contexto.new_page()
    pagina.goto(url)
    pagina.wait_for_function("navigator.serviceWorker.controller !== null")
    expect(pagina.get_by_role("heading", name="Ingresar", exact=True)).to_be_visible()
    return pagina


def contenido_cache(pagina):
    return pagina.evaluate("""async () => {
      const resultado = {};
      for (const nombre of await caches.keys()) {
        const cache = await caches.open(nombre);
        resultado[nombre] = (await cache.keys()).map(s => new URL(s.url).pathname).sort();
      }
      return resultado;
    }""")


def test_controla_raiz_y_cachea_solo_la_lista_publica(contexto_pwa, servidor_pwa):
    url, _, _ = servidor_pwa
    pagina = abrir_controlada(contexto_pwa, url)
    assert pagina.evaluate("navigator.serviceWorker.controller.scriptURL") == url + "/sw.js"
    assert pagina.evaluate("async () => (await navigator.serviceWorker.ready).scope") == url + "/"
    lista = json.loads(
        re.search(r"const RECURSOS_ESTATICOS = (\[.*?\]);", (ESTATICOS / "sw.js").read_text(encoding="utf-8"), re.S)[
            1
        ].replace(",\n]", "\n]")
    )
    assert contenido_cache(pagina) == {"gimnasio-estaticos-1": sorted(lista)}
    # Cada recurso actual de ejecución está en la lista inicial. Excluye HTML, SW, pruebas y documentación.
    existentes = {
        "/" + archivo.relative_to(ESTATICOS).as_posix()
        for archivo in ESTATICOS.rglob("*")
        if archivo.is_file()
        and archivo.suffix in {".js", ".css", ".png", ".webmanifest"}
        and not archivo.name.endswith(".test.js")
        and archivo.name != "sw.js"
    }
    assert set(lista) == existentes
    pagina.evaluate("""async () => {
      for (const ruta of ['/api/sesion', '/api/estado', '/index.html', '/js/inicio.js?otra=1']) await fetch(ruta);
    }""")
    assert contenido_cache(pagina) == {"gimnasio-estaticos-1": sorted(lista)}
    assert pagina.evaluate("async () => (await indexedDB.databases()).length") == 0


def test_api_y_escrituras_sin_red_no_se_guardan_ni_reenvian(contexto_pwa, servidor_pwa):
    url, _, escrituras = servidor_pwa
    pagina = abrir_controlada(contexto_pwa, url)
    cache_inicial = contenido_cache(pagina)
    # Se solicita estando en línea antes de cortar la red: tampoco vale la caché HTTP.
    assert pagina.evaluate("async () => (await fetch('/api/sesion')).status") == 200
    contexto_pwa.set_offline(True)
    resultados = pagina.evaluate("""async () => {
      const { llamarApi } = await import('/js/comun/api.js');
      const resultados = [];
      for (const metodo of ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']) {
        try {
          await llamarApi('/api/sesion', { metodo, cuerpo: metodo === 'GET' ? undefined : {} });
          resultados.push('éxito inesperado');
        } catch (error) { resultados.push(error.codigo); }
      }
      return resultados;
    }""")
    assert resultados == ["conexion_requerida"] * 5
    pagina.get_by_label("Cédula o correo").fill("9900001")
    pagina.get_by_label("Clave", exact=True).fill("clave-ficticia")
    pagina.get_by_role("button", name="Entrar", exact=True).click()
    expect(pagina.get_by_role("alert")).to_contain_text("Se requiere conexión")
    expect(pagina.get_by_label("Cédula o correo")).to_have_value("9900001")
    expect(pagina.locator("[data-bienvenida]")).to_be_hidden()
    contexto_pwa.set_offline(False)
    pagina.wait_for_function("navigator.onLine")
    assert pagina.evaluate("async () => (await fetch('/api/estado')).status") == 200
    # Espera acotada para detectar reenvíos después del evento online.
    pagina.wait_for_timeout(500)
    assert escrituras == []
    assert contenido_cache(pagina) == cache_inicial
    assert pagina.evaluate("async () => (await indexedDB.databases()).length") == 0
    # La escritura manual sí llega al servidor. El cuerpo inválido evita necesitar una base.
    assert (
        pagina.evaluate("""async () => (await fetch('/api/sesion', {
      method: 'POST', headers: {'X-Gimnasio': '1', 'Content-Type': 'application/json'}, body: '{}'
    })).status""")
        == 400
    )
    assert escrituras == ["POST"]


def test_navegacion_sin_red_exige_conexion(contexto_pwa, servidor_pwa):
    url, _, _ = servidor_pwa
    pagina = abrir_controlada(contexto_pwa, url)
    contexto_pwa.set_offline(True)
    respuesta = pagina.goto(url)
    assert respuesta.status == 503
    expect(pagina.get_by_role("heading", name="Conexión requerida", exact=True)).to_be_visible()
    expect(pagina.get_by_text("Gimnasio Pro requiere conexión a Internet.", exact=False)).to_be_visible()
    assert all("/" not in rutas for rutas in contenido_cache(pagina).values())


def test_actualizacion_conserva_formulario_y_elimina_cache_anterior(contexto_pwa, servidor_pwa):
    url, app, _ = servidor_pwa
    pagina = abrir_controlada(contexto_pwa, url)
    otra = abrir_controlada(contexto_pwa, url)
    pagina.get_by_label("Cédula o correo").fill("9900001")
    pagina.get_by_label("Clave", exact=True).fill("clave-ficticia")
    # Una caché ajena a Gimnasio Pro no debe purgarse.
    pagina.evaluate("caches.open('otra-aplicacion')")
    app.config["VERSION_PWA"] = "2"
    pagina.evaluate("async () => (await navigator.serviceWorker.ready).update()")
    expect(pagina.locator("[data-actualizacion]")).to_be_visible()
    expect(pagina.get_by_label("Cédula o correo")).to_have_value("9900001")
    expect(pagina.get_by_label("Clave", exact=True)).to_have_value("clave-ficticia")
    assert "gimnasio-estaticos-1" in contenido_cache(pagina)
    # Una pestaña cerrada no basta: la otra puede tener trabajo en curso.
    pagina.close()
    assert otra.evaluate("async () => Boolean((await navigator.serviceWorker.getRegistration()).waiting)")
    otra.goto("about:blank")
    pagina = abrir_controlada(contexto_pwa, url)
    pagina.wait_for_function("""async () => {
      const nombres = await caches.keys();
      return nombres.includes('gimnasio-estaticos-2') && !nombres.includes('gimnasio-estaticos-1');
    }""")
    assert set(contenido_cache(pagina)) == {"gimnasio-estaticos-2", "otra-aplicacion"}
    expect(pagina.locator("[data-actualizacion]")).to_be_hidden()
