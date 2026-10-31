"""Recepción usa API y MySQL reales en escritorio y celular, con hechos aislados."""

import re
from datetime import UTC, datetime

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.demo.servicio import poner_al_dia

expect = pytest.importorskip("playwright.sync_api").expect
pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("ancho,alto", [(1440, 900), (390, 844)])
def test_escena_entrada_sin_recarga_y_seleccion_por_teclado(pagina_demo, demo_aislada, ancho, alto):
    pagina = pagina_demo
    pagina.set_viewport_size({"width": ancho, "height": alto})
    ingresar(pagina, demo_aislada)
    escena = pagina.locator('[data-escena-ocupacion][data-lista="true"]')
    expect(escena).to_be_visible()
    expect(pagina.locator("[data-punto-visita]")).to_have_count(0)
    pagina.evaluate("window.recepcionSinRecargar = true")
    pagina.locator("[data-entrada]").get_by_role("button", name="Registrar entrada", exact=True).click()
    punto = pagina.locator("[data-punto-visita]")
    expect(punto).to_have_count(1)
    expect(punto).not_to_have_attribute("aria-label", re.compile("Lucía"))
    expect(pagina.locator("[data-evento]")).to_have_text(re.compile("^Entrada → "))
    expect(pagina.locator("[data-ocupacion-cifra]")).to_have_text("1")
    pagina.keyboard.press("Escape")
    # Desde el selector: Tab llega a registrar entrada y luego al punto anónimo.
    pagina.get_by_label("Socio", exact=True).focus()
    pagina.keyboard.press("Tab")
    pagina.keyboard.press("Tab")
    expect(punto).to_be_focused()
    pagina.keyboard.press("Enter")
    expect(pagina.locator("[data-tarjeta-contextual]")).to_contain_text("Lucía Benítez")
    expect(pagina.locator("[data-rotulo-visita]")).to_contain_text("Lucía Benítez")
    assert pagina.evaluate("window.recepcionSinRecargar === true")
    pagina.keyboard.press("Escape")
    lista = pagina.locator('[aria-labelledby="titulo-zonas"]')
    expect(lista).to_be_visible()
    if ancho <= 600:
        assert escena.bounding_box()["y"] + escena.bounding_box()["height"] <= lista.bounding_box()["y"]
    assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth")


# Sin GPU un cuadro animado ocupa todos los núcleos: la escena se comporta como con movimiento reducido.
SIMULAR_SIN_GPU = """(() => {
  const original = WebGL2RenderingContext.prototype.getParameter;
  WebGL2RenderingContext.prototype.getParameter = function(parametro) {
    const renderizador = this.getExtension('WEBGL_debug_renderer_info')?.UNMASKED_RENDERER_WEBGL;
    return parametro === renderizador ? 'ANGLE (SwiftShader Device)' : original.call(this, parametro);
  };
})();"""


@pytest.mark.parametrize("sin_gpu", [False, True], ids=["movimiento_reducido", "sin_gpu"])
def test_escena_sin_movimiento_ubica_entrada_inmediatamente(pagina_demo, demo_aislada, sin_gpu):
    pagina = pagina_demo
    if sin_gpu:
        pagina.add_init_script(SIMULAR_SIN_GPU)
    else:
        pagina.emulate_media(reduced_motion="reduce")
    ingresar(pagina, demo_aislada)
    expect(pagina.locator('[data-escena-ocupacion][data-lista="true"]')).to_be_visible()
    pagina.locator("[data-entrada]").get_by_role("button", name="Registrar entrada", exact=True).click()
    punto = pagina.locator("[data-punto-visita]")
    expect(punto).to_be_visible()
    pagina.keyboard.press("Escape")
    # Dos cuadros consecutivos tienen la misma posición: no recorre la puerta.
    posiciones = punto.evaluate("""async elemento => {
      await new Promise(requestAnimationFrame);
      await new Promise(requestAnimationFrame);
      const antes = [elemento.style.left, elemento.style.top];
      await new Promise(requestAnimationFrame);
      return [antes, [elemento.style.left, elemento.style.top]];
    }""")
    assert posiciones[0] == posiciones[1]
    expect(pagina.get_by_role("heading", name="Por zona", exact=True)).to_be_visible()
    pagina.locator('[data-elegir-zona="en_la_sede"]').click()
    pagina.locator("[data-visita-zona]").click()
    expect(pagina.locator("[data-tarjeta-contextual]")).to_contain_text("Lucía Benítez")


