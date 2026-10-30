"""Captura ambos prototipos y mide diez segundos sin limitar CPU ni red."""

import argparse
import json
import platform
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = Path(__file__).resolve().parent


def verificar(canal=None):
    resultados = []
    with ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(RAIZ))) as servidor:
        hilo = Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        try:
            with sync_playwright() as playwright:
                navegador = playwright.chromium.launch(channel=canal)
                for direccion in ("a", "b"):
                    for dispositivo, ancho, alto in (("escritorio", 1280, 1000), ("celular", 375, 812)):
                        contexto = navegador.new_context(
                            viewport={"width": ancho, "height": alto},
                            is_mobile=dispositivo == "celular",
                            has_touch=dispositivo == "celular",
                            device_scale_factor=1,
                            color_scheme="light",
                        )
                        pagina = contexto.new_page()
                        errores = []
                        pagina.on("pageerror", lambda error, errores=errores: errores.append(str(error)))
                        pagina.goto(f"http://127.0.0.1:{servidor.server_port}/prototipos/escena-ocupacion/{direccion}/")
                        pagina.wait_for_function("window.prototipo?.listo")
                        assert pagina.locator(".persona").count() == 40
                        assert pagina.locator("#total").inner_text() == "40 de 80"
                        pagina.locator(".persona").first.focus()
                        pagina.keyboard.press("Enter")
                        assert "Visita 1 ·" in pagina.locator("#rotulo").inner_text()
                        pagina.locator(".persona").nth(1).click()
                        assert "Visita 2 ·" in pagina.locator("#rotulo").inner_text()
                        assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth")
                        pagina.wait_for_timeout(11000)
                        medicion = pagina.evaluate("""() => ({...prototipo.fps,
                            bytes_descargados: performance.getEntriesByType('resource')
                                .reduce((n,r)=>n+r.encodedBodySize,0)
                                + performance.getEntriesByType('navigation')[0].encodedBodySize,
                            navegador: navigator.userAgent})""")
                        pagina.screenshot(path=str(DESTINO / f"{direccion}-{dispositivo}.png"), full_page=True)
                        # Movimiento reducido: entrada, cambio y salida se completan en un cuadro.
                        pagina.emulate_media(reduced_motion="reduce")
                        pagina.wait_for_timeout(100)
                        for _ in range(3):
                            antes = pagina.evaluate("prototipo.personas.map(p => [p.id, p.zona])")
                            pagina.evaluate("prototipo.avanzar()")
                            pagina.wait_for_timeout(100)
                            despues = pagina.evaluate("prototipo.personas.map(p => [p.id, p.zona])")
                            evento = pagina.locator("#evento").inner_text()
                            if evento.startswith("Entrada"):
                                assert len(despues) == len(antes) + 1
                            elif evento.startswith("Salida"):
                                assert len(despues) == len(antes) - 1
                            else:
                                assert len(despues) == len(antes) and despues != antes
                            assert pagina.evaluate("prototipo.personas.every(p => !p.hasta)")
                            assert pagina.locator("#total").inner_text() == f"{len(despues)} de 80"
                        assert not errores, errores
                        resultados.append(
                            {
                                "direccion": direccion,
                                "dispositivo": dispositivo,
                                "equipo": platform.platform(),
                                "procesador": platform.processor(),
                                **medicion,
                            }
                        )
                        print(resultados[-1], flush=True)
                        contexto.close()
                navegador.close()
        finally:
            servidor.shutdown()
            hilo.join()
    (DESTINO / "mediciones.json").write_text(
        json.dumps(resultados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--canal", choices=("chrome", "msedge"), default=None)
    verificar(argumentos.parse_args().canal)
