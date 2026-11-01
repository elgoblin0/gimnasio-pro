"""Recorrido de etapa 1 con semilla, API y MySQL reales, sin respuestas simuladas."""

from datetime import UTC, timedelta
from urllib.parse import urlparse

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import desde_bytes
from gimnasio.demo.servicio import poner_al_dia

expect = pytest.importorskip("playwright.sync_api").expect
pytestmark = [pytest.mark.e2e, pytest.mark.parametrize("ancho,alto", [(1440, 900), (390, 844)])]


def preparar(pagina, ancho, alto, *, aforo=False):
    pagina.set_viewport_size({"width": ancho, "height": alto})
    errores = []
    pagina.on("pageerror", lambda error: errores.append(str(error)))
    pagina.on(
        "console",
        lambda mensaje: (
            errores.append(mensaje.text) if mensaje.type == "error" and not (aforo and "409" in mensaje.text) else None
        ),
    )
    return errores


def tiempo_de_recorrido(instancia, *, dias=0):
    # Representa el tiempo entre cambios de rol/sesión sin desactivar el límite de la demo.
    instancia.app.extensions["reloj"].avanzar(timedelta(days=dias, minutes=1))
    if dias:
        # El salto de días prepara datos; no debe bloquear el servidor de un solo
        # hilo mientras la interfaz espera una serie o una propuesta.
        with instancia.app.app_context():
            poner_al_dia()


def ingresar(pagina, instancia, rol):
    pagina.goto(instancia.url)
    etiqueta = "recepción" if rol == "recepcion" else "socio"
    pagina.get_by_role("button", name=f"Entrar como {etiqueta}", exact=True).click()
    enlace = "Ir a recepción" if rol == "recepcion" else "Ver mi entrenamiento"
    pagina.get_by_role("link", name=enlace, exact=True).click()
    expect(
        pagina.get_by_text("Recepción lista." if rol == "recepcion" else "Propuesta actualizada.", exact=True)
    ).to_be_visible()
    expect(
        pagina.get_by_text("Datos ficticios que se reinician cada día. Requiere conexión.", exact=True)
    ).to_be_visible()


def salir(pagina, instancia):
    pagina.get_by_role("button", name="Cerrar sesión", exact=True).click()
    expect(pagina.get_by_role("heading", name="Ingresar", exact=True)).to_be_visible()
    assert pagina.request.get(instancia.url + "/api/sesion").json() == {"usuario": None}


def seleccionar_principal(pagina):
    opciones = pagina.locator("#socio option").evaluate_all(
        "opciones => opciones.filter(o => o.value).map(o => ({id:o.value,nombre:o.textContent}))"
    )
    socio = next(o for o in opciones if "Lucía Benítez" in o["nombre"])
    pagina.get_by_label("Socio", exact=True).select_option(socio["id"])
    return socio["id"]


def registrar_entrada(pagina):
    with pagina.expect_response(
        lambda respuesta: urlparse(respuesta.url).path == "/api/entradas" and respuesta.request.method == "POST"
    ) as resultado:
        pagina.locator("[data-entrada]").get_by_role("button", name="Registrar entrada", exact=True).click()
    respuesta = resultado.value
    assert respuesta.status == 201
    expect(pagina.get_by_text("Entrada registrada.", exact=True)).to_be_visible()
    return respuesta.json()["entrada"]["id"]


def registrar_salida(pagina, nombre="Lucía Benítez"):
    pagina.get_by_role("button", name=f"Registrar salida de {nombre}", exact=True).click()
    expect(pagina.get_by_text("Salida registrada.", exact=True)).to_be_visible()


def consulta(pagina, instancia, ruta):
    respuesta = pagina.request.get(instancia.url + ruta)
    assert respuesta.status == 200
    return respuesta.json()


def objetivos(propuesta):
    return {e["id"]: e["objetivos"] for e in propuesta["ejercicios"]}


