"""Restricciones ficticias, bajas por inserción, privacidad y aviso transaccional."""

import json
from uuid import uuid4

import mysql.connector
import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.ids import a_bytes, desde_bytes, nuevo_id
from gimnasio.demo.servicio import reiniciar
from gimnasio.entrenamiento import repositorio as repositorio_entrenamiento
from gimnasio.entrenamiento.servicio import (
    consultar_propuesta,
    consultar_sesion,
    crear_sesion,
    registrar_dolor,
    registrar_serie,
)
from gimnasio.salud.servicio import restricciones_vigentes
from pruebas.test_entrenamiento_api import entrenamiento_api as entrenamiento_api


@pytest.mark.bd
@pytest.mark.parametrize("con_alternativa", [False, True])
def test_iniciar_sesion_restringida_deja_aviso_sin_exponer_descripcion(app_con_bd, con_alternativa):
    app_con_bd.config["MODO_DEMO"] = True
    with app_con_bd.app_context():
        reiniciar()
        with transaccion() as cursor:
            cursor.execute("SELECT * FROM restricciones_salud WHERE levanta_a IS NULL")
            restriccion = cursor.fetchone()
            if not con_alternativa:
                cursor.execute(
                    """INSERT INTO restricciones_salud
                       (id,socio_id,patron_movimiento,descripcion,registrada_en,autor_id)
                       VALUES (%s,%s,'sentadilla',%s,%s,%s)""",
                    (
                        nuevo_id().bytes,
                        restriccion["socio_id"],
                        restriccion["descripcion"],
                        restriccion["registrada_en"],
                        restriccion["autor_id"],
                    ),
                )
        socio = {"id": str(desde_bytes(restriccion["socio_id"])), "rol": "socio"}
        propuesta = consultar_propuesta(socio["id"], socio)
        assert "restriccion_salud" in propuesta["frenos"]
        assert restriccion["descripcion"] not in json.dumps(propuesta, ensure_ascii=False, default=str)
        identificador = str(nuevo_id())
        datos = {"id": identificador, "sesion_planificada_id": propuesta["sesion_planificada"]["id"]}
        crear_sesion(datos, socio)
        crear_sesion(datos, socio)
        sesion = consultar_sesion(identificador, socio)
        assert restriccion["descripcion"] not in json.dumps(sesion, ensure_ascii=False, default=str)
        with transaccion() as cursor:
            cursor.execute(
                "SELECT * FROM avisos_entrenador WHERE freno='restriccion_salud' AND socio_id=%s",
                (restriccion["socio_id"],),
            )
            avisos = cursor.fetchall()
        assert len(avisos) == 1
        assert avisos[0]["entrenador_id"] == restriccion["autor_id"]
        assert restriccion["descripcion"] in avisos[0]["explicacion"]
        entrenador = {"id": str(desde_bytes(restriccion["autor_id"])), "rol": "entrenador"}
        assert consultar_propuesta(socio["id"], entrenador)["frenos"] == propuesta["frenos"]
        with pytest.raises(ErrorDeDominio):
            consultar_propuesta(socio["id"], {"id": str(nuevo_id()), "rol": "entrenador"})
        afectado = next(
            e for e in sesion["ejercicios"] if any(r["regla"] == "restriccion_salud" for r in e["explicacion"])
        )
        assert afectado["no_disponible"] is not con_alternativa
        assert afectado["objetivos"]["series"] > 0
        if con_alternativa:
            assert sesion["sustituciones"][afectado["id"]]["sustitucion"]["motivo"] == "restriccion_salud"
        with pytest.raises(ErrorDeDominio):
            registrar_serie(
                identificador,
                {
                    "id": str(nuevo_id()),
                    "ejercicio_planificado_id": afectado["id"],
                    "ejercicio_hecho_id": afectado["ejercicio_id"],
                    "repeticiones": 8,
                    "carga": "20.50",
                },
                socio,
            )
        for rol in ("recepcion", "administracion"):
            with pytest.raises(ErrorDeDominio):
                consultar_propuesta(socio["id"], {"id": socio["id"], "rol": rol})
        if con_alternativa:
            registrar_dolor(
                identificador,
                {
                    "id": str(nuevo_id()),
                    "ejercicio_planificado_id": afectado["id"],
                    "zonas": ["cuadriceps"],
                },
                socio,
            )
            assert restriccion["descripcion"] not in json.dumps(
                consultar_sesion(identificador, socio),
                ensure_ascii=False,
                default=str,
            )
            with transaccion() as cursor:
                cursor.execute(
                    "SELECT explicacion FROM avisos_entrenador WHERE freno='restriccion_salud' AND socio_id=%s",
                    (restriccion["socio_id"],),
                )
                assert all(restriccion["descripcion"] in f["explicacion"] for f in cursor.fetchall())


