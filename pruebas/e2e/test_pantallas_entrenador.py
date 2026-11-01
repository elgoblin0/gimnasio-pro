"""Pantallas del entrenador y de administración, con API y MySQL reales."""

import json
import re

import pytest

expect = pytest.importorskip("playwright.sync_api").expect
pytestmark = pytest.mark.e2e


@pytest.fixture
def pagina_demo(demo_aislada, playwright):
    """Sin service worker: lo que pasa por él no llega a `page.route` ni a los eventos de la página."""
    with (
        playwright.chromium.launch(channel="chromium") as navegador,
        navegador.new_context(locale="es-PY", service_workers="block") as contexto,
    ):
        yield contexto.new_page()


def entrar(pagina, demo, rol):
    errores = []
    pagina.on("pageerror", lambda error: errores.append(str(error)))
    pagina.goto(demo.url)
    pagina.get_by_role("button", name=f"Entrar como {rol}", exact=True).click()
    return errores


def socios_de_marcos(pagina):
    return {
        f"{s['nombre']} {s['apellido']}": s["id"]
        for s in pagina.evaluate("fetch('/api/entrenador/socios').then(r => r.json())")["socios"]
    }


def api_post(pagina, ruta, cuerpo):
    return pagina.evaluate(
        """async ([ruta, cuerpo]) => {
          const respuesta = await fetch(ruta, {
            method: "POST",
            headers: {"Content-Type": "application/json", "X-Gimnasio": "1", "Idempotency-Key": crypto.randomUUID()},
            body: JSON.stringify(cuerpo),
          });
          return respuesta.status;
        }""",
        [ruta, cuerpo],
    )


def test_administracion_gestiona_plantillas_sin_socio(pagina_demo, demo_aislada):
    pagina = pagina_demo
    errores = entrar(pagina, demo_aislada, "administración")
    pagina.wait_for_url("**/administracion.html")
    pagina.get_by_role("link", name="Plantillas", exact=True).click()
    pagina.get_by_role("link", name="Crear plantilla", exact=True).click()
    expect(pagina.locator("[data-duracion]")).to_be_hidden()
    pagina.get_by_label("Nombre", exact=True).fill("Plantilla ficticia nueva")
    pagina.get_by_label("Descripción", exact=True).fill("Prueba de administración")
    pagina.get_by_role("button", name="Agregar sesión", exact=True).click()
    pagina.locator("[data-agregar-ejercicio]").select_option(label="Sentadilla ficticia")
    expect(pagina.locator('[data-campo="carga_partida"]')).to_have_count(0)
    pagina.get_by_role("button", name="Guardar plantilla", exact=True).click()
    pagina.wait_for_url("**/plantillas.html")
    fila = pagina.locator("[data-plantillas] > li").filter(has_text="Plantilla ficticia nueva")
    fila.get_by_role("link", name="Editar", exact=True).click()
    pagina.get_by_label("Nombre", exact=True).fill("Plantilla ficticia editada")
    pagina.get_by_role("button", name="Guardar plantilla", exact=True).click()
    pagina.wait_for_url("**/plantillas.html")
    fila = pagina.locator("[data-plantillas] > li").filter(has_text="Plantilla ficticia editada")
    fila.get_by_role("button", name="Archivar", exact=True).click()
    expect(fila).to_contain_text("Archivada")
    assert errores == []


