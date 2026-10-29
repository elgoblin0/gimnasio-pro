"""Entrada atómica por recepción sobre visitas e idempotencia reales."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import a_bytes, nuevo_id
from gimnasio.permisos.servicio import crear_usuario
from gimnasio.visitas import repositorio

pytestmark = pytest.mark.bd


@pytest.fixture
def visitas_api(app_con_bd, reloj_fijo):
    app = app_con_bd
    datos = SimpleNamespace(app=app, reloj=reloj_fijo, usuarios={}, socios=[])
    with app.app_context(), transaccion() as cursor:
        datos.sede = nuevo_id(reloj_fijo)
        cursor.execute(
            "INSERT INTO sedes (id,nombre,aforo_maximo,actualizada_en) VALUES (%s,'Sede ficticia',1,%s)",
            (a_bytes(datos.sede), reloj_fijo.ahora()),
        )
        for indice, rol in enumerate(("recepcion", "entrenador", "administracion", "socio", "socio", "socio")):
            usuario = crear_usuario(
                cursor, {"nombre": "Persona", "apellido": "Ficticia", "cedula": str(9900500 + indice)}, rol
            )
            datos.usuarios.setdefault(rol, usuario)
            if rol == "socio":
                datos.socios.append(usuario)
                cursor.execute(
                    "INSERT INTO membresias (id,socio_id,desde,hasta,actualizada_en) "
                    "VALUES (%s,%s,'2026-10-27','2026-10-27',%s)",
                    (a_bytes(nuevo_id(reloj_fijo)), a_bytes(usuario), reloj_fijo.ahora()),
                )

    def cliente(rol="recepcion"):
        cliente = app.test_client()
        if rol:
            with cliente.session_transaction() as sesion:
                sesion["usuario_id"] = str(datos.usuarios[rol])
        return cliente

    datos.cliente = cliente
    datos.cuerpo = lambda socio=None: {
        "id": str(nuevo_id(reloj_fijo)),
        "socio_id": str(socio or datos.socios[0]),
        "sede_id": str(datos.sede),
    }
    return datos


def enviar(cliente, cuerpo, clave=None):
    return cliente.post(
        "/api/entradas", json=cuerpo, headers={"X-Gimnasio": "1", "Idempotency-Key": clave or str(uuid4())}
    )


def contar(datos, tabla="entradas"):
    assert tabla in {"entradas", "salidas", "series_realizadas", "solicitudes_idempotentes"}
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute(f"SELECT COUNT(*) AS cantidad FROM {tabla}")
        return cursor.fetchone()["cantidad"]


def test_entrada_aforo_lleno_y_reingreso_sin_cupo(visitas_api):
    datos = visitas_api
    cuerpo = datos.cuerpo()
    assert enviar(datos.cliente(), cuerpo).status_code == 201
    assert enviar(datos.cliente(), datos.cuerpo()).status_code == 409
    assert enviar(datos.cliente(), datos.cuerpo(datos.socios[1])).status_code == 409
    assert contar(datos) == 1
    assert contar(datos, "series_realizadas") == 0
    with datos.app.app_context(), transaccion() as cursor:
        from gimnasio.comun.ids import desde_texto

        repositorio.insertar_salida(
            cursor, nuevo_id(datos.reloj), desde_texto(cuerpo["id"]), datos.usuarios["recepcion"], datos.reloj.ahora()
        )
    assert enviar(datos.cliente(), datos.cuerpo()).status_code == 201
    assert contar(datos) == 2
    with datos.app.app_context(), transaccion() as cursor:
        assert repositorio.contar_ocupacion_registrada(cursor, datos.sede) == 1


@pytest.mark.parametrize(
    "rol,estado", [(None, 401), ("socio", 403), ("entrenador", 403), ("administracion", 403), ("recepcion", 201)]
)
def test_solo_recepcion_registra_entrada(visitas_api, rol, estado):
    assert enviar(visitas_api.cliente(rol), visitas_api.cuerpo()).status_code == estado


def test_idempotencia_sobre_entrada_real(visitas_api):
    datos = visitas_api
    cliente, cuerpo, clave = datos.cliente(), datos.cuerpo(), str(uuid4())
    assert cliente.post("/api/entradas", json=cuerpo, headers={"X-Gimnasio": "1"}).status_code == 428
    assert cliente.post("/api/entradas", json=cuerpo, headers={"Idempotency-Key": clave}).status_code == 403
    primera = enviar(cliente, cuerpo, clave)
    repetida = enviar(cliente, cuerpo, clave)
    assert primera.status_code == repetida.status_code == 201
    assert primera.data == repetida.data
    assert enviar(cliente, datos.cuerpo(), clave).status_code == 422
    assert enviar(cliente, cuerpo).status_code == 201
    assert enviar(cliente, cuerpo | {"socio_id": str(datos.socios[1])}).status_code == 403
    assert contar(datos) == 1


def test_referencias_cuerpo_y_membresia_invalidos(visitas_api):
    datos = visitas_api
    assert enviar(datos.cliente(), datos.cuerpo() | {"sede_id": str(nuevo_id(datos.reloj))}).status_code == 404
    assert enviar(datos.cliente(), datos.cuerpo() | {"socio_id": str(nuevo_id(datos.reloj))}).status_code == 404
    assert enviar(datos.cliente(), datos.cuerpo() | {"id": "inválido"}).status_code == 422
    assert enviar(datos.cliente(), datos.cuerpo() | {"autor_id": str(datos.socios[0])}).status_code == 422
    from datetime import timedelta

    datos.reloj.avanzar(timedelta(days=1))
    assert enviar(datos.cliente(), datos.cuerpo()).status_code == 422
    assert contar(datos) == 0


def test_fallo_revierte_entrada_y_respuesta(visitas_api, monkeypatch):
    datos = visitas_api
    original = repositorio.insertar_entrada

    def fallar(*argumentos, **nombrados):
        original(*argumentos, **nombrados)
        raise RuntimeError("fallo después del hecho")

    monkeypatch.setattr(repositorio, "insertar_entrada", fallar)
    cuerpo, clave = datos.cuerpo(), str(uuid4())
    with pytest.raises(RuntimeError):
        enviar(datos.cliente(), cuerpo, clave)
    assert contar(datos) == contar(datos, "solicitudes_idempotentes") == 0
    monkeypatch.setattr(repositorio, "insertar_entrada", original)
    assert enviar(datos.cliente(), cuerpo, clave).status_code == 201


@pytest.mark.parametrize("mismo_socio", [False, True])
def test_dos_conexiones_respetan_aforo_y_una_visita_por_socio(visitas_api, monkeypatch, mismo_socio):
    datos = visitas_api
    if mismo_socio:
        with datos.app.app_context(), transaccion() as cursor:
            cursor.execute("UPDATE sedes SET aforo_maximo = 2 WHERE id = %s", (a_bytes(datos.sede),))
    tomada, segunda, continuar = Event(), Event(), Event()
    original = repositorio.bloquear_sede

    def bloquear(cursor, sede_id):
        if tomada.is_set():
            segunda.set()
            return original(cursor, sede_id)
        fila = original(cursor, sede_id)
        tomada.set()
        assert continuar.wait(15)
        return fila

    monkeypatch.setattr(repositorio, "bloquear_sede", bloquear)
    with ThreadPoolExecutor(max_workers=2) as hilos:
        primera = hilos.submit(enviar, datos.cliente(), datos.cuerpo())
        try:
            assert tomada.wait(10)
            otra = hilos.submit(enviar, datos.cliente(), datos.cuerpo(datos.socios[0 if mismo_socio else 1]))
            assert segunda.wait(10)
        finally:
            continuar.set()
        assert sorted((primera.result(timeout=15).status_code, otra.result(timeout=15).status_code)) == [201, 409]
    assert contar(datos) == 1


def test_misma_clave_simultanea_no_duplica_entrada(visitas_api, monkeypatch):
    datos = visitas_api
    tomada, continuar = Event(), Event()
    original = repositorio.bloquear_sede

    def bloquear(cursor, sede_id):
        fila = original(cursor, sede_id)
        tomada.set()
        assert continuar.wait(15)
        return fila

    monkeypatch.setattr(repositorio, "bloquear_sede", bloquear)
    cuerpo, clave = datos.cuerpo(), str(uuid4())
    with ThreadPoolExecutor(max_workers=1) as hilos:
        primera = hilos.submit(enviar, datos.cliente(), cuerpo, clave)
        try:
            assert tomada.wait(10)
            assert enviar(datos.cliente(), cuerpo, clave).status_code == 409
        finally:
            continuar.set()
        assert primera.result(timeout=15).status_code == 201
    assert enviar(datos.cliente(), cuerpo, clave).status_code == 201
    assert contar(datos) == 1


def test_personal_con_sesion_no_ocupa_aforo(visitas_api):
    datos = visitas_api
    for rol in ("recepcion", "entrenador", "administracion"):
        assert datos.cliente(rol).get("/api/sesion").status_code == 200
    with datos.app.app_context(), transaccion() as cursor:
        assert repositorio.contar_ocupacion_registrada(cursor, datos.sede) == 0
    assert enviar(datos.cliente(), datos.cuerpo()).status_code == 201


def enviar_salida(cliente, cuerpo, clave=None):
    return cliente.post(
        "/api/salidas", json=cuerpo, headers={"X-Gimnasio": "1", "Idempotency-Key": clave or str(uuid4())}
    )


def abrir(datos):
    cuerpo = datos.cuerpo()
    assert enviar(datos.cliente(), cuerpo).status_code == 201
    return cuerpo["id"]


def test_salida_cierra_visita_y_lectura_calcula_duracion_sin_escribir(visitas_api):
    from datetime import timedelta

    datos = visitas_api
    cliente = datos.cliente()
    entrada_id = abrir(datos)
    datos.reloj.avanzar(timedelta(minutes=45))
    visitas = cliente.get("/api/visitas?abiertas=1").json["visitas"]
    assert len(visitas) == 1
    assert visitas[0]["id"] == entrada_id
    assert visitas[0]["duracion"] == 2700
    assert visitas[0]["entrada"].endswith("+00:00")
    assert visitas[0]["entrada_local"].endswith("-03:00")
    assert set(visitas[0]) == {
        "id",
        "socio_id",
        "nombre",
        "cedula",
        "entrada",
        "entrada_local",
        "duracion",
        "minutos",
        "permanencia_habitual",
        "permanencia_habitual_sede",
        "por_conciliar",
    }
    assert visitas[0]["minutos"] == 45
    assert visitas[0]["permanencia_habitual"] == {
        "suficiente": False,
        "observaciones": 0,
        "mediana": None,
        "p25": None,
        "p75": None,
    }
    assert visitas[0]["por_conciliar"] is False
    assert cliente.get("/api/visitas?abiertas=1").json["visitas"] == visitas
    assert cliente.get("/api/ocupacion").json == {
        "sede_id": str(datos.sede),
        "ocupacion_registrada": 1,
        "aforo_maximo": 1,
        "por_conciliar": 0,
    }
    respuesta = enviar_salida(cliente, {"id": str(nuevo_id(datos.reloj)), "entrada_id": entrada_id})
    assert respuesta.status_code == 201
    assert respuesta.json["salida"]["entrada_id"] == entrada_id
    assert cliente.get("/api/ocupacion").json["ocupacion_registrada"] == 0
    assert cliente.get("/api/visitas?abiertas=1").json == {"visitas": []}
    assert contar(datos, "series_realizadas") == 0
    assert contar(datos, "salidas") == 1


def test_salida_idempotente_y_cuerpo_invalido(visitas_api):
    datos = visitas_api
    cuerpo = {"id": str(nuevo_id(datos.reloj)), "entrada_id": abrir(datos)}
    cliente, clave = datos.cliente(), str(uuid4())
    assert cliente.post("/api/salidas", json=cuerpo, headers={"X-Gimnasio": "1"}).status_code == 428
    primera = enviar_salida(cliente, cuerpo, clave)
    assert primera.status_code == 201
    assert enviar_salida(cliente, cuerpo, clave).data == primera.data
    assert enviar_salida(cliente, cuerpo).json == primera.json
    assert enviar_salida(cliente, cuerpo | {"id": str(nuevo_id(datos.reloj))}, clave).status_code == 422
    assert enviar_salida(cliente, cuerpo | {"id": str(nuevo_id(datos.reloj))}).status_code == 409
    assert enviar_salida(cliente, cuerpo | {"entrada_id": str(nuevo_id(datos.reloj))}).status_code == 404
    assert enviar_salida(cliente, {"id": "inválido", "entrada_id": cuerpo["entrada_id"]}).status_code == 422
    assert contar(datos, "salidas") == 1


@pytest.mark.parametrize("rol", ["socio", "entrenador", "administracion"])
def test_lecturas_y_salida_solo_para_recepcion(visitas_api, rol):
    datos = visitas_api
    cliente = datos.cliente(rol)
    for ruta in ("/api/visitas?abiertas=1", "/api/ocupacion", "/api/visitas/socios"):
        assert cliente.get(ruta).status_code == 403
    assert (
        enviar_salida(cliente, {"id": str(nuevo_id(datos.reloj)), "entrada_id": str(nuevo_id(datos.reloj))}).status_code
        == 403
    )


def test_listado_minimo_excluye_socios_inactivos(visitas_api):
    datos = visitas_api
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("UPDATE usuarios SET activo=FALSE WHERE id=%s", (a_bytes(datos.socios[1]),))
    filas = datos.cliente().get("/api/visitas/socios").json["socios"]
    assert {fila["id"] for fila in filas} == {str(datos.socios[0]), str(datos.socios[2])}
    assert all(set(fila) == {"id", "nombre", "cedula"} for fila in filas)


def test_dos_claves_de_salida_no_duplican_y_misma_clave_simultanea(visitas_api, monkeypatch):
    datos = visitas_api
    entrada_id = abrir(datos)
    tomada, continuar = Event(), Event()
    original = repositorio.bloquear_sede

    def bloquear(cursor, sede_id):
        fila = original(cursor, sede_id)
        if not tomada.is_set():
            tomada.set()
            assert continuar.wait(15)
        return fila

    monkeypatch.setattr(repositorio, "bloquear_sede", bloquear)
    cuerpo, clave = {"id": str(nuevo_id(datos.reloj)), "entrada_id": entrada_id}, str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as hilos:
        primera = hilos.submit(enviar_salida, datos.cliente(), cuerpo, clave)
        try:
            assert tomada.wait(10)
            assert enviar_salida(datos.cliente(), cuerpo, clave).status_code == 409
            otra = hilos.submit(enviar_salida, datos.cliente(), cuerpo | {"id": str(nuevo_id(datos.reloj))})
        finally:
            continuar.set()
        assert primera.result(timeout=15).status_code == 201
        assert otra.result(timeout=15).status_code == 409
    assert enviar_salida(datos.cliente(), cuerpo, clave).status_code == 201
    assert contar(datos, "salidas") == 1


def test_fallo_revierte_salida_y_su_clave(visitas_api, monkeypatch):
    datos = visitas_api
    cuerpo, clave = {"id": str(nuevo_id(datos.reloj)), "entrada_id": abrir(datos)}, str(uuid4())
    original = repositorio.insertar_salida

    def fallar(*argumentos, **nombrados):
        original(*argumentos, **nombrados)
        raise RuntimeError("fallo después de salida")

    monkeypatch.setattr(repositorio, "insertar_salida", fallar)
    with pytest.raises(RuntimeError):
        enviar_salida(datos.cliente(), cuerpo, clave)
    assert contar(datos, "salidas") == 0
    assert contar(datos, "solicitudes_idempotentes") == 1  # Solo la entrada confirmada.
    monkeypatch.setattr(repositorio, "insertar_salida", original)
    assert enviar_salida(datos.cliente(), cuerpo, clave).status_code == 201


def test_visita_de_cinco_horas_sin_historial_por_conciliar_primero(visitas_api):
    from datetime import timedelta

    datos = visitas_api
    ahora = datos.reloj.ahora()
    prolongada, reciente = nuevo_id(datos.reloj), nuevo_id(datos.reloj)
    with datos.app.app_context(), transaccion() as cursor:
        for entrada, socio, minutos in ((reciente, datos.socios[0], 30), (prolongada, datos.socios[1], 300)):
            repositorio.insertar_entrada(
                cursor, entrada, socio, datos.sede, datos.usuarios["recepcion"], ahora - timedelta(minutes=minutos)
            )
    visitas = datos.cliente().get("/api/visitas?abiertas=1").json["visitas"]
    assert [visita["id"] for visita in visitas] == [str(prolongada), str(reciente)]
    assert [visita["por_conciliar"] for visita in visitas] == [True, False]
    assert visitas[0]["minutos"] == 300
    assert visitas[0]["permanencia_habitual"]["observaciones"] == 0
    assert datos.cliente().get("/api/ocupacion").json["por_conciliar"] == 1
    assert contar(datos, "salidas") == 0


@pytest.mark.parametrize("caso", ["confirmada", "corregida", "salida_anulada", "entrada_anulada", "antigua"])
def test_duraciones_confiables_respetan_estado_vigente_y_ocho_semanas(visitas_api, caso):
    from datetime import timedelta

    datos = visitas_api
    ahora = datos.reloj.ahora()
    entrada, salida = nuevo_id(datos.reloj), nuevo_id(datos.reloj)
    momento = ahora - timedelta(weeks=9 if caso == "antigua" else 1)
    autor = datos.usuarios["recepcion"]
    with datos.app.app_context(), transaccion() as cursor:
        repositorio.insertar_entrada(cursor, entrada, datos.socios[0], datos.sede, autor, momento)
        repositorio.insertar_salida(cursor, salida, entrada, autor, momento + timedelta(minutes=60))
        if caso in ("corregida", "salida_anulada"):
            repositorio.insertar_salida(
                cursor,
                nuevo_id(datos.reloj),
                entrada,
                autor,
                momento + timedelta(minutes=90),
                corrige_a=salida,
                motivo="Corrección ficticia",
                anulada=caso == "salida_anulada",
            )
        if caso == "entrada_anulada":
            repositorio.insertar_entrada(
                cursor,
                nuevo_id(datos.reloj),
                datos.socios[0],
                datos.sede,
                autor,
                momento + timedelta(minutes=1),
                corrige_a=entrada,
                motivo="Anulación ficticia",
                anulada=True,
            )
        filas = repositorio.listar_duraciones_confiables(
            cursor, datos.sede, ahora - timedelta(weeks=8), ahora, datos.socios[0]
        )
        assert [fila["minutos"] for fila in filas] == (
            [90] if caso == "corregida" else [60] if caso == "confirmada" else []
        )
        assert (
            repositorio.listar_duraciones_confiables(
                cursor, datos.sede, ahora - timedelta(weeks=8), ahora, datos.socios[1]
            )
            == []
        )


def test_permanencia_del_socio_y_umbral_de_la_sede(visitas_api):
    from datetime import timedelta

    datos = visitas_api
    ahora = datos.reloj.ahora()
    autor = datos.usuarios["recepcion"]
    with datos.app.app_context(), transaccion() as cursor:
        for socio, minutos in ((datos.socios[0], 60), (datos.socios[1], 300)):
            for dia in range(1, 6):
                entrada = nuevo_id(datos.reloj)
                momento = ahora - timedelta(days=dia)
                repositorio.insertar_entrada(cursor, entrada, socio, datos.sede, autor, momento)
                repositorio.insertar_salida(
                    cursor, nuevo_id(datos.reloj), entrada, autor, momento + timedelta(minutes=minutos)
                )
        repositorio.insertar_entrada(
            cursor, nuevo_id(datos.reloj), datos.socios[0], datos.sede, autor, ahora - timedelta(minutes=300)
        )
    visita = datos.cliente().get("/api/visitas?abiertas=1").json["visitas"][0]
    assert visita["permanencia_habitual"] == {
        "suficiente": True,
        "observaciones": 5,
        "mediana": 60,
        "p25": 60,
        "p75": 60,
    }
    # La sede tiene mediana de 180: umbral de 360, aunque el socio suele quedarse 60.
    assert visita["por_conciliar"] is False
    assert datos.cliente().get("/api/ocupacion").json["por_conciliar"] == 0


def conciliar(datos, entrada_id, cuerpo, clave=None, rol="recepcion"):
    return datos.cliente(rol).post(
        f"/api/visitas/{entrada_id}/conciliacion",
        json=cuerpo,
        headers={"X-Gimnasio": "1", "Idempotency-Key": clave or str(uuid4())},
    )


def preparar_conciliacion(datos):
    from datetime import timedelta

    entrada = datos.cuerpo()
    assert enviar(datos.cliente(), entrada).status_code == 201
    datos.reloj.avanzar(timedelta(hours=4))
    return entrada["id"], {
        "id": str(nuevo_id(datos.reloj)),
        "salida_en": "2026-10-27T10:00:00-03:00",
        "motivo": "El socio informó su hora real de salida",
    }


def test_conciliacion_idempotente_baja_ocupacion_y_es_confiable(visitas_api):
    from datetime import timedelta

    datos = visitas_api
    entrada_id, cuerpo = preparar_conciliacion(datos)
    clave = str(uuid4())
    assert datos.cliente().get("/api/ocupacion").json["ocupacion_registrada"] == 1
    primera = conciliar(datos, entrada_id, cuerpo, clave)
    assert primera.status_code == 201
    assert conciliar(datos, entrada_id, cuerpo, clave).data == primera.data
    assert conciliar(datos, entrada_id, cuerpo).data == primera.data
    assert contar(datos, "salidas") == 1
    assert datos.cliente().get("/api/ocupacion").json["ocupacion_registrada"] == 0
    with datos.app.app_context(), transaccion() as cursor:
        cursor.execute("SELECT motivo, corrige_a FROM salidas")
        assert cursor.fetchone() == {"motivo": cuerpo["motivo"], "corrige_a": None}
        duraciones = repositorio.listar_duraciones_confiables(
            cursor, datos.sede, datos.reloj.ahora() - timedelta(days=1), datos.reloj.ahora()
        )
        assert [fila["minutos"] for fila in duraciones] == [60]
    respuesta = conciliar(datos, entrada_id, cuerpo | {"id": str(nuevo_id(datos.reloj))})
    assert respuesta.status_code == 409
    assert respuesta.json["error"]["codigo"] == "visita_cerrada"


@pytest.mark.parametrize("motivo", [None, "", "   ", "x" * 501, 12])
def test_conciliacion_rechaza_motivo_invalido(visitas_api, motivo):
    entrada_id, cuerpo = preparar_conciliacion(visitas_api)
    assert conciliar(visitas_api, entrada_id, cuerpo | {"motivo": motivo}).status_code == 422
    del cuerpo["motivo"]
    assert conciliar(visitas_api, entrada_id, cuerpo).status_code == 422
    assert contar(visitas_api, "salidas") == 0


@pytest.mark.parametrize(
    "hora",
    [
        "2026-10-27T17:00:00Z",
        "2026-10-27T11:00:00Z",
        "2026-10-27T12:00:00Z",
        "2026-10-27T13:00:00",
        "inválida",
        None,
    ],
)
def test_conciliacion_rechaza_hora_invalida(visitas_api, hora):
    entrada_id, cuerpo = preparar_conciliacion(visitas_api)
    respuesta = conciliar(visitas_api, entrada_id, cuerpo | {"salida_en": hora})
    assert respuesta.status_code == 422
    assert respuesta.json["error"]["codigo"] == "salida_invalida"
    assert contar(visitas_api, "salidas") == 0


@pytest.mark.parametrize("rol", ["socio", "entrenador"])
def test_conciliacion_prohibe_otros_roles(visitas_api, rol):
    entrada_id, cuerpo = preparar_conciliacion(visitas_api)
    assert conciliar(visitas_api, entrada_id, cuerpo, rol=rol).status_code == 403


def test_conciliacion_exige_clave(visitas_api):
    entrada_id, cuerpo = preparar_conciliacion(visitas_api)
    respuesta = visitas_api.cliente().post(
        f"/api/visitas/{entrada_id}/conciliacion", json=cuerpo, headers={"X-Gimnasio": "1"}
    )
    assert respuesta.status_code == 428