def resumen_bd(instancia, socio_id):
    from gimnasio.comun.ids import desde_texto

    # Las visitas de Lucía en la semilla son de hace dos días o más: se cuentan las del recorrido.
    desde = (instancia.app.extensions["reloj"].ahora() - timedelta(days=1)).astimezone(UTC).replace(tzinfo=None)
    with instancia.app.app_context(), transaccion() as cursor:
        identificador = desde_texto(socio_id).bytes
        resultado = {}
        cursor.execute(
            "SELECT COUNT(*) AS cantidad FROM entradas WHERE socio_id=%s AND registrada_en >= %s",
            (identificador, desde),
        )
        resultado["entradas"] = cursor.fetchone()["cantidad"]
        cursor.execute(
            "SELECT COUNT(*) AS cantidad FROM salidas s JOIN entradas e ON e.id=s.entrada_id "
            "WHERE e.socio_id=%s AND e.registrada_en >= %s",
            (identificador, desde),
        )
        resultado["salidas"] = cursor.fetchone()["cantidad"]
        cursor.execute(
            "SELECT COUNT(*) AS cantidad FROM series_realizadas s "
            "JOIN sesiones_realizadas sr ON sr.id=s.sesion_realizada_id "
            "WHERE sr.socio_id=%s AND sr.creada_en >= '2026-10-27'",
            (identificador,),
        )
        resultado["series"] = cursor.fetchone()["cantidad"]
        return resultado


def test_recorrido_parcial_salida_reingreso_y_cierre(pagina_demo, demo_aislada, ancho, alto):
    pagina = pagina_demo
    errores = preparar(pagina, ancho, alto)
    ingresar(pagina, demo_aislada, "recepcion")
    socio = seleccionar_principal(pagina)
    inicial = consulta(pagina, demo_aislada, "/api/ocupacion")["ocupacion_registrada"]
    primera = registrar_entrada(pagina)
    expect(pagina.locator("[data-ocupacion]")).to_have_text(f"{inicial + 1} de 60")
    assert [v["id"] for v in consulta(pagina, demo_aislada, "/api/visitas?abiertas=1")["visitas"]] == [primera]
    salir(pagina, demo_aislada)
    tiempo_de_recorrido(demo_aislada)
    ingresar(pagina, demo_aislada, "socio")
    antes = consulta(pagina, demo_aislada, "/api/entrenamiento/propuesta")
    expect(pagina.locator("[data-ajuste]").first).to_contain_text("Subís")
    ocupacion = consulta(pagina, demo_aislada, "/api/ocupacion")
    assert ocupacion["ocupacion_registrada"] == inicial + 1
    assert ocupacion["aforo_maximo"] == 60
    assert set(ocupacion) == {"ocupacion_registrada", "aforo_maximo", "version"}
    assert pagina.request.get(demo_aislada.url + "/api/visitas").status == 403
    assert pagina.locator("[data-salida], [data-entrada]").count() == 0
    if pagina.locator("[data-chequeo]").is_visible():
        pagina.get_by_role("button", name="Saltear", exact=True).click()
    pagina.get_by_role("button", name="Iniciar sesión realizada", exact=True).click()
    expect(pagina.get_by_text("Sesión realizada iniciada.", exact=True)).to_be_visible()
    enlace = pagina.url
    boton = pagina.get_by_role("button", name="Registrar serie de Sentadilla ficticia", exact=True)
    boton.focus()
    with pagina.expect_response(
        lambda r: urlparse(r.url).path.endswith("/series") and r.request.method == "POST"
    ) as guardada:
        pagina.keyboard.press("Enter")
    expect(pagina.get_by_text("Serie guardada.", exact=True)).to_be_visible()
    solicitud = guardada.value.request
    repetida = pagina.request.post(
        solicitud.url,
        data=solicitud.post_data,
        headers={
            "X-Gimnasio": "1",
            "Content-Type": "application/json",
            "Idempotency-Key": solicitud.headers["idempotency-key"],
        },
    )
    assert repetida.status == 201
    assert repetida.json() == guardada.value.json()
    parcial = consulta(pagina, demo_aislada, "/api/entrenamiento/propuesta")
    assert parcial["sesion_planificada"] == antes["sesion_planificada"]
    assert objetivos(parcial) == objetivos(antes)
    assert sum(e["realizado"] for e in parcial["ejercicios"]) == 1
    assert sum(e["pendiente"] for e in parcial["ejercicios"]) == sum(e["pendiente"] for e in antes["ejercicios"]) - 1
    pagina.reload()
    expect(pagina.locator("[data-series] li")).to_have_count(1)
    assert pagina.url == enlace
    assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth")
    salir(pagina, demo_aislada)
    tiempo_de_recorrido(demo_aislada)
    ingresar(pagina, demo_aislada, "recepcion")
    registrar_salida(pagina)
    expect(pagina.locator("[data-ocupacion]")).to_have_text(f"{inicial} de 60")
    seleccionar_principal(pagina)
    segunda = registrar_entrada(pagina)
    assert segunda != primera
    visitas = consulta(pagina, demo_aislada, "/api/visitas?abiertas=1")["visitas"]
    assert len(visitas) == 1 and visitas[0]["id"] == segunda
    assert resumen_bd(demo_aislada, socio) == {"entradas": 2, "salidas": 1, "series": 1}
    registrar_salida(pagina)
    expect(pagina.locator("[data-ocupacion]")).to_have_text(f"{inicial} de 60")
    assert resumen_bd(demo_aislada, socio) == {"entradas": 2, "salidas": 2, "series": 1}
    await_sw = pagina.evaluate("() => navigator.serviceWorker.ready.then(() => true)")
    assert await_sw
    recursos = pagina.evaluate("""async () => {
      const rutas = [];
      for (const nombre of await caches.keys()) {
        if (!nombre.startsWith('gimnasio-estaticos-')) continue;
        for (const pedido of await (await caches.open(nombre)).keys()) rutas.push(new URL(pedido.url).pathname);
      }
      return rutas;
    }""")
    assert {"/js/entrenamiento.js", "/js/recepcion.js", "/js/comun/series.js"} <= set(recursos)
    assert all(not ruta.startswith("/api/") and not ruta.endswith(".html") for ruta in recursos)
    salir(pagina, demo_aislada)
    assert errores == []


