"""Menú único por rol en la cabecera de todas las pantallas, con API y MySQL reales."""

import pytest

expect = pytest.importorskip("playwright.sync_api").expect
pytestmark = pytest.mark.e2e

ANCHOS = [1440, 390]
ROLES = {
    "socio": {
        "boton": "socio",
        "menu": ["Mi entrenamiento", "Mi progreso", "Clases", "Mi ficha"],
        "incluidas": {"/resumen-sesion.html": "Mi entrenamiento"},
    },
    "recepcion": {
        "boton": "recepción",
        "menu": ["Recepción", "Pagos", "Clases"],
        "incluidas": {"/ficha.html?socio=sin-elegir": "Recepción"},
    },
    "entrenador": {
        "boton": "entrenador",
        "menu": ["Bandeja", "Equipos", "Clases"],
        "incluidas": {"/editor-programa.html": "Bandeja"},
    },
    "administracion": {
        "boton": "administración",
        "menu": ["Administración", "Clases"],
        "incluidas": {
            "/pagos.html": "Administración",
            "/equipos.html": "Administración",
            "/plantillas.html": "Administración",
            "/editor-programa.html?plantilla=nueva": "Administración",
            "/ficha.html?socio=sin-elegir": "Administración",
        },
    },
}
MEDIDAS = """() => {
  const cabecera = document.querySelector("body > header.cabecera");
  const nav = cabecera.querySelector("nav");
  const enlace = getComputedStyle(nav.querySelector("a"));
  const salida = cabecera.querySelector("[data-cerrar]");
  const interruptor = cabecera.querySelector("[data-interruptor-efectos]");
  const caja = (nodo) => {
    const { left, top, width, height } = nodo.getBoundingClientRect();
    return [left, top, width, height];
  };
  const letra = (nodo) => {
    const { fontFamily, fontSize, fontWeight, color } = getComputedStyle(nodo);
    return [fontFamily, fontSize, fontWeight, color];
  };
  return {
    cabecera: caja(cabecera),
    fondo: getComputedStyle(cabecera).backgroundColor,
    marca: [caja(cabecera.querySelector(".cabecera-marca")), letra(cabecera.querySelector(".cabecera-marca"))],
    nav: caja(nav),
    enlace: [enlace.fontFamily, enlace.fontSize, enlace.minHeight, enlace.paddingInlineStart],
    salida: [caja(salida), letra(salida)],
    interruptor: [caja(interruptor), letra(interruptor)],
  };
}"""


def entrar(contexto, demo, rol):
    pagina = contexto.new_page()
    errores = []
    pagina.on("pageerror", lambda error: errores.append(str(error)))
    pagina.goto(demo.url)
    pagina.get_by_role("button", name=f"Entrar como {ROLES[rol]['boton']}", exact=True).click()
    expect(pagina.locator("[data-ingreso]")).to_be_hidden()
    pagina.wait_for_function("localStorage.getItem('gimnasio-sesion-menu') !== null")
    return pagina, errores


def comprobar_menu(pagina, rol, activa, valor):
    menu = pagina.get_by_role("navigation", name="Secciones", exact=True)
    expect(menu.get_by_role("link")).to_have_text(ROLES[rol]["menu"])
    expect(menu.locator("[aria-current]")).to_have_count(1)
    expect(menu.get_by_role("link", name=activa, exact=True)).to_have_attribute("aria-current", valor)
    expect(pagina.get_by_role("button", name="Cerrar sesión", exact=True)).to_be_visible()
    expect(pagina.locator(".cabecera [data-interruptor-efectos]")).to_be_visible()
    assert pagina.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


@pytest.mark.parametrize("ancho", ANCHOS)
@pytest.mark.parametrize("rol", ROLES)
def test_el_menu_del_rol_es_el_mismo_en_todas_sus_pantallas(navegador, demo_aislada, rol, ancho):
    with navegador.new_context(
        locale="es-PY", viewport={"width": ancho, "height": 844}, service_workers="block", reduced_motion="reduce"
    ) as contexto:
        pagina, errores = entrar(contexto, demo_aislada, rol)
        medidas = {}
        pagina.goto(demo_aislada.url + "/clases.html")
        for texto in ROLES[rol]["menu"]:
            # Se recorre con el propio menú, desde la pantalla anterior: el menú lleva a todas partes.
            menu = pagina.get_by_role("navigation", name="Secciones", exact=True)
            menu.get_by_role("link", name=texto, exact=True).click()
            comprobar_menu(pagina, rol, texto, "page")
            medidas[texto] = pagina.evaluate(MEDIDAS)
        for pantalla, seccion in ROLES[rol]["incluidas"].items():
            pagina.goto(demo_aislada.url + pantalla)
            comprobar_menu(pagina, rol, seccion, "true")
            medidas[pantalla] = pagina.evaluate(MEDIDAS)
        referencia = medidas[ROLES[rol]["menu"][0]]
        distintas = {
            pantalla: {clave: valor for clave, valor in medida.items() if valor != referencia[clave]}
            for pantalla, medida in medidas.items()
            if medida != referencia
        }
        assert distintas == {}, f"Referencia: {referencia}"
        assert errores == []


