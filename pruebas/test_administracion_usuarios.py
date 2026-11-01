"""Personal, claves provisionales y listas acotadas sin datos de salud."""

from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from mysql.connector.cursor import MySQLCursor

from gimnasio.comun.bd import transaccion
from gimnasio.permisos import repositorio
from pruebas.test_clases_avisos import avisos
from pruebas.test_clases_reservas import agenda, entrar, solicitar
from pruebas.test_clases_reservas import reservas as reservas
from pruebas.test_pagos import escribir
from pruebas.test_pagos import pagos as pagos
from pruebas.test_socios_alta import alta

pytestmark = pytest.mark.bd


def crear_personal(cliente, rol="entrenador", cedula="8899101", **opciones):
    return escribir(
        cliente,
        "/api/usuarios",
        {"nombre": "Personal", "apellido": "Ficticio", "cedula": cedula, "rol": rol},
        **opciones,
    )


@pytest.mark.parametrize("rol", ["recepcion", "entrenador", "administracion"])
def test_crear_cada_rol_sin_clave_demo(pagos, rol):
    app, cliente, _, _ = pagos
    respuesta = crear_personal(cliente, rol)
    assert respuesta.status_code == 201, respuesta.json
    assert "clave_provisional" not in respuesta.json
    with app.app_context(), transaccion() as cursor:
        cursor.execute(
            "SELECT rol,clave_hash,debe_cambiar_clave FROM usuarios WHERE id=%s",
            (UUID(respuesta.json["usuario_id"]).bytes,),
        )
        assert cursor.fetchone() == {"rol": rol, "clave_hash": None, "debe_cambiar_clave": 0}
    assert crear_personal(cliente, "socio", "8899102").status_code == 422
    assert crear_personal(cliente, rol, "8899101").status_code == 409
    assert escribir(cliente, f"/api/usuarios/{respuesta.json['usuario_id']}/clave").status_code == 409


def test_claves_solo_una_entrega_y_cambio_obligatorio(pagos):
    app, cliente, _, _ = pagos
    app.config["MODO_DEMO"] = False
    clave = str(uuid4())
    respuesta = crear_personal(cliente, clave=clave)
    assert respuesta.status_code == 201, respuesta.json
    identificador = respuesta.json["usuario_id"]
    assert "clave_provisional" not in crear_personal(cliente, clave=clave).json
    personal = app.test_client()
    provisional = respuesta.json["clave_provisional"]
    assert escribir(personal, "/api/sesion", {"identificador": "8899101", "clave": provisional}).status_code == 200
    assert personal.get("/api/entrenador/bandeja").json["error"]["codigo"] == "debe_cambiar_clave"
    assert (
        escribir(
            personal, "/api/sesion/clave", {"clave_actual": provisional, "clave_nueva": "definitiva-ficticia"}
        ).status_code
        == 200
    )
    assert personal.get("/api/entrenador/bandeja").status_code == 200
    clave = str(uuid4())
    restablecida = escribir(cliente, f"/api/usuarios/{identificador}/clave", clave=clave)
    assert restablecida.status_code == 200
    assert "clave_provisional" not in escribir(cliente, f"/api/usuarios/{identificador}/clave", clave=clave).json
    assert personal.get("/api/entrenador/bandeja").json["error"]["codigo"] == "debe_cambiar_clave"
    assert (
        escribir(
            personal,
            "/api/sesion/clave",
            {"clave_actual": restablecida.json["clave_provisional"], "clave_nueva": "definitiva-nueva"},
        ).status_code
        == 200
    )


def test_tope_demo_compartido_con_socios(pagos):
    _, cliente, _, _ = pagos
    for numero in range(10):
        assert alta(cliente, cedula=str(8899200 + numero)).status_code == 201
        assert crear_personal(cliente, cedula=str(8899300 + numero)).status_code == 201
    assert alta(cliente, cedula="8899400").status_code == 429
    assert crear_personal(cliente, cedula="8899401").status_code == 429