def test_visita_sin_entrenamiento_no_acredita_series(pagina_demo, demo_aislada, ancho, alto):
    pagina = pagina_demo
    errores = preparar(pagina, ancho, alto)
    ingresar(pagina, demo_aislada, "socio")
    antes = consulta(pagina, demo_aislada, "/api/entrenamiento/propuesta")
    salir(pagina, demo_aislada)
    tiempo_de_recorrido(demo_aislada)
    ingresar(pagina, demo_aislada, "recepcion")
    socio = seleccionar_principal(pagina)
    registrar_entrada(pagina)
    tiempo_de_recorrido(demo_aislada)
    registrar_salida(pagina)
    salir(pagina, demo_aislada)
    tiempo_de_recorrido(demo_aislada)
    ingresar(pagina, demo_aislada, "socio")
    despues = consulta(pagina, demo_aislada, "/api/entrenamiento/propuesta")
    assert objetivos(despues) == objetivos(antes)
    assert all(e["realizado"] == 0 and e["pendiente"] == e["objetivos"]["series"] for e in despues["ejercicios"])
    assert resumen_bd(demo_aislada, socio) == {"entradas": 1, "salidas": 1, "series": 0}
    salir(pagina, demo_aislada)
    assert errores == []


def test_secuencia_terminada_se_conserva_tras_recarga_y_otra_semana(pagina_demo, demo_aislada, ancho, alto):
    pagina = pagina_demo
    errores = preparar(pagina, ancho, alto)
    ingresar(pagina, demo_aislada, "socio")
    sesiones = []
    for _ in range(2):
        propuesta = consulta(pagina, demo_aislada, "/api/entrenamiento/propuesta")
        assert propuesta["sesion_planificada"] is not None
        if pagina.locator("[data-chequeo]").is_visible():
            pagina.get_by_role("button", name="Saltear", exact=True).click()
        pagina.get_by_role("button", name="Iniciar sesión realizada", exact=True).click()
        expect(pagina.get_by_text("Sesión realizada iniciada.", exact=True)).to_be_visible()
        sesiones.append(pagina.url)
        for ejercicio in propuesta["ejercicios"]:
            for _ in range(ejercicio["pendiente"]):
                pagina.get_by_role("button", name=f"Registrar serie de {ejercicio['nombre']}", exact=True).click()
                expect(pagina.get_by_text("Serie guardada.", exact=True)).to_be_visible()
            # Representa el descanso entre ejercicios con el límite de la demo activo.
            tiempo_de_recorrido(demo_aislada)
        tiempo_de_recorrido(demo_aislada, dias=1)
    assert sesiones[0] != sesiones[1]
    expect(pagina.get_by_role("heading", name="Secuencia realizada", exact=True)).to_be_visible()
    expect(pagina.get_by_role("button", name="Iniciar sesión realizada", exact=True)).to_be_hidden()
    tiempo_de_recorrido(demo_aislada, dias=7)
    pagina.reload()
    expect(pagina.get_by_role("heading", name="Secuencia realizada", exact=True)).to_be_visible()
    propuesta = consulta(pagina, demo_aislada, "/api/entrenamiento/propuesta")
    assert propuesta["sesion_planificada"] is None
    assert propuesta["explicacion"][0]["regla"] == "secuencia_realizada"
    assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth")
    salir(pagina, demo_aislada)
    assert errores == []


