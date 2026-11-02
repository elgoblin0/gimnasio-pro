"""Controles transversales del CI: accesibilidad con axe y presupuesto de carga en cada vista principal."""

# Sin ficha: control transversal del CI; no cambia ninguna capacidad.

from pathlib import Path

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

AXE = Path(__file__).parent / "vendor" / "axe-core@4.14.0" / "axe.min.js"

# Vista: (botón de «entrar como…» o None, ruta). El editor se abre con el primer socio de la demo.
VISTAS = {
    "portada": (None, "/"),
    "inicio-socio": ("Entrar como socio", "/"),
    "entrenamiento": ("Entrar como socio", "/entrenamiento.html"),
    "ficha": ("Entrar como socio", "/ficha.html"),
    "clases-socio": ("Entrar como socio", "/clases.html"),
    "recepcion": ("Entrar como recepción", "/recepcion.html"),
    "pagos": ("Entrar como recepción", "/pagos.html"),
    "bandeja": ("Entrar como entrenador", "/bandeja.html"),
    "editor-programa": ("Entrar como entrenador", "/editor-programa.html"),
    "plantillas": ("Entrar como administración", "/plantillas.html"),
    "equipos": ("Entrar como entrenador", "/equipos.html"),
    "clases-entrenador": ("Entrar como entrenador", "/clases.html"),
    "administracion": ("Entrar como administración", "/administracion.html"),
}

PANTALLA_INICIAL = {"Entrar como entrenador": "/bandeja.html", "Entrar como administración": "/administracion.html"}

# Bytes del cuerpo sin comprimir por tipo de recurso, y milisegundos hasta el primer contenido pintado.
# Al cierre de la etapa 6 lo más pesado sin 3D era 60 KB de JS, 38 KB de CSS y ninguna fuente; los topes
# dejan lugar para el sistema base (#292) y para un CI más lento que una PC.
PRESUPUESTO = {"script": 150_000, "css": 80_000, "font": 250_000, "primer_pintado_ms": 1_500}
# Con 3D se suma Three.js sin minificar (2,3 MB de JS); «otros» incluye las respuestas de la API.
PRESUPUESTO_3D = {"script": 2_600_000, "otros": 1_000_000}
VISTAS_3D = {"entrenamiento", "editor-programa"}

MEDIR = """() => {
  const tipos = { script: 0, css: 0, font: 0, otros: 0 };
  for (const recurso of performance.getEntriesByType("resource")) {
    const ruta = new URL(recurso.name).pathname;
    const tipo = ruta.endsWith(".js") ? "script" : ruta.endsWith(".css") ? "css"
      : /\\.(woff2?|ttf|otf)$/.test(ruta) ? "font" : "otros";
    tipos[tipo] += recurso.decodedBodySize;
  }
  const pintado = performance.getEntriesByName("first-contentful-paint")[0];
  return { ...tipos, primer_pintado_ms: pintado ? pintado.startTime : null };
}"""


def abrir(navegador, url_base, vista, esquema="light"):
    boton, ruta = VISTAS[vista]
    contexto = navegador.new_context(locale="es-PY", color_scheme=esquema, service_workers="block")
    pagina = contexto.new_page()
    pagina.goto(url_base)
    if boton:
        pagina.get_by_role("button", name=boton, exact=True).click()
        # Entrenador y administración salen de la portada a su pantalla inicial; socio y recepción se quedan.
        destino = PANTALLA_INICIAL.get(boton)
        if destino:
            pagina.wait_for_url(url_base + destino)
        else:
            expect(pagina.locator("[data-bienvenida]")).to_be_visible()
    if vista == "editor-programa":
        socios = pagina.evaluate("fetch('/api/sesion/demo/socios').then(r => r.json())")["socios"]
        ruta = f"{ruta}?socio={socios[0]['id']}"
    # Sin caché, cada vista se mide como una primera visita aunque la portada ya haya bajado lo común.
    cdp = contexto.new_cdp_session(pagina)
    cdp.send("Network.enable")
    cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
    pagina.goto(url_base + ruta)
    pagina.wait_for_load_state("load")
    assert pagina.url == url_base + ruta, f"{vista} redirigió a {pagina.url}"
    expect(pagina.locator("main").first).to_be_visible()
    # Las vistas piden sus datos al cargar; sin esperar, axe revisaría los estados de carga.
    pagina.wait_for_timeout(800)
    return contexto, pagina


@pytest.mark.parametrize("esquema", ["light", "dark"], ids=["claro", "oscuro"])
@pytest.mark.parametrize("vista", list(VISTAS))
def test_vista_sin_violaciones_serias_de_accesibilidad(navegador, url_base, vista, esquema):
    contexto, pagina = abrir(navegador, url_base, vista, esquema)
    with contexto:
        pagina.add_script_tag(path=str(AXE))
        resultado = pagina.evaluate(
            "() => axe.run(document, { resultTypes: ['violations'], runOnly: ['wcag2a', 'wcag2aa', 'best-practice'] })"
        )
        serias = [v for v in resultado["violations"] if v["impact"] in ("serious", "critical")]
        detalle = "\n".join(
            f"{v['id']} ({v['impact']}): {v['help']} → {[n['target'] for n in v['nodes'][:3]]}" for v in serias
        )
        assert not serias, f"{vista} en {esquema}:\n{detalle}"


@pytest.mark.parametrize("vista", list(VISTAS))
def test_vista_dentro_del_presupuesto_de_carga(navegador, url_base, vista):
    contexto, pagina = abrir(navegador, url_base, vista)
    with contexto:
        medida = pagina.evaluate(MEDIR)
        limites = PRESUPUESTO | (PRESUPUESTO_3D if vista in VISTAS_3D else {})
        excesos = {clave: (medida[clave], tope) for clave, tope in limites.items() if (medida[clave] or 0) > tope}
        assert not excesos, f"{vista} excede el presupuesto (medido, tope): {excesos}"