def test_escena_sin_webgl_conserva_seleccion_por_zona(pagina_demo, demo_aislada):
    pagina = pagina_demo
    pagina.add_init_script("""(() => {
      const original = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function(tipo, ...opciones) {
        return tipo.startsWith('webgl') ? null : original.call(this, tipo, ...opciones);
      };
    })();""")
    ingresar(pagina, demo_aislada)
    expect(pagina.locator("[data-alternativa-escena]")).to_be_visible()
    expect(pagina.locator("[data-escena-ocupacion]")).to_be_hidden()
    expect(pagina.get_by_role("heading", name="Por zona", exact=True)).to_be_visible()
    pagina.locator("[data-entrada]").get_by_role("button", name="Registrar entrada", exact=True).click()
    pagina.keyboard.press("Escape")
    pagina.locator('[data-elegir-zona="en_la_sede"]').click()
    pagina.locator("[data-visita-zona]").click()
    expect(pagina.locator("[data-tarjeta-contextual]")).to_contain_text("Lucía Benítez")


def test_visitas_simuladas_a_las_diecinueve_y_entrada_real(pagina_demo, demo_aislada):
    # Preparar el salto de diez horas fuera de la espera de la interfaz.
    # La consulta de recepción todavía genera el último minuto por la API real.
    demo_aislada.app.extensions["reloj"].fijar(datetime(2026, 10, 27, 21, 59, tzinfo=UTC))
    with demo_aislada.app.app_context():
        poner_al_dia()
    demo_aislada.app.extensions["reloj"].fijar(datetime(2026, 10, 27, 22, tzinfo=UTC))
    ingresar(pagina_demo, demo_aislada)
    expect(pagina_demo.locator("[data-visitas]").get_by_text("simulada", exact=True).first).to_be_visible()
    pagina_demo.locator("[data-visitas]").get_by_role("button", name="Ver tarjeta contextual").first.click()
    expect(pagina_demo.locator("[data-tarjeta-contextual]")).to_contain_text("Socio simulado de la demo")
    pagina_demo.keyboard.press("Escape")
    pagina_demo.locator("[data-entrada]").get_by_role("button", name="Registrar entrada", exact=True).click()
    expect(pagina_demo.get_by_text("Entrada registrada.", exact=True)).to_be_visible()
    assert contar(demo_aislada, "entradas") == 1


def ingresar(pagina, instancia):
    pagina.goto(instancia.url)
    pagina.get_by_role("button", name="Entrar como recepción", exact=True).click()
    pagina.get_by_role("link", name="Ir a recepción", exact=True).click()
    expect(pagina.get_by_text("Recepción lista.", exact=True)).to_be_visible()
    opciones = pagina.locator("#socio option").evaluate_all(
        "opciones => opciones.filter(o => o.value).map(o => ({id:o.value,nombre:o.textContent}))"
    )
    socio = next(o for o in opciones if "Lucía Benítez" in o["nombre"])
    pagina.get_by_label("Socio", exact=True).select_option(socio["id"])
    return socio


def contar(instancia, tabla):
    """Cuenta los hechos de Lucía sin incluir las visitas históricas de otros socios."""
    assert tabla in {"entradas", "salidas"}
    with instancia.app.app_context(), transaccion() as cursor:
        cursor.execute(
            f"""SELECT COUNT(*) AS cantidad FROM {tabla} h
                JOIN usuarios u ON u.id = h.socio_id
                WHERE u.rol = 'socio' AND u.es_demo = TRUE"""
            if tabla == "entradas"
            else """SELECT COUNT(*) AS cantidad FROM salidas h
                    JOIN entradas e ON e.id = h.entrada_id
                    JOIN usuarios u ON u.id = e.socio_id
                    WHERE u.rol = 'socio' AND u.es_demo = TRUE"""
        )
        return cursor.fetchone()["cantidad"]


