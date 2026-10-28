"""Registro de series reales desde el rol socio, con reintentos manuales y recarga."""

import re
from urllib.parse import parse_qs, urlparse

import pytest

from gimnasio.comun.bd import transaccion

expect = pytest.importorskip("playwright.sync_api").expect
pytestmark = pytest.mark.e2e


def iniciar(pagina, instancia):
    pagina.goto(instancia.url)
    pagina.get_by_role("button", name="Entrar como socio", exact=True).click()
    pagina.get_by_role("link", name="Ver mi entrenamiento", exact=True).click()
    boton = pagina.get_by_role("button", name="Iniciar sesión realizada", exact=True)
    expect(boton).to_be_visible()
    boton.focus()
    pagina.keyboard.press("Enter")
    expect(pagina.get_by_text("Sesión realizada iniciada.", exact=True)).to_be_visible()


def contar(instancia):
    with instancia.app.app_context(), transaccion() as cursor:
        cursor.execute(
            "SELECT COUNT(*) AS cantidad FROM series_realizadas s "
            "JOIN sesiones_realizadas sr ON sr.id=s.sesion_realizada_id "
            "JOIN usuarios u ON u.id=sr.socio_id WHERE u.es_demo=TRUE AND sr.creada_en >= '2026-10-27'"
        )
        return cursor.fetchone()["cantidad"]


@pytest.mark.parametrize("ancho,alto", [(1440, 900), (390, 844)])
def test_fuerza_cardio_pendientes_y_recarga(pagina_demo, demo_aislada, programa_demo, ancho, alto):
    pagina = pagina_demo
    pagina.set_viewport_size({"width": ancho, "height": alto})
    errores = []
    pagina.on("pageerror", lambda error: errores.append(str(error)))
    pagina.on("console", lambda mensaje: errores.append(mensaje.text) if mensaje.type == "error" else None)
    iniciar(pagina, demo_aislada)
    expect(pagina).to_have_url(re.compile(r"\?sesion=[0-9a-f-]{36}$"))
    assert set(parse_qs(urlparse(pagina.url).query)) == {"sesion"}
    enlace = pagina.url
    expect(pagina.get_by_label("Repeticiones de Sentadilla ficticia", exact=True)).to_have_value("8")
    pagina.get_by_label("Repeticiones de Sentadilla ficticia", exact=True).fill("11")
    pagina.get_by_label("Carga en kg de Sentadilla ficticia", exact=True).fill("22.75")
    rir = pagina.get_by_label("RIR opcional de Sentadilla ficticia (0 a 10)", exact=True)
    expect(rir).to_have_value("")
    rir.fill("0")
    rir.focus()
    pagina.keyboard.press("Enter")
    expect(pagina.get_by_text("Serie guardada.", exact=True)).to_be_visible()
    expect(pagina.locator("[data-descanso]")).to_be_visible()
    expect(pagina.locator("[data-restantes]")).to_contain_text("s")
    pagina.get_by_role("button", name="Saltear descanso", exact=True).click()
    expect(pagina.locator("[data-descanso-anuncio]")).to_have_text("Descanso terminado.")
    assert (
        pagina.evaluate("""async () => {
      let cambios = 0;
      const observador = new MutationObserver(() => cambios++);
      observador.observe(document.querySelector('[data-descanso-anuncio]'), { childList: true });
      await new Promise(resolve => setTimeout(resolve, 600));
      observador.disconnect();
      return cambios;
    }""")
        == 0
    )
    pagina.get_by_role("button", name="Sumar 30 s", exact=True).click()
    expect(pagina.locator("[data-descanso-anuncio]")).to_be_empty()
    tarjeta = pagina.locator(f'[data-ejercicio="{programa_demo.ejercicios[0]}"]')
    expect(tarjeta).to_contain_text("Series realizadas: 1 · Pendientes: 1")
    expect(pagina.locator("[data-series]")).to_contain_text("11 repeticiones · 22,75 kg")
    pagina.reload()
    expect(pagina.locator("[data-descanso]")).to_be_hidden()
    expect(pagina.locator("[data-series]")).to_contain_text("11 repeticiones · 22,75 kg")
    expect(pagina.locator("[data-series]")).to_contain_text("RIR 0")
    assert pagina.url == enlace
    cardio = pagina.locator(f'[data-ejercicio="{programa_demo.ejercicios[1]}"]')
    assert cardio.locator("input").count() == 3
    assert cardio.locator('[name="repeticiones"], [name="carga"]').count() == 0
    pagina.get_by_label("Duración en segundos de Caminata ficticia", exact=True).fill("121")
    pagina.get_by_label("Distancia en metros de Caminata ficticia", exact=True).fill("1500.27")
    pagina.get_by_role("button", name="Registrar serie de Caminata ficticia", exact=True).click()
    expect(pagina.locator("[data-series]")).to_contain_text("121 s · 1.500,27 m")
    assert contar(demo_aislada) == 2
    assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert errores == []