@pytest.mark.parametrize("ancho", ANCHOS)
@pytest.mark.parametrize("pantalla", ["Pagos", "Equipos", "Plantillas"])
def test_administracion_llega_desde_su_panel_y_vuelve_con_el_menu(navegador, demo_aislada, pantalla, ancho):
    with navegador.new_context(
        locale="es-PY", viewport={"width": ancho, "height": 844}, service_workers="block"
    ) as contexto:
        pagina, errores = entrar(contexto, demo_aislada, "administracion")
        pagina.goto(demo_aislada.url + "/administracion.html")
        panel = pagina.get_by_role("navigation", name="Panel de administración", exact=True)
        enlace = panel.get_by_role("link", name=pantalla, exact=True)
        # Se ve sin deslizar: el índice no esconde pantallas fuera del borde.
        caja = enlace.bounding_box()
        assert caja["x"] + caja["width"] <= ancho
        enlace.click()
        pagina.wait_for_url(f"**/{pantalla.lower()}.html")
        comprobar_menu(pagina, "administracion", "Administración", "true")
        pagina.get_by_role("navigation", name="Secciones", exact=True).get_by_role(
            "link", name="Administración", exact=True
        ).click()
        pagina.wait_for_url("**/administracion.html")
        comprobar_menu(pagina, "administracion", "Administración", "page")
        assert errores == []


@pytest.mark.parametrize("ancho", ANCHOS)
def test_la_cabecera_no_se_mueve_mientras_responde_la_sesion(navegador, demo_aislada, ancho):
    with navegador.new_context(
        locale="es-PY", viewport={"width": ancho, "height": 844}, service_workers="block", reduced_motion="reduce"
    ) as contexto:
        pagina, _ = entrar(contexto, demo_aislada, "recepcion")
        # Al aparecer lo que sigue al <nav> en el documento, el menú ya tiene que estar dibujado.
        pagina.add_init_script("""
          new MutationObserver((_, observador) => {
            if (!document.querySelector("[data-cerrar]")) return;
            window.enlacesAlLlegarLaSalida = document.querySelectorAll(".cabecera nav a").length;
            observador.disconnect();
          }).observe(document, { childList: true, subtree: true });
        """)
        retenidas = []
        pagina.route("**/api/sesion", lambda ruta: retenidas.append(ruta))
        pagina.goto(demo_aislada.url + "/clases.html", wait_until="domcontentloaded")
        assert pagina.evaluate("window.enlacesAlLlegarLaSalida") == 3
        expect(pagina.get_by_text("Datos ficticios · se reinician cada día", exact=True)).to_be_visible()
        expect(pagina.locator(".cabecera [data-interruptor-efectos]")).to_be_visible()
        pagina.wait_for_function("document.querySelector('[data-estado]').textContent === 'Cargando clases…'")
        antes = pagina.evaluate(MEDIDAS)
        assert retenidas
        for retenida in retenidas:
            retenida.continue_()
        pagina.unroute("**/api/sesion")
        expect(pagina.locator("[data-agenda] li").first).to_be_visible()
        assert pagina.evaluate(MEDIDAS) == antes


def test_el_aviso_de_la_demo_no_espera_a_la_sesion_en_una_pantalla_con_hidden_estricto(navegador, demo_aislada):
    with navegador.new_context(
        locale="es-PY", viewport={"width": 390, "height": 844}, service_workers="block", reduced_motion="reduce"
    ) as contexto:
        pagina, _ = entrar(contexto, demo_aislada, "entrenador")
        retenidas = []
        pagina.route("**/api/sesion", lambda ruta: retenidas.append(ruta))
        # bandeja.html carga pantallas.css, donde [hidden] es !important.
        pagina.goto(demo_aislada.url + "/bandeja.html", wait_until="domcontentloaded")
        expect(pagina.get_by_text("Datos ficticios · se reinician cada día", exact=True)).to_be_visible()
        for retenida in retenidas:
            retenida.continue_()
        pagina.unroute("**/api/sesion")


def test_el_menu_cambia_con_la_persona_y_se_olvida_al_cerrar_sesion(navegador, demo_aislada):
    with navegador.new_context(locale="es-PY", service_workers="block") as contexto:
        pagina, errores = entrar(contexto, demo_aislada, "socio")
        pagina.goto(demo_aislada.url + "/clases.html")
        comprobar_menu(pagina, "socio", "Clases", "page")
        # Otra pestaña entró con otro rol: esta pantalla lo corrige cuando recibe la sesión real.
        pagina.evaluate(
            "localStorage.setItem('gimnasio-sesion-menu', JSON.stringify({ rol: 'entrenador', demo: true }))"
        )
        pagina.goto(demo_aislada.url + "/clases.html")
        comprobar_menu(pagina, "socio", "Clases", "page")
        # Sin nada recordado, el menú igual aparece.
        pagina.evaluate("localStorage.clear()")
        pagina.goto(demo_aislada.url + "/resumen-sesion.html")
        comprobar_menu(pagina, "socio", "Mi entrenamiento", "true")
        pagina.get_by_role("button", name="Cerrar sesión", exact=True).click()
        expect(pagina.get_by_role("heading", name="Ingresar", exact=True)).to_be_visible()
        assert pagina.evaluate("localStorage.getItem('gimnasio-sesion-menu')") is None
        assert errores == []
