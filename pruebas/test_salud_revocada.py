"""Revocar el consentimiento de salud: motor sin datos de salud y progresión congelada (ADR 0025 y 0030)."""

import json
from decimal import Decimal

import pytest
from mysql.connector import IntegrityError

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import a_bytes, desde_texto, nuevo_id
from gimnasio.permisos.servicio import registrar_consentimiento
from pruebas.test_entrenamiento_api import (
    alternativas_api as alternativas_api,
)
from pruebas.test_entrenamiento_api import (
    dolor_api as dolor_api,
)
from pruebas.test_entrenamiento_api import (
    entrenamiento_api as entrenamiento_api,
)
from pruebas.test_entrenamiento_api import (
    escribir,
    iniciar,
)

pytestmark = pytest.mark.bd


def consentir(datos, otorgado, socio=None):
    socio = socio or datos.usuarios["socio"]
    with datos.app.app_context(), transaccion() as cursor:
        registrar_consentimiento(cursor, socio, "salud", otorgado, "1", socio)


def contar(datos, tabla, sesion):
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute(
            f"SELECT COUNT(*) AS n FROM {tabla} WHERE sesion_realizada_id=%s", (a_bytes(desde_texto(sesion)),)
        )
        return cursor.fetchone()["n"]


def revocar_demo(datos):
    respuesta = escribir(
        datos.cliente_dolor,
        "/api/yo/consentimientos/salud",
        {"otorgado": False, "version_texto": "salud-1"},
    )
    assert respuesta.status_code == 200


def otorgar_demo(datos):
    respuesta = escribir(
        datos.cliente_dolor,
        "/api/yo/consentimientos/salud",
        {"otorgado": True, "version_texto": "salud-1"},
    )
    assert respuesta.status_code == 200


def lectura(datos):
    return datos.cliente_dolor.get(datos.ruta_dolor).json


def test_dolor_guarda_prescripcion_ajustada_y_el_reintento_no_agrega_otra(dolor_api, monkeypatch):
    datos = dolor_api
    cliente, ruta = datos.cliente_dolor, datos.ruta_dolor
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute(
            "SELECT id, version_reglas FROM prescripciones_efectivas WHERE sesion_realizada_id=%s",
            (a_bytes(desde_texto(datos.sesion_dolor)),),
        )
        efectiva = cursor.fetchone()
    # La sesión conserva la versión con la que empezó aunque cambie el motor.
    monkeypatch.setattr("gimnasio.entrenamiento.servicio.VERSION_REGLAS", "0.0.0")
    assert contar(datos, "prescripciones_ajustadas", datos.sesion_dolor) == 0
    assert escribir(cliente, ruta + "/dolores", datos.cuerpo_dolor).status_code == 201
    assert contar(datos, "prescripciones_ajustadas", datos.sesion_dolor) == 1
    assert escribir(cliente, ruta + "/dolores", datos.cuerpo_dolor).status_code == 201
    assert contar(datos, "prescripciones_ajustadas", datos.sesion_dolor) == 1
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT * FROM prescripciones_ajustadas")
        fila = cursor.fetchone()
    assert fila["version_reglas"] == efectiva["version_reglas"]
    assert fila["prescripcion_efectiva_id"] == efectiva["id"]
    assert fila["dolor_reportado_id"] == a_bytes(desde_texto(datos.cuerpo_dolor["id"]))
    with pytest.raises(IntegrityError) as error, datos.app.app_context(), transaccion() as cursor:
        cursor.execute(
            "INSERT INTO prescripciones_ajustadas "
            "(id, sesion_realizada_id, prescripcion_efectiva_id, dolor_reportado_id, "
            "version_reglas, creada_en, ejercicios, explicacion) "
            "SELECT %s, sesion_realizada_id, prescripcion_efectiva_id, dolor_reportado_id, "
            "version_reglas, creada_en, ejercicios, explicacion FROM prescripciones_ajustadas WHERE id=%s",
            (a_bytes(nuevo_id(datos.reloj)), fila["id"]),
        )
    assert error.value.errno == 1062
    ejercicios = json.loads(fila["ejercicios"])
    assert [e["id"] for e in ejercicios] == [e["id"] for e in lectura(datos)["ejercicios"]]
    assert any(r["regla"] == "dolor_reportado" for r in json.loads(fila["explicacion"]))