@pytest.mark.parametrize("ancho,alto", [(1440, 900), (390, 844)])
def test_entrada_abre_tarjeta_y_escape_la_cierra(pagina_demo, demo_aislada, ancho, alto):
    pagina = pagina_demo
    pagina.set_viewport_size({"width": ancho, "height": alto})
    ingresar(pagina, demo_aislada)
    pagina.locator("[data-entrada]").get_by_role("button", name="Registrar entrada", exact=True).click()
    tarjeta = pagina.locator("[data-tarjeta-contextual]")
    expect(tarjeta).to_be_visible()
    expect(tarjeta).to_contain_text("Membresía")
    expect(tarjeta).to_contain_text("Lucía Benítez")
    # La tarjeta abierta no debe tapar las operaciones de recepción (regresión del CI).
    pagina.locator("[data-entrada]").get_by_role("button", name="Registrar entrada", exact=True).click(trial=True)
    for nombre in ("Cerrar sesión", "Registrar salida de Lucía Benítez"):
        pagina.get_by_role("button", name=nombre, exact=True).click(trial=True)
    assert pagina.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    pagina.keyboard.press("Escape")
    expect(tarjeta).not_to_be_visible()
    pagina.get_by_role("button", name="Ver tarjeta contextual de Lucía Benítez").focus()
    pagina.keyboard.press("Enter")
    expect(tarjeta).to_be_visible()


def test_sondeo_entre_recepciones_y_ocupacion_del_socio(pagina_demo, demo_aislada):
    primera = pagina_demo
    segunda = primera.context.new_page()
    socio = primera.context.browser.new_context()
    try:
        ingresar(primera, demo_aislada)
        # Las pestañas comparten la sesión de recepción del mismo contexto.
        segunda.goto(demo_aislada.url + "/recepcion.html")
        expect(segunda.get_by_text("Recepción lista.", exact=True)).to_be_visible()
        expect(segunda.locator("[data-ocupacion]")).to_have_text("0 de 60")
        primera.bring_to_front()
        primera.locator("[data-entrada]").get_by_role("button", name="Registrar entrada", exact=True).click()
        expect(primera.locator("[data-ocupacion]")).to_have_text("1 de 60")
        segunda.bring_to_front()
        expect(segunda.locator("[data-ocupacion]")).to_have_text("1 de 60", timeout=9000)
        expect(segunda.get_by_role("button", name="Registrar salida de Lucía Benítez")).to_be_visible()
        expect(segunda.locator("[data-punto-visita]")).to_have_count(1)
        pagina_socio = socio.new_page()
        pagina_socio.goto(demo_aislada.url)
        pagina_socio.get_by_role("button", name="Entrar como socio", exact=True).click()
        expect(pagina_socio.get_by_role("heading", name="Hola, Lucía", exact=True)).to_be_visible()
        pagina_socio.goto(demo_aislada.url + "/entrenamiento.html")
        expect(pagina_socio.get_by_role("heading", name="Ocupación ahora")).to_be_visible()
        expect(pagina_socio.locator("[data-ocupacion]")).to_have_text("1 de 60")
        expect(pagina_socio.locator("[data-aforo]")).to_have_attribute("value", "1")
        pagina_socio.get_by_role("button", name="Saltear", exact=True).click()
        pagina_socio.get_by_role("button", name="Iniciar sesión realizada", exact=True).click()
        expect(pagina_socio.get_by_text("Sesión realizada iniciada.", exact=True)).to_be_visible()
        pagina_socio.get_by_role("button", name="Registrar serie de Sentadilla ficticia", exact=True).click()
        expect(pagina_socio.get_by_text("Serie guardada.", exact=True)).to_be_visible()
        segunda.bring_to_front()
        expect(segunda.locator('[data-zona-sede="peso_libre"] span')).to_have_text("1", timeout=9000)
        expect(segunda.get_by_role("progressbar", name="Peso libre", exact=True)).to_have_attribute("value", "1")
        expect(segunda.locator("[data-punto-visita]")).to_have_attribute("aria-label", re.compile("Peso libre"))
    finally:
        segunda.close()
        socio.close()


