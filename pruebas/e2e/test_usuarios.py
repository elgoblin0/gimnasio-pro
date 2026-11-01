"""Administración de personal y pérdida de asignación con el editor abierto."""

from uuid import UUID, uuid4

import pytest
from playwright.sync_api import expect

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import desde_bytes
from gimnasio.permisos.servicio import asignar_entrenador, crear_usuario
from pruebas.e2e.test_pantallas_entrenador import entrar, socios_de_marcos

pytestmark = pytest.mark.e2e


def test_administracion_crea_personal_y_asigna_socio(pagina_demo, demo_aislada):
    pagina = pagina_demo
    errores = entrar(pagina, demo_aislada, "administración")
    pagina.wait_for_url("**/administracion.html")
    panel = pagina.locator("#usuarios")
    alta = panel.locator("form").filter(has=pagina.get_by_role("button", name="Crear personal"))
    expect(alta.get_by_role("button", name="Crear personal")).to_be_visible()
    alta.get_by_label("Nombre", exact=True).fill("Personal nuevo")
    alta.get_by_label("Apellido", exact=True).fill("Ficticio")
    alta.get_by_label("Cédula", exact=True).fill("8899801")
    alta.get_by_role("combobox").select_option("entrenador")
    with pagina.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/api/usuarios")) as creacion:
        alta.get_by_role("button", name="Crear personal").click()
    assert creacion.value.status == 201
    entrenadores = pagina.request.get(demo_aislada.url + "/api/usuarios?rol=entrenador&q=8899801")
    assert entrenadores.status == 200
    assert [usuario["id"] for usuario in entrenadores.json()["usuarios"]] == [creacion.value.json()["usuario_id"]]
    expect(panel).to_contain_text("Usuario creado en modo demo, sin clave.")
    # Alta de socio por su ruta propia, sin asignación inicial.
    respuesta = pagina.request.post(
        demo_aislada.url + "/api/socios",
        data={
            "nombre": "Socio sin entrenador",
            "apellido": "Ficticio",
            "cedula": "8899802",
            "consentimiento_datos": True,
        },
        headers={"X-Gimnasio": "1", "Idempotency-Key": str(uuid4())},
    )
    assert respuesta.status == 201
    pagina.get_by_role("button", name="Volver a cargar usuarios").click()
    socio = panel.locator("[data-sin-entrenador] li").filter(has_text="Socio sin entrenador Ficticio")
    expect(socio).to_be_visible()
    socio.get_by_role("combobox").select_option(label="Personal nuevo Ficticio")
    socio.get_by_role("button", name="Asignar entrenador").click()
    expect(panel).to_contain_text("Entrenador asignado.")
    expect(socio).to_have_count(0)
    assert errores == []


def test_editor_sin_asignacion_recibe_403_y_conserva_formulario(pagina_demo, demo_aislada):
    pagina = pagina_demo
    errores = entrar(pagina, demo_aislada, "entrenador")
    pagina.wait_for_url("**/bandeja.html")
    socio_id = socios_de_marcos(pagina)["Gabriela González"]
    pagina.goto(f"{demo_aislada.url}/editor-programa.html?socio={socio_id}")
    pagina.locator('[data-origen^="plantilla:"]').first.click()
    for carga in pagina.locator('[data-campo="carga_partida"]').all():
        carga.fill("0")
    pagina.locator("[data-nombre-sesion]").first.fill("Mi sesión conservada")
    with demo_aislada.app.app_context(), transaccion() as cursor:
        entrenador = crear_usuario(
            cursor, {"nombre": "Nuevo", "apellido": "Ficticio", "cedula": "8899803"}, "entrenador"
        )
    with demo_aislada.app.app_context():
        asignar_entrenador(socio_id, {"entrenador_id": str(entrenador)})
    with pagina.expect_response(
        lambda r: r.request.method == "POST" and r.url.endswith(f"/api/socios/{socio_id}/programas")
    ) as respuesta:
        pagina.locator("[data-publicar]").click()
    assert respuesta.value.status == 403
    expect(pagina.locator("[data-nombre-sesion]").first).to_have_value("Mi sesión conservada")
    guardado = pagina.evaluate("id => JSON.parse(localStorage.getItem(`gimnasio.editor-programa.${id}`))", socio_id)
    assert guardado["semana"]["sesiones"][0]["nombre"] == "Mi sesión conservada"
    # Recupera también al volver a tener la asignación, sin reabrir el registro anterior.
    with demo_aislada.app.app_context(), transaccion() as cursor:
        cursor.execute(
            "SELECT entrenador_id FROM asignaciones_entrenador WHERE socio_id=%s "
            "AND hasta IS NOT NULL ORDER BY desde LIMIT 1",
            (UUID(socio_id).bytes,),
        )
        anterior = str(desde_bytes(cursor.fetchone()["entrenador_id"]))
    with demo_aislada.app.app_context():
        asignar_entrenador(socio_id, {"entrenador_id": anterior})
    pagina.reload()
    expect(pagina.locator("[data-nombre-sesion]").first).to_have_value("Mi sesión conservada")
    assert errores == []