def test_revocar_con_dolor_en_la_sesion_conserva_ejercicios_objetivos_y_sustituciones(dolor_api):
    datos = dolor_api
    cliente, ruta = datos.cliente_dolor, datos.ruta_dolor
    assert escribir(cliente, ruta + "/dolores", datos.cuerpo_dolor).status_code == 201
    quitado = escribir(
        cliente, ruta + "/dolores", datos.cuerpo_dolor | {"id": str(nuevo_id(datos.reloj)), "zonas": ["cuadriceps"]}
    )
    assert quitado.status_code == 201
    antes = lectura(datos)
    revocar_demo(datos)
    despues = lectura(datos)
    assert despues["ejercicios"] == antes["ejercicios"]
    assert despues["sustituciones"] == antes["sustituciones"]
    ejercicio = despues["ejercicios"][0]
    assert ejercicio["objetivos"]["series"] == 0
    serie = {
        "id": str(nuevo_id(datos.reloj)),
        "ejercicio_planificado_id": ejercicio["id"],
        "repeticiones": 10,
        "carga": "20.50",
    }
    respuesta = escribir(cliente, ruta + "/series", serie)
    assert respuesta.status_code == 409
    assert respuesta.json["error"]["codigo"] == "dolor_reportado"


def test_revocar_sin_dolor_en_la_sesion_conserva_la_prescripcion_efectiva(dolor_api):
    datos = dolor_api
    antes = lectura(datos)
    revocar_demo(datos)
    assert lectura(datos)["ejercicios"] == antes["ejercicios"]
    assert lectura(datos)["prescripcion_efectiva"] == antes["prescripcion_efectiva"]


def test_la_siguiente_propuesta_acredita_lo_mismo_que_antes_de_revocar(dolor_api):
    datos = dolor_api
    cliente, ruta = datos.cliente_dolor, datos.ruta_dolor
    assert escribir(cliente, ruta + "/dolores", datos.cuerpo_dolor | {"zonas": ["cuadriceps"]}).status_code == 201
    antes = cliente.get("/api/entrenamiento/propuesta").json
    assert antes["sesion_planificada"]["id"] != lectura(datos)["sesion_planificada"]["id"]
    revocar_demo(datos)
    despues = cliente.get("/api/entrenamiento/propuesta").json
    assert despues["sesion_planificada"] == antes["sesion_planificada"]
    assert [e["id"] for e in despues["ejercicios"]] == [e["id"] for e in antes["ejercicios"]]


def test_lo_planificado_y_no_realizado_sigue_pendiente_al_revocar(dolor_api):
    datos = dolor_api
    cliente = datos.cliente_dolor
    antes = cliente.get("/api/entrenamiento/propuesta").json
    revocar_demo(datos)
    despues = cliente.get("/api/entrenamiento/propuesta").json
    assert despues["sesion_planificada"] == antes["sesion_planificada"]
    assert [e["pendiente"] for e in despues["ejercicios"]] == [e["pendiente"] for e in antes["ejercicios"]]
    assert all(e["pendiente"] > 0 for e in despues["ejercicios"])


def test_retomar_sesion_parcial_conserva_la_carga_prescrita_con_o_sin_consentimiento(dolor_api):
    datos = dolor_api
    cliente, ruta = datos.cliente_dolor, datos.ruta_dolor
    ejercicio = lectura(datos)["ejercicios"][0]
    serie = {
        "id": str(nuevo_id(datos.reloj)),
        "ejercicio_planificado_id": ejercicio["id"],
        "repeticiones": ejercicio["objetivos"]["repeticiones_maximas"],
        "carga": ejercicio["objetivos"]["carga"],
    }
    assert escribir(cliente, ruta + "/series", serie).status_code == 201
    prescrita = [e["objetivos"]["carga"] for e in lectura(datos)["ejercicios"]]
    revocar_demo(datos)
    assert [e["objetivos"]["carga"] for e in lectura(datos)["ejercicios"]] == prescrita
    # La propuesta congelada no sube nada: retoma la carga anterior al incremento.
    sin = cliente.get("/api/entrenamiento/propuesta").json
    assert Decimal(sin["ejercicios"][0]["objetivos"]["carga"]) <= Decimal(prescrita[0])
    assert "subir_carga" not in {r["regla"] for r in sin["explicacion"]}
    otorgar_demo(datos)
    assert [e["objetivos"]["carga"] for e in lectura(datos)["ejercicios"]] == prescrita


def test_sin_consentimiento_la_propuesta_congela_y_lo_explica(dolor_api):
    datos = dolor_api
    cliente = datos.cliente_dolor
    revocar_demo(datos)
    propuesta = cliente.get("/api/entrenamiento/propuesta").json
    reglas = {r["regla"] for r in propuesta["explicacion"]}
    assert "subir_carga" not in reglas and "tope_semanal" not in reglas
    assert propuesta["version_reglas"] == "3.2.0"