def test_plantilla_archivada_con_editor_abierto_conserva_formulario(pagina_demo, demo_aislada):
    from gimnasio.programas.servicio import archivar_plantilla

    pagina = pagina_demo
    errores = entrar(pagina, demo_aislada, "entrenador")
    pagina.wait_for_url("**/bandeja.html")
    socios = socios_de_marcos(pagina)
    socio_id = next(iter(socios.values()))
    pagina.goto(f"{demo_aislada.url}/editor-programa.html?socio={socio_id}")
    origen = pagina.locator('[data-origen^="plantilla:"]').first
    expect(origen).to_be_visible()
    plantilla_id = origen.get_attribute("data-origen").partition(":")[2]
    origen.click()
    for carga in pagina.locator('[data-campo="carga_partida"]').all():
        carga.fill("0")
    pagina.locator("[data-nombre-sesion]").first.fill("Mi sesión conservada")
    with demo_aislada.app.app_context():
        archivar_plantilla(plantilla_id)
    with pagina.expect_response(
        lambda respuesta: (
            respuesta.request.method == "POST" and respuesta.url.endswith(f"/api/socios/{socio_id}/programas")
        )
    ) as respuesta:
        pagina.locator("[data-publicar]").click()
    assert respuesta.value.status == 409
    assert respuesta.value.json()["error"]["codigo"] == "plantilla_archivada"
    expect(pagina.locator("[data-nombre-sesion]").first).to_have_value("Mi sesión conservada")
    expect(pagina.locator("[data-problemas]")).to_contain_text("archivada")
    pagina.reload()
    expect(pagina.locator("[data-nombre-sesion]").first).to_have_value("Mi sesión conservada")
    assert errores == []


def test_administracion_entra_a_equipos_y_ve_el_cambio_de_inmediato(pagina_demo, demo_aislada):
    pagina = pagina_demo
    errores = entrar(pagina, demo_aislada, "administración")
    pagina.wait_for_url("**/administracion.html")
    pagina.get_by_role("link", name="Equipos", exact=True).click()
    pagina.wait_for_url("**/equipos.html")
    expect(pagina.get_by_role("link", name="Bandeja", exact=True)).to_be_hidden()

    barra = pagina.locator('[data-equipo="barra"]')
    expect(barra).to_have_attribute("data-estado-equipo", "disponible")
    barra.get_by_role("button", name="Marcar fuera de servicio", exact=True).focus()
    pagina.keyboard.press("Enter")
    # El foco pasa al motivo: se confirma sin soltar el teclado.
    expect(barra.get_by_label("Motivo opcional")).to_be_focused()
    pagina.keyboard.type("Rota")
    pagina.keyboard.press("Enter")
    expect(barra).to_have_attribute("data-estado-equipo", "fuera_de_servicio")
    expect(barra).to_contain_text("Motivo: Rota")
    expect(barra.get_by_role("button", name="Marcar disponible", exact=True)).to_be_focused()

    expect(pagina.locator("body")).not_to_contain_text("Restricción de salud")
    assert errores == []


def test_alternativas_se_reordenan_con_teclado_sin_perder_el_foco(pagina_demo, demo_aislada):
    pagina = pagina_demo
    errores = entrar(pagina, demo_aislada, "administración")
    pagina.wait_for_url("**/administracion.html")
    pagina.get_by_role("link", name="Equipos", exact=True).click()
    pagina.wait_for_url("**/equipos.html")

    titulo = pagina.get_by_role("heading", name="Sentadilla ficticia", exact=True)
    fila = pagina.locator("[data-ejercicio]").filter(has=titulo)
    renglones = fila.locator("[data-alternativa]")
    primera = renglones.first.get_attribute("data-alternativa")
    renglones.first.get_by_role("button", name=re.compile("^Bajar ")).focus()
    pagina.keyboard.press("Enter")
    expect(renglones.nth(1)).to_have_attribute("data-alternativa", primera)
    expect(fila.locator("[data-mover]:focus")).to_have_count(1)
    assert errores == []


def test_alternativas_ofrecen_solo_lo_compatible_y_explican_el_rechazo(pagina_demo, demo_aislada):
    pagina = pagina_demo
    errores = entrar(pagina, demo_aislada, "administración")
    pagina.wait_for_url("**/administracion.html")
    pagina.get_by_role("link", name="Equipos", exact=True).click()
    pagina.wait_for_url("**/equipos.html")

    fila = pagina.locator("[data-ejercicio]").filter(has_text="Press con mancuernas ficticio").first
    opcion = fila.locator("option").filter(has_text="Sentadilla ficticia")
    expect(opcion).to_contain_text("otro patrón de movimiento")
    expect(opcion).to_be_disabled()

    # Un catálogo viejo puede ofrecer algo que la API ya no acepta: el rechazo se lee con nombres.
    ejercicios = pagina.evaluate("fetch('/api/ejercicios').then(r => r.json())")["ejercicios"]
    sentadilla = next(e for e in ejercicios if e["nombre"] == "Sentadilla ficticia")
    pagina.evaluate(
        """(valor) => {
          const opciones = [...document.querySelectorAll("[data-ejercicio] option")];
          const opcion = opciones.find((o) => o.value === valor && o.disabled);
          opcion.disabled = false;
          opcion.selected = true;
          opcion.closest("form").requestSubmit();
        }""",
        sentadilla["id"],
    )
    expect(pagina.get_by_role("alert").filter(has_text="debe tener igual patrón")).to_contain_text(
        "Sentadilla ficticia"
    )
    assert errores == []


