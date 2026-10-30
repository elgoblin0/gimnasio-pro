"""Mide cuadros de la recepción real con 50 visitas ficticias, sin MySQL ni medidor en pantalla.

Uso: python scripts/medir_escena_ocupacion.py
Chromium y Playwright deben estar instalados. Las respuestas API se sustituyen solo en este navegador.
"""

import argparse
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[1]
ZONAS = ["musculacion", "peso_libre", "cardio", "funcional", "en_la_sede"]
MEDIR = """(() => {
  const original = window.requestAnimationFrame;
  window.cuadrosEscena = [];
  window.requestAnimationFrame = funcion => original(ahora => {
    window.cuadrosEscena.push(ahora);
    funcion(ahora);
  });
})();"""


class Recursos(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def visita(indice):
    return {
        "id": f"visita-{indice}",
        "socio_id": f"socio-{indice}",
        "nombre": f"Socio ficticio {indice}",
        "cedula": str(1000000 + indice),
        "entrada": "2026-10-30T12:00:00Z",
        "zona": ZONAS[indice % 5],
        "minutos": indice,
        "simulada": indice % 3 == 0,
        "por_conciliar": indice % 17 == 0,
        "permanencia_habitual": {"suficiente": False, "observaciones": 0},
    }


def medir(navegador, url, ancho, alto, cpu, capturas=None):
    with navegador.new_context(
        viewport={"width": ancho, "height": alto},
        is_mobile=cpu > 1,
        has_touch=cpu > 1,
        device_scale_factor=1,
        color_scheme="dark",
        service_workers="block",
    ) as contexto:
        pagina = contexto.new_page()
        errores = []
        pagina.on("pageerror", lambda error: errores.append(str(error)))
        sesion = contexto.new_cdp_session(pagina)
        sesion.send("Emulation.setCPUThrottlingRate", {"rate": cpu})
        visitas = [visita(i) for i in range(50)]

        def responder(ruta):
            recurso = ruta.request.url.split("/api/")[1].split("?")[0]
            datos = {
                "sesion": {"usuario": {"rol": "recepcion"}},
                "estado": {"modo_demo": True},
                "visitas": {"visitas": visitas},
                "visitas/socios": {"socios": []},
                "ocupacion": {
                    "sede_id": "sede-ficticia",
                    "ocupacion_registrada": len(visitas),
                    "aforo_maximo": 60,
                    "por_zona": {zona: sum(v["zona"] == zona for v in visitas) for zona in ZONAS},
                },
                "mejores-horarios": {clave: {"datos_insuficientes": True} for clave in ("hoy", "manana")},
            }
            ruta.fulfill(json=datos[recurso])

        pagina.route("**/api/**", responder)
        pagina.add_init_script(MEDIR)
        pagina.goto(url + "/recepcion.html")
        pagina.wait_for_selector('[data-escena-ocupacion][data-lista="true"]', timeout=30000)
        pagina.wait_for_timeout(12000)
        pagina.evaluate("window.cuadrosEscena = []")
        # Cambian las 50 zonas de la sede simultáneamente; la cantidad permanece en 50.
        for dato in visitas:
            dato["zona"] = ZONAS[(ZONAS.index(dato["zona"]) + 1) % 5]
        pagina.get_by_role("button", name="Actualizar visitas", exact=True).click()
        pagina.wait_for_timeout(16000)
        cuadros = pagina.evaluate("window.cuadrosEscena")
        intervalos = [b - a for a, b in zip(cuadros, cuadros[1:], strict=False) if b - a < 500]
        assert intervalos, errores
        fps = sorted(1000 / intervalo for intervalo in intervalos)
        resultado = {
            "viewport": f"{ancho}x{alto}",
            "cpu": cpu,
            "visitas": 50,
            "cuadros": len(intervalos),
            "fps_promedio": round(1000 * len(intervalos) / sum(intervalos), 1),
            "fps_p5": round(fps[int(len(fps) * 0.05)], 1),
            "errores": errores,
            "sin_scroll_horizontal": pagina.evaluate("document.documentElement.scrollWidth <= innerWidth"),
        }
        pagina.evaluate("window.cuadrosEscena = []")
        pagina.wait_for_timeout(2000)
        resultado["cuadros_en_reposo_2s"] = pagina.evaluate("window.cuadrosEscena.length")
        if capturas:
            capturas.mkdir(parents=True, exist_ok=True)
            pagina.locator(".ocupacion-distribucion").screenshot(path=str(capturas / f"escena-{ancho}.png"))
        return resultado


def main():
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--canal", default="chromium", choices=["chromium", "chrome", "msedge"])
    argumentos.add_argument("--capturas", type=Path)
    opciones = argumentos.parse_args()
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), partial(Recursos, directory=str(RAIZ / "gimnasio" / "static")))
    hilo = Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    try:
        with sync_playwright() as playwright, playwright.chromium.launch(channel=opciones.canal) as navegador:
            url = f"http://127.0.0.1:{servidor.server_port}"
            print(f"Chromium {navegador.version}; DPR 1; esquema oscuro; 50 cambios simultáneos")
            for ancho, alto, cpu in [(1440, 900, 1), (390, 844, 4)]:
                print(
                    json.dumps(medir(navegador, url, ancho, alto, cpu, opciones.capturas), ensure_ascii=False),
                    flush=True,
                )
    finally:
        servidor.shutdown()
        hilo.join()
        servidor.server_close()


if __name__ == "__main__":
    main()