def test_lista_filtros_paginacion_y_una_consulta(pagos):
    app, cliente, _, _ = pagos
    with app.app_context(), transaccion() as cursor:
        from gimnasio.permisos.servicio import crear_usuario

        for numero in range(51):
            crear_usuario(
                cursor, {"nombre": "Lista", "apellido": "Ficticia", "cedula": str(8800000 + numero)}, "entrenador"
            )
    consultas = []
    ejecutar = MySQLCursor.execute

    def contar(cursor, consulta, *argumentos, **opciones):
        if consulta.lstrip().upper().startswith("SELECT"):
            consultas.append(consulta)
        return ejecutar(cursor, consulta, *argumentos, **opciones)

    with (
        patch.object(repositorio, "listar_usuarios", wraps=repositorio.listar_usuarios) as listar,
        patch.object(MySQLCursor, "execute", contar),
    ):
        primera = cliente.get("/api/usuarios?rol=entrenador&q=Lista&activo=true")
        assert listar.call_count == 1
    # Una lectura del usuario de sesión y una de la lista, aunque devuelva 50 filas.
    # El controlador también consulta variables de sesión al abrir la conexión.
    assert len([sql for sql in consultas if "FROM usuarios" in sql or "FROM personas" in sql]) == 2
    assert primera.status_code == 200
    assert primera.json["hay_mas"] and len(primera.json["usuarios"]) == 50
    segunda = cliente.get("/api/usuarios?rol=entrenador&q=Lista&activo=true&pagina=2").json
    assert len(segunda["usuarios"]) == 1 and not segunda["hay_mas"]
    assert not {u["id"] for u in primera.json["usuarios"]} & {u["id"] for u in segunda["usuarios"]}
    assert set(segunda["usuarios"][0]) == {"id", "rol", "activo", "nombre", "apellido", "cedula"}
    assert cliente.get("/api/usuarios?activo=false&q=Lista").json["usuarios"] == []
    for filtro in ("rol=inventado", "activo=quizas", "pagina=0", "pagina=no"):
        assert cliente.get(f"/api/usuarios?{filtro}").status_code == 422


@pytest.mark.parametrize("rol", ["socio", "recepcion", "entrenador"])
def test_cada_ruta_solo_administracion(pagos, rol):
    _, cliente, _, datos = pagos
    assert escribir(cliente, f"/api/sesion/demo/{rol}").status_code == 200
    assert crear_personal(cliente).status_code == 403
    assert cliente.get("/api/usuarios").status_code == 403
    assert escribir(cliente, f"/api/usuarios/{datos['socio_id']}/clave").status_code == 403
    assert cliente.get("/api/socios/sin-entrenador").status_code == 403
    assert escribir(cliente, f"/api/socios/{datos['socio_id']}/entrenador", {}, metodo="put").status_code == 403
    for accion in ("desactivar", "reactivar"):
        assert escribir(cliente, f"/api/usuarios/{datos['socio_id']}/{accion}").status_code == 403


def test_ultima_administracion_y_reactivacion_sin_asignaciones(pagos):
    app, cliente, autor, datos = pagos
    app.config["MODO_DEMO"] = False
    # La lista de socios sin entrenador deja afuera a los simulados, como el que trae este fixture.
    with app.app_context(), transaccion() as cursor:
        cursor.execute(
            "UPDATE personas p JOIN usuarios u ON u.persona_id=p.id SET p.simulada=FALSE WHERE u.id=%s",
            (UUID(datos["socio_id"]).bytes,),
        )
    rechazo = escribir(cliente, f"/api/usuarios/{autor['id']}/desactivar")
    assert rechazo.status_code == 409
    assert rechazo.json["error"]["codigo"] == "ultima_administracion"
    entrenador = crear_personal(cliente).json["usuario_id"]
    ruta = f"/api/usuarios/{entrenador}"
    assert (
        escribir(
            cliente, f"/api/socios/{datos['socio_id']}/entrenador", {"entrenador_id": entrenador}, metodo="put"
        ).status_code
        == 200
    )
    assert escribir(cliente, ruta + "/desactivar").status_code == 200
    assert datos["socio_id"] in [fila["id"] for fila in cliente.get("/api/socios/sin-entrenador").json["socios"]]
    assert escribir(cliente, ruta + "/reactivar").status_code == 200
    assert datos["socio_id"] in [fila["id"] for fila in cliente.get("/api/socios/sin-entrenador").json["socios"]]
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT hasta FROM asignaciones_entrenador WHERE entrenador_id=%s", (UUID(entrenador).bytes,))
        assert all(fila["hasta"] is not None for fila in cursor.fetchall())
    otra = crear_personal(cliente, "administracion", "8899102").json["usuario_id"]
    assert escribir(cliente, f"/api/usuarios/{otra}/desactivar").status_code == 200


