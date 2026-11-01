"""Borrado de datos de salud: irreversible, acotado al socio y sin romper el historial (ADR 0025)."""

import json
from base64 import b64decode
from uuid import uuid4

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.formatos import normalizar_cedula
from gimnasio.comun.ids import a_bytes, desde_bytes, desde_texto, nuevo_id
from gimnasio.permisos.servicio import registrar_consentimiento
from gimnasio.salud.borrado import CEDULA_SOCIO_BORRADO_DEMO, sin_datos_salud
from pruebas.test_entrenamiento_api import dolor_api as dolor_api
from pruebas.test_entrenamiento_api import entrenamiento_api as entrenamiento_api
from pruebas.test_entrenamiento_api import escribir

pytestmark = pytest.mark.bd

CENTINELA = "centinela-del-socio"
CENTINELA_AJENO = "centinela-del-ajeno"
REGLAS_DE_SALUD = {"dolor_reportado", "restriccion_salud"}


def borrar(cliente, clave=None, cuerpo=None):
    return escribir(cliente, "/api/yo/salud/borrar", cuerpo or {"confirmacion": "BORRAR"}, clave or str(uuid4()))


def consentimiento(cliente, otorgado):
    respuesta = escribir(cliente, "/api/yo/consentimientos/salud", {"otorgado": otorgado, "version_texto": "salud-1"})
    assert respuesta.status_code == 200
    return respuesta.json["salud"]


def razones(texto):
    return [
        {
            "regla": "restriccion_salud",
            "version": "1",
            "datos": {"ejercicio_id": "a", "ejercicio_hecho_id": "b", "descripcion": texto, "explicacion": texto},
        },
        {"regla": "dolor_reportado", "version": "1", "datos": {"ejercicio_id": "a", "zonas": texto}},
        {"regla": "subir_carga", "version": "1", "datos": {"ejercicio_id": "a", "carga_base": "10"}},
    ]


def plantar(cursor, socio, sesion, entrenador, ahora, texto, *, con_prescripcion):
    """Un dato centinela en cada tabla alcanzada por el borrado."""
    condicion, restriccion, chequeo, dolor, aviso = (nuevo_id().bytes for _ in range(5))
    cursor.execute(
        "INSERT INTO condiciones_salud (id,socio_id,descripcion,registrada_en) VALUES (%s,%s,%s,%s)",
        (condicion, socio, texto, ahora),
    )
    cursor.execute(
        "INSERT INTO revisiones_condicion (id,condicion_id,autor_id,nota,registrada_en) VALUES (%s,%s,%s,%s,%s)",
        (nuevo_id().bytes, condicion, entrenador, texto, ahora),
    )
    cursor.execute(
        """INSERT INTO restricciones_salud (id,socio_id,zona,descripcion,autor_id,registrada_en)
           VALUES (%s,%s,'rodillas',%s,%s,%s)""",
        (restriccion, socio, texto, entrenador, ahora),
    )
    cursor.execute(
        """INSERT INTO restricciones_salud (id,socio_id,zona,descripcion,autor_id,registrada_en,levanta_a)
           VALUES (%s,%s,'rodillas',%s,%s,%s,%s)""",
        (nuevo_id().bytes, socio, texto, entrenador, ahora, restriccion),
    )
    cursor.execute(
        "INSERT INTO chequeos_dia (id,socio_id,fecha_local,sueno,energia,registrado_en) VALUES (%s,%s,%s,3,3,%s)",
        (chequeo, socio, ahora.date(), ahora),
    )
    cursor.execute(
        """INSERT INTO dolores_reportados (id,socio_id,zona,origen,chequeo_id,registrado_en)
           VALUES (%s,%s,'rodillas','chequeo',%s,%s)""",
        (nuevo_id().bytes, socio, chequeo, ahora),
    )
    cursor.execute(
        """INSERT INTO dolores_reportados (id,socio_id,zona,origen,sesion_realizada_id,registrado_en)
           VALUES (%s,%s,'rodillas','sesion',%s,%s)""",
        (dolor, socio, sesion, ahora),
    )
    cursor.execute(
        "INSERT INTO avisos_personal (id,socio_id,texto,autor_id,registrado_en) VALUES (%s,%s,%s,%s,%s)",
        (nuevo_id().bytes, socio, texto, entrenador, ahora),
    )
    cursor.execute(
        """INSERT INTO avisos_entrenador (id,socio_id,entrenador_id,sesion_realizada_id,freno,explicacion,creado_en)
           VALUES (%s,%s,%s,%s,'plantado',%s,%s)""",
        (aviso, socio, entrenador, sesion, json.dumps(razones(texto)), ahora),
    )
    cursor.execute(
        "INSERT INTO revisiones_aviso (id,aviso_id,entrenador_id,nota,revisada_en) VALUES (%s,%s,%s,%s,%s)",
        (nuevo_id().bytes, aviso, entrenador, texto, ahora),
    )
    ejercicios = [{"id": "a", "explicacion": razones(texto)}]
    efectiva = nuevo_id().bytes
    if con_prescripcion:
        cursor.execute("SELECT id,ejercicios FROM prescripciones_efectivas WHERE sesion_realizada_id=%s", (sesion,))
        fila = cursor.fetchone()
        efectiva = fila["id"]
        guardados = json.loads(fila["ejercicios"])
        guardados[0]["explicacion"] += razones(texto)
        cursor.execute(
            "UPDATE prescripciones_efectivas SET ejercicios=%s,explicacion=%s WHERE id=%s",
            (json.dumps(guardados), json.dumps(razones(texto)), efectiva),
        )
    else:
        cursor.execute(
            """INSERT INTO prescripciones_efectivas
               (id,sesion_realizada_id,version_reglas,creada_en,ejercicios,explicacion,frenos)
               VALUES (%s,%s,'1',%s,%s,%s,'["restriccion_salud"]')""",
            (efectiva, sesion, ahora, json.dumps(ejercicios), json.dumps(razones(texto))),
        )
    cursor.execute(
        """INSERT INTO prescripciones_ajustadas
           (id,sesion_realizada_id,prescripcion_efectiva_id,dolor_reportado_id,version_reglas,creada_en,
            ejercicios,explicacion)
           VALUES (%s,%s,%s,%s,'1',%s,%s,%s)""",
        (nuevo_id().bytes, sesion, efectiva, dolor, ahora, json.dumps(ejercicios), json.dumps(razones(texto))),
    )