@pytest.mark.bd
def test_baja_por_insercion_no_borra_la_restriccion(app_con_bd):
    app_con_bd.config["MODO_DEMO"] = True
    with app_con_bd.app_context():
        reiniciar()
        with transaccion() as cursor:
            cursor.execute("SELECT * FROM restricciones_salud LIMIT 1")
            original = cursor.fetchone()
            cursor.execute(
                """INSERT INTO restricciones_salud
                   (id,socio_id,zona,descripcion,registrada_en,autor_id,levanta_a)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (
                    nuevo_id().bytes,
                    original["socio_id"],
                    original["zona"],
                    "Baja ficticia",
                    original["registrada_en"],
                    original["autor_id"],
                    original["id"],
                ),
            )
        assert restricciones_vigentes(desde_bytes(original["socio_id"])) == ()
        reiniciar()
        assert len(restricciones_vigentes(desde_bytes(original["socio_id"]))) == 1


@pytest.mark.bd
def test_restriccion_anonimizada_deja_de_estar_vigente(app_con_bd):
    """El borrado de #229 escribe este estado (ADR 0025); acá se comprueba solo el esquema y la lectura."""
    app_con_bd.config["MODO_DEMO"] = True
    with app_con_bd.app_context():
        reiniciar()
        with transaccion() as cursor:
            cursor.execute("SELECT * FROM restricciones_salud LIMIT 1")
            original = cursor.fetchone()
            cursor.execute(
                """UPDATE restricciones_salud
                   SET anonimizada=TRUE,ejercicio_id=NULL,patron_movimiento=NULL,zona=NULL,descripcion=''
                   WHERE id=%s""",
                (original["id"],),
            )
        assert restricciones_vigentes(desde_bytes(original["socio_id"])) == ()


@pytest.mark.bd
@pytest.mark.parametrize(
    "cambio",
    [
        "zona='pie'",
        "anonimizada=TRUE",
        "ejercicio_id=NULL,patron_movimiento=NULL,zona=NULL",
        "patron_movimiento='sentadilla',zona='rodillas'",
    ],
)
def test_restriccion_rechaza_objetivos_invalidos(app_con_bd, cambio):
    app_con_bd.config["MODO_DEMO"] = True
    with app_con_bd.app_context():
        reiniciar()
        with pytest.raises(mysql.connector.Error), transaccion() as cursor:
            cursor.execute(f"UPDATE restricciones_salud SET {cambio} WHERE zona IS NOT NULL")
            assert cursor.rowcount > 0


@pytest.mark.bd
def test_dolor_anonimizado_no_se_lee_y_la_zona_nula_exige_el_estado(app_con_bd):
    app_con_bd.config["MODO_DEMO"] = True
    with app_con_bd.app_context():
        reiniciar()
        dolor_id = nuevo_id().bytes
        with transaccion() as cursor:
            cursor.execute("SELECT id,socio_id,creada_en FROM sesiones_realizadas LIMIT 1")
            sesion = cursor.fetchone()
            socio_id = desde_bytes(sesion["socio_id"])
            cursor.execute(
                """INSERT INTO dolores_reportados (id,socio_id,zona,origen,sesion_realizada_id,registrado_en)
                   VALUES (%s,%s,'rodillas','sesion',%s,%s)""",
                (dolor_id, sesion["socio_id"], sesion["id"], sesion["creada_en"]),
            )
            assert dolor_id in {f["id"] for f in repositorio_entrenamiento.listar_dolores(cursor, socio_id)}
        for cambio in ("zona='pie'", "zona=NULL", "anonimizada=TRUE"):
            with pytest.raises(mysql.connector.Error), transaccion() as cursor:
                cursor.execute(f"UPDATE dolores_reportados SET {cambio} WHERE id=%s", (dolor_id,))
        with transaccion() as cursor:
            cursor.execute("UPDATE dolores_reportados SET zona=NULL,anonimizada=TRUE WHERE id=%s", (dolor_id,))
            assert dolor_id not in {f["id"] for f in repositorio_entrenamiento.listar_dolores(cursor, socio_id)}
            assert None not in repositorio_entrenamiento.dolores_sesion(
                cursor, desde_bytes(sesion["id"]), sesion["creada_en"].date()
            )
            filas = repositorio_entrenamiento.listar_dolores_socio(cursor, socio_id)
            assert all(f["zona"] is not None for f in filas if f["sesion_realizada_id"])


@pytest.mark.bd
def test_reinicio_limpia_las_constancias_de_borrado(app_con_bd):
    app_con_bd.config["MODO_DEMO"] = True
    with app_con_bd.app_context():
        reiniciar()
        with transaccion() as cursor:
            cursor.execute("SELECT socio_id,registrada_en FROM restricciones_salud LIMIT 1")
            fila = cursor.fetchone()
            cursor.execute(
                "INSERT INTO borrados_salud (id,socio_id,registrado_en) VALUES (%s,%s,%s)",
                (nuevo_id().bytes, fila["socio_id"], fila["registrada_en"]),
            )
        reiniciar()
        with transaccion() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM borrados_salud")
            assert cursor.fetchone()["total"] == 0


def guardar(cliente, otorgado=True, clave=None, **extras):
    return cliente.post(
        "/api/yo/consentimientos/salud",
        json={"otorgado": otorgado, "version_texto": "salud-1", **extras},
        headers={"X-Gimnasio": "1", "Idempotency-Key": clave or str(uuid4())},
    )


@pytest.mark.bd
def test_alternar_conserva_historial_y_reintento_no_duplica(entrenamiento_api):
    datos = entrenamiento_api
    cliente = datos.cliente()
    assert cliente.get("/api/yo/consentimientos").json["salud"]["otorgado"] is False
    for otorgado in (True, False, True, False, True):
        clave = str(uuid4())
        respuesta = guardar(cliente, otorgado, clave)
        assert respuesta.status_code == 200
        assert respuesta.json["salud"]["otorgado"] is otorgado
        assert guardar(cliente, otorgado, clave).json == respuesta.json
        assert cliente.get("/api/yo/consentimientos").json == respuesta.json
    assert datos.cliente("ajeno").get("/api/yo/consentimientos").json["salud"]["otorgado"] is False
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT * FROM consentimientos ORDER BY registrado_en,id")
        filas = cursor.fetchall()
        assert [bool(f["otorgado"]) for f in filas] == [True, False, True, False, True]
        assert all(f["socio_id"] == f["registrado_por"] == a_bytes(datos.usuarios["socio"]) for f in filas)


@pytest.mark.parametrize("rol", ["recepcion", "entrenador", "administracion"])
@pytest.mark.bd
def test_personal_no_gestiona_consentimiento(entrenamiento_api, rol):
    cliente = entrenamiento_api.cliente(rol)
    assert cliente.get("/api/yo/consentimientos").status_code == 403
    assert guardar(cliente).status_code == 403


@pytest.mark.parametrize(
    "extras", [{"socio_id": "ajeno"}, {"version_texto": "viejo"}, {"otorgado": "false"}, {"tipo": "imagen"}]
)
@pytest.mark.bd
def test_no_admite_otro_socio_tipo_version_o_valor(entrenamiento_api, extras):
    assert guardar(entrenamiento_api.cliente(), **extras).status_code == 422


@pytest.mark.bd
def test_revocar_conserva_las_restricciones_del_socio(app_con_bd):
    from gimnasio.comun.ids import desde_bytes
    from gimnasio.demo.servicio import reiniciar
    from gimnasio.salud.servicio import restricciones_vigentes

    app_con_bd.config["MODO_DEMO"] = True
    with app_con_bd.app_context():
        reiniciar()
        with transaccion() as cursor:
            cursor.execute("SELECT socio_id FROM restricciones_salud LIMIT 1")
            socio = desde_bytes(cursor.fetchone()["socio_id"])
        antes = restricciones_vigentes(socio)
        assert antes
    cliente = app_con_bd.test_client()
    with cliente.session_transaction() as sesion:
        sesion["usuario_id"] = str(socio)
    assert guardar(cliente, False).status_code == 200
    with app_con_bd.app_context():
        assert restricciones_vigentes(socio) == ()
        with transaccion() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM restricciones_salud WHERE socio_id=%s", (socio.bytes,))
            assert cursor.fetchone()["total"] >= len(antes)
    assert guardar(cliente, True).status_code == 200
    with app_con_bd.app_context():
        assert restricciones_vigentes(socio) == antes
    assert cliente.get("/api/yo/ficha").status_code == 200


@pytest.mark.bd
def test_consultas_solo_en_lecturas_del_entrenador_y_perduran(entrenamiento_api):
    from gimnasio.permisos.servicio import registrar_consentimiento

    datos = entrenamiento_api
    socio = datos.usuarios["socio"]
    propia, entrenador = datos.cliente(), datos.cliente("entrenador")
    salud = f"/api/socios/{socio}/salud"
    vista = f"/api/entrenador/socios/{socio}"
    assert entrenador.get(vista).status_code == 200
    assert entrenador.get(salud).status_code == 403
    assert propia.get("/api/yo/salud/consultas").json["consultas"] == []
    assert guardar(propia).status_code == 200
    assert propia.get("/api/yo/salud").status_code == 200
    assert propia.get("/api/entrenamiento/propuesta").status_code == 200
    assert entrenador.get("/api/entrenador/bandeja").status_code == 200
    assert propia.get("/api/yo/salud/consultas").json["consultas"] == []
    assert entrenador.get(salud).status_code == 200
    assert entrenador.get(vista).status_code == 200
    consultas = propia.get("/api/yo/salud/consultas").json["consultas"]
    assert len(consultas) == 2
    assert all(c["nombre"] == "entrenador" and c["rol"] == "entrenador" for c in consultas)
    assert consultas[0]["id"] > consultas[1]["id"]
    assert datos.cliente("ajeno").get("/api/yo/salud/consultas").json["consultas"] == []
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute(
            "UPDATE asignaciones_entrenador SET hasta=%s WHERE id=%s", (datos.reloj.ahora(), datos.asignacion.bytes)
        )
        cursor.execute(
            "INSERT INTO asignaciones_entrenador (id,socio_id,entrenador_id,desde) VALUES (%s,%s,%s,%s)",
            (nuevo_id().bytes, socio.bytes, datos.usuarios["otro"].bytes, datos.reloj.ahora()),
        )
    assert propia.get("/api/yo/salud/consultas").json["consultas"] == consultas
    assert entrenador.get(salud).status_code == 403
    assert datos.cliente("otro").get(salud).status_code == 200
    with datos.app.app_context(), transaccion() as cursor:
        registrar_consentimiento(cursor, socio, "salud", False, "salud-1", socio)
    posteriores = propia.get("/api/yo/salud/consultas").json["consultas"]
    assert posteriores[1:] == consultas
    assert posteriores[0]["nombre"] == "otro"
    assert datos.cliente("otro").get(vista).status_code == 200
    assert propia.get("/api/yo/salud/consultas").json["consultas"] == posteriores


@pytest.mark.bd
def test_consultas_paginadas_de_a_50_y_pagina_invalida(entrenamiento_api):
    from gimnasio.salud.servicio import registrar_consulta_ficha

    datos = entrenamiento_api
    with datos.app.app_context(), transaccion() as cursor:
        for _ in range(51):
            registrar_consulta_ficha(cursor, datos.usuarios["socio"], datos.usuarios["entrenador"])
    cliente = datos.cliente()
    primera = cliente.get("/api/yo/salud/consultas").json
    segunda = cliente.get("/api/yo/salud/consultas?pagina=2").json
    assert len(primera["consultas"]) == 50 and primera["hay_mas"]
    assert len(segunda["consultas"]) == 1 and not segunda["hay_mas"]
    assert primera["consultas"][-1]["id"] > segunda["consultas"][0]["id"]
    assert cliente.get("/api/yo/salud/consultas?pagina=3").json["consultas"] == []
    for pagina in ("0", "-1", "abc", "1.5"):
        assert cliente.get(f"/api/yo/salud/consultas?pagina={pagina}").status_code == 422


@pytest.mark.bd
@pytest.mark.parametrize("rol", ["recepcion", "entrenador", "administracion"])
def test_personal_no_descarga_ni_lista_consultas_propias(entrenamiento_api, rol):
    cliente = entrenamiento_api.cliente(rol)
    assert cliente.get("/api/yo/datos").status_code == 403
    assert cliente.get("/api/yo/salud/consultas").status_code == 403


@pytest.mark.bd
def test_descarga_todas_las_secciones_propias_incluso_con_salud_revocada(entrenamiento_api):
    from gimnasio.permisos.servicio import registrar_consentimiento

    datos = entrenamiento_api
    with datos.app.app_context(), transaccion() as cursor:
        ahora = datos.reloj.ahora()
        autor = datos.usuarios["entrenador"].bytes

        def insertar(tabla, **campos):
            identificador = nuevo_id().bytes
            valores = {"id": identificador, **campos}
            cursor.execute(
                f"INSERT INTO {tabla} ({','.join(valores)}) VALUES ({','.join(['%s'] * len(valores))})",
                tuple(valores.values()),
            )
            return identificador

        tipo = insertar(
            "tipos_membresia",
            nombre="Tipo ficticio",
            duracion_dias=30,
            precio=100000,
            creado_en=ahora,
            actualizado_en=ahora,
        )
        clase = insertar(
            "clases",
            nombre="Clase ficticia",
            entrenador_id=autor,
            dia_semana=1,
            hora_inicio="10:00:00",
            duracion_minutos=60,
            cupo=10,
            creada_en=ahora,
            actualizada_en=ahora,
        )
        ocurrencia = insertar(
            "ocurrencias_clase",
            clase_id=clase,
            fecha=ahora.date(),
            hora_inicio="10:00:00",
            duracion_minutos=60,
            creada_en=ahora,
        )
        for nombre in ("socio", "ajeno"):
            socio = datos.usuarios[nombre]
            cursor.execute(
                """INSERT INTO perfiles_entrenamiento (socio_id,objetivo,actualizado_en,actualizado_por)
                   VALUES (%s,%s,%s,%s)""",
                (socio.bytes, f"Objetivo de {nombre}", ahora, socio.bytes),
            )
            pago = insertar(
                "pagos",
                socio_id=socio.bytes,
                tipo_id=tipo,
                medio="efectivo",
                monto=100000,
                autor_id=autor,
                registrado_en=ahora,
            )
            insertar(
                "anulaciones_pago", pago_id=pago, motivo=f"Anulación de {nombre}", autor_id=autor, registrado_en=ahora
            )
            insertar(
                "membresias",
                socio_id=socio.bytes,
                desde=ahora.date(),
                hasta=ahora.date(),
                actualizada_en=ahora,
                pago_id=pago,
                tipo_id=tipo,
            )
            entrada = insertar(
                "entradas",
                socio_id=socio.bytes,
                sede_id=datos.sede.bytes,
                autor_id=autor,
                registrada_en=ahora,
            )
            insertar("salidas", entrada_id=entrada, autor_id=autor, registrada_en=ahora)
            sesion = insertar(
                "sesiones_realizadas",
                socio_id=socio.bytes,
                sesion_planificada_id=datos.sesiones[0].bytes,
                creada_en=ahora,
            )
            insertar(
                "series_realizadas",
                sesion_realizada_id=sesion,
                ejercicio_planificado_id=datos.ejercicios[0][0].bytes,
                repeticiones=10,
                carga="20.50",
                autor_id=socio.bytes,
                registrada_en=ahora,
            )
            reserva = insertar(
                "reservas",
                socio_id=socio.bytes,
                ocurrencia_id=ocurrencia,
                solicitada_en=ahora,
                autor_id=socio.bytes,
            )
            insertar("cancelaciones_reserva", reserva_id=reserva, autor_id=socio.bytes, registrado_en=ahora)
            aviso = insertar(
                "avisos_socio",
                socio_id=socio.bytes,
                ocurrencia_id=ocurrencia,
                tipo="ocurrencia_cancelada",
                registrado_en=ahora,
            )
            insertar("vistos_aviso_socio", aviso_id=aviso, registrado_en=ahora)
            condicion = insertar(
                "condiciones_salud",
                socio_id=socio.bytes,
                descripcion=f"Condición de {nombre}",
                registrada_en=ahora,
            )
            insertar("revisiones_condicion", condicion_id=condicion, autor_id=autor, nota=nombre, registrada_en=ahora)
            insertar(
                "restricciones_salud",
                socio_id=socio.bytes,
                zona="rodillas",
                descripcion=f"Restricción de {nombre}",
                autor_id=autor,
                registrada_en=ahora,
            )
            insertar(
                "dolores_reportados",
                socio_id=socio.bytes,
                zona="rodillas",
                origen="sesion",
                sesion_realizada_id=sesion,
                registrado_en=ahora,
            )
            insertar(
                "chequeos_dia",
                socio_id=socio.bytes,
                fecha_local=ahora.date(),
                sueno=3,
                energia=3,
                registrado_en=ahora,
            )
            insertar("consultas_ficha", socio_id=socio.bytes, consultado_por=autor, registrada_en=ahora)
            insertar(
                "avisos_personal",
                socio_id=socio.bytes,
                texto=f"Aviso para el personal de {nombre}",
                autor_id=autor,
                registrado_en=ahora,
            )
            registrar_consentimiento(cursor, socio, "salud", True, "salud-1", socio)
            registrar_consentimiento(cursor, socio, "salud", False, "salud-1", socio)
    respuesta = datos.cliente().get("/api/yo/datos?socio_id=" + str(datos.usuarios["ajeno"]))
    assert respuesta.status_code == 200
    assert respuesta.mimetype == "application/json"
    assert respuesta.headers["Content-Disposition"] == 'attachment; filename="mis-datos.json"'
    assert respuesta.cache_control.no_store
    descarga = respuesta.json
    assert {
        "persona",
        "perfil_entrenamiento",
        "membresias",
        "pagos",
        "anulaciones_pago",
        "visitas",
        "salidas",
        "sesiones_realizadas",
        "series_realizadas",
        "reservas",
        "cancelaciones_reserva",
        "avisos_socio",
        "avisos_personal",
        "vistos_aviso_socio",
        "condiciones",
        "revisiones_condicion",
        "restricciones",
        "dolores",
        "consentimientos",
        "consultas_ficha",
        "chequeos_dia",
    } == set(descarga)
    assert all(descarga.values()), "Cada sección lleva datos del socio de prueba"
    texto = respuesta.get_data(as_text=True)
    assert "clave_hash" not in texto and "ajeno" not in texto
    assert str(datos.usuarios["ajeno"]) not in texto
    assert descarga["condiciones"][0]["descripcion"] == "Condición de socio"
    assert descarga["restricciones"][0]["descripcion"] == "Restricción de socio"
    assert descarga["dolores"][0]["zona"] == "rodillas"
    assert descarga["avisos_personal"][0]["texto"] == "Aviso para el personal de socio"
    assert descarga["series_realizadas"][0]["carga"] == "20.50"
    for seccion in descarga.values():
        for fila in seccion:
            if "socio_id" in fila:
                assert fila["socio_id"] == str(datos.usuarios["socio"])
    assert datos.cliente().get("/api/yo/salud/consultas").json["consultas"][0]["nombre"] == "entrenador"