def test_aforo_lleno_rechaza_sin_hecho_y_admite_con_nueva_operacion(pagina_demo, demo_aislada, ancho, alto):
    pagina = pagina_demo
    errores = preparar(pagina, ancho, alto, aforo=True)
    with demo_aislada.app.app_context(), transaccion() as cursor:
        cursor.execute("UPDATE sedes SET aforo_maximo=1")
        cursor.execute(
            "SELECT u.id,CONCAT(p.nombre,' ',p.apellido) AS nombre FROM usuarios u "
            "JOIN personas p ON p.id=u.persona_id WHERE u.rol='socio' AND u.activo=TRUE "
            "ORDER BY u.es_demo DESC,u.id LIMIT 2"
        )
        socios = cursor.fetchall()
    ingresar(pagina, demo_aislada, "recepcion")
    pagina.get_by_label("Socio", exact=True).select_option(str(desde_bytes(socios[0]["id"])))
    registrar_entrada(pagina)
    pagina.get_by_label("Socio", exact=True).select_option(str(desde_bytes(socios[1]["id"])))
    with pagina.expect_response(
        lambda r: urlparse(r.url).path == "/api/entradas" and r.request.method == "POST"
    ) as respuesta:
        pagina.locator("[data-entrada]").get_by_role("button", name="Registrar entrada", exact=True).click()
    rechazada = respuesta.value
    assert rechazada.status == 409
    expect(pagina.get_by_role("alert")).to_contain_text("aforo máximo")
    expect(pagina.locator("[data-ocupacion]")).to_have_text("1 de 1")
    assert len(consulta(pagina, demo_aislada, "/api/visitas?abiertas=1")["visitas"]) == 1
    assert resumen_bd(demo_aislada, str(desde_bytes(socios[1]["id"])))["entradas"] == 0
    registrar_salida(pagina, socios[0]["nombre"])
    expect(pagina.locator("[data-ocupacion]")).to_have_text("0 de 1")
    pagina.get_by_label("Socio", exact=True).select_option(str(desde_bytes(socios[1]["id"])))
    with pagina.expect_response(
        lambda r: urlparse(r.url).path == "/api/entradas" and r.request.method == "POST"
    ) as respuesta:
        pagina.locator("[data-entrada]").get_by_role("button", name="Registrar entrada", exact=True).click()
    aceptada = respuesta.value
    assert aceptada.status == 201
    assert aceptada.request.post_data_json["id"] != rechazada.request.post_data_json["id"]
    assert aceptada.request.headers["idempotency-key"] != rechazada.request.headers["idempotency-key"]
    expect(pagina.locator("[data-ocupacion]")).to_have_text("1 de 1")
    registrar_salida(pagina, socios[1]["nombre"])
    expect(pagina.locator("[data-ocupacion]")).to_have_text("0 de 1")
    salir(pagina, demo_aislada)
    assert errores == []
