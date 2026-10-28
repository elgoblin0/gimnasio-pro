"""Verifica interacción y guarda mediciones/capturas sin conectar la aplicación."""

import json
from contextlib import nullcontext
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = Path(__file__).resolve().parent


def verificar(destino=DESTINO, navegador_disponible=None):
    resultados = []
    with ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(RAIZ))) as servidor:
        hilo = Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        try:
            with nullcontext(navegador_disponible) if navegador_disponible else sync_playwright() as playwright:
                navegador = playwright.chromium.launch()
                for version in ("modelo", "estilizado"):
                    for dispositivo, ancho, alto in (("escritorio", 1280, 1000), ("celular", 390, 844)):
                        contexto = navegador.new_context(
                            viewport={"width": ancho, "height": alto},
                            is_mobile=dispositivo == "celular",
                            has_touch=dispositivo == "celular",
                            device_scale_factor=1,
                            reduced_motion="reduce",
                        )
                        pagina = contexto.new_page()
                        errores = []
                        pagina.on("pageerror", lambda error, errores=errores: errores.append(str(error)))
                        pagina.on(
                            "console",
                            lambda mensaje, errores=errores: (
                                errores.append(mensaje.text) if mensaje.type == "error" else None
                            ),
                        )
                        pagina.goto(f"http://127.0.0.1:{servidor.server_port}/prototipos/cuerpo-3d/{version}/")
                        pagina.wait_for_function("window.prototipo?.listo")
                        if version == "modelo":
                            asignadas = pagina.evaluate(
                                "[...new Set(prototipo.cuerpo.children.flatMap("
                                "m => m.geometry.groups.map(g => g.materialIndex)))].sort((a,b)=>a-b)"
                            )
                            assert asignadas == list(range(15)), asignadas
                        pagina.evaluate(
                            "window.selecciones = []; window.addEventListener('zona-seleccionada', "
                            "e => selecciones.push(e.detail.zona))"
                        )
                        for zona in pagina.evaluate("prototipo.zonas"):
                            pagina.locator(f'[data-zona="{zona}"]').click()
                            for estado in ("trabajada", "con_dolor"):
                                pagina.locator("#estado").select_option(estado)
                                assert pagina.evaluate("z => prototipo.estados[z]", zona) == estado
                        assert len(set(pagina.evaluate("selecciones"))) == 14
                        for zona in pagina.evaluate("prototipo.zonas"):
                            pagina.locator(f'[data-zona="{zona}"]').click()
                            pagina.locator("#estado").select_option(
                                "trabajada"
                                if zona in ("pecho", "cuadriceps")
                                else "con_dolor"
                                if zona == "rodillas"
                                else "sin_marcar"
                            )
                        pagina.locator('[data-zona="pecho"]').click()
                        pagina.locator("canvas").scroll_into_view_if_needed()
                        rectangulo = pagina.locator("canvas").bounding_box()
                        # Raycasting real sobre el torso frontal, tanto con ratón como con toque.
                        x, y = rectangulo["x"] + rectangulo["width"] / 2, rectangulo["y"] + rectangulo["height"] * 0.38
                        antes = len(pagina.evaluate("selecciones"))
                        if dispositivo == "celular":
                            pagina.touchscreen.tap(x, y)
                        else:
                            pagina.mouse.click(x, y)
                        assert len(pagina.evaluate("selecciones")) == antes + 1
                        assert pagina.evaluate("selecciones.at(-1)") == ("abdomen" if version == "modelo" else "pecho")
                        pagina.screenshot(path=str(destino / f"{version}-{dispositivo}.png"), full_page=True)
                        medicion = pagina.evaluate("""async () => {
                          const inicio = performance.now(); const cuadros = [];
                          await new Promise(resolve => {
                            function rotar(t) {prototipo.cuerpo.rotation.y = (t-inicio)*.001; cuadros.push(t);
                              if (t-inicio < 3000) requestAnimationFrame(rotar); else resolve();}
                            requestAnimationFrame(rotar);
                          });
                          return {primer_cuadro_ms: Math.round(prototipo.primerCuadro),
                            fps: Math.round((cuadros.length-1)*1000/(cuadros.at(-1)-cuadros[0])),
                            bytes_descargados: performance.getEntriesByType('resource')
                              .reduce((n,r)=>n+r.encodedBodySize,0)
                              + performance.getEntriesByType('navigation')[0].encodedBodySize,
                            llamadas: prototipo.dibujante.info.render.calls,
                            navegador: navigator.userAgent};
                        }""")
                        assert not errores, errores
                        resultados.append({"version": version, "dispositivo": dispositivo, **medicion})
                        print(resultados[-1], flush=True)
                        contexto.close()
                navegador.close()
        finally:
            servidor.shutdown()
            hilo.join()
    (destino / "mediciones.json").write_text(
        json.dumps(resultados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    verificar()