def filas_de_salud(cursor, socio):
    consultas = {
        "condiciones": "SELECT * FROM condiciones_salud WHERE socio_id=%s ORDER BY id",
        "revisiones_condicion": (
            "SELECT r.* FROM revisiones_condicion r JOIN condiciones_salud c ON c.id=r.condicion_id "
            "WHERE c.socio_id=%s ORDER BY r.id"
        ),
        "restricciones": "SELECT * FROM restricciones_salud WHERE socio_id=%s ORDER BY id",
        "dolores": "SELECT * FROM dolores_reportados WHERE socio_id=%s ORDER BY id",
        "avisos_personal": "SELECT * FROM avisos_personal WHERE socio_id=%s ORDER BY id",
        "avisos": "SELECT * FROM avisos_entrenador WHERE socio_id=%s ORDER BY id",
        "revisiones_aviso": (
            "SELECT r.* FROM revisiones_aviso r JOIN avisos_entrenador a ON a.id=r.aviso_id "
            "WHERE a.socio_id=%s ORDER BY r.id"
        ),
        "efectivas": (
            "SELECT p.* FROM prescripciones_efectivas p JOIN sesiones_realizadas s ON s.id=p.sesion_realizada_id "
            "WHERE s.socio_id=%s ORDER BY p.id"
        ),
        "ajustadas": (
            "SELECT a.* FROM prescripciones_ajustadas a JOIN sesiones_realizadas s ON s.id=a.sesion_realizada_id "
            "WHERE s.socio_id=%s ORDER BY a.id"
        ),
    }
    resultado = {}
    for nombre, consulta in consultas.items():
        cursor.execute(consulta, (socio,))
        resultado[nombre] = cursor.fetchall()
    return resultado


def todo_el_texto(cursor):
    cursor.execute("SHOW TABLES")
    tablas = [next(iter(fila.values())) for fila in cursor.fetchall()]
    partes = []
    for tabla in tablas:
        cursor.execute(f"SELECT * FROM `{tabla}`")
        partes.append(str(cursor.fetchall()))
    return "\n".join(partes)


def respuestas_guardadas(cursor, socio):
    cursor.execute("SELECT respuesta FROM solicitudes_idempotentes WHERE usuario_id=%s", (socio,))
    return [b64decode(json.loads(f["respuesta"])["cuerpo"]).decode() for f in cursor.fetchall()]


def razones_guardadas(valor):
    if isinstance(valor, list):
        return [razon for elemento in valor for razon in razones_guardadas(elemento)]
    if not isinstance(valor, dict):
        return []
    return ([valor] if "regla" in valor else []) + razones_guardadas(list(valor.values()))


