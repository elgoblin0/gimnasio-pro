"""Pagos y membresías atómicos, permisos y conservación del historial."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Event
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
def pagos(app_con_bd, sembrar_demo):
    app_con_bd.config["MODO_DEMO"] = True
    sembrar_demo(app_con_bd)
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


@pytest.mark.bd
@pytest.mark.parametrize("demora", [timedelta(0), timedelta(seconds=1)])
def test_anulacion_respeta_orden_de_renovaciones_concurrentes(pagos, reloj_fijo, monkeypatch, demora):
    app, cliente, autor, datos = pagos
    otro = escribir(cliente, "/api/tipos-membresia", {"nombre": "Semanal", "duracion_dias": 7, "precio": 50000}).json
    esperando, continuar = Event(), Event()
    bloquear = socios.bloquear_socio_activo

    def esperar_bloqueo(*argumentos, **opciones):
        esperando.set()
        assert continuar.wait(timeout=10)
        return bloquear(*argumentos, **opciones)

    def registrar_demorado():
        with app.app_context():
            return servicio.registrar_pago(datos, autor)

    with ThreadPoolExecutor(max_workers=1) as ejecutor, monkeypatch.context() as parche:
        parche.setattr(socios, "bloquear_socio_activo", esperar_bloqueo)
        pendiente = ejecutor.submit(registrar_demorado)
        try:
            assert esperando.wait(timeout=10)
            parche.setattr(socios, "bloquear_socio_activo", bloquear)
            reloj_fijo.avanzar(demora)
            primera = escribir(cliente, "/api/pagos", datos | {"tipo_id": otro["id"]}).json
        finally:
            continuar.set()
        segunda = pendiente.result(timeout=10)

    assert date.fromisoformat(segunda["membresia"]["desde"]) == date.fromisoformat(
        primera["membresia"]["hasta"]
    ) + timedelta(days=1)
    assert escribir(cliente, f"/api/pagos/{primera['id']}/anular", {"motivo": "Error ficticio"}).status_code == 409
    assert escribir(cliente, f"/api/pagos/{segunda['id']}/anular", {"motivo": "Error ficticio"}).status_code == 201
    with app.app_context():
        socio_id = desde_texto(datos["socio_id"])
        assert socios.consultar_membresia(socio_id, date.fromisoformat(segunda["membresia"]["desde"])) is None
    assert escribir(cliente, f"/api/pagos/{primera['id']}/anular", {"motivo": "Error ficticio"}).status_code == 201


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


@pytest.mark.bd
def test_anulaciones_encadenadas_recalculan_y_conservan_filas(pagos, reloj_fijo):
    app, cliente, _, datos = pagos
    socio_id = desde_texto(datos["socio_id"])
    hoy = fecha_local(reloj_fijo.ahora())
    with app.app_context():
        original = socios.membresia_para_tarjeta(socio_id, hoy)
    primera = escribir(cliente, "/api/pagos", datos).json
    reloj_fijo.avanzar(timedelta(seconds=1))
    segunda = escribir(cliente, "/api/pagos", datos).json
    anteriores = filas(app, "membresias")
    ruta = f"/api/pagos/{primera['id']}/anular"
    respuesta = escribir(cliente, ruta, {"motivo": "Error ficticio"})
    assert respuesta.status_code == 409
    assert respuesta.json["error"]["codigo"] == "no_es_ultimo_pago"
    assert escribir(cliente, f"/api/pagos/{segunda['id']}/anular", {}).status_code == 422
    clave = str(uuid4())
    anulada = escribir(cliente, f"/api/pagos/{segunda['id']}/anular", {"motivo": "Error ficticio"}, clave=clave)
    assert anulada.status_code == 201
    assert (
        escribir(cliente, f"/api/pagos/{segunda['id']}/anular", {"motivo": "Error ficticio"}, clave=clave).data
        == anulada.data
    )
    assert escribir(cliente, f"/api/pagos/{segunda['id']}/anular", {"motivo": "Otro motivo"}).status_code == 409
    assert len(filas(app, "anulaciones_pago")) == 1
    with app.app_context():
        assert socios.membresia_para_tarjeta(socio_id, hoy)["ultimo_hasta"] == primera["membresia"]["hasta"]
        dia = date.fromisoformat(primera["membresia"]["desde"])
        assert socios.consultar_membresia(socio_id, dia)["hasta"].isoformat() == primera["membresia"]["hasta"]
        assert socios.consultar_membresia(socio_id, date.fromisoformat(segunda["membresia"]["desde"])) is None
    assert escribir(cliente, ruta, {"motivo": "Error ficticio anterior"}).status_code == 201
    with app.app_context():
        assert socios.membresia_para_tarjeta(socio_id, hoy) == original
    assert filas(app, "membresias") == anteriores
    assert len(filas(app, "anulaciones_pago")) == 2
    nueva = escribir(cliente, "/api/pagos", datos).json
    assert nueva["membresia"]["desde"] == primera["membresia"]["desde"]
    assert nueva["membresia"]["hasta"] == primera["membresia"]["hasta"]
    with app.app_context():
        demo.reiniciar()
    assert filas(app, "anulaciones_pago") == []


@pytest.mark.bd
@pytest.mark.parametrize("motivo", [None, "", "  ", "x" * 501, 1, []])
def test_motivo_anulacion_invalido(pagos, motivo):
    app, cliente, _, datos = pagos
    pago = escribir(cliente, "/api/pagos", datos).json
    assert escribir(cliente, f"/api/pagos/{pago['id']}/anular", {"motivo": motivo}).status_code == 422
    assert filas(app, "anulaciones_pago") == []


@pytest.mark.bd
def test_anular_no_cierra_visita_abierta(pagos):
    app, cliente, autor, datos = pagos
    with app.app_context():
        with transaccion() as cursor:
            cursor.execute("SELECT id FROM sedes ORDER BY id LIMIT 1")
            sede_id = desde_bytes(cursor.fetchone()["id"])
        visitas.registrar_entrada(
            {"id": str(nuevo_id()), "socio_id": datos["socio_id"], "sede_id": str(sede_id)}, autor
        )
    pago = escribir(cliente, "/api/pagos", datos).json
    antes = filas(app, "entradas"), filas(app, "salidas")
    assert escribir(cliente, f"/api/pagos/{pago['id']}/anular", {"motivo": "Error ficticio"}).status_code == 201
    assert (filas(app, "entradas"), filas(app, "salidas")) == antes


@pytest.mark.bd
def test_anular_no_cancela_reserva_con_esa_vigencia(pagos, reloj_fijo):
    app, cliente, _, datos = pagos
    hoy = fecha_local(reloj_fijo.ahora())
    with app.app_context(), transaccion() as cursor:
        cursor.execute(
            "UPDATE membresias SET desde=%s, hasta=%s WHERE socio_id=%s",
            (hoy - timedelta(days=30), hoy - timedelta(days=1), a_bytes(desde_texto(datos["socio_id"]))),
        )
    pago = escribir(cliente, "/api/pagos", datos).json
    entrenador = cliente.get("/api/clases").json["entrenadores"][0]["id"]
    clase = escribir(
        cliente,
        "/api/clases",
        {
            "nombre": "Clase ficticia",
            "dia_semana": hoy.isoweekday(),
            "hora_inicio": "18:00",
            "duracion_minutos": 60,
            "cupo": 10,
            "entrenador_id": entrenador,
        },
    ).json
    cliente.post("/api/sesion/demo/recepcion", headers={"X-Gimnasio": "1"})
    reserva = escribir(
        cliente,
        "/api/clases/reservas",
        {
            "clase_id": clase["id"],
            "fecha": hoy.isoformat(),
            "socio_id": datos["socio_id"],
        },
    )
    assert reserva.status_code == 201
    antes = filas(app, "reservas"), filas(app, "cancelaciones_reserva")
    assert escribir(cliente, f"/api/pagos/{pago['id']}/anular", {"motivo": "Error ficticio"}).status_code == 201
    assert (filas(app, "reservas"), filas(app, "cancelaciones_reserva")) == antes


@pytest.mark.bd
def test_anular_restaura_vencimiento_y_rechaza_entrada(pagos, reloj_fijo):
    app, cliente, autor, datos = pagos
    hoy = fecha_local(reloj_fijo.ahora())
    with app.app_context(), transaccion() as cursor:
        cursor.execute(
            "UPDATE membresias SET desde=%s, hasta=%s WHERE socio_id=%s",
            (hoy - timedelta(days=30), hoy - timedelta(days=1), a_bytes(desde_texto(datos["socio_id"]))),
        )
        cursor.execute("SELECT id FROM sedes ORDER BY id LIMIT 1")
        sede_id = str(desde_bytes(cursor.fetchone()["id"]))
    pago = escribir(cliente, "/api/pagos", datos).json
    with app.app_context():
        assert socios.consultar_membresia(desde_texto(datos["socio_id"]), hoy)
    assert escribir(cliente, f"/api/pagos/{pago['id']}/anular", {"motivo": "Error ficticio"}).status_code == 201
    with app.app_context():
        assert socios.consultar_membresia(desde_texto(datos["socio_id"]), hoy) is None
        with pytest.raises(ErrorDeDominio) as error:
            visitas.registrar_entrada({"id": str(nuevo_id()), "socio_id": datos["socio_id"], "sede_id": sede_id}, autor)
        assert error.value.codigo == "membresia_no_vigente"


@pytest.mark.bd
def test_lista_total_fechas_locales_y_anulacion(pagos, reloj_fijo):
    from datetime import UTC, datetime

    _, cliente, _, datos = pagos
    reloj_fijo.fijar(datetime(2026, 10, 28, 2, 59, tzinfo=UTC))
    primero = escribir(cliente, "/api/pagos", datos).json
    reloj_fijo.avanzar(timedelta(minutes=1))
    segundo = escribir(cliente, "/api/pagos", datos | {"monto": 123}).json
    lista = cliente.get("/api/pagos").json
    assert [pago["id"] for pago in lista["pagos"]] == [segundo["id"]]
    assert lista["total"] == 123
    assert cliente.get("/api/pagos?desde=2026-10-27&hasta=2026-10-27").json["pagos"][0]["id"] == primero["id"]
    assert escribir(cliente, f"/api/pagos/{segundo['id']}/anular", {"motivo": "Error ficticio"}).status_code == 201
    lista = cliente.get("/api/pagos?desde=2026-10-27&hasta=2026-10-28").json
    assert lista["total"] == 250000
    assert lista["pagos"][0]["anulacion"]["motivo"] == "Error ficticio"
    assert lista["pagos"][0]["socio"] and lista["pagos"][0]["autor"] and lista["pagos"][0]["tipo"]


@pytest.mark.parametrize("desde,hasta", [("2026-01-01", "2026-03-04"), ("2026-02-02", "2026-02-01"), ("mal", None)])
def test_intervalo_invalido(desde, hasta):
    from gimnasio.comun.reloj import ZONA_SEDE

    with pytest.raises(ErrorDeDominio) as error:
        servicio.intervalo_fechas(desde, hasta, date(2026, 2, 1), ZONA_SEDE)
    assert error.value.estado_http == 422


@pytest.mark.bd
@pytest.mark.parametrize(
    "rol,personal,propios",
    [("socio", 403, 200), ("recepcion", 200, 403), ("entrenador", 403, 403), ("administracion", 200, 403)],
)
def test_permisos_nuevas_rutas(pagos, rol, personal, propios):
    _, cliente, _, datos = pagos
    pago = escribir(cliente, "/api/pagos", datos).json
    cliente.post(f"/api/sesion/demo/{rol}", headers={"X-Gimnasio": "1"})
    assert cliente.get("/api/pagos").status_code == personal
    assert cliente.get("/api/yo/pagos").status_code == propios
    assert escribir(cliente, f"/api/pagos/{pago['id']}/anular", {"motivo": "Error ficticio"}).status_code == (
        201 if personal == 200 else 403
    )


@pytest.mark.bd
def test_pagos_propios_ignora_identificador_ajeno(pagos):
    _, cliente, _, datos = pagos
    usuario = cliente.post("/api/sesion/demo/socio", headers={"X-Gimnasio": "1"}).json["usuario"]
    cliente.post("/api/sesion/demo/administracion", headers={"X-Gimnasio": "1"})
    personas = cliente.get("/api/pagos/socios").json["socios"]
    otro = next(persona["id"] for persona in personas if persona["id"] != usuario["id"])
    propio = escribir(cliente, "/api/pagos", datos | {"socio_id": usuario["id"]}).json
    escribir(cliente, "/api/pagos", datos | {"socio_id": otro})
    cliente.post("/api/sesion/demo/socio", headers={"X-Gimnasio": "1"})
    respuesta = cliente.get(f"/api/yo/pagos?socio_id={otro}").json
    assert [pago["id"] for pago in respuesta["pagos"]] == [propio["id"]]
    assert respuesta["membresia"]["vigente"]
    assert respuesta["dias_restantes"] is not None


@pytest.mark.bd
def test_anulaciones_concurrentes_insertan_una_sola_fila(pagos):
    app, cliente, autor, datos = pagos
    pago = escribir(cliente, "/api/pagos", datos).json

    def anular(_):
        with app.app_context():
            try:
                servicio.anular_pago(pago["id"], {"motivo": "Error ficticio"}, autor)
                return 201
            except ErrorDeDominio as error:
                return error.estado_http

    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        assert sorted(ejecutor.map(anular, range(2))) == [201, 409]
    assert len(filas(app, "anulaciones_pago")) == 1


@pytest.mark.bd
def test_anula_pago_de_socio_inactivo(pagos):
    app, cliente, _, datos = pagos
    pago = escribir(cliente, "/api/pagos", datos).json
    with app.app_context(), transaccion() as cursor:
        cursor.execute("UPDATE usuarios SET activo=FALSE WHERE id=%s", (a_bytes(desde_texto(datos["socio_id"])),))
    assert escribir(cliente, f"/api/pagos/{pago['id']}/anular", {"motivo": "Error ficticio"}).status_code == 201


@pytest.mark.bd
def test_renovar_ve_anulacion_posterior_a_su_primera_lectura(pagos):
    app, cliente, autor, datos = pagos
    pago = escribir(cliente, "/api/pagos", datos).json

    def anular():
        with app.app_context():
            servicio.anular_pago(pago["id"], {"motivo": "Error ficticio"}, autor)

    with app.app_context(), transaccion() as cursor:
        # Fija una lectura anterior a la anulación bajo REPEATABLE READ.
        cursor.execute("SELECT COUNT(*) AS cantidad FROM anulaciones_pago")
        assert cursor.fetchone()["cantidad"] == 0
        with ThreadPoolExecutor(max_workers=1) as ejecutor:
            ejecutor.submit(anular).result(timeout=10)
        nueva = servicio.registrar_pago(datos, autor)
    assert nueva["membresia"]["desde"] == pago["membresia"]["desde"]


@pytest.mark.bd
def test_lista_no_hace_consulta_por_pago(pagos, monkeypatch):
    from contextlib import contextmanager

    app, cliente, _, datos = pagos
    for _ in range(3):
        assert escribir(cliente, "/api/pagos", datos).status_code == 201
    consultas = []

    @contextmanager
    def contar():
        with transaccion() as cursor:

            class Contador:
                def execute(self, *argumentos):
                    consultas.append(argumentos[0])
                    return cursor.execute(*argumentos)

                def __getattr__(self, nombre):
                    return getattr(cursor, nombre)

            yield Contador()

    monkeypatch.setattr(servicio, "transaccion", contar)
    with app.app_context():
        assert len(servicio.listar_pagos()["pagos"]) == 3
    assert len(consultas) == 2


def test_intervalo_admite_exactamente_62_dias():
    from gimnasio.comun.reloj import ZONA_SEDE

    desde, hasta = servicio.intervalo_fechas("2026-01-01", "2026-03-03", date(2026, 1, 1), ZONA_SEDE)
    assert hasta - desde == timedelta(days=62)