def test_bandeja_recibe_un_aviso_sin_recargar_y_se_revisa_con_teclado(pagina_demo, demo_aislada):
    pagina = pagina_demo
    errores = entrar(pagina, demo_aislada, "entrenador")
    pagina.wait_for_url("**/bandeja.html")
    fila = pagina.locator('[data-grupo="aviso_seguridad"] [data-enlace-socio]').first
    expect(fila).to_be_visible()
    nombre = fila.locator(".fila-nombre").inner_text()
    pagina.evaluate("window.sinRecargar = true")

    # Otro aviso llega mientras la pantalla está abierta: lo trae el sondeo con otra ETag.
    bandeja = pagina.evaluate("fetch('/api/entrenador/bandeja').then(r => r.json())")
    nueva = {
        "id": "01a190f5-7dde-7000-8000-00000000ffff",
        "nombre": "Socio",
        "apellido": "Reciente",
        "figura_cuerpo": None,
        "explicacion": [],
        "motivos": [{"tipo": "aviso_seguridad", "fecha": "2026-10-27T11:59:00+00:00", "aviso_id": "nuevo"}],
    }
    bandeja["grupos"][0]["socios"].append(nueva)
    pagina.route(
        "**/api/entrenador/bandeja",
        lambda ruta: ruta.fulfill(
            json=bandeja, headers={"ETag": '"con-aviso-nuevo"', "Content-Type": "application/json"}
        ),
    )
    expect(pagina.locator('[data-grupo="aviso_seguridad"]')).to_contain_text("Socio Reciente", timeout=12000)
    expect(pagina.locator("[data-estado]")).to_contain_text("Socio Reciente")
    pagina.unroute("**/api/entrenador/bandeja")

    fila = pagina.locator('[data-grupo="aviso_seguridad"] [data-enlace-socio]').filter(has_text=nombre)
    fila.focus()
    pagina.keyboard.press("Enter")
    expect(pagina.locator("[data-hoja]")).to_be_focused()
    expect(pagina.locator("[data-socio-nombre]")).to_have_text(nombre)
    expect(pagina.locator("[data-avisos-sin-revisar] li")).to_have_count(1)

    pagina.get_by_label("Nota opcional").fill("Hablé con el socio.")
    pagina.get_by_role("button", name="Marcar como revisado", exact=True).click()
    expect(pagina.locator("[data-revision]")).to_be_hidden()
    expect(pagina.locator("[data-avisos-revisados]")).to_contain_text("Hablé con el socio.")
    expect(pagina.locator('[data-grupo="aviso_seguridad"]')).not_to_contain_text(nombre, timeout=12000)
    assert pagina.evaluate("window.sinRecargar") is True
    assert errores == []


def test_bandeja_no_muestra_los_datos_del_socio_anterior_si_falla_la_lectura(pagina_demo, demo_aislada):
    pagina = pagina_demo
    entrar(pagina, demo_aislada, "entrenador")
    pagina.wait_for_url("**/bandeja.html")
    filas = pagina.locator('[data-grupo="aviso_seguridad"] [data-enlace-socio]')
    expect(filas.nth(1)).to_be_visible()
    filas.first.click()
    expect(pagina.locator("[data-revision]")).to_be_visible()

    otro = filas.nth(1).get_attribute("data-enlace-socio")
    pagina.route(
        f"**/api/entrenador/socios/{otro}",
        lambda ruta: ruta.fulfill(status=500, json={"error": {"codigo": "error", "mensaje": "No se pudo leer."}}),
    )
    filas.nth(1).click()
    expect(pagina.locator("[data-socio-error]")).to_have_text("No se pudo leer.")
    expect(pagina.locator("[data-socio]")).to_be_hidden()

    pagina.unroute(f"**/api/entrenador/socios/{otro}")
    pagina.go_back()
    expect(pagina.locator("[data-socio-error]")).to_have_text("")
    expect(pagina.locator("[data-socio]")).to_be_visible()