@pytest.fixture
def borrado_api(dolor_api):
    """Socio de la semilla con un dolor en la sesión en curso y un entrenador; el límite de la demo se prueba aparte."""
    datos = dolor_api
    datos.socio_texto = datos.cliente_dolor.get("/api/sesion").json["usuario"]["id"]
    datos.socio = a_bytes(desde_texto(datos.socio_texto))
    datos.entrenador = datos.app.test_client()
    respuesta = datos.entrenador.post("/api/sesion/demo/entrenador", headers={"X-Gimnasio": "1"})
    assert respuesta.status_code == 200
    datos.entrenador_id = a_bytes(desde_texto(respuesta.json["usuario"]["id"]))
    datos.app.config["MODO_DEMO"] = False
    assert escribir(datos.cliente_dolor, datos.ruta_dolor + "/dolores", datos.cuerpo_dolor).status_code == 201
    return datos


def test_rechazado_con_consentimiento_vigente_y_sin_cambios(borrado_api):
    datos = borrado_api
    with datos.app.app_context(), transaccion() as cursor:
        antes = filas_de_salud(cursor, datos.socio)
    respuesta = borrar(datos.cliente_dolor)
    assert respuesta.status_code == 409
    assert respuesta.json["error"]["codigo"] == "consentimiento_vigente"
    with datos.app.app_context(), transaccion() as cursor:
        assert filas_de_salud(cursor, datos.socio) == antes
        cursor.execute("SELECT COUNT(*) AS n FROM borrados_salud")
        assert cursor.fetchone()["n"] == 0


@pytest.mark.parametrize(
    "cuerpo", [{"confirmacion": "borrar"}, {"confirmacion": True}, {"confirmacion": "BORRAR", "socio_id": "x"}, []]
)
def test_exige_la_confirmacion_exacta(borrado_api, cuerpo):
    consentimiento(borrado_api.cliente_dolor, False)
    respuesta = escribir(borrado_api.cliente_dolor, "/api/yo/salud/borrar", cuerpo)
    assert respuesta.status_code == 422
    assert respuesta.json["error"]["codigo"] == "confirmacion_invalida"


def test_el_personal_no_borra(borrado_api):
    assert borrar(borrado_api.entrenador).status_code == 403


def test_ningun_dato_centinela_queda_legible_y_los_del_otro_socio_no_cambian(borrado_api):
    datos = borrado_api
    condicion = escribir(datos.cliente_dolor, "/api/yo/salud/condiciones", {"descripcion": CENTINELA + "-respuesta"})
    assert condicion.status_code == 201
    with datos.app.app_context(), transaccion() as cursor:
        ahora = datos.reloj.ahora()
        cursor.execute("SELECT id FROM usuarios WHERE rol='socio' AND id<>%s LIMIT 1", (datos.socio,))
        ajeno = cursor.fetchone()["id"]
        sesion = a_bytes(desde_texto(datos.sesion_dolor))
        cursor.execute("SELECT sesion_planificada_id FROM sesiones_realizadas WHERE id=%s", (sesion,))
        planificada = cursor.fetchone()["sesion_planificada_id"]
        sesion_ajena = nuevo_id().bytes
        cursor.execute(
            "INSERT INTO sesiones_realizadas (id,socio_id,sesion_planificada_id,creada_en) VALUES (%s,%s,%s,%s)",
            (sesion_ajena, ajeno, planificada, ahora),
        )
        plantar(cursor, datos.socio, sesion, datos.entrenador_id, ahora, CENTINELA, con_prescripcion=True)
        plantar(cursor, ajeno, sesion_ajena, datos.entrenador_id, ahora, CENTINELA_AJENO, con_prescripcion=False)
        antes = filas_de_salud(cursor, datos.socio)
        ajeno_antes = filas_de_salud(cursor, ajeno)
        assert any(CENTINELA in cuerpo for cuerpo in respuestas_guardadas(cursor, datos.socio))
    consentimiento(datos.cliente_dolor, False)
    respuesta = borrar(datos.cliente_dolor)
    assert respuesta.status_code == 200
    with datos.app.app_context(), transaccion() as cursor:
        texto = todo_el_texto(cursor)
        assert CENTINELA not in texto
        assert CENTINELA_AJENO in texto
        assert not any(CENTINELA in cuerpo for cuerpo in respuestas_guardadas(cursor, datos.socio))
        despues = filas_de_salud(cursor, datos.socio)
        assert filas_de_salud(cursor, ajeno) == ajeno_antes
        cursor.execute(
            "SELECT socio_id FROM borrados_salud WHERE id=%s",
            (a_bytes(desde_texto(respuesta.json["borrado_salud_id"])),),
        )
        assert cursor.fetchone()["socio_id"] == datos.socio
    for tabla, filas in antes.items():
        assert [f["id"] for f in despues[tabla]] == [f["id"] for f in filas], f"{tabla} conserva filas e ids"
    assert all(f["anonimizada"] and f["descripcion"] is None for f in despues["condiciones"])
    assert all(f["nota"] is None for tabla in ("revisiones_condicion", "revisiones_aviso") for f in despues[tabla])
    assert all(
        f["anonimizada"] and f["descripcion"] is None and f["zona"] is None and f["patron_movimiento"] is None
        for f in despues["restricciones"]
    )
    assert all(f["anonimizada"] and f["zona"] is None for f in despues["dolores"])
    assert all(f["anonimizada"] and f["texto"] is None for f in despues["avisos_personal"])
    guardadas = [
        razon
        for tabla, columnas in (
            ("avisos", ("explicacion",)),
            ("efectivas", ("ejercicios", "explicacion")),
            ("ajustadas", ("ejercicios", "explicacion")),
        )
        for fila in despues[tabla]
        for columna in columnas
        for razon in razones_guardadas(json.loads(fila[columna]))
    ]
    salud = [r for r in guardadas if r["regla"] in REGLAS_DE_SALUD]
    assert salud and all(set(r["datos"]) <= {"ejercicio_id", "ejercicio_hecho_id"} and r["version"] for r in salud)
    assert {"carga_base": "10", "ejercicio_id": "a"} in [r["datos"] for r in guardadas if r["regla"] == "subir_carga"]


