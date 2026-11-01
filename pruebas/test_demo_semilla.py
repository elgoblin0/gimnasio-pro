"""Semilla ficticia, reinicio transaccional y accesos por rol de la demo."""

import json
from collections import Counter
from datetime import UTC, timedelta
from statistics import median
from uuid import uuid4

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.formatos import normalizar_cedula, normalizar_telefono
from gimnasio.comun.ids import desde_bytes, nuevo_id
from gimnasio.comun.reloj import ZONA_SEDE, fecha_local
from gimnasio.demo import servicio
from gimnasio.demo.nombres import APELLIDOS, NOMBRES
from gimnasio.demo.semilla import main
from gimnasio.socios.servicio import consultar_membresia


def test_las_personas_son_deterministas_y_sus_datos_son_ficticios():
    personas = servicio.generar_personas()
    assert personas == servicio.generar_personas()
    assert len(personas) == 80
    assert len({persona["cedula"] for persona in personas}) == 80
    assert len({persona["correo"] for persona in personas}) == 80
    assert [(p["nombre"], p["apellido"], p["rol"]) for p in personas if p["es_demo"]] == [
        ("Lucía", "Benítez", "socio"),
        ("Rocío", "Ayala", "recepcion"),
        ("Marcos", "Giménez", "entrenador"),
        ("Ana", "Duarte", "administracion"),
    ]
    for indice, persona in enumerate(personas):
        if indice < 40:
            assert 9_900_000 <= int(persona["cedula"]) <= 9_999_999
        else:
            assert 98_000_000 <= int(persona["cedula"]) < 98_000_040
        assert normalizar_cedula(persona["cedula"]) == persona["cedula"]
        assert normalizar_telefono(persona["telefono"]) == persona["telefono"]
        assert persona["telefono"].startswith("+5959")
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


@pytest.mark.bd
def test_reinicio_despues_de_dolor_con_prescripcion_ajustada(app_con_bd):
    from gimnasio.entrenamiento.servicio import consultar_sesion, crear_sesion, registrar_dolor

    app_con_bd.config["MODO_DEMO"] = True
    with app_con_bd.app_context():
        servicio.reiniciar()
        with transaccion() as cursor:
            cursor.execute("SELECT id FROM usuarios WHERE rol='socio' AND es_demo=TRUE")
            socio_id = cursor.fetchone()["id"]
            socio = {"id": str(desde_bytes(socio_id)), "rol": "socio"}
            cursor.execute(
                "SELECT s.id FROM sesiones_planificadas s "
                "JOIN programas_entrenamiento p ON p.id=s.programa_id "
                "WHERE p.socio_id=%s ORDER BY s.posicion LIMIT 1",
                (socio_id,),
            )
            planificada_id = str(desde_bytes(cursor.fetchone()["id"]))
        sesion_id = str(nuevo_id())
        crear_sesion({"id": sesion_id, "sesion_planificada_id": planificada_id}, socio)
        sesion = consultar_sesion(sesion_id, socio)
        registrar_dolor(
            sesion_id,
            {"id": str(nuevo_id()), "ejercicio_planificado_id": sesion["ejercicios"][0]["id"], "zonas": ["cuadriceps"]},
            socio,
        )
        assert len(consultar(app_con_bd, "SELECT id FROM prescripciones_ajustadas")) == 1
        servicio.reiniciar()
        assert consultar(app_con_bd, "SELECT id FROM prescripciones_ajustadas") == []
        assert consultar(app_con_bd, "SELECT id FROM dolores_reportados") == []