def test_doble_clic_y_respuesta_perdida_conservan_la_serie(pagina_demo, demo_aislada, programa_demo):
    pagina = pagina_demo
    pagina.add_init_script("""(() => {
      const original = window.fetch;
      let perder = true;
      window.enviosDeSerie = [];
      window.fetch = async (ruta, opciones) => {
        if (!ruta.endsWith('/series') || opciones?.method !== 'POST') return original(ruta, opciones);
        window.enviosDeSerie.push([opciones.body, opciones.headers['Idempotency-Key']]);
        const respuesta = await original(ruta, opciones);
        if (perder) { perder = false; throw new TypeError('Respuesta perdida después del commit'); }
        return respuesta;
      };
    })();""")
    iniciar(pagina, demo_aislada)
    pagina.get_by_role("button", name="Registrar serie de Sentadilla ficticia", exact=True).dblclick()
    expect(pagina.get_by_role("button", name="Reintentar operación", exact=True)).to_be_visible()
    expect(pagina.get_by_label("Carga en kg de Sentadilla ficticia", exact=True)).to_be_disabled()
    assert contar(demo_aislada) == 1
    pagina.get_by_role("button", name="Reintentar operación", exact=True).click()
    expect(pagina.get_by_text("Serie guardada.", exact=True)).to_be_visible()
    envios = pagina.evaluate("window.enviosDeSerie")
    assert len(envios) == 2
    assert envios[0] == envios[1]
    assert contar(demo_aislada) == 1


def test_desconexion_no_confirma_ni_reenvia_series(pagina_demo, demo_aislada, programa_demo):
    pagina = pagina_demo
    iniciar(pagina, demo_aislada)
    pagina.context.set_offline(True)
    pagina.get_by_role("button", name="Registrar serie de Sentadilla ficticia", exact=True).click()
    expect(pagina.get_by_role("button", name="Reintentar operación", exact=True)).to_be_visible()
    expect(pagina.get_by_text("Serie guardada.", exact=True)).to_be_hidden()
    assert contar(demo_aislada) == 0
    pagina.context.set_offline(False)
    pagina.get_by_role("button", name="Actualizar propuesta", exact=True).click()
    expect(pagina.get_by_text("Propuesta actualizada.", exact=True)).to_be_visible()
    assert contar(demo_aislada) == 0
    pagina.get_by_role("button", name="Reintentar operación", exact=True).click()
    expect(pagina.get_by_text("Serie guardada.", exact=True)).to_be_visible()
    assert contar(demo_aislada) == 1


def test_medidas_invalidas_tienen_error_inline_y_no_crean_hechos(pagina_demo, demo_aislada, programa_demo):
    pagina = pagina_demo
    iniciar(pagina, demo_aislada)
    entrada = pagina.get_by_label("Repeticiones de Sentadilla ficticia", exact=True)
    entrada.fill("1.5")
    pagina.get_by_role("button", name="Registrar serie de Sentadilla ficticia", exact=True).click()
    expect(pagina.get_by_role("alert")).to_contain_text("Revisá las medidas")
    expect(entrada).to_be_focused()
    assert contar(demo_aislada) == 0


def test_sesion_parcial_conserva_pendientes_y_carga_anterior(pagina_demo, demo_aislada, programa_demo):
    from gimnasio.comun.ids import a_bytes, nuevo_id
    from gimnasio.entrenamiento import repositorio

    with demo_aislada.app.app_context(), transaccion() as cursor:
        reloj = demo_aislada.app.extensions["reloj"]
        anterior = nuevo_id(reloj)
        repositorio.insertar_sesion(cursor, anterior, programa_demo.socio, programa_demo.planificada, reloj.ahora())
        repositorio.insertar_serie(
            cursor,
            nuevo_id(reloj),
            anterior,
            programa_demo.ejercicios[0],
            programa_demo.socio,
            reloj.ahora(),
            repeticiones=9,
            carga="17.50",
        )
    pagina = pagina_demo
    iniciar(pagina, demo_aislada)
    tarjeta = pagina.locator(f'[data-ejercicio="{programa_demo.ejercicios[0]}"]')
    expect(tarjeta).to_contain_text("Series realizadas: 1 · Pendientes: 1")
    expect(tarjeta).to_contain_text("Carga anterior: 17,50 kg · 9 repeticiones")
    expect(pagina.get_by_label("Carga en kg de Sentadilla ficticia", exact=True)).to_have_value("20.50")
    with demo_aislada.app.app_context(), transaccion() as cursor:
        cursor.execute(
            "UPDATE ejercicios_planificados SET carga=NULL WHERE id=%s", (a_bytes(programa_demo.ejercicios[0]),)
        )
    pagina.reload()
    expect(pagina.get_by_label("Carga en kg de Sentadilla ficticia", exact=True)).to_have_value("17.50")
    expect(pagina.get_by_label("Repeticiones de Sentadilla ficticia", exact=True)).to_have_value("8")
    pagina.get_by_role("button", name="Registrar serie de Sentadilla ficticia", exact=True).click()
    expect(tarjeta).to_contain_text("Series realizadas: 2 · Pendientes: 0")
    expect(tarjeta.get_by_role("button", name="Registrar serie de Sentadilla ficticia", exact=True)).to_have_count(0)
