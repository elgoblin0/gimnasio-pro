"""Recorrido guiado sobre la app real de la demo (ADR 0032), con la semilla, la API y MySQL reales."""

import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gimnasio.comun.bd import transaccion
from pruebas.e2e.test_esqueleto_andante import preparar

pytestmark = pytest.mark.e2e

AXE = Path(__file__).parent / "vendor" / "axe-core@4.14.0" / "axe.min.js"
PASOS = 7
PANTALLAS = {
    1: "/",
    2: "/recepcion.html",
    3: "/recepcion.html",
    4: "/entrenamiento.html",
    5: "/entrenamiento.html",
    6: "/bandeja.html",
    7: "/resumen-sesion.html",
}


def tarjeta_de(pagina):
    return pagina.locator("[data-recorrido-tarjeta]")


def empezar(pagina, url):
    pagina.goto(url)
    pagina.get_by_role("button", name="Ver recorrido", exact=True).click()
    tarjeta = tarjeta_de(pagina)
    expect(tarjeta).to_contain_text(f"Recorrido · paso 1 de {PASOS}")
    # En pausa el avance lo da la prueba: el automático no se adelanta a un clic lento del CI.
    tarjeta.get_by_role("button", name="Pausar", exact=True).click()
    expect(tarjeta.get_by_role("button", name="Seguir solo", exact=True)).to_have_attribute("aria-pressed", "true")
    return tarjeta


def esperar_paso(pagina, numero):
    tarjeta = tarjeta_de(pagina)
    expect(tarjeta).to_contain_text(f"Recorrido · paso {numero} de {PASOS}", timeout=20_000)
    nombre = "Terminar recorrido" if numero == PASOS else "Siguiente"
    expect(tarjeta.get_by_role("button", name=nombre, exact=True)).to_be_enabled(timeout=20_000)
    assert re.search(re.escape(PANTALLAS[numero]) + r"(\?|$)", pagina.url), pagina.url
    texto = tarjeta.locator("[data-recorrido-texto]").inner_text()
    expect(tarjeta.locator("[data-recorrido-anuncio]")).to_have_text(f"Paso {numero} de {PASOS}. {texto}")
    # La tarjeta y sus botones se ven enteros; la parte que explica se ve desde su comienzo, sin que la tarjeta la pise.
    pagina.wait_for_function(
        """() => {
          const tarjeta = document.querySelector('[data-recorrido-tarjeta]');
          const caja = tarjeta.getBoundingClientRect();
          if (caja.top < 0 || caja.bottom > innerHeight + 1) return false;
          for (const boton of tarjeta.querySelectorAll('button:not([hidden])')) {
            const b = boton.getBoundingClientRect();
            if (b.top < 0 || b.bottom > innerHeight || b.left < 0 || b.right > innerWidth) return false;
          }
          const ancla = document.querySelector('[data-recorrido-ancla]');
          if (!ancla) return true;
          let { top, bottom } = ancla.getBoundingClientRect();
          const cabecera = document.querySelector('body > .cabecera')?.getBoundingClientRect().bottom ?? 0;
          if (getComputedStyle(ancla).position !== 'fixed' && top < cabecera - 1) return false;
          if (top + 40 > caja.top) return false;
          // El ancla recortada por cada columna que se desplaza sola y por la tarjeta: tiene que quedar algo.
          for (let padre = ancla.parentElement; padre && padre !== document.body; padre = padre.parentElement) {
            if (getComputedStyle(padre).overflowY === 'visible') continue;
            const marco = padre.getBoundingClientRect();
            [top, bottom] = [Math.max(top, marco.top), Math.min(bottom, marco.bottom)];
          }
          return Math.min(bottom, caja.top) - Math.max(top, 0) >= 40;
        }""",
        timeout=5_000,
    )
    expect(pagina.locator("[data-recorrido-ancla]")).to_have_count(0 if numero == 1 else 1)
    return texto