def test_bandeja_guardar_salud_no_oculta_la_ficha_abierta_despues(pagina_demo, demo_aislada):
    pagina = pagina_demo
    entrar(pagina, demo_aislada, "entrenador")
    pagina.wait_for_url("**/bandeja.html")
    filas = pagina.locator('[data-grupo="aviso_seguridad"] [data-enlace-socio]')
    expect(filas.nth(1)).to_be_visible()
    socio_a = filas.first.get_attribute("data-enlace-socio")
    socio_b = filas.nth(1).get_attribute("data-enlace-socio")
    nombre_b = filas.nth(1).locator(".fila-nombre").inner_text()
    filas.first.click()
    salud = pagina.locator("[data-salud]")
    salud.get_by_label("Objetivo", exact=True).select_option("zona")
    salud.get_by_label("Resultado", exact=True).select_option("rodillas")
    salud.get_by_label("Descripción de la restricción", exact=True).fill("Restricción ficticia de prueba")

    retenidas = []
    pagina.route(f"**/api/socios/{socio_a}/salud", lambda ruta: retenidas.append(ruta))
    pagina.route(f"**/api/entrenador/socios/{socio_b}", lambda ruta: retenidas.append(ruta))
    with pagina.expect_request(f"**/api/socios/{socio_a}/salud"):
        salud.get_by_role("button", name="Registrar restricción", exact=True).click()
    with pagina.expect_request(f"**/api/entrenador/socios/{socio_b}"):
        pagina.locator(f'[data-enlace-socio="{socio_b}"]').first.click()

    # La recarga de salud de A termina mientras la lectura de B sigue en curso.
    retenidas[0].continue_()
    expect(salud.locator("h3", has_text="Registrar restricción")).to_be_attached()
    retenidas[1].continue_()
    expect(pagina.locator("[data-socio-nombre]")).to_have_text(nombre_b)
    expect(pagina.locator("[data-socio]")).to_be_visible()


@pytest.mark.parametrize("alternativa", ["sin_webgl", "movimiento_reducido"])
def test_editor_cambia_las_series_por_zona_sin_llamar_a_la_api(pagina_demo, demo_aislada, alternativa):
    pagina = pagina_demo
    pagina.emulate_media(reduced_motion="reduce" if alternativa == "movimiento_reducido" else "no-preference")
    if alternativa == "sin_webgl":
        pagina.add_init_script(
            "const original = HTMLCanvasElement.prototype.getContext;"
            "HTMLCanvasElement.prototype.getContext = function(tipo, ...opciones) {"
            "return tipo.startsWith('webgl') ? null : original.call(this, tipo, ...opciones); };"
        )
    errores = entrar(pagina, demo_aislada, "entrenador")
    pagina.wait_for_url("**/bandeja.html")
    socio = socios_de_marcos(pagina)["Gabriela González"]
    pagina.goto(f"{demo_aislada.url}/editor-programa.html?socio={socio}")

    expect(pagina.locator("[data-sin-sesiones]")).to_be_visible()
    pagina.get_by_role("button", name=re.compile("^Inicial de cuerpo completo")).click()
    primera = pagina.locator(".fila-plan").first
    expect(primera).to_be_visible()

    pagina.wait_for_load_state("networkidle")
    # Después de las descargas: antes, el 3D todavía podría montarse y tapar la silueta.
    expect(pagina.locator(".silueta-volumen")).to_be_visible()
    expect(pagina.locator("canvas")).to_have_count(0)
    zona = pagina.locator('.silueta-volumen [data-zona="cuadriceps"]')
    antes = int(zona.get_attribute("data-series"))
    assert antes > 0
    expect(zona.locator("text")).to_contain_text(f"Cuádriceps · {antes} series")

    llamadas = []
    pagina.on("request", lambda solicitud: llamadas.append(solicitud.url) if "/api/" in solicitud.url else None)
    primera.get_by_role("button", name=re.compile("^Una serie más")).click()
    primera.get_by_role("button", name=re.compile("^Una serie más")).press("Enter")
    expect(zona).to_have_attribute("data-series", str(antes + 2))
    assert llamadas == []
    assert errores == []