@pytest.mark.parametrize("ancho,alto", [(1440, 900), (390, 844)])
def test_entrada_salida_recarga_y_teclado(pagina_demo, demo_aislada, ancho, alto):
    pagina = pagina_demo
    pagina.set_viewport_size({"width": ancho, "height": alto})
    errores = []
    pagina.on("pageerror", lambda error: errores.append(str(error)))
    pagina.on("console", lambda mensaje: errores.append(mensaje.text) if mensaje.type == "error" else None)
    ingresar(pagina, demo_aislada)
    expect(pagina.get_by_text("Datos ficticios que se reinician cada día. Requiere conexión.")).to_be_visible()
    expect(pagina.locator("[data-ocupacion]")).to_have_text("0 de 60")
    boton = pagina.locator("[data-entrada]").get_by_role("button", name="Registrar entrada", exact=True)
    boton.focus()
    pagina.keyboard.press("Enter")
    expect(pagina.get_by_text("Entrada registrada.", exact=True)).to_be_visible()
    expect(pagina.locator("[data-ocupacion]")).to_have_text("1 de 60")
    expect(pagina.locator("[data-visitas]")).to_contain_text(re.compile(r"lleva \d+ min"))
    pagina.reload()
    expect(pagina.get_by_role("button", name="Registrar salida de Lucía Benítez")).to_be_visible()
    pagina.get_by_role("button", name="Registrar salida de Lucía Benítez").click()
    expect(pagina.get_by_text("Salida registrada.", exact=True)).to_be_visible()
    expect(pagina.locator("[data-ocupacion]")).to_have_text("0 de 60")
    expect(pagina.get_by_text("No hay visitas abiertas.", exact=True)).to_be_visible()
    assert pagina.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert contar(demo_aislada, "entradas") == contar(demo_aislada, "salidas") == 1
    assert errores == []


def test_respuesta_perdida_reintento_manual_y_cierre_sin_salida(pagina_demo, demo_aislada):
    pagina = pagina_demo
    pagina.add_init_script("""(() => {
      const original = window.fetch;
      window.enviosDeEntrada = [];
      let perder = true;
      window.fetch = async (ruta, opciones) => {
        if (ruta !== '/api/entradas' || opciones?.method !== 'POST') return original(ruta, opciones);
        window.enviosDeEntrada.push([opciones.body, opciones.headers['Idempotency-Key']]);
        const respuesta = await original(ruta, opciones);
        if (perder) { perder = false; throw new TypeError('Respuesta perdida después del commit'); }
        return respuesta;
      };
    })();""")
    ingresar(pagina, demo_aislada)
    pagina.locator("[data-entrada]").get_by_role("button", name="Registrar entrada", exact=True).dblclick()
    expect(pagina.get_by_role("button", name="Reintentar operación")).to_be_visible()
    assert contar(demo_aislada, "entradas") == 1
    pagina.get_by_role("button", name="Reintentar operación").click()
    expect(pagina.get_by_text("Entrada registrada.", exact=True)).to_be_visible()
    envios = pagina.evaluate("window.enviosDeEntrada")
    assert len(envios) == 2
    assert envios[0] == envios[1]
    assert contar(demo_aislada, "entradas") == 1
    pagina.get_by_role("button", name="Cerrar sesión", exact=True).click()
    expect(pagina.get_by_role("heading", name="Ingresar", exact=True)).to_be_visible()
    assert contar(demo_aislada, "salidas") == 0


def test_red_fallida_no_reenvia_al_recuperar_conexion(pagina_demo, demo_aislada):
    pagina = pagina_demo
    ingresar(pagina, demo_aislada)
    pagina.context.set_offline(True)
    pagina.locator("[data-entrada]").get_by_role("button", name="Registrar entrada", exact=True).click()
    expect(pagina.get_by_role("button", name="Reintentar operación")).to_be_visible()
    pagina.context.set_offline(False)
    pagina.get_by_role("button", name="Actualizar visitas").click()
    expect(pagina.get_by_text("No hay visitas abiertas.", exact=True)).to_be_visible()
    assert contar(demo_aislada, "entradas") == 0
    pagina.get_by_role("button", name="Reintentar operación").click()
    expect(pagina.get_by_text("Entrada registrada.", exact=True)).to_be_visible()
    assert contar(demo_aislada, "entradas") == 1


