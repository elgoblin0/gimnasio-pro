"""Personal, claves provisionales y listas acotadas sin datos de salud."""

from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from mysql.connector.cursor import MySQLCursor

from gimnasio.comun.bd import transaccion
from gimnasio.permisos import repositorio
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