@pytest.mark.parametrize("accion", ["desactivar", "reactivar"])
def test_demo_protege_usuarios_de_entrar_como(pagos, accion):
    _, cliente, autor, _ = pagos
    socio_demo = cliente.get("/api/sesion/demo/socios").json["socios"][0]
    for identificador in (autor["id"], socio_demo["id"]):
        respuesta = escribir(cliente, f"/api/usuarios/{identificador}/{accion}")
        assert respuesta.status_code == 409
        assert respuesta.json["error"]["codigo"] == "usuario_demo_protegido"


def test_desactivar_invalida_sesion_e_impide_ingreso(pagos):
    app, cliente, _, _ = pagos
    app.config["MODO_DEMO"] = False
    creada = crear_personal(cliente, "recepcion").json
    personal = app.test_client()
    assert (
        escribir(
            personal, "/api/sesion", {"identificador": "8899101", "clave": creada["clave_provisional"]}
        ).status_code
        == 200
    )
    assert (
        escribir(
            personal,
            "/api/sesion/clave",
            {"clave_actual": creada["clave_provisional"], "clave_nueva": "definitiva-ficticia"},
        ).status_code
        == 200
    )
    assert escribir(cliente, f"/api/usuarios/{creada['usuario_id']}/desactivar").status_code == 200
    assert personal.get("/api/pagos/socios").status_code == 401
    assert (
        escribir(personal, "/api/sesion", {"identificador": "8899101", "clave": "definitiva-ficticia"}).status_code
        == 401
    )


def test_baja_por_revocacion_conserva_historial_y_no_duplica(pagos):
    app, cliente, autor, datos = pagos
    app.config["MODO_DEMO"] = False
    socio = datos["socio_id"]
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT * FROM consentimientos WHERE socio_id=%s ORDER BY id", (UUID(socio).bytes,))
        originales = cursor.fetchall()
    ruta = f"/api/usuarios/{socio}/desactivar"
    clave = str(uuid4())
    for reintento in (clave, clave, str(uuid4())):
        respuesta = escribir(cliente, ruta, {"por_revocacion": True}, clave=reintento)
        assert respuesta.status_code == 200
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT * FROM consentimientos WHERE socio_id=%s ORDER BY id", (UUID(socio).bytes,))
        actuales = cursor.fetchall()
        por_id = {fila["id"]: fila for fila in actuales}
        assert all(por_id[fila["id"]] == fila for fila in originales)
        nuevos = [fila for fila in actuales if fila["id"] not in {original["id"] for original in originales}]
        assert len(nuevos) == 1
        assert nuevos[0]["tipo"] == "datos_personales" and not nuevos[0]["otorgado"]
        assert nuevos[0]["registrado_por"] == UUID(autor["id"]).bytes
        cursor.execute(
            "SELECT p.* FROM personas p JOIN usuarios u ON u.persona_id=p.id WHERE u.id=%s", (UUID(socio).bytes,)
        )
        assert cursor.fetchone()["nombre"]
    assert escribir(cliente, f"/api/usuarios/{socio}/reactivar").status_code == 200
    with app.app_context(), transaccion() as cursor:
        assert not repositorio.consentimiento_vigente(cursor, UUID(socio), "datos_personales")["otorgado"]