def test_membresia_aforo_y_acceso_del_socio(pagina_demo, demo_aislada):
    pagina = pagina_demo
    socio = ingresar(pagina, demo_aislada)
    with demo_aislada.app.app_context(), transaccion() as cursor:
        from gimnasio.comun.ids import a_bytes, desde_texto

        cursor.execute(
            "UPDATE membresias SET desde='2026-09-27', hasta='2026-10-26' WHERE socio_id=%s",
            (a_bytes(desde_texto(socio["id"])),),
        )
    pagina.locator("[data-entrada]").get_by_role("button", name="Registrar entrada", exact=True).click()
    expect(pagina.get_by_role("alert")).to_contain_text("membresía vigente")
    with demo_aislada.app.app_context(), transaccion() as cursor:
        cursor.execute(
            "UPDATE membresias SET hasta='2026-11-26' WHERE socio_id=%s", (a_bytes(desde_texto(socio["id"])),)
        )
        cursor.execute("UPDATE sedes SET aforo_maximo=0")
    pagina.locator("[data-entrada]").get_by_role("button", name="Registrar entrada", exact=True).click()
    expect(pagina.get_by_role("alert")).to_contain_text("aforo máximo")
    assert contar(demo_aislada, "entradas") == 0
    pagina.get_by_role("button", name="Cerrar sesión", exact=True).click()
    pagina.get_by_role("button", name="Entrar como socio", exact=True).click()
    expect(pagina.get_by_role("heading", name="Hola, Lucía", exact=True)).to_be_visible()
    pagina.goto(demo_aislada.url + "/recepcion.html")
    expect(pagina.get_by_text("Ingresá como recepción desde el inicio para registrar visitas.")).to_be_visible()
    expect(pagina.locator("[data-contenido]")).to_be_hidden()


def test_foco_durante_post_no_intercala_lecturas_anteriores(pagina_demo, demo_aislada):
    pagina = pagina_demo
    pagina.add_init_script("""(() => {
      const original = window.fetch;
      window.lecturasDeVisitas = 0;
      window.fetch = async (ruta, opciones) => {
        if (ruta === '/api/ocupacion' || ruta === '/api/visitas?abiertas=1' || ruta === '/api/visitas/socios') {
          window.lecturasDeVisitas++;
        }
        const respuesta = await original(ruta, opciones);
        if (ruta === '/api/entradas' && opciones?.method === 'POST') {
          window.entradaEnEspera = true;
          await new Promise(resolver => { window.liberarEntrada = resolver; });
        }
        return respuesta;
      };
    })();""")
    ingresar(pagina, demo_aislada)
    lecturas = pagina.evaluate("window.lecturasDeVisitas")
    pagina.locator("[data-entrada]").get_by_role("button", name="Registrar entrada", exact=True).click()
    pagina.wait_for_function("window.entradaEnEspera === true")
    pagina.evaluate("window.dispatchEvent(new Event('focus'))")
    pagina.get_by_role("button", name="Actualizar visitas").click()
    assert pagina.evaluate("window.lecturasDeVisitas") == lecturas
    pagina.evaluate("window.liberarEntrada()")
    expect(pagina.locator("[data-ocupacion]")).to_have_text("1 de 60")
    expect(pagina.get_by_role("button", name="Registrar salida de Lucía Benítez")).to_be_visible()
    # La propia respuesta del POST actualiza la pantalla sin lecturas adicionales.
    assert pagina.evaluate("window.lecturasDeVisitas") == lecturas