def test_cuerpo_3d_del_editor_usa_la_figura_del_socio_y_sigue_cada_edicion(pagina_demo, demo_aislada):
    pagina = pagina_demo
    errores = entrar(pagina, demo_aislada, "entrenador")
    pagina.wait_for_url("**/bandeja.html")
    socio = socios_de_marcos(pagina)["Lucía Benítez"]
    modelos = []
    pagina.on("request", lambda solicitud: modelos.append(solicitud.url) if solicitud.url.endswith(".glb") else None)
    pagina.goto(f"{demo_aislada.url}/editor-programa.html?socio={socio}")
    expect(pagina.locator('[data-volumen][data-cuerpo3d="listo"]')).to_be_visible(timeout=30000)
    assert [modelo.rsplit("/", 1)[1] for modelo in modelos] == ["femenina.glb"]
    # La figura es del socio: desde el editor no se elige.
    expect(pagina.get_by_role("group", name="Figura del cuerpo")).to_have_count(0)

    cifra = pagina.locator(".cuerpo-cifras strong")
    antes = int(cifra.inner_text())
    pagina.locator(".fila-plan").first.get_by_role("button", name=re.compile("^Una serie más")).click()
    expect(cifra).to_have_text(str(antes + 1))
    expect(pagina.locator('.cuerpo-zonas [data-zona="cuadriceps"] .cuerpo-estado')).not_to_have_text("0")
    assert errores == []


def test_editor_conserva_el_formulario_explica_lo_que_falta_y_publica(pagina_demo, demo_aislada):
    pagina = pagina_demo
    errores = entrar(pagina, demo_aislada, "entrenador")
    pagina.wait_for_url("**/bandeja.html")
    socio = socios_de_marcos(pagina)["Gabriela González"]
    pagina.goto(f"{demo_aislada.url}/editor-programa.html?socio={socio}")
    expect(pagina.locator("[data-sin-sesiones]")).to_be_visible()
    # Abrir el editor no es editar: al volver no hay nada que recuperar.
    pagina.reload()
    expect(pagina.locator("[data-sin-sesiones]")).to_be_visible()
    expect(pagina.locator("[data-recuperado]")).to_be_hidden()
    pagina.get_by_role("button", name=re.compile("^Inicial de cuerpo completo")).click()
    expect(pagina.locator(".fila-plan").first).to_be_visible()

    pagina.get_by_role("spinbutton", name="Duración").fill("3")
    pagina.get_by_role("button", name="Publicar versión 1", exact=True).click()
    expect(pagina.locator("[data-problemas]")).to_contain_text("La duración va de 4 a 12 semanas.")
    expect(pagina.locator("[data-problemas]")).to_contain_text("fijá una carga de partida")

    pagina.get_by_role("spinbutton", name="Duración").fill("6")
    pagina.reload()
    expect(pagina.locator("[data-recuperado]")).to_contain_text("Recuperamos")
    expect(pagina.get_by_role("spinbutton", name="Duración")).to_have_value("6")

    for campo in pagina.locator('[data-campo="carga_partida"]').all():
        if not campo.input_value():
            campo.fill("25")
    # La misma carga de partida queda en todas las filas del ejercicio.
    primero = pagina.locator(".fila-plan").first
    assert primero.locator('[data-campo="carga_partida"]').input_value() == "25"

    pagina.get_by_role("button", name="Publicar versión 1", exact=True).click()
    expect(pagina.locator("[data-publicado-titulo]")).to_have_text("Publicaste la versión 1")
    programa = pagina.evaluate(f"fetch('/api/socios/{socio}/programa').then(r => r.json())")["programa"]
    assert programa["version"] == 1 and programa["duracion_semanas"] == 6

    pagina.reload()
    expect(pagina.locator("[data-recuperado]")).to_be_hidden()
    assert errores == []