def test_ejercicio_excluido_por_restriccion_vuelve_a_proponerse_y_se_excluye_otra_vez(entrenamiento_api):
    datos = entrenamiento_api
    cliente = datos.cliente()
    consentir(datos, True)
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT ejercicio_id FROM ejercicios_planificados LIMIT 1")
        catalogo = cursor.fetchone()["ejercicio_id"]
        cursor.execute(
            "INSERT INTO restricciones_salud (id,socio_id,ejercicio_id,descripcion,registrada_en,autor_id) "
            "VALUES (%s,%s,%s,'Restricción ficticia',%s,%s)",
            (
                a_bytes(nuevo_id(datos.reloj)),
                a_bytes(datos.usuarios["socio"]),
                catalogo,
                datos.reloj.ahora(),
                a_bytes(datos.usuarios["entrenador"]),
            ),
        )

    def series_propuestas():
        return [e["objetivos"]["series"] for e in cliente.get("/api/entrenamiento/propuesta").json["ejercicios"]]

    excluidos = series_propuestas()
    assert 0 in excluidos
    consentir(datos, False)
    revocado = series_propuestas()
    assert 0 not in revocado
    consentir(datos, True)
    assert series_propuestas() == excluidos
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute(
            "SELECT COUNT(*) AS n FROM restricciones_salud WHERE socio_id=%s", (a_bytes(datos.usuarios["socio"]),)
        )
        assert cursor.fetchone()["n"] == 1


def test_al_otorgar_de_nuevo_la_sesion_se_proyecta_en_vivo_con_restricciones_nuevas(dolor_api):
    datos = dolor_api
    cliente, ruta = datos.cliente_dolor, datos.ruta_dolor
    assert escribir(cliente, ruta + "/dolores", datos.cuerpo_dolor).status_code == 201
    revocar_demo(datos)
    ejercicio = lectura(datos)["ejercicios"][0]
    assert ejercicio["objetivos"]["series"] > 0
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute(
            "SELECT socio_id FROM sesiones_realizadas WHERE id=%s", (a_bytes(desde_texto(datos.sesion_dolor)),)
        )
        socio = cursor.fetchone()["socio_id"]
        cursor.execute("SELECT autor_id FROM restricciones_salud LIMIT 1")
        autor = cursor.fetchone()["autor_id"]
        cursor.execute(
            "INSERT INTO restricciones_salud (id,socio_id,patron_movimiento,descripcion,registrada_en,autor_id) "
            "SELECT %s,%s,e.patron_movimiento,'Restricción durante la revocación',%s,%s FROM ejercicios e "
            "JOIN ejercicios_planificados p ON p.ejercicio_id=e.id WHERE p.id=%s",
            (
                a_bytes(nuevo_id(datos.reloj)),
                socio,
                datos.reloj.ahora(),
                autor,
                a_bytes(desde_texto(ejercicio["id"])),
            ),
        )
    sin = lectura(datos)["ejercicios"][0]
    assert sin["objetivos"]["series"] > 0
    otorgar_demo(datos)
    con = lectura(datos)["ejercicios"][0]
    assert con["objetivos"]["series"] == 0
    assert any(r["regla"] == "restriccion_salud" for r in con["explicacion"])


def test_maquina_ocupada_sigue_ofreciendo_alternativas_sin_consentimiento(alternativas_api):
    datos = alternativas_api
    cliente = datos.cliente()
    consentir(datos, True)
    consentir(datos, False)
    sesion = iniciar(datos)
    ejercicio = str(datos.ejercicios[0][0])
    respuesta = cliente.get(f"/api/entrenamiento/sesiones/{sesion}/ejercicios/{ejercicio}/alternativas")
    assert respuesta.status_code == 200
    assert [a["ejercicio_id"] for a in respuesta.json["alternativas"]] == list(map(str, datos.alternativas))
    assert respuesta.json["explicacion"]["regla"] == "maquina_ocupada"


def test_equipo_fuera_de_servicio_sigue_ofreciendo_alternativas_sin_consentimiento(alternativas_api):
    datos = alternativas_api
    consentir(datos, True)
    consentir(datos, False)
    with datos.app.app_context(), transaccion() as cursor:
        equipo = nuevo_id(datos.reloj)
        cursor.execute(
            "INSERT INTO equipos (id,nombre,creado_en) VALUES (%s,'barra',%s)",
            (a_bytes(equipo), datos.reloj.ahora()),
        )
    assert (
        escribir(
            datos.cliente("entrenador"), f"/api/equipos/{equipo}/estado", {"estado": "fuera_de_servicio"}
        ).status_code
        == 200
    )
    propuesta = datos.cliente().get("/api/entrenamiento/propuesta").json
    ejercicio = propuesta["ejercicios"][0]
    assert ejercicio["ejercicio_hecho_id"] in set(map(str, datos.alternativas))
    assert ejercicio["objetivos"]["series"] > 0
    assert not ejercicio["no_disponible"]