def datos_semilla(app):
    return {
        "sedes": consultar(app, "SELECT nombre, zona_horaria, aforo_maximo, actualizada_en FROM sedes"),
        "personas": consultar(
            app,
            """SELECT p.nombre, p.apellido, p.cedula, p.telefono, p.correo, p.creada_en, p.actualizada_en,
                      p.simulada, u.rol, u.es_demo, u.activo, u.creado_en, u.actualizado_en
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
def test_historial_de_ocho_semanas_con_horario_y_aforo(app_con_bd, reloj_fijo):
    from gimnasio.visitas import repositorio as visitas

    app_con_bd.config["MODO_DEMO"] = True

    def reiniciar_y_leer():
        with app_con_bd.app_context():
            servicio.reiniciar()
            with transaccion() as cursor:
                sede = visitas.obtener_sede(cursor)
                assert sede["zona_horaria"] == "America/Asuncion"
                assert json.loads(sede["horario"]) == servicio.HORARIO_SEDE
                assert visitas.contar_ocupacion_registrada(cursor, desde_bytes(sede["id"])) == 0
        return consultar(
            app_con_bd,
            """SELECT e.socio_id, e.registrada_en AS entrada, s.registrada_en AS salida,
                      e.corrige_a, e.anulada, s.corrige_a AS salida_corrige_a,
                      s.anulada AS salida_anulada, u.es_demo, p.correo, a.rol AS autor,
                      e.autor_id = s.autor_id AS mismo_autor, m.desde, m.hasta
               FROM entradas e LEFT JOIN salidas s ON s.entrada_id = e.id
               JOIN usuarios u ON u.id = e.socio_id JOIN personas p ON p.id = u.persona_id
               JOIN usuarios a ON a.id = e.autor_id JOIN membresias m ON m.socio_id = u.id
               ORDER BY e.registrada_en, e.socio_id""",
        )

    primera = reiniciar_y_leer()
    assert primera == reiniciar_y_leer()
    assert len({v["socio_id"] for v in primera}) == 40
    semanas, duraciones, eventos = set(), [], []
    entradas_por_dia = Counter()
    martes = Counter()
    hoy = fecha_local(reloj_fijo.ahora())
    for visita in primera:
        entrada = visita["entrada"].replace(tzinfo=UTC).astimezone(ZONA_SEDE)
        assert visita["salida"] is not None
        salida = visita["salida"].replace(tzinfo=UTC).astimezone(ZONA_SEDE)
        assert hoy - timedelta(weeks=8) <= entrada.date() < hoy
        semanas.add(entrada.date().isocalendar()[:2])
        assert entrada.date() == salida.date()
        franjas = servicio.HORARIO_SEDE.get(str(entrada.isoweekday()), [])
        assert any(inicio <= entrada.strftime("%H:%M") < salida.strftime("%H:%M") <= fin for inicio, fin in franjas)
        duraciones.append((salida - entrada).total_seconds() / 60)
        assert not visita["es_demo"] and visita["correo"].startswith("historial")
        assert visita["desde"] <= hoy <= visita["hasta"]
        assert visita["autor"] == "recepcion" and visita["mismo_autor"]
        assert visita["corrige_a"] is None and visita["salida_corrige_a"] is None
        assert not visita["anulada"] and not visita["salida_anulada"]
        entradas_por_dia[entrada.isoweekday()] += 1
        if entrada.isoweekday() == 2:
            for hora in (14, 18):
                inicio = entrada.replace(hour=hora, minute=0)
                if entrada < inicio + timedelta(hours=1) and salida > inicio:
                    martes[hora] += 1
        eventos.extend(((entrada, 1), (salida, -1)))
    assert len(semanas) >= 8
    assert min(duraciones) >= 40 and max(duraciones) <= 110
    assert 65 <= median(duraciones) <= 75
    assert martes[18] > martes[14]
    assert entradas_por_dia[6] < entradas_por_dia[2]
    ocupacion = 0
    for _, cambio in sorted(eventos):
        ocupacion += cambio
        assert 0 <= ocupacion <= 60
    assert ocupacion == 0


@pytest.mark.bd
def test_la_semilla_copiada_de_las_pruebas_es_igual_a_la_generada(app_con_bd, sembrar_demo):
    app_con_bd.config["MODO_DEMO"] = True
    with app_con_bd.app_context():
        servicio.reiniciar()
    generada = datos_semilla(app_con_bd)
    # La primera puede generarla; la segunda siempre la copia.
    sembrar_demo(app_con_bd)
    sembrar_demo(app_con_bd)
    assert datos_semilla(app_con_bd) == generada


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
        if rol == "socio":
            respuesta = cliente.put(
                "/api/yo/ficha",
                json={"perfil_entrenamiento": {"objetivo": "Fuerza"}},
                headers={"X-Gimnasio": "1", "Idempotency-Key": str(uuid4())},
            )
            assert respuesta.status_code == 200
            assert len(consultar(app_con_bd, "SELECT * FROM perfiles_entrenamiento")) == 1
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
    assert consultar(app_con_bd, "SELECT * FROM perfiles_entrenamiento") == []
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
    assert len(socios) == 145
    assert {a["cedula"] for a in primera["asignaciones"]} == {p["cedula"] for p in socios if not p["simulada"]}
    assert all(a["rol"] == "entrenador" and a["hasta"] is None for a in primera["asignaciones"])
    assert len(primera["membresias"]) == len(socios)
    assert {m["cedula"] for m in primera["membresias"]} == {p["cedula"] for p in socios}
    assert all(m["hasta"] - m["desde"] == timedelta(days=29) for m in primera["membresias"])
    assert len(primera["consentimientos"]) == sum(not p["simulada"] for p in socios) == 85
    assert all(c["tipo"] == "salud" and c["otorgado"] and c["propio"] for c in primera["consentimientos"])
    assert all(p["activo"] for p in primera["personas"])
    assert len({c["clave_hash"] for c in claves if c["clave_hash"]}) == 80
    assert {c["clave_hash"] for c in claves if c["clave_hash"]}.isdisjoint(
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
        assert len(membresias) == 145
        assert all(m["cantidad"] == 1 for m in membresias)
        assert len(con_salud) < len(membresias)
        vigentes = [
            consultar_membresia(desde_bytes(m["socio_id"]), fecha_local(reloj_fijo.ahora())) for m in membresias
        ]
        assert sum(m is not None for m in vigentes) == 144
        assert sum(m is None for m in vigentes) == 1  # Caso explícito de membresía vencida de #48.


@pytest.mark.bd
def test_consentimiento_de_todos_los_socios_de_recorridos(app_con_bd):
    app_con_bd.config["MODO_DEMO"] = True
    with app_con_bd.app_context():
        servicio.reiniciar()
    socios = consultar(
        app_con_bd,
        "SELECT u.id FROM usuarios u JOIN personas p ON p.id=u.persona_id WHERE u.rol='socio' AND NOT p.simulada",
    )
    consentimientos = consultar(app_con_bd, "SELECT socio_id,otorgado FROM consentimientos WHERE tipo='salud'")
    assert {f["id"] for f in socios} == {f["socio_id"] for f in consentimientos if f["otorgado"]}