def test_repetir_no_falla_y_la_misma_clave_no_duplica_la_constancia(borrado_api):
    datos = borrado_api
    consentimiento(datos.cliente_dolor, False)

    def constancias():
        with datos.app.app_context(), transaccion() as cursor:
            cursor.execute("SELECT COUNT(*) AS n FROM borrados_salud WHERE socio_id=%s", (datos.socio,))
            return cursor.fetchone()["n"]

    clave = str(uuid4())
    primera = borrar(datos.cliente_dolor, clave)
    assert primera.status_code == 200
    assert borrar(datos.cliente_dolor, clave).json == primera.json
    assert constancias() == 1
    assert borrar(datos.cliente_dolor).status_code == 200
    assert constancias() == 2


def test_otorgar_de_nuevo_empieza_sin_datos_y_un_id_borrado_responde_como_inexistente(borrado_api):
    datos = borrado_api
    with datos.app.app_context(), transaccion() as cursor:
        ahora = datos.reloj.ahora()
        sesion = a_bytes(desde_texto(datos.sesion_dolor))
        plantar(cursor, datos.socio, sesion, datos.entrenador_id, ahora, CENTINELA, con_prescripcion=True)
        cursor.execute("SELECT id FROM condiciones_salud WHERE socio_id=%s LIMIT 1", (datos.socio,))
        condicion = str(desde_bytes(cursor.fetchone()["id"]))
        cursor.execute("SELECT id FROM restricciones_salud WHERE socio_id=%s AND levanta_a IS NULL", (datos.socio,))
        restricciones = [str(desde_bytes(f["id"])) for f in cursor.fetchall()]
    consentimiento(datos.cliente_dolor, False)
    assert borrar(datos.cliente_dolor).status_code == 200
    assert consentimiento(datos.cliente_dolor, True)["otorgado"] is True
    propia = datos.cliente_dolor.get("/api/yo/salud").json
    assert propia["condiciones"] == [] and propia["restricciones"] == [] and propia["dolores"] == []
    socio = datos.socio_texto
    ficha = datos.entrenador.get(f"/api/socios/{socio}/salud").json
    assert ficha["aviso_personal"] is None and ficha["condiciones"] == [] and ficha["dolores"] == []
    vista = datos.entrenador.get(f"/api/entrenador/socios/{socio}").json
    assert vista["salud"]["dolores_reportados"] == [] and vista["salud"]["restricciones_salud"] == []
    bandeja = datos.entrenador.get("/api/entrenador/bandeja")
    assert bandeja.status_code == 200 and CENTINELA not in bandeja.get_data(as_text=True)
    frenos = datos.cliente_dolor.get("/api/entrenamiento/propuesta").json["frenos"]
    assert not REGLAS_DE_SALUD & set(frenos)
    # Un pedido sobre un dato borrado no lo recupera ni lo reemplaza.
    ruta = f"/api/socios/{socio}/salud"
    assert escribir(datos.entrenador, f"{ruta}/condiciones/{condicion}/revisar", {}).status_code == 422
    for restriccion in restricciones:
        assert escribir(datos.entrenador, f"{ruta}/restricciones/{restriccion}/levantar", {}).status_code == 422
    cuerpo = {"id": condicion, "descripcion": "Otra condición ficticia"}
    repetida = escribir(datos.cliente_dolor, "/api/yo/salud/condiciones", cuerpo)
    assert repetida.status_code == 409 and repetida.json["error"]["codigo"] == "id_en_uso"
    cuerpo = {"id": restricciones[0], "zona": "rodillas", "descripcion": "Otra restricción ficticia"}
    repetida = escribir(datos.entrenador, f"{ruta}/restricciones", cuerpo)
    assert repetida.status_code == 409 and repetida.json["error"]["codigo"] == "id_en_uso"
    # Los datos nuevos, con consentimiento, se guardan y se leen como siempre.
    nueva = escribir(datos.cliente_dolor, "/api/yo/salud/condiciones", {"descripcion": "Condición nueva ficticia"})
    assert nueva.status_code == 201
    assert [c["descripcion"] for c in datos.cliente_dolor.get("/api/yo/salud").json["condiciones"]] == [
        "Condición nueva ficticia"
    ]


