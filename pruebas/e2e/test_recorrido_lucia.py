"""Etapa 2 completa con la semilla reiniciable, sin simular API ni hechos."""

import json
import re
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import expect

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import desde_texto
from pruebas.e2e.test_esqueleto_andante import ingresar, preparar

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("ancho,alto,sin_webgl", [(1440, 900, False), (390, 844, False), (1440, 900, True)])
def test_recorrido_lucia_etapa_2(pagina_demo, demo_aislada, ancho, alto, sin_webgl):
    pagina = pagina_demo
    errores = preparar(pagina, ancho, alto)
    pagina.emulate_media(reduced_motion="no-preference")
    if sin_webgl:
        pagina.add_init_script(
            "const original = HTMLCanvasElement.prototype.getContext;"
            "HTMLCanvasElement.prototype.getContext = function(tipo, ...opciones) {"
            "return tipo.startsWith('webgl') ? null : original.call(this, tipo, ...opciones); };"
        )
    ingresar(pagina, demo_aislada, "socio")
    sentadilla = pagina.locator("[data-ejercicio]").filter(
        has=pagina.get_by_role("heading", name="Sentadilla ficticia", exact=True)
    )
    expect(sentadilla).to_contain_text("Subís 2,5 kg")
    expect(sentadilla).to_contain_text("2 series")
    pagina.get_by_label("Sueño", exact=True).select_option("1")
    pagina.get_by_label("Energía", exact=True).select_option("5")
    pagina.get_by_role("button", name="Guardar chequeo del día", exact=True).click()
    expect(pagina.locator("[data-chequeo]")).to_be_hidden()
    expect(sentadilla).to_contain_text("una serie menos")
    expect(sentadilla).to_contain_text("se anulan las subas de hoy")
    expect(sentadilla).to_contain_text("1 serie")
    pagina.get_by_role("button", name="Iniciar sesión realizada", exact=True).click()
    expect(pagina.locator("[data-sesion-actual]")).to_be_visible()
    sesion = parse_qs(urlparse(pagina.url).query)["sesion"][0]
    expect(sentadilla).to_contain_text("Carga anterior: 20,50 kg · 12 repeticiones")

    # El cardio deja disponibles ambas sentadillas para mostrar luego el freno y el récord.
    pagina.get_by_label("RIR opcional de Caminata ficticia (0 a 10)", exact=True).fill("2")
    pagina.get_by_role("button", name="Máquina ocupada de Caminata ficticia", exact=True).click()
    pagina.get_by_role("button", name=re.compile("Propuesta: Caminata sin cinta ficticia")).click()
    expect(pagina.get_by_text("Sustitución guardada.", exact=True)).to_be_visible()
    pagina.get_by_label("RIR opcional de Caminata sin cinta ficticia (0 a 10)", exact=True).fill("2")
    pagina.get_by_role("button", name="Registrar serie de Caminata sin cinta ficticia", exact=True).click()
    expect(pagina.locator("[data-series]")).to_contain_text("RIR 2")
    expect(pagina.locator("[data-descanso]")).to_be_visible()
    expect(pagina.locator("[data-restantes]")).to_contain_text("s")
    pagina.get_by_role("button", name="Saltear descanso", exact=True).click()

    # Bate la marca histórica antes de reportar dolor en las rodillas.
    pagina.get_by_label("Carga en kg de Sentadilla con mancuernas ficticia", exact=True).fill("23")
    pagina.get_by_label("RIR opcional de Sentadilla con mancuernas ficticia (0 a 10)", exact=True).fill("2")
    pagina.get_by_role("button", name="Registrar serie de Sentadilla con mancuernas ficticia", exact=True).click()
    expect(pagina.locator("[data-record]")).to_have_text("Récord: 23,00 kg en Sentadilla con mancuernas ficticia")
    expect(pagina.locator("[data-record]")).to_have_attribute("aria-live", "polite")

    pagina.get_by_role("button", name="Me duele durante Sentadilla ficticia", exact=True).click()
    sentadilla.get_by_role("checkbox", name="Rodillas", exact=True).click()
    sentadilla.get_by_role("button", name="Guardar dolor reportado", exact=True).click()
    expect(pagina.get_by_text("Dolor reportado guardado. Se avisó al entrenador.", exact=True)).to_be_visible()
    cajon = pagina.locator("[data-ejercicio]").filter(
        has=pagina.get_by_role("heading", name="Sentadilla en cajón ficticia", exact=True)
    )
    expect(cajon).to_contain_text("no involucra la zona con dolor")
    expect(cajon.get_by_label("Carga en kg de Sentadilla en cajón ficticia", exact=True)).to_have_value("20.50")
    cajon.get_by_label("RIR opcional de Sentadilla en cajón ficticia (0 a 10)", exact=True).fill("2")
    cajon.get_by_role("button", name="Registrar serie de Sentadilla en cajón ficticia", exact=True).click()
    expect(pagina.locator("[data-series]")).to_contain_text("Sentadilla en cajón ficticia")

    with demo_aislada.app.app_context(), transaccion() as cursor:
        cursor.execute(
            "SELECT a.freno,a.explicacion,a.entrenador_id,a.socio_id,s.socio_id AS socio_sesion "
            "FROM avisos_entrenador a JOIN sesiones_realizadas s ON s.id=a.sesion_realizada_id "
            "WHERE s.id=%s",
            (desde_texto(sesion).bytes,),
        )
        avisos = cursor.fetchall()
        assert sorted(a["freno"] for a in avisos) == ["chequeo_desfavorable", "dolor_reportado"]
        assert all(a["entrenador_id"] and a["socio_id"] == a["socio_sesion"] for a in avisos)
        assert all(json.loads(a["explicacion"]) for a in avisos)

    pagina.get_by_role("button", name="Terminar sesión", exact=True).click()
    expect(pagina.get_by_text("Resumen actualizado.", exact=True)).to_be_visible()
    cuerpo = pagina.locator("[data-zonas-resumen]")
    if sin_webgl:
        expect(cuerpo.locator("svg")).to_be_visible()
        expect(cuerpo.locator("canvas")).to_have_count(0)
    else:
        expect(cuerpo).to_have_attribute("data-cuerpo3d", "listo")
        expect(cuerpo.locator("canvas")).to_be_visible()
    expect(pagina.locator("[data-zonas-texto]")).to_contain_text("Rodillas: trabajada y con dolor")
    expect(pagina.locator("[data-records]")).to_contain_text("Sentadilla con mancuernas ficticia")
    expect(pagina.locator("[data-sustituciones]")).to_contain_text("máquina ocupada")
    expect(pagina.locator("[data-sustituciones]")).to_contain_text("dolor reportado")
    assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth")
    pagina.get_by_role("link", name="Mi entrenamiento", exact=True).click()
    pagina.get_by_role("button", name="Ver progreso", exact=True).click()
    expect(pagina.locator("[data-progreso] svg")).to_be_visible()
    expect(pagina.locator("[data-progreso] tbody tr").first).to_be_attached()
    assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert errores == []