def test_reintento_espera_la_lectura_en_curso(pagina_demo, demo_aislada):
    pagina = pagina_demo
    pagina.add_init_script("""(() => {
      const original = window.fetch;
      let perder = true;
      window.enviosDeEntrada = 0;
      window.fetch = async (ruta, opciones) => {
        if (ruta === '/api/entradas' && opciones?.method === 'POST') {
          window.enviosDeEntrada++;
          const respuesta = await original(ruta, opciones);
          if (perder) { perder = false; throw new TypeError('Respuesta perdida'); }
          return respuesta;
        }
        const respuesta = await original(ruta, opciones);
        if (ruta === '/api/ocupacion' && window.retenerLectura) {
          window.lecturaEnEspera = true;
          await new Promise(resolver => { window.liberarLectura = resolver; });
        }
        return respuesta;
      };
    })();""")
    ingresar(pagina, demo_aislada)
    pagina.locator("[data-entrada]").get_by_role("button", name="Registrar entrada", exact=True).click()
    expect(pagina.get_by_role("button", name="Reintentar operación")).to_be_visible()
    pagina.evaluate("window.retenerLectura = true")
    pagina.get_by_role("button", name="Actualizar visitas").click()
    pagina.wait_for_function("window.lecturaEnEspera === true")
    expect(pagina.get_by_role("button", name="Reintentar operación")).to_be_disabled()
    pagina.evaluate("document.querySelector('[data-reintentar]').dispatchEvent(new Event('click'))")
    assert pagina.evaluate("window.enviosDeEntrada") == 1
    pagina.evaluate("window.retenerLectura = false; window.liberarLectura()")
    expect(pagina.get_by_role("button", name="Reintentar operación")).to_be_enabled()
    pagina.get_by_role("button", name="Reintentar operación").click()
    expect(pagina.get_by_text("Entrada registrada.", exact=True)).to_be_visible()
    expect(pagina.locator("[data-ocupacion]")).to_have_text("1 de 60")
    assert contar(demo_aislada, "entradas") == 1


def test_conciliar_salida_desaparece_sin_recargar(pagina_demo, demo_aislada):
    from datetime import timedelta

    from gimnasio.comun.ids import desde_texto, nuevo_id
    from gimnasio.comun.reloj import reloj_actual
    from gimnasio.visitas import repositorio

    pagina = pagina_demo
    socio = ingresar(pagina, demo_aislada)
    with demo_aislada.app.app_context(), transaccion() as cursor:
        sede = repositorio.obtener_sede(cursor)
        from gimnasio.comun.ids import desde_bytes

        # El autor es recepción; la sesión HTTP se consulta por la API real.
        autor = pagina.evaluate("fetch('/api/sesion').then(r => r.json()).then(d => d.usuario.id)")
        ahora = reloj_actual().ahora()
        repositorio.insertar_entrada(
            cursor,
            nuevo_id(),
            desde_texto(socio["id"]),
            desde_bytes(sede["id"]),
            desde_texto(autor),
            ahora - timedelta(hours=8),
        )
    pagina.get_by_role("button", name="Actualizar visitas").click()
    pagina.get_by_role("button", name="Conciliar salida", exact=True).click()
    dialogo = pagina.get_by_role("dialog", name="Conciliar salida", exact=True)
    dialogo.get_by_label("Motivo", exact=True).fill("El socio confirmó que salió una hora después de entrar")
    dialogo.get_by_role("button", name="Confirmar salida", exact=True).click()
    expect(dialogo).not_to_be_visible()
    expect(pagina.locator("[data-ocupacion]")).to_have_text("0 de 60")
    expect(pagina.locator("[data-visitas] li")).to_have_count(0)
    assert contar(demo_aislada, "salidas") == 1


@pytest.mark.parametrize("rol,pantalla", [("socio", "entrenamiento"), ("recepcion", "recepcion")])
def test_mejores_horarios_con_etiqueta_prevision(pagina_demo, demo_aislada, rol, pantalla):
    pagina = pagina_demo
    pagina.goto(demo_aislada.url)
    pagina.locator(f"[data-rol='{rol}']").click()
    expect(pagina.locator("[data-bienvenida]")).to_be_visible()
    pagina.goto(demo_aislada.url + f"/{pantalla}.html")
    bloque = pagina.locator("[data-mejores-horarios]")
    expect(bloque).to_be_visible()
    expect(bloque.get_by_role("heading", level=2)).to_contain_text("previsi")
    expect(bloque.get_by_role("heading", name="Hoy", exact=True)).to_be_visible()
    expect(bloque.locator("[data-horarios-manana] h3")).to_be_visible()
    expect(bloque.locator("li")).to_have_count(6)