@pytest.mark.parametrize("posicion", [0, 1])
def test_baja_cancela_promueve_sin_duplicar_ni_retroceder(reservas, posicion):
    app, cliente, clase, socios, _, _ = reservas
    originales = [solicitar(cliente, clase, socio).json["id"] for socio in socios[:3]]
    entrar(cliente, "administracion")
    app.config["MODO_DEMO"] = False
    socio = socios[posicion]
    ruta = f"/api/usuarios/{socio}"
    clave = str(uuid4())
    for reintento in (clave, clave, str(uuid4())):
        respuesta = escribir(cliente, ruta + "/desactivar", clave=reintento)
        assert respuesta.status_code == 200, respuesta.json
    assert [(a["socio_id"], a["tipo"]) for a in avisos(app)] == (
        [(socios[1], "paso_a_tener_lugar")] if posicion == 0 else []
    )
    assert escribir(cliente, ruta + "/reactivar").status_code == 200
    # La consulta de recepción permite ver reservas de todos sin reabrir una sesión demo.
    with cliente.session_transaction() as sesion, app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT id FROM usuarios WHERE rol='recepcion' LIMIT 1")
        from gimnasio.comun.ids import desde_bytes

        sesion["usuario_id"] = str(desde_bytes(cursor.fetchone()["id"]))
    assert agenda(cliente, socio)[0]["reserva"] is None
    assert agenda(cliente, socios[1 if posicion == 0 else 0])[0]["reserva"]["estado"] == "con_lugar"
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT id FROM reservas ORDER BY id")
        assert {UUID(r).bytes for r in originales} == {r["id"] for r in cursor.fetchall()}
        cursor.execute("SELECT reserva_id FROM cancelaciones_reserva")
        assert cursor.fetchall() == [{"reserva_id": UUID(originales[posicion]).bytes}]


def test_baja_no_toca_ocurrencias_empezadas(reservas):
    from datetime import UTC, datetime

    app, cliente, clase, socios, _, _ = reservas
    original = solicitar(cliente, clase, socios[0]).json["id"]
    entrar(cliente, "administracion")
    app.config["MODO_DEMO"] = False
    app.extensions["reloj"].fijar(datetime(2026, 10, 27, 21, 0, tzinfo=UTC))
    assert escribir(cliente, f"/api/usuarios/{socios[0]}/desactivar").status_code == 200
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT id FROM cancelaciones_reserva WHERE reserva_id=%s", (UUID(original).bytes,))
        assert cursor.fetchall() == []
    assert avisos(app) == []


def test_socio_cierra_asignacion_sin_revocar_consentimiento(pagos):
    app, cliente, _, datos = pagos
    app.config["MODO_DEMO"] = False
    socio = datos["socio_id"]
    entrenador = crear_personal(cliente).json["usuario_id"]
    assert (
        escribir(cliente, f"/api/socios/{socio}/entrenador", {"entrenador_id": entrenador}, metodo="put").status_code
        == 200
    )
    with app.app_context(), transaccion() as cursor:
        anterior = repositorio.consentimiento_vigente(cursor, UUID(socio), "datos_personales")
    assert escribir(cliente, f"/api/usuarios/{socio}/desactivar").status_code == 200
    assert escribir(cliente, f"/api/usuarios/{socio}/reactivar").status_code == 200
    with app.app_context(), transaccion() as cursor:
        assert not repositorio.tiene_asignacion_vigente(cursor, UUID(socio), UUID(entrenador))
        assert repositorio.consentimiento_vigente(cursor, UUID(socio), "datos_personales") == anterior


def test_entrenador_con_clase_archivada_sin_reservas_puede_desactivarse(reservas):
    app, cliente, clase, _, datos, _ = reservas
    entrar(cliente, "administracion")
    assert escribir(cliente, f"/api/clases/{clase}/archivar").status_code == 200
    app.config["MODO_DEMO"] = False
    assert escribir(cliente, f"/api/usuarios/{datos['entrenador_id']}/desactivar").status_code == 200