def test_recorrido_completo_dos_veces_sobre_la_misma_semilla(pagina_demo, demo_aislada):
    pagina = pagina_demo
    errores = preparar(pagina, 1440, 900)
    for vuelta in (1, 2):
        tarjeta = empezar(pagina, demo_aislada.url)
        # Quien apretó «Ver recorrido» sigue viendo la portada como estaba: sin marca, sin desplazarla ni espacio extra.
        esperar_paso(pagina, 1)
        assert pagina.evaluate("scrollY") == 0
        assert pagina.evaluate("getComputedStyle(document.body).paddingBlockEnd") == "0px"
        textos = {}
        for numero in range(1, PASOS + 1):
            textos[numero] = esperar_paso(pagina, numero)
            if numero == 4:
                # Se vio el chequeo con lo que Lucía contó antes de que se guardara.
                assert pagina.locator("[data-chequeo]").is_hidden()
            if numero < PASOS:
                tarjeta.get_by_role("button", name="Siguiente", exact=True).click()
        # El último paso es el resumen de la sesión que Lucía registró en el recorrido.
        expect(pagina.locator("[data-zonas-texto] li").first).to_contain_text("trabajada")
        if vuelta == 1:
            expect(pagina.locator("[data-records]")).to_contain_text("repeticiones")
            assert "bate un récord personal" in textos[7]
        tarjeta.get_by_role("button", name="Terminar recorrido", exact=True).click()
        expect(tarjeta).to_have_count(0)
        # Termina invitando a explorar por rol, sin sesión abierta. Se espera a la portada: terminar navega.
        expect(pagina.get_by_role("button", name="Entrar como socio", exact=True)).to_be_visible()
        assert pagina.evaluate("sessionStorage.getItem('gimnasio-recorrido')") is None
        assert pagina.request.get(demo_aislada.url + "/api/sesion").json() == {"usuario": None}

        # La primera vuelta registra la entrada; la segunda encuentra a Lucía adentro y no la duplica.
        if vuelta == 1:
            assert "Recepción registra su entrada" in textos[2]
        else:
            assert textos[2].startswith("Lucía ya está adentro")
        assert "tarjeta contextual" in textos[2]
        assert "Como durmió mal" in textos[4]
        assert "registra 2 series" in textos[5]
        assert "marca el aviso como revisado" in textos[6]

    with demo_aislada.app.app_context(), transaccion() as cursor:
        cursor.execute(
            "SELECT u.id FROM usuarios u JOIN personas p ON p.id=u.persona_id "
            "WHERE p.nombre='Lucía' AND p.apellido='Benítez' AND u.rol='socio'"
        )
        lucia = cursor.fetchone()["id"]
        cursor.execute(
            "SELECT COUNT(*) AS n FROM avisos_entrenador a JOIN sesiones_realizadas s ON s.id=a.sesion_realizada_id "
            "WHERE s.socio_id=%s AND a.freno='chequeo_desfavorable'",
            (lucia,),
        )
        assert cursor.fetchone()["n"] == 2
    # Dos vueltas, una sola visita abierta de Lucía.
    encabezados = {"X-Gimnasio": "1", "Idempotency-Key": "01a19c00-0000-7000-8000-000000000001"}
    pagina.request.post(demo_aislada.url + "/api/sesion/demo/recepcion", headers=encabezados)
    visitas = pagina.request.get(demo_aislada.url + "/api/visitas?abiertas=1").json()["visitas"]
    assert [v["nombre"] for v in visitas].count("Lucía Benítez") == 1
    assert errores == []


def test_se_ve_lo_que_lucia_conto_antes_de_guardar_el_chequeo(pagina_demo, demo_aislada):
    pagina = pagina_demo
    errores = preparar(pagina, 1440, 900)
    tarjeta = empezar(pagina, demo_aislada.url)
    for numero in range(1, 4):
        esperar_paso(pagina, numero)
        tarjeta.get_by_role("button", name="Siguiente", exact=True).click()
    texto = tarjeta.locator("[data-recorrido-texto]")
    expect(texto).to_contain_text("durmió mal", timeout=20_000)
    # Mientras se lee, el chequeo está a la vista con sus valores y no se puede saltear la acción a medias.
    expect(pagina.locator("[data-chequeo]")).to_be_visible()
    expect(pagina.locator("[data-chequeo]")).to_have_attribute("data-recorrido-ancla", "")
    assert pagina.locator("#chequeo-sueno").input_value() == "1"
    expect(tarjeta.get_by_role("button", name="Siguiente", exact=True)).to_be_disabled()
    # Salir mientras se lee cancela la acción: el chequeo no se guarda.
    tarjeta.get_by_role("button", name="Salir del recorrido", exact=True).click()
    expect(tarjeta).to_have_count(0)
    pagina.wait_for_timeout(5_500)
    expect(pagina.locator("[data-chequeo]")).to_be_visible()
    assert errores == []


def test_salir_a_mitad_queda_en_la_pantalla_real_del_paso(pagina_demo, demo_aislada):
    pagina = pagina_demo
    errores = preparar(pagina, 390, 844)
    tarjeta = empezar(pagina, demo_aislada.url)
    # El teclado avanza fuera de los campos; la tarjeta va al pie también en un celular.
    for numero in range(1, 5):
        esperar_paso(pagina, numero)
        pagina.locator("body").press("ArrowRight")
    esperar_paso(pagina, 5)
    assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth")

    tarjeta.get_by_role("button", name="Salir del recorrido", exact=True).focus()
    pagina.keyboard.press("Escape")
    expect(tarjeta).to_have_count(0)
    expect(pagina.locator("[data-recorrido-ancla]")).to_have_count(0)
    assert re.search(r"/entrenamiento\.html\?sesion=", pagina.url), pagina.url
    # Queda la pantalla real de ese paso, con la sesión del socio abierta y sus series guardadas.
    expect(pagina.locator("[data-sesion-actual]")).to_be_visible()
    expect(pagina.locator("[data-series] li")).to_have_count(2)
    expect(pagina.get_by_role("button", name=re.compile("^Registrar serie de ")).first).to_be_enabled()
    pagina.reload()
    expect(pagina.locator("[data-sesion-actual]")).to_be_visible()
    expect(tarjeta).to_have_count(0)
    assert errores == []


@pytest.mark.parametrize("esquema", ["light", "dark"], ids=["claro", "oscuro"])
def test_tarjeta_del_recorrido_sin_violaciones_serias_de_accesibilidad(navegador, url_base, esquema):
    contexto = navegador.new_context(
        locale="es-PY", color_scheme=esquema, service_workers="block", reduced_motion="reduce"
    )
    with contexto:
        pagina = contexto.new_page()
        empezar(pagina, url_base)
        esperar_paso(pagina, 1)
        expect(tarjeta_de(pagina).locator("[data-recorrido-anuncio]")).to_have_attribute("aria-live", "polite")
        pagina.add_script_tag(path=str(AXE))
        resultado = pagina.evaluate(
            "() => axe.run({ include: [['[data-recorrido-tarjeta]']] },"
            " { resultTypes: ['violations'], runOnly: ['wcag2a', 'wcag2aa', 'best-practice'] })"
        )
        serias = [v for v in resultado["violations"] if v["impact"] in ("serious", "critical")]
        assert not serias, [(v["id"], v["help"]) for v in serias]
