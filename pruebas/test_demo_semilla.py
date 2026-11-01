"""Semilla ficticia, reinicio transaccional y accesos por rol de la demo."""

import json
from collections import Counter
from datetime import UTC, datetime, timedelta
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
            cursor.execute("SELECT id FROM usuarios WHERE rol='socio' AND es_demo=TRUE ORDER BY id LIMIT 1")
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
               JOIN personas p ON p.id = s.persona_id ORDER BY p.cedula, c.registrado_en, c.id""",
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
            assert len(consultar(app_con_bd, "SELECT * FROM perfiles_entrenamiento")) == 5
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
    assert len(consultar(app_con_bd, "SELECT * FROM perfiles_entrenamiento")) == 5
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
    assert len(socios) == 149
    sin_entrenador = {"95000003"}
    assert {a["cedula"] for a in primera["asignaciones"]} == {
        p["cedula"] for p in socios if not p["simulada"] and p["cedula"] not in sin_entrenador
    }
    assert all(a["rol"] == "entrenador" and a["hasta"] is None for a in primera["asignaciones"])
    assert len(primera["membresias"]) == len(socios)
    assert {m["cedula"] for m in primera["membresias"]} == {p["cedula"] for p in socios}
    assert all(m["hasta"] - m["desde"] == timedelta(days=29) for m in primera["membresias"])
    assert len(primera["consentimientos"]) == sum(not p["simulada"] for p in socios) + 1 == 90
    assert all(c["tipo"] == "salud" and c["propio"] for c in primera["consentimientos"])
    # La única revocación es la del socio que muestra la progresión congelada.
    assert [c["otorgado"] for c in primera["consentimientos"]].count(False) == 1
    assert all(p["activo"] for p in primera["personas"])
    assert len({c["clave_hash"] for c in claves if c["clave_hash"]}) == 82
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
        assert len(membresias) == 149
        assert all(m["cantidad"] == 1 for m in membresias)
        assert len(con_salud) < len(membresias)
        vigentes = [
            consultar_membresia(desde_bytes(m["socio_id"]), fecha_local(reloj_fijo.ahora())) for m in membresias
        ]
        assert sum(m is not None for m in vigentes) == 148
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


# Domingo 23:30, lunes 08:00 y miércoles 18:00 en Asunción (UTC-3).
RELOJES_DE_LA_SEMANA = {
    "domingo_a_la_noche": datetime(2026, 11, 2, 2, 30, tzinfo=UTC),
    "lunes_a_la_manana": datetime(2026, 11, 2, 11, 0, tzinfo=UTC),
    "miercoles_a_la_tarde": datetime(2026, 10, 28, 21, 0, tzinfo=UTC),
}
HEADERS = {"X-Gimnasio": "1"}


def usuario_demo(app, nombre):
    return consultar(
        app,
        f"SELECT u.id FROM usuarios u JOIN personas p ON p.id=u.persona_id WHERE u.es_demo AND p.nombre='{nombre}'",
    )[0]["id"]


def agenda_de(app, rol, nombre):
    cliente = app.test_client()
    respuesta = cliente.post(
        f"/api/sesion/demo/{rol}", json={"usuario_id": str(desde_bytes(usuario_demo(app, nombre)))}, headers=HEADERS
    )
    assert respuesta.status_code == 200
    respuesta = cliente.get("/api/clases/agenda")
    assert respuesta.status_code == 200
    return respuesta.get_json()


def fecha_fijada(app, clase):
    filas = consultar(
        app,
        f"SELECT o.fecha FROM ocurrencias_clase o JOIN clases c ON c.id=o.clase_id WHERE c.nombre='{clase}'",
    )
    assert len(filas) == 1
    return filas[0]["fecha"].isoformat()


def ocurrencia_de(agenda, app, clase):
    fecha = fecha_fijada(app, clase)
    return next(o for o in agenda["ocurrencias"] if o["clase"] == clase and o["fecha"] == fecha)


@pytest.fixture(params=RELOJES_DE_LA_SEMANA)
def semilla_de_operacion(request, app_con_bd, reloj_fijo):
    app_con_bd.config["MODO_DEMO"] = True
    reloj_fijo.fijar(RELOJES_DE_LA_SEMANA[request.param])
    with app_con_bd.app_context():
        servicio.reiniciar()
    return app_con_bd, reloj_fijo


@pytest.mark.bd
def test_clases_de_la_semana_con_llena_libre_y_cancelada(semilla_de_operacion):
    app, reloj = semilla_de_operacion
    clases = consultar(
        app,
        "SELECT c.archivada, p.nombre FROM clases c JOIN usuarios u ON u.id=c.entrenador_id "
        "JOIN personas p ON p.id=u.persona_id",
    )
    assert len(clases) == 8
    assert {c["nombre"] for c in clases} == {"Marcos"}
    assert not any(c["archivada"] for c in clases)
    agenda = agenda_de(app, "socio", "Lucía")
    ahora = reloj.ahora().astimezone(servicio.ZONA_SEDE).replace(tzinfo=None)

    # La clase llena sigue siendo futura y está dentro del rango de la agenda, a cualquier hora.
    llenas = [o for o in agenda["ocurrencias"] if o["espera"] > 0]
    assert [o["clase"] for o in llenas] == [servicio.CLASE_LLENA]
    llena = llenas[0]
    assert (llena["cupo"], llena["libres"], llena["espera"], llena["cancelada"]) == (3, 0, 2, False)
    assert agenda["desde"] <= llena["fecha"] <= agenda["hasta"]
    assert datetime.fromisoformat(f"{llena['fecha']}T{llena['hora_inicio']}") > ahora
    assert llena["reserva"]["estado"] == "con_lugar"

    hugo = agenda_de(app, "socio", "Hugo")
    suya = next(o for o in hugo["ocurrencias"] if o["identificador"] == llena["identificador"])
    assert (suya["reserva"]["estado"], suya["reserva"]["posicion"]) == ("en_espera", 1)

    libre = ocurrencia_de(agenda, app, servicio.CLASE_CON_CUPO)
    assert libre["libres"] > 0 and libre["espera"] == 0 and not libre["cancelada"]
    assert ocurrencia_de(agenda, app, servicio.CLASE_CANCELADA)["cancelada"]


@pytest.mark.bd
def test_membresias_con_pagos_y_dos_socios_con_pago_pendiente(semilla_de_operacion):
    from gimnasio.reglas.membresia import pago_pendiente
    from gimnasio.visitas.servicio import consultar_tarjeta

    app, reloj = semilla_de_operacion
    tipos = consultar(app, "SELECT * FROM tipos_membresia ORDER BY precio")
    assert [(t["nombre"], t["duracion_dias"], t["precio"]) for t in tipos] == [
        ("Mensual", 30, 150_000),
        ("Trimestral", 90, 400_000),
        ("Anual", 365, 1_400_000),
    ]
    sin_pago = consultar(
        app,
        "SELECT p.simulada FROM membresias m JOIN usuarios u ON u.id=m.socio_id JOIN personas p ON p.id=u.persona_id "
        "WHERE m.pago_id IS NULL",
    )
    assert len(sin_pago) == 60 and all(fila["simulada"] for fila in sin_pago)
    hoy = fecha_local(reloj.ahora())
    reales = consultar(
        app,
        "SELECT m.socio_id, m.hasta FROM membresias m JOIN usuarios u ON u.id=m.socio_id "
        "JOIN personas p ON p.id=u.persona_id WHERE NOT p.simulada",
    )
    pendientes = [fila for fila in reales if pago_pendiente(hoy, fila["hasta"])]
    assert sorted((fila["hasta"] - hoy).days for fila in pendientes) == [-1, 4]
    por_vencer = next(f for f in pendientes if f["hasta"] > hoy)
    with app.app_context():
        tarjeta = consultar_tarjeta(str(desde_bytes(por_vencer["socio_id"])))
    assert tarjeta["pago_pendiente"]
    assert "mensaje" in tarjeta["aviso_personal"]
    # Ninguno rompe la simulación de visitas.
    reloj.avanzar(timedelta(hours=2))
    with app.app_context():
        servicio.poner_al_dia()


@pytest.mark.bd
def test_salud_consultas_y_socios_dedicados(semilla_de_operacion):
    from gimnasio.entrenador.servicio import consultar_bandeja
    from gimnasio.salud.borrado import CEDULA_SOCIO_BORRADO_DEMO

    app, _ = semilla_de_operacion
    marcos = {"id": str(desde_bytes(usuario_demo(app, "Marcos"))), "rol": "entrenador"}
    with app.app_context():
        assert "condicion_sin_revisar" in json.dumps(consultar_bandeja(marcos))
    assert len(consultar(app, "SELECT * FROM consultas_ficha")) == 3
    demos = consultar(
        app,
        "SELECT p.nombre, p.cedula FROM usuarios u JOIN personas p ON p.id=u.persona_id "
        "WHERE u.es_demo AND u.rol='socio' ORDER BY p.nombre",
    )
    assert [d["nombre"] for d in demos] == ["Dalila", "Hugo", "Lucía"]
    assert next(d for d in demos if d["nombre"] == "Dalila")["cedula"] == CEDULA_SOCIO_BORRADO_DEMO

    def de_socio(tabla, nombre, condicion=""):
        return consultar(
            app,
            f"SELECT 1 AS hay FROM {tabla} t JOIN usuarios u ON u.id=t.socio_id "
            f"JOIN personas p ON p.id=u.persona_id WHERE p.nombre='{nombre}' {condicion}",
        )

    assert len(de_socio("consentimientos", "Dalila", "AND t.tipo='salud' AND t.otorgado")) == 1
    for tabla in ("condiciones_salud", "restricciones_salud", "avisos_personal"):
        assert de_socio(tabla, "Dalila"), tabla
    # El socio de la progresión congelada otorgó su consentimiento y después lo revocó.
    ultimo = consultar(
        app,
        "SELECT c.otorgado FROM consentimientos c JOIN usuarios u ON u.id=c.socio_id "
        "JOIN personas p ON p.id=u.persona_id WHERE p.nombre='Rafael' AND c.tipo='salud' "
        "ORDER BY c.registrado_en DESC, c.id DESC",
    )
    assert [bool(fila["otorgado"]) for fila in ultimo] == [False, True]
    assert len(consultar(app, "SELECT * FROM perfiles_entrenamiento")) == 5
    sin_entrenador = consultar(
        app,
        "SELECT p.nombre FROM usuarios u JOIN personas p ON p.id=u.persona_id WHERE u.rol='socio' AND NOT p.simulada "
        "AND NOT EXISTS (SELECT 1 FROM asignaciones_entrenador a WHERE a.socio_id=u.id AND a.hasta IS NULL)",
    )
    assert [fila["nombre"] for fila in sin_entrenador] == ["Silvia"]


@pytest.mark.bd
def test_dos_reinicios_dejan_el_mismo_estado_de_la_etapa(app_con_bd):
    app_con_bd.config["MODO_DEMO"] = True
    tablas = (
        "tipos_membresia",
        "pagos",
        "clases",
        "ocurrencias_clase",
        "reservas",
        "cancelaciones_ocurrencia",
        "avisos_socio",
        "perfiles_entrenamiento",
        "condiciones_salud",
        "revisiones_condicion",
        "avisos_personal",
        "consultas_ficha",
        "restricciones_salud",
    )

    def contar():
        return {t: consultar(app_con_bd, f"SELECT COUNT(*) AS n FROM {t}")[0]["n"] for t in tablas}

    with app_con_bd.app_context():
        servicio.reiniciar()
    primera = contar()
    assert all(primera.values()), primera
    with app_con_bd.app_context():
        servicio.reiniciar()
    assert contar() == primera