def test_baja_revierte_cancelaciones_y_avisos_si_falla_el_estado(reservas, monkeypatch):
    from gimnasio.comun.errores import ErrorDeDominio

    app, cliente, clase, socios, _, _ = reservas
    for socio in socios[:2]:
        assert solicitar(cliente, clase, socio).status_code == 201
    entrar(cliente, "administracion")
    app.config["MODO_DEMO"] = False

    def fallar(*argumentos):
        raise ErrorDeDominio("fallo_de_prueba", "Fallo ficticio al cambiar el estado.", 409)

    monkeypatch.setattr(repositorio, "cambiar_activo", fallar)
    assert escribir(cliente, f"/api/usuarios/{socios[0]}/desactivar").status_code == 409
    with app.app_context(), transaccion() as cursor:
        assert repositorio.buscar_por_id(cursor, UUID(socios[0]))["activo"]
        cursor.execute("SELECT id FROM cancelaciones_reserva")
        assert cursor.fetchall() == []
    assert avisos(app) == []


@pytest.mark.parametrize("archivada", [False, True])
def test_entrenador_con_clase_o_reservas_futuras_se_rechaza(reservas, archivada):
    app, cliente, clase, socios, datos, _ = reservas
    assert solicitar(cliente, clase, socios[0]).status_code == 201
    entrar(cliente, "administracion")
    if archivada:
        assert escribir(cliente, f"/api/clases/{clase}/archivar").status_code == 200
    app.config["MODO_DEMO"] = False
    respuesta = escribir(cliente, f"/api/usuarios/{datos['entrenador_id']}/desactivar")
    assert respuesta.status_code == 409
    assert respuesta.json["error"]["codigo"] == "clases_a_cargo"
    with app.app_context(), transaccion() as cursor:
        assert repositorio.buscar_por_id(cursor, UUID(datos["entrenador_id"]))["activo"]


def test_socio_con_visita_abierta_se_rechaza(pagos):
    from gimnasio.comun.ids import nuevo_id
    from gimnasio.visitas.repositorio import insertar_entrada

    app, cliente, autor, datos = pagos
    app.config["MODO_DEMO"] = False
    with app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT id FROM sedes LIMIT 1")
        from gimnasio.comun.ids import desde_bytes

        insertar_entrada(
            cursor,
            nuevo_id(),
            UUID(datos["socio_id"]),
            desde_bytes(cursor.fetchone()["id"]),
            UUID(autor["id"]),
            app.extensions["reloj"].ahora(),
        )
    respuesta = escribir(cliente, f"/api/usuarios/{datos['socio_id']}/desactivar", {"por_revocacion": True})
    assert respuesta.status_code == 409
    assert respuesta.json["error"]["codigo"] == "visita_abierta"
    with app.app_context(), transaccion() as cursor:
        assert repositorio.buscar_por_id(cursor, UUID(datos["socio_id"]))["activo"]


def test_estado_valida_cuerpo_id_y_encabezados(pagos):
    app, cliente, _, datos = pagos
    ruta = f"/api/usuarios/{datos['socio_id']}/desactivar"
    assert cliente.post(ruta).status_code == 403
    assert cliente.post(ruta, headers={"X-Gimnasio": "1"}).status_code == 428
    for cuerpo in ([], {"por_revocacion": "true"}, {"otro": True}):
        assert escribir(cliente, ruta, cuerpo).status_code == 422
    assert escribir(cliente, "/api/usuarios/invalido/desactivar").status_code == 422
    from gimnasio.comun.ids import nuevo_id

    with app.app_context():
        inexistente = nuevo_id()
    assert escribir(cliente, f"/api/usuarios/{inexistente}/desactivar").status_code == 404


def test_no_se_reserva_con_entrenador_desactivado(reservas):
    app, cliente, clase, socios, datos, _ = reservas
    reserva = solicitar(cliente, clase, socios[0]).json["id"]
    assert escribir(cliente, f"/api/clases/reservas/{reserva}/cancelar").status_code == 200
    entrar(cliente, "administracion")
    assert escribir(cliente, f"/api/clases/{clase}/archivar").status_code == 200
    app.config["MODO_DEMO"] = False
    assert escribir(cliente, f"/api/usuarios/{datos['entrenador_id']}/desactivar").status_code == 200
    app.config["MODO_DEMO"] = True
    entrar(cliente, "recepcion")
    respuesta = solicitar(cliente, clase, socios[1])
    assert respuesta.status_code == 409
    assert respuesta.json["error"]["codigo"] == "entrenador_inactivo"
