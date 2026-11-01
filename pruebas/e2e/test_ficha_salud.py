"""Etapa 5: el socio dedicado al borrado revoca, borra y descarga; el entrenador deja de ver su salud."""

import json
from pathlib import Path

import pytest
from playwright.sync_api import expect

from gimnasio.comun.bd import transaccion

pytestmark = pytest.mark.e2e


def contar(demo, consulta):
    with demo.app.app_context(), transaccion() as cursor:
        cursor.execute(consulta)
        return cursor.fetchone()["n"]


def test_dalila_revoca_ve_la_explicacion_borra_descarga_y_marcos_no_ve_su_salud(navegador, demo_aislada):
    with (
        navegador.new_context(locale="es-PY", accept_downloads=True) as contexto_dalila,
        navegador.new_context(locale="es-PY") as contexto_marcos,
    ):
        dalila = contexto_dalila.new_page()
        dalila.goto(demo_aislada.url)
        dalila.get_by_role("button", name="Entrar como Dalila Borrado", exact=True).click()
        expect(dalila.locator("[data-bienvenida]")).to_be_visible()
        socio = dalila.request.get(demo_aislada.url + "/api/sesion").json()["usuario"]["id"]

        marcos = contexto_marcos.new_page()
        marcos.goto(demo_aislada.url)
        marcos.get_by_role("button", name="Entrar como entrenador", exact=True).click()
        marcos.wait_for_url("**/bandeja.html")
        antes = marcos.request.get(f"{demo_aislada.url}/api/socios/{socio}/salud")
        assert antes.status == 200
        assert "Asma leve" in json.dumps(antes.json())

        dalila.goto(demo_aislada.url + "/ficha.html")
        seccion = dalila.locator("[data-consentimientos]")
        dialogos = []
        dalila.on("dialog", lambda dialogo: (dialogos.append(dialogo.message), dialogo.accept()))
        seccion.get_by_role("button", name="Revocar consentimiento de salud", exact=True).click()
        assert "no tendrás subas" in dialogos[0]
        expect(seccion).to_contain_text("Sin consentimiento de salud vigente.")
        expect(seccion).to_contain_text("no tendré subas automáticas")
        assert marcos.request.get(f"{demo_aislada.url}/api/socios/{socio}/salud").status == 403

        seccion.get_by_label("Escribí BORRAR para confirmar", exact=True).fill("BORRAR")
        seccion.get_by_role("button", name="Borrar mis datos de salud", exact=True).click()
        expect(seccion.get_by_text("Tus datos de salud se borraron.", exact=True)).to_be_visible()
        assert contar(demo_aislada, "SELECT COUNT(*) AS n FROM borrados_salud") == 1

        consultas = dalila.locator("[data-consultas-ficha]")
        expect(consultas).to_contain_text("Marcos Giménez")
        with dalila.expect_download() as descarga:
            consultas.get_by_role("button", name="Descargar mis datos", exact=True).click()
        assert descarga.value.suggested_filename == "mis-datos.json"
        expect(consultas).to_contain_text("Datos descargados.")
        datos = json.loads(Path(descarga.value.path()).read_text(encoding="utf-8"))
        assert "Asma leve" not in json.dumps(datos)

        dalila.reload()
        expect(dalila.locator("[data-salud]")).not_to_contain_text("Asma leve")