def test_editor_avisa_si_otra_persona_publico_y_conserva_la_semana(pagina_demo, demo_aislada):
    pagina = pagina_demo
    errores = entrar(pagina, demo_aislada, "entrenador")
    pagina.wait_for_url("**/bandeja.html")
    socio = socios_de_marcos(pagina)["Lucía Benítez"]
    pagina.goto(f"{demo_aislada.url}/editor-programa.html?socio={socio}")
    expect(pagina.locator(".fila-plan").first).to_be_visible()
    pagina.locator("[data-nombre-sesion]").first.fill("Mi sesión corregida")

    vigente = pagina.evaluate(f"fetch('/api/socios/{socio}/programa').then(r => r.json())")["programa"]
    ejercicio = vigente["sesiones"][0]["ejercicios"][0]
    otra = {
        "version_base": vigente["version"],
        "semanas": 4,
        "sesiones": [
            {
                "nombre": "Publicada por otra persona",
                "ejercicios": [
                    {
                        "ejercicio_id": ejercicio["ejercicio_id"],
                        "series": 3,
                        "repeticiones_minimas": 8,
                        "repeticiones_maximas": 12,
                        "carga": ejercicio["carga"],
                    }
                ],
            }
        ],
    }
    assert api_post(pagina, f"/api/socios/{socio}/programas", otra) == 201

    pagina.get_by_role("button", name=re.compile("^Publicar versión")).click()
    conflicto = pagina.locator("[data-conflicto]")
    expect(conflicto).to_contain_text("Otra persona publicó la versión 2")
    expect(pagina.locator("[data-nombre-sesion]").first).to_have_value("Mi sesión corregida")

    conflicto.get_by_role("button", name="Mantener mi semana sobre esa versión").click()
    pagina.get_by_role("button", name="Publicar versión 3", exact=True).click()
    expect(pagina.locator("[data-publicado-titulo]")).to_have_text("Publicaste la versión 3")
    assert errores == []


def test_editor_marca_el_choque_con_restriccion_y_ofrece_alternativas(pagina_demo, demo_aislada):
    pagina = pagina_demo
    errores = entrar(pagina, demo_aislada, "entrenador")
    pagina.wait_for_url("**/bandeja.html")
    socio = socios_de_marcos(pagina)["Lucía Benítez"]
    pagina.goto(f"{demo_aislada.url}/editor-programa.html?socio={socio}")
    primera = pagina.locator(".fila-plan").first
    expect(primera).to_be_visible()
    vigente = pagina.evaluate(f"fetch('/api/socios/{socio}/programa').then(r => r.json())")["programa"]
    ejercicio = vigente["sesiones"][0]["ejercicios"][0]
    alternativa = ejercicio["alternativas"][0]
    error = {
        "codigo": "choque_restriccion",
        "mensaje": "La semana tipo contiene ejercicios con restricciones de salud vigentes.",
        "choques": [
            {
                "ejercicio_id": ejercicio["ejercicio_id"],
                "nombre": ejercicio["nombre"],
                "mensaje": f"{ejercicio['nombre']}: restricción de salud por rodillas.",
                "restriccion": {},
                "alternativas": [{"ejercicio_id": alternativa["ejercicio_id"], "nombre": alternativa["nombre"]}],
            }
        ],
    }
    pagina.route(
        f"**/api/socios/{socio}/programas",
        lambda ruta: ruta.fulfill(status=409, content_type="application/json", body=json.dumps({"error": error})),
    )
    pagina.get_by_role("button", name=re.compile("^Publicar versión")).click()
    fila = pagina.locator(f'.fila-plan[data-fila-ejercicio="{ejercicio["ejercicio_id"]}"]').first
    expect(fila).to_contain_text("restricción de salud por rodillas")
    expect(pagina.locator("[data-problemas]")).to_contain_text("restricción de salud vigente")
    fila.get_by_role("button", name=f"Usar {alternativa['nombre']}").click()
    expect(pagina.locator(f'.fila-plan[data-fila-ejercicio="{alternativa["ejercicio_id"]}"]').first).to_be_visible()
    expect(pagina.locator(f'.fila-plan[data-fila-ejercicio="{ejercicio["ejercicio_id"]}"]')).to_have_count(0)
    assert errores == []
