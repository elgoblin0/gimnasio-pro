"""Pagos y membresías atómicos, permisos y conservación del historial."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from uuid import uuid4

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.ids import a_bytes, desde_bytes, desde_texto, nuevo_id
from gimnasio.comun.reloj import fecha_local
from gimnasio.demo import servicio as demo
from gimnasio.pagos import servicio
from gimnasio.socios import servicio as socios
from gimnasio.visitas import servicio as visitas


def escribir(cliente, ruta, cuerpo=None, *, metodo="post", clave=None):
    return getattr(cliente, metodo)(
        ruta, json=cuerpo, headers={"X-Gimnasio": "1", "Idempotency-Key": clave or str(uuid4())}
    )


@pytest.fixture
def pagos(app_con_bd):
    app_con_bd.config["MODO_DEMO"] = True
    with app_con_bd.app_context():
        demo.reiniciar()
    cliente = app_con_bd.test_client()
    autor = cliente.post("/api/sesion/demo/administracion", headers={"X-Gimnasio": "1"}).get_json()["usuario"]
    tipo = escribir(cliente, "/api/tipos-membresia", {"nombre": "Mensual", "duracion_dias": 30, "precio": 250000})
    assert tipo.status_code == 201
    socio = cliente.get("/api/pagos/socios").get_json()["socios"][0]
    return app_con_bd, cliente, autor, {"socio_id": socio["id"], "tipo_id": tipo.get_json()["id"], "medio": "efectivo"}


def filas(app, tabla):
    # Solo nombres fijos de estas pruebas, nunca texto recibido del cliente.
    with app.app_context(), transaccion() as cursor:
        cursor.execute(f"SELECT * FROM {tabla} ORDER BY id")
        return cursor.fetchall()


@pytest.mark.bd
def test_pago_renueva_vencida_y_permite_entrada(pagos, reloj_fijo):
    app, cliente, autor, datos = pagos
    socio_id = desde_texto(datos["socio_id"])
    hoy = fecha_local(reloj_fijo.ahora())
    with app.app_context(), transaccion() as cursor:
        cursor.execute(
            "UPDATE membresias SET desde=%s, hasta=%s WHERE socio_id=%s",
            (hoy - timedelta(days=30), hoy - timedelta(days=1), a_bytes(socio_id)),
        )
    with app.app_context():
        assert socios.consultar_membresia(socio_id, hoy) is None
    respuesta = escribir(cliente, "/api/pagos", datos)
    assert respuesta.status_code == 201
    pago = respuesta.get_json()
    assert pago["monto"] == 250000
    assert pago["autor_id"] == autor["id"]
    assert pago["membresia"]["desde"] == hoy.isoformat()
    with app.app_context():
        assert socios.consultar_membresia(socio_id, hoy) is not None
        with transaccion() as cursor:
            cursor.execute("SELECT id FROM sedes ORDER BY id LIMIT 1")
            sede_id = cursor.fetchone()["id"]
            # La semilla puede tener una visita del socio: se cierra desde el servicio.
            cursor.execute(
                "SELECT e.id FROM entradas e WHERE e.socio_id=%s "
                "AND NOT EXISTS (SELECT 1 FROM salidas s WHERE s.entrada_id=e.id)",
                (a_bytes(socio_id),),
            )
            for entrada in cursor.fetchall():
                visitas.registrar_salida_en_transaccion(
                    cursor, desde_bytes(entrada["id"]), desde_texto(autor["id"]), reloj_fijo.ahora()
                )
        entrada = visitas.registrar_entrada(
            {"id": str(nuevo_id()), "socio_id": str(socio_id), "sede_id": str(desde_bytes(sede_id))}, autor
        )
        assert entrada["socio_id"] == str(socio_id)


@pytest.mark.bd
def test_dos_pagos_encadenan_y_conservan_membresia_anterior(pagos):
    app, cliente, _, datos = pagos
    anteriores = filas(app, "membresias")
    assert all(fila["tipo_id"] is None for fila in anteriores)
    primera = escribir(cliente, "/api/pagos", datos).get_json()
    segunda = escribir(cliente, "/api/pagos", datos).get_json()
    assert date.fromisoformat(segunda["membresia"]["desde"]) == date.fromisoformat(
        primera["membresia"]["hasta"]
    ) + timedelta(days=1)
    despues = filas(app, "membresias")
    assert len(despues) == len(anteriores) + 2
    assert all(fila in despues for fila in anteriores)
    assert len(filas(app, "pagos")) == 2


@pytest.mark.bd
def test_idempotencia_y_precio_historico(pagos):
    app, cliente, _, datos = pagos
    clave = str(uuid4())
    antes = len(filas(app, "membresias"))
    primera = escribir(cliente, "/api/pagos", datos, clave=clave)
    assert primera.status_code == 201
    assert escribir(cliente, "/api/pagos", datos, clave=clave).data == primera.data
    assert len(filas(app, "pagos")) == 1
    assert len(filas(app, "membresias")) == antes + 1
    assert (
        escribir(
            cliente,
            f"/api/tipos-membresia/{datos['tipo_id']}",
            {"nombre": "Mensual", "duracion_dias": 30, "precio": 300000},
            metodo="put",
        ).status_code
        == 200
    )
    assert filas(app, "pagos")[0]["monto"] == 250000
    assert escribir(cliente, "/api/pagos", datos).get_json()["monto"] == 300000
    assert escribir(cliente, "/api/pagos", datos | {"monto": 0}).get_json()["monto"] == 0


@pytest.mark.bd
def test_falla_membresia_revierte_pago_y_permite_reintento(pagos, monkeypatch):
    app, cliente, _, datos = pagos
    antes = filas(app, "membresias")
    clave = str(uuid4())
    with monkeypatch.context() as parche:

        def fallar(*args, **kwargs):
            raise RuntimeError("Falla simulada al crear membresía")

        parche.setattr(socios.repositorio, "insertar_membresia", fallar)
        with pytest.raises(RuntimeError, match="Falla simulada"):
            escribir(cliente, "/api/pagos", datos, clave=clave)
    assert filas(app, "pagos") == []
    assert filas(app, "membresias") == antes
    assert escribir(cliente, "/api/pagos", datos, clave=clave).status_code == 201


@pytest.mark.bd
def test_archivar_conserva_pago_membresias_y_vigencia(pagos):
    app, cliente, _, datos = pagos
    respuesta = escribir(cliente, "/api/pagos", datos)
    assert respuesta.status_code == 201
    membresia = respuesta.get_json()["membresia"]
    anteriores = filas(app, "membresias"), filas(app, "pagos")
    assert escribir(cliente, f"/api/tipos-membresia/{datos['tipo_id']}/archivar").status_code == 200
    assert (filas(app, "membresias"), filas(app, "pagos")) == anteriores
    with app.app_context():
        vigente = socios.consultar_membresia(desde_texto(datos["socio_id"]), date.fromisoformat(membresia["desde"]))
        assert vigente["id"] == membresia["id"]
    assert escribir(cliente, "/api/pagos", datos).status_code == 422
    assert cliente.get("/api/tipos-membresia").get_json()["tipos"][0]["archivado"]
    cliente.post("/api/sesion/demo/recepcion", headers={"X-Gimnasio": "1"})
    assert cliente.get("/api/tipos-membresia").get_json() == {"tipos": []}


@pytest.mark.bd
def test_pago_no_toca_visitas_y_reinicio_demo(pagos):
    app, cliente, autor, datos = pagos
    with app.app_context():
        with transaccion() as cursor:
            cursor.execute("SELECT id FROM sedes ORDER BY id LIMIT 1")
            sede_id = desde_bytes(cursor.fetchone()["id"])
        visitas.registrar_entrada(
            {"id": str(nuevo_id()), "socio_id": datos["socio_id"], "sede_id": str(sede_id)}, autor
        )
    antes = filas(app, "entradas"), filas(app, "salidas")
    assert any(entrada["id"] not in {salida["entrada_id"] for salida in antes[1]} for entrada in antes[0])
    assert escribir(cliente, "/api/pagos", datos).status_code == 201
    assert (filas(app, "entradas"), filas(app, "salidas")) == antes
    with app.app_context():
        demo.reiniciar()
    assert filas(app, "pagos") == []
    assert filas(app, "tipos_membresia") == []


@pytest.mark.bd
def test_pago_rechaza_socio_inactivo_inexistente_o_no_socio(pagos):
    app, cliente, autor, datos = pagos
    with app.app_context(), transaccion() as cursor:
        cursor.execute("UPDATE usuarios SET activo=FALSE WHERE id=%s", (a_bytes(desde_texto(datos["socio_id"])),))
        inexistente = str(nuevo_id())
    for socio_id in (datos["socio_id"], autor["id"], inexistente):
        assert escribir(cliente, "/api/pagos", datos | {"socio_id": socio_id}).status_code == 422
    assert filas(app, "pagos") == []


@pytest.mark.bd
@pytest.mark.parametrize(
    "rol,lectura,escritura,pago",
    [
        ("socio", 403, 403, 403),
        ("entrenador", 403, 403, 403),
        ("recepcion", 200, 403, 201),
        ("administracion", 200, 201, 201),
    ],
)
def test_permisos_de_rutas(pagos, rol, lectura, escritura, pago):
    _, cliente, _, datos = pagos
    cliente.post(f"/api/sesion/demo/{rol}", headers={"X-Gimnasio": "1"})
    assert cliente.get("/api/tipos-membresia").status_code == lectura
    assert cliente.get("/api/pagos/socios").status_code == lectura
    assert (
        escribir(
            cliente, "/api/tipos-membresia", {"nombre": "Semanal", "duracion_dias": 7, "precio": 50000}
        ).status_code
        == escritura
    )
    assert escribir(
        cliente,
        f"/api/tipos-membresia/{datos['tipo_id']}",
        {"nombre": "Mensual", "duracion_dias": 30, "precio": 250000},
        metodo="put",
    ).status_code == (200 if escritura == 201 else 403)
    assert escribir(cliente, "/api/pagos", datos).status_code == pago
    assert escribir(cliente, f"/api/tipos-membresia/{datos['tipo_id']}/archivar").status_code == (
        200 if escritura == 201 else 403
    )


@pytest.mark.bd
def test_encabezados_obligatorios(pagos):
    _, cliente, _, datos = pagos
    assert cliente.post("/api/pagos", json=datos, headers={"X-Gimnasio": "1"}).status_code == 428
    assert cliente.post("/api/pagos", json=datos, headers={"Idempotency-Key": str(uuid4())}).status_code == 403


@pytest.mark.bd
def test_pagos_concurrentes_de_tipos_distintos(pagos):
    app, cliente, autor, datos = pagos
    otro = escribir(
        cliente, "/api/tipos-membresia", {"nombre": "Semanal", "duracion_dias": 7, "precio": 50000}
    ).get_json()

    def registrar(tipo_id):
        with app.app_context():
            return servicio.registrar_pago(datos | {"tipo_id": tipo_id}, autor)

    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        pagos_nuevos = list(ejecutor.map(registrar, [datos["tipo_id"], otro["id"]]))
    membresias = sorted((pago["membresia"] for pago in pagos_nuevos), key=lambda membresia: membresia["desde"])
    assert date.fromisoformat(membresias[1]["desde"]) == date.fromisoformat(membresias[0]["hasta"]) + timedelta(days=1)


@pytest.mark.parametrize(
    "datos",
    [
        None,
        {},
        {"nombre": " ", "duracion_dias": 30, "precio": 1},
        {"nombre": "Mensual", "duracion_dias": 0, "precio": 1},
        {"nombre": "Mensual", "duracion_dias": True, "precio": 1},
        {"nombre": "Mensual", "duracion_dias": 1, "precio": -1},
        {"nombre": "Mensual", "duracion_dias": 1, "precio": 1.5},
    ],
)
def test_validacion_tipo(datos):
    with pytest.raises(ErrorDeDominio) as error:
        servicio.validar_tipo(datos)
    assert error.value.estado_http == 422


@pytest.mark.parametrize("monto", [-1, True, 1.5, "250000", None, 2**64])
def test_monto_invalido_sin_escrituras(monto, reloj_fijo):
    from gimnasio import crear_app

    app = crear_app({"ENTORNO": "prueba"}, reloj_fijo)
    with app.app_context(), pytest.raises(ErrorDeDominio) as error:
        servicio.registrar_pago(
            {"socio_id": str(nuevo_id()), "tipo_id": str(nuevo_id()), "medio": "efectivo", "monto": monto}, {}
        )
    assert error.value.estado_http == 422


@pytest.mark.bd
def test_sin_membresia_previa_y_medios_de_pago(pagos, reloj_fijo):
    from gimnasio.permisos.servicio import crear_usuario

    app, cliente, _, datos = pagos
    with app.app_context(), transaccion() as cursor:
        socio_id = crear_usuario(cursor, {"nombre": "Socio", "apellido": "Ficticio", "cedula": "9988776"}, "socio")
    for medio in ("efectivo", "transferencia", "tarjeta", "otro"):
        respuesta = escribir(cliente, "/api/pagos", datos | {"socio_id": str(socio_id), "medio": medio})
        assert respuesta.status_code == 201
        assert respuesta.get_json()["medio"] == medio
    with app.app_context():
        assert socios.consultar_membresia(socio_id, fecha_local(reloj_fijo.ahora()))["desde"] == fecha_local(
            reloj_fijo.ahora()
        )


@pytest.mark.bd
def test_cuerpos_invalidos_y_tipo_inexistente(pagos):
    app, cliente, _, datos = pagos
    for cuerpo in (
        None,
        {},
        datos | {"medio": "cheque"},
        datos | {"medio": []},
        datos | {"socio_id": "incorrecto"},
        datos | {"extra": 1},
    ):
        assert escribir(cliente, "/api/pagos", cuerpo).status_code == 422
    with app.app_context():
        inexistente = str(nuevo_id())
    assert escribir(cliente, "/api/pagos", datos | {"tipo_id": inexistente}).status_code == 404
    assert escribir(cliente, f"/api/tipos-membresia/{inexistente}/archivar").status_code == 404
    assert filas(app, "pagos") == []


@pytest.mark.bd
def test_pago_solo_puede_renovar_una_membresia(pagos):
    from mysql.connector import IntegrityError

    app, cliente, _, datos = pagos
    pago = escribir(cliente, "/api/pagos", datos).get_json()
    with app.app_context(), pytest.raises(IntegrityError) as error, transaccion() as cursor:
        cursor.execute(
            "INSERT INTO membresias (id, socio_id, desde, hasta, actualizada_en, pago_id, tipo_id) "
            "SELECT %s, socio_id, desde, hasta, actualizada_en, pago_id, tipo_id FROM membresias WHERE pago_id=%s",
            (a_bytes(nuevo_id()), a_bytes(desde_texto(pago["id"]))),
        )
    assert error.value.errno == 1062
