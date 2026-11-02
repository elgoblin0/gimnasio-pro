"""Recorrido guiado sobre la app real de la demo (ADR 0032), con la semilla, la API y MySQL reales."""

import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gimnasio.comun.bd import transaccion
from pruebas.e2e.test_esqueleto_andante import preparar

pytestmark = pytest.mark.e2e

AXE = Path(__file__).parent / "vendor" / "axe-core@4.14.0" / "axe.min.js"
PASOS = 10
PANTALLAS = {
    1: "/",
    2: "/recepcion.html",
    3: "/recepcion.html",
    4: "/recepcion.html",
    5: "/entrenamiento.html",
    6: "/entrenamiento.html",
    7: "/bandeja.html",
    8: "/bandeja.html",
    9: "/administracion.html",
    10: "/",
}


def tarjeta_de(pagina):
    return pagina.locator("[data-recorrido-tarjeta]")


def empezar(pagina, url):
    pagina.goto(url)
    pagina.get_by_role("button", name="Ver recorrido", exact=True).click()
    tarjeta = tarjeta_de(pagina)
    expect(tarjeta).to_contain_text("Recorrido · paso 1 de 10")
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
    expect(pagina.locator("[data-recorrido-ancla]")).to_have_count(1)
    return texto


def test_recorrido_completo_dos_veces_sobre_la_misma_semilla(pagina_demo, demo_aislada):
    pagina = pagina_demo
    errores = preparar(pagina, 1440, 900)
    for vuelta in (1, 2):
        tarjeta = empezar(pagina, demo_aislada.url)
        textos = {}
        for numero in range(1, PASOS + 1):
            textos[numero] = esperar_paso(pagina, numero)
            nombre = "Terminar recorrido" if numero == PASOS else "Siguiente"
            tarjeta.get_by_role("button", name=nombre, exact=True).click()
        expect(tarjeta).to_have_count(0)
        assert pagina.evaluate("sessionStorage.getItem('gimnasio-recorrido')") is None
        # Termina invitando a explorar por rol, sin sesión abierta.
        expect(pagina.get_by_role("button", name="Entrar como socio", exact=True)).to_be_visible()
        assert pagina.request.get(demo_aislada.url + "/api/sesion").json() == {"usuario": None}

        # La primera vuelta registra la entrada; la segunda encuentra a Lucía adentro y no la duplica.
        if vuelta == 1:
            assert "recepción registra su entrada" in textos[3]
        else:
            assert textos[3].startswith("Lucía ya está adentro")
        assert "durmió mal" in textos[5]
        assert "registra una serie de" in textos[6]
        assert "freno de seguridad" in textos[7]
        assert "marca el aviso como revisado" in textos[8]

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


def test_salir_a_mitad_queda_en_la_pantalla_real_del_paso(pagina_demo, demo_aislada):
    pagina = pagina_demo
    errores = preparar(pagina, 390, 844)
    tarjeta = empezar(pagina, demo_aislada.url)
    # El teclado avanza fuera de los campos; la tarjeta va al pie en un celular.
    for numero in range(1, 6):
        esperar_paso(pagina, numero)
        pagina.locator("body").press("ArrowRight")
    esperar_paso(pagina, 6)
    expect(tarjeta).to_have_attribute("data-lugar", "pie")
    assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth")

    tarjeta.get_by_role("button", name="Salir del recorrido", exact=True).focus()
    pagina.keyboard.press("Escape")
    expect(tarjeta).to_have_count(0)
    expect(pagina.locator("[data-recorrido-ancla]")).to_have_count(0)
    assert re.search(r"/entrenamiento\.html\?sesion=", pagina.url), pagina.url
    # Queda la pantalla real de ese paso, con la sesión del socio abierta y su serie guardada.
    expect(pagina.locator("[data-sesion-actual]")).to_be_visible()
    expect(pagina.locator("[data-series] li")).to_have_count(1)
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