def serie_hecha(datos, cliente, ruta, ejercicio, repeticiones, carga):
    respuesta = escribir(
        cliente,
        ruta + "/series",
        {
            "id": str(nuevo_id(datos.reloj)),
            "ejercicio_planificado_id": ejercicio,
            "repeticiones": repeticiones,
            "carga": carga,
        },
    )
    assert respuesta.status_code == 201


def completar_sesion(datos, cliente, repeticiones, carga="20.50"):
    sesion = iniciar(datos)
    ruta = f"/api/entrenamiento/sesiones/{sesion}"
    for ejercicio in datos.ejercicios[0]:
        for _ in range(2):
            serie_hecha(datos, cliente, ruta, str(ejercicio), repeticiones, carga)
    return sesion


def test_series_durante_la_revocacion_quedan_y_al_otorgar_la_suba_respeta_el_tope_semanal(entrenamiento_api):
    datos = entrenamiento_api
    cliente = datos.cliente()
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("UPDATE ejercicios SET incremento_carga=2.5")
    consentir(datos, True)
    completar_sesion(datos, cliente, 10)
    suba = cliente.get("/api/entrenamiento/propuesta").json
    assert Decimal(suba["ejercicios"][0]["objetivos"]["carga"]) > Decimal("20.50")
    consentir(datos, False)
    congelada = cliente.get("/api/entrenamiento/propuesta").json
    assert Decimal(congelada["ejercicios"][0]["objetivos"]["carga"]) == Decimal("20.50")
    assert "sin_consentimiento_salud" in {r["regla"] for r in congelada["explicacion"]}
    assert "subir_carga" not in {r["regla"] for r in congelada["explicacion"]}
    sesion = str(nuevo_id(datos.reloj))
    cuerpo = {"id": sesion, "sesion_planificada_id": congelada["sesion_planificada"]["id"]}
    assert escribir(cliente, "/api/entrenamiento/sesiones", cuerpo).status_code == 201
    ruta = f"/api/entrenamiento/sesiones/{sesion}"
    for ejercicio in congelada["ejercicios"]:
        serie_hecha(datos, cliente, ruta, ejercicio["id"], 10, ejercicio["objetivos"]["carga"])
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT COUNT(*) AS n FROM series_realizadas")
        assert cursor.fetchone()["n"] == 6
    consentir(datos, True)
    otorgada = cliente.get("/api/entrenamiento/propuesta").json
    sube = [Decimal(e["objetivos"]["carga"]) for e in otorgada["ejercicios"]]
    # Las semanas congeladas no acumulan: la suba nunca supera un incremento sobre la última carga.
    assert max(sube) <= Decimal("20.50") + Decimal("2.5")


def test_aviso_anterior_sigue_en_la_bandeja_y_se_puede_revisar_sin_datos_de_salud(dolor_api):
    datos = dolor_api
    cliente, ruta = datos.cliente_dolor, datos.ruta_dolor
    assert escribir(cliente, ruta + "/dolores", datos.cuerpo_dolor).status_code == 201
    revocar_demo(datos)
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute(
            "SELECT socio_id FROM sesiones_realizadas WHERE id=%s", (a_bytes(desde_texto(datos.sesion_dolor)),)
        )
        socio = cursor.fetchone()["socio_id"]
        cursor.execute(
            "SELECT entrenador_id FROM asignaciones_entrenador WHERE socio_id=%s AND hasta IS NULL", (socio,)
        )
        entrenador = cursor.fetchone()["entrenador_id"]
    from gimnasio.comun.ids import desde_bytes

    with cliente.session_transaction() as sesion:
        sesion.clear()
        sesion["usuario_id"] = str(desde_bytes(entrenador))
    ruta_socio = f"/api/entrenador/socios/{desde_bytes(socio)}"
    ficha = cliente.get(ruta_socio)
    assert ficha.status_code == 200
    assert ficha.json["sin_consentimiento"] is True and ficha.json["salud"] is None
    avisos = ficha.json["avisos"]
    assert avisos and all(a["freno"] for a in avisos)
    assert "zonas" not in json.dumps(avisos)
    bandeja = cliente.get("/api/entrenador/bandeja").json
    socios = {s["id"]: s for g in bandeja["grupos"] for s in g["socios"]}
    motivos = socios[str(desde_bytes(socio))]["motivos"]
    assert "sin_consentimiento_salud" in {m["tipo"] for m in motivos}
    assert "aviso_seguridad" in {m["tipo"] for m in motivos}
    assert json.dumps(motivos).count("rodillas") == 0
    revision = escribir(cliente, ruta_socio + "/avisos/revision", {"aviso_ids": [avisos[0]["id"]]})
    assert revision.status_code in {200, 201}
