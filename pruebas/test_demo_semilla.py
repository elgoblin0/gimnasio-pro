"""Semilla ficticia, reinicio transaccional y accesos por rol de la demo."""

from datetime import timedelta

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.formatos import normalizar_cedula, normalizar_telefono
from gimnasio.demo import servicio
from gimnasio.demo.nombres import APELLIDOS, NOMBRES
from gimnasio.demo.semilla import main
from gimnasio.socios.servicio import consultar_membresia


def test_las_personas_son_deterministas_y_sus_datos_son_ficticios():
    personas = servicio.generar_personas()
    assert personas == servicio.generar_personas()
    assert len(personas) == 40
    assert len({persona["cedula"] for persona in personas}) == 40
    assert len({persona["correo"] for persona in personas}) == 40
    assert [(p["nombre"], p["apellido"], p["rol"]) for p in personas if p["es_demo"]] == [
        ("Lucía", "Benítez", "socio"),
        ("Rocío", "Ayala", "recepcion"),
        ("Marcos", "Giménez", "entrenador"),
        ("Ana", "Duarte", "administracion"),
    ]
    for persona in personas:
        assert 9_900_000 <= int(persona["cedula"]) <= 9_999_999
        assert normalizar_cedula(persona["cedula"]) == persona["cedula"]
        assert normalizar_telefono(persona["telefono"]) == persona["telefono"]
        assert persona["telefono"].startswith("+59599")
        assert persona["correo"].endswith("@demo.gimnasio.invalid")
    for persona in personas[4:]:
        assert persona["nombre"] in NOMBRES
        assert persona["apellido"] in APELLIDOS
        assert persona["rol"] == "socio"
        assert not persona["es_demo"]


def test_el_comando_exige_reiniciar_antes_de_acceder_a_la_base():
    with pytest.raises(SystemExit) as error:
        main([])
    assert error.value.code == 2


def consultar(app, sql):
    with app.app_context(), transaccion() as cursor:
        cursor.execute(sql)
        return cursor.fetchall()


def datos_semilla(app):
    return {
        "sedes": consultar(app, "SELECT nombre, zona_horaria, aforo_maximo, actualizada_en FROM sedes"),
        "personas": consultar(
            app,
            """SELECT p.nombre, p.apellido, p.cedula, p.telefono, p.correo, p.creada_en, p.actualizada_en,
                      u.rol, u.es_demo, u.activo, u.creado_en, u.actualizado_en
               FROM personas p JOIN usuarios u ON u.persona_id = p.id ORDER BY p.cedula""",
        ),
        "asignaciones": consultar(
            app,
            """SELECT p.cedula, e.rol, a.desde, a.hasta
               FROM asignaciones_entrenador a JOIN usuarios s ON s.id = a.socio_id
               JOIN personas p ON p.id = s.persona_id JOIN usuarios e ON e.id = a.entrenador_id
               ORDER BY p.cedula""",
        ),
        "consentimientos": consultar(
            app,
            """SELECT p.cedula, c.tipo, c.version_texto, c.otorgado, c.registrado_en,
                      c.socio_id = c.registrado_por AS propio
               FROM consentimientos c JOIN usuarios s ON s.id = c.socio_id
               JOIN personas p ON p.id = s.persona_id ORDER BY p.cedula""",
        ),
        "membresias": consultar(
            app,
            """SELECT p.cedula, m.desde, m.hasta, m.actualizada_en
               FROM membresias m JOIN usuarios u ON u.id = m.socio_id
               JOIN personas p ON p.id = u.persona_id ORDER BY p.cedula""",
        ),
        "intentos": consultar(app, "SELECT * FROM intentos_de_ingreso"),
        "migraciones": consultar(app, "SELECT * FROM migraciones_aplicadas ORDER BY version"),
    }