def test_el_limite_de_la_demo_admite_solo_al_socio_dedicado_y_a_los_creados_en_ella(entrenamiento_api):
    datos = entrenamiento_api
    assert normalizar_cedula(CEDULA_SOCIO_BORRADO_DEMO) == CEDULA_SOCIO_BORRADO_DEMO
    socio, ajeno = datos.usuarios["socio"], datos.usuarios["ajeno"]
    recepcion = datos.usuarios["recepcion"]
    cliente, cliente_ajeno = datos.cliente(), datos.cliente("ajeno")
    consentimiento(cliente, False)
    consentimiento(cliente_ajeno, False)
    datos.app.config["MODO_DEMO"] = True

    def rechazado(cliente_demo):
        respuesta = borrar(cliente_demo)
        return respuesta.status_code == 403 and respuesta.json["error"]["codigo"] == "borrado_no_disponible_demo"

    assert rechazado(cliente)
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("UPDATE usuarios SET es_demo=TRUE WHERE id IN (%s,%s)", (socio.bytes, ajeno.bytes))
    # Un usuario demo de la semilla sigue sin poder: su recorrido no se rompe.
    assert rechazado(cliente)
    with datos.app.app_context(), transaccion() as cursor:
        # Creado en la demo: recepción registró su consentimiento de datos personales.
        registrar_consentimiento(cursor, socio, "datos_personales", True, "1", recepcion)
        cursor.execute(
            "UPDATE personas p JOIN usuarios u ON u.persona_id=p.id SET p.cedula=%s WHERE u.id=%s",
            (CEDULA_SOCIO_BORRADO_DEMO, ajeno.bytes),
        )
    assert borrar(cliente).status_code == 200
    assert borrar(cliente_ajeno).status_code == 200
    datos.app.config["MODO_DEMO"] = False
    otro = datos.cliente("ajeno")
    assert borrar(otro).status_code == 200


def test_sesion_en_curso_series_y_pendientes_se_conservan(borrado_api):
    datos = borrado_api
    cliente, ruta = datos.cliente_dolor, datos.ruta_dolor
    consentimiento(cliente, False)
    antes = cliente.get(ruta).json
    disponible = next(e for e in antes["ejercicios"] if e["pendiente"] > 0 and not e["no_disponible"])

    def serie():
        return escribir(
            cliente,
            ruta + "/series",
            {
                "id": str(nuevo_id(datos.reloj)),
                "ejercicio_planificado_id": disponible["id"],
                "repeticiones": 8,
                "carga": "20.50",
            },
        )

    assert serie().status_code == 201
    antes = cliente.get(ruta).json
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT * FROM series_realizadas WHERE autor_id=%s ORDER BY id", (datos.socio,))
        series = cursor.fetchall()
        cursor.execute("SELECT * FROM sustituciones ORDER BY id")
        sustituciones = cursor.fetchall()
    assert borrar(cliente).status_code == 200

    def sin_explicacion(lectura):
        return [{c: v for c, v in e.items() if c != "explicacion"} for e in lectura["ejercicios"]]

    despues = cliente.get(ruta).json
    assert sin_explicacion(despues) == sin_explicacion(antes)
    assert despues["sustituciones"] == antes["sustituciones"]
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT * FROM series_realizadas WHERE autor_id=%s ORDER BY id", (datos.socio,))
        assert cursor.fetchall() == series
        cursor.execute("SELECT * FROM sustituciones ORDER BY id")
        assert cursor.fetchall() == sustituciones
    assert "rodillas" not in json.dumps([e["explicacion"] for e in despues["ejercicios"]])
    # La sesión se puede retomar, con y sin consentimiento.
    assert cliente.get("/api/entrenamiento/propuesta").status_code == 200
    assert serie().status_code == 201
    consentimiento(cliente, True)
    assert cliente.get(ruta).status_code == 200
    assert cliente.get("/api/entrenamiento/propuesta").status_code == 200
    assert serie().status_code == 201


def test_avisos_se_conservan_y_revisan_con_freno_visible_sin_datos_de_salud(borrado_api):
    datos = borrado_api
    vista_ruta = f"/api/entrenador/socios/{datos.socio_texto}"
    antes = datos.entrenador.get(vista_ruta).json["avisos"]
    assert "dolor_reportado" in {a["freno"] for a in antes}
    consentimiento(datos.cliente_dolor, False)
    assert borrar(datos.cliente_dolor).status_code == 200
    for otorgado in (False, True):
        if otorgado:
            consentimiento(datos.cliente_dolor, True)
        respuesta = datos.entrenador.get(vista_ruta)
        assert respuesta.status_code == 200
        despues = respuesta.json["avisos"]
        assert [(a["id"], a["freno"]) for a in despues] == [(a["id"], a["freno"]) for a in antes]
        assert "rodillas" not in json.dumps(razones_guardadas([a["explicacion"] for a in despues]))
    pendientes = [a["id"] for a in despues if not a["revisado"]]
    revision = escribir(
        datos.entrenador,
        f"{vista_ruta}/avisos/revision",
        {"aviso_ids": pendientes, "nota": "Revisado en la prueba"},
    )
    assert revision.status_code in {200, 201}
    assert all(a["revisado"] for a in datos.entrenador.get(vista_ruta).json["avisos"])


def test_las_consultas_de_ficha_se_conservan(borrado_api):
    datos = borrado_api
    assert datos.entrenador.get(f"/api/entrenador/socios/{datos.socio_texto}").status_code == 200
    antes = datos.cliente_dolor.get("/api/yo/salud/consultas").json["consultas"]
    assert antes
    consentimiento(datos.cliente_dolor, False)
    assert borrar(datos.cliente_dolor).status_code == 200
    assert datos.cliente_dolor.get("/api/yo/salud/consultas").json["consultas"] == antes


def test_la_descarga_devuelve_las_filas_con_los_campos_vacios(borrado_api):
    datos = borrado_api
    consentimiento(datos.cliente_dolor, False)
    assert borrar(datos.cliente_dolor).status_code == 200
    descarga = datos.cliente_dolor.get("/api/yo/datos").json
    assert descarga["dolores"] and all(d["zona"] is None and d["anonimizada"] for d in descarga["dolores"])


def test_consentimiento_distingue_revocado_de_nunca_otorgado(entrenamiento_api):
    cliente = entrenamiento_api.cliente()
    assert cliente.get("/api/yo/consentimientos").json["salud"]["revocado"] is False
    assert consentimiento(cliente, True)["revocado"] is False
    assert consentimiento(cliente, False)["revocado"] is True
    assert consentimiento(cliente, True)["revocado"] is False


def test_sin_datos_salud_filtra_razones_a_cualquier_profundidad():
    guardado = {"ejercicios": [{"id": "a", "explicacion": razones("texto")}], "frenos": ["dolor_reportado"]}
    limpio = sin_datos_salud(guardado)
    assert "texto" not in json.dumps(limpio)
    assert limpio["frenos"] == ["dolor_reportado"]
    assert limpio["ejercicios"][0]["explicacion"][0] == {
        "regla": "restriccion_salud",
        "version": "1",
        "datos": {"ejercicio_id": "a", "ejercicio_hecho_id": "b"},
    }
    assert sin_datos_salud({"regla": "dolor_reportado"}) == {"regla": "dolor_reportado", "datos": {}}