@pytest.mark.bd
def test_dos_reinicios_dejan_los_mismos_datos(app_con_bd, reloj_fijo):
    app_con_bd.config["MODO_DEMO"] = True
    migraciones = consultar(app_con_bd, "SELECT * FROM migraciones_aplicadas ORDER BY version")
    with app_con_bd.app_context():
        servicio.reiniciar()
    primera = datos_semilla(app_con_bd)
    claves = consultar(app_con_bd, "SELECT clave_hash FROM usuarios")

    # Un ingreso entre reinicios agrega datos que también deben desaparecer.
    app_con_bd.config["MODO_DEMO"] = True
    cliente = app_con_bd.test_client()
    for rol, nombre in (
        ("socio", "Lucía"),
        ("recepcion", "Rocío"),
        ("entrenador", "Marcos"),
        ("administracion", "Ana"),
    ):
        respuesta = cliente.post(f"/api/sesion/demo/{rol}", headers={"X-Gimnasio": "1"})
        assert respuesta.status_code == 200
        assert respuesta.get_json()["usuario"]["nombre"] == nombre
    assert (
        cliente.post(
            "/api/sesion", json={"identificador": "9900000", "clave": "no-publicada"}, headers={"X-Gimnasio": "1"}
        ).status_code
        == 401
    )
    assert len(consultar(app_con_bd, "SELECT * FROM intentos_de_ingreso")) == 1

    with app_con_bd.app_context():
        servicio.reiniciar()
    assert datos_semilla(app_con_bd) == primera
    assert primera["migraciones"] == migraciones
    assert primera["sedes"] == [
        {
            "nombre": "Gimnasio Pro Demo · Asunción",
            "zona_horaria": "America/Asuncion",
            "aforo_maximo": 60,
            "actualizada_en": reloj_fijo.ahora().replace(tzinfo=None),
        }
    ]
    socios = [p for p in primera["personas"] if p["rol"] == "socio"]
    assert len(socios) == 37
    assert {a["cedula"] for a in primera["asignaciones"]} == {p["cedula"] for p in socios}
    assert all(a["rol"] == "entrenador" and a["hasta"] is None for a in primera["asignaciones"])
    assert len(primera["membresias"]) == len(socios)
    assert {m["cedula"] for m in primera["membresias"]} == {p["cedula"] for p in socios}
    assert all(m["hasta"] - m["desde"] == timedelta(days=29) for m in primera["membresias"])
    assert len(primera["consentimientos"]) == round(len(socios) * 0.8) == 30
    assert all(c["tipo"] == "salud" and c["otorgado"] and c["propio"] for c in primera["consentimientos"])
    assert all(p["activo"] for p in primera["personas"])
    assert len({c["clave_hash"] for c in claves if c["clave_hash"]}) == 40
    assert {c["clave_hash"] for c in claves}.isdisjoint(
        c["clave_hash"] for c in consultar(app_con_bd, "SELECT clave_hash FROM usuarios")
    )


@pytest.mark.bd
def test_las_fechas_siguen_el_reloj_de_la_app(app_con_bd, reloj_fijo):
    app_con_bd.config["MODO_DEMO"] = True
    with app_con_bd.app_context():
        servicio.reiniciar()
    primera = datos_semilla(app_con_bd)
    intervalo = timedelta(days=9)
    reloj_fijo.avanzar(intervalo)
    with app_con_bd.app_context():
        servicio.reiniciar()
    segunda = datos_semilla(app_con_bd)
    for tabla, columnas in (
        ("personas", ("creada_en", "actualizada_en", "creado_en", "actualizado_en")),
        ("sedes", ("actualizada_en",)),
        ("asignaciones", ("desde",)),
        ("consentimientos", ("registrado_en",)),
        ("membresias", ("desde", "hasta", "actualizada_en")),
    ):
        for anterior, posterior in zip(primera[tabla], segunda[tabla], strict=True):
            for columna in columnas:
                assert posterior[columna] == anterior[columna] + intervalo
    assert segunda["migraciones"] == primera["migraciones"]


@pytest.mark.bd
def test_un_error_durante_la_carga_conserva_los_datos_anteriores(app_con_bd, monkeypatch):
    app_con_bd.config["MODO_DEMO"] = True
    with app_con_bd.app_context():
        servicio.reiniciar()
    anterior = datos_semilla(app_con_bd)
    usuarios = consultar(app_con_bd, "SELECT * FROM usuarios ORDER BY id")

    def fallar(*argumentos, **nombrados):
        raise RuntimeError("fallo simulado durante la carga")

    monkeypatch.setattr(servicio.permisos, "crear_usuario", fallar)
    with app_con_bd.app_context(), pytest.raises(RuntimeError, match="fallo simulado"):
        servicio.reiniciar()
    assert datos_semilla(app_con_bd) == anterior
    assert consultar(app_con_bd, "SELECT * FROM usuarios ORDER BY id") == usuarios


@pytest.mark.bd
def test_membresias_de_semilla_sin_superposiciones_y_sin_depender_de_salud(app_con_bd, reloj_fijo):
    app_con_bd.config["MODO_DEMO"] = True
    from gimnasio.comun.ids import desde_bytes
    from gimnasio.comun.reloj import fecha_local

    with app_con_bd.app_context():
        servicio.reiniciar()
        with transaccion() as cursor:
            cursor.execute("SELECT socio_id, COUNT(*) AS cantidad FROM membresias GROUP BY socio_id")
            membresias = cursor.fetchall()
            cursor.execute("SELECT DISTINCT socio_id FROM consentimientos WHERE tipo = 'salud'")
            con_salud = {fila["socio_id"] for fila in cursor.fetchall()}
        assert len(membresias) == 37
        assert all(m["cantidad"] == 1 for m in membresias)
        assert len(con_salud) < len(membresias)
        vigentes = [
            consultar_membresia(desde_bytes(m["socio_id"]), fecha_local(reloj_fijo.ahora())) for m in membresias
        ]
        assert sum(m is not None for m in vigentes) == 36
        assert sum(m is None for m in vigentes) == 1  # Caso explícito de membresía vencida de #48.
