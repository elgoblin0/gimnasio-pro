"""Límites de la demo sin MySQL, con el reloj inyectado."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO

import pytest
from flask import request

from gimnasio import crear_app


def crear_demo(reloj, **config):
    app = crear_app(
        {"ENTORNO": "prueba", "SECRET_KEY": "solo-pruebas", "MODO_DEMO": True, "EN_RENDER": False} | config,
        reloj=reloj,
    )

    @app.post("/api/prueba/cuerpo")
    def cuerpo():
        return {"bytes": len(request.get_data())}

    return app


def test_la_demo_admite_60_solicitudes_por_minuto_y_por_ip(reloj_fijo):
    cliente = crear_demo(reloj_fijo).test_client()
    for _ in range(60):
        assert cliente.get("/api/estado").status_code == 200
    respuesta = cliente.get("/api/estado")
    assert respuesta.status_code == 429
    assert respuesta.get_json()["error"]["codigo"] == "demasiadas_solicitudes"
    assert respuesta.headers["Retry-After"] == "60"
    assert cliente.get("/api/estado", environ_overrides={"REMOTE_ADDR": "192.0.2.2"}).status_code == 200

    reloj_fijo.avanzar(timedelta(seconds=59))
    assert cliente.get("/api/estado").status_code == 429
    reloj_fijo.avanzar(timedelta(seconds=1))
    assert cliente.get("/api/estado").status_code == 200


def test_la_ventana_es_movil_y_los_rechazos_no_extienden_la_espera(reloj_fijo):
    cliente = crear_demo(reloj_fijo).test_client()
    for _ in range(30):
        cliente.get("/api/estado")
    reloj_fijo.avanzar(timedelta(seconds=30))
    for _ in range(30):
        cliente.get("/api/estado")
    reloj_fijo.avanzar(timedelta(seconds=29))
    assert cliente.get("/api/estado").headers["Retry-After"] == "1"
    reloj_fijo.avanzar(timedelta(seconds=1))
    for _ in range(30):
        assert cliente.get("/api/estado").status_code == 200
    assert cliente.get("/api/estado").status_code == 429


def test_los_archivos_y_las_rutas_inexistentes_comparten_el_limite(reloj_fijo):
    cliente = crear_demo(reloj_fijo).test_client()
    for _ in range(30):
        assert cliente.get("/").status_code == 200
        assert cliente.get("/no-existe").status_code == 404
    assert cliente.get("/api/estado").status_code == 429


def test_las_solicitudes_simultaneas_no_esquivan_el_limite(reloj_fijo):
    app = crear_demo(reloj_fijo)

    def solicitar(_numero):
        return app.test_client().get("/api/estado").status_code

    with ThreadPoolExecutor(max_workers=8) as hilos:
        estados = list(hilos.map(solicitar, range(80)))
    assert estados.count(200) == 60
    assert estados.count(429) == 20


@pytest.mark.parametrize("ruta", ["/api/prueba/cuerpo", "/api/estado", "/"])
def test_rechaza_mas_de_un_mb_incluso_si_la_ruta_no_lee_el_cuerpo(reloj_fijo, ruta):
    respuesta = (
        crear_demo(reloj_fijo)
        .test_client()
        .open(
            ruta,
            method="POST" if ruta == "/api/prueba/cuerpo" else "GET",
            data=b"x" * 1_000_001,
            headers={"X-Gimnasio": "1"},
        )
    )
    assert respuesta.status_code == 413


def test_admite_un_mb_y_conserva_el_cuerpo_para_la_ruta(reloj_fijo):
    respuesta = (
        crear_demo(reloj_fijo)
        .test_client()
        .post("/api/prueba/cuerpo", data=b"x" * 1_000_000, headers={"X-Gimnasio": "1"})
    )
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"bytes": 1_000_000}


@pytest.mark.parametrize("cantidad, estado", [(1_000_000, 200), (1_000_001, 413)])
def test_controla_el_tamano_sin_content_length(reloj_fijo, cantidad, estado):
    respuesta = (
        crear_demo(reloj_fijo)
        .test_client()
        .open(
            "/api/prueba/cuerpo",
            method="POST",
            headers={"X-Gimnasio": "1"},
            environ_overrides={
                "CONTENT_LENGTH": "",
                "wsgi.input_terminated": True,
                "wsgi.input": BytesIO(b"x" * cantidad),
            },
        )
    )
    assert respuesta.status_code == estado
    if estado == 200:
        assert respuesta.get_json() == {"bytes": cantidad}


def test_fuera_de_demo_no_aplica_ninguno_de_los_limites(reloj_fijo):
    cliente = crear_demo(reloj_fijo, MODO_DEMO=False).test_client()
    for _ in range(61):
        assert cliente.get("/api/estado").status_code == 200
    respuesta = cliente.post("/api/prueba/cuerpo", data=b"x" * 1_000_001, headers={"X-Gimnasio": "1"})
    assert respuesta.status_code == 200


def test_en_render_separa_las_ip_de_cloudflare_e_ignora_x_forwarded_for(reloj_fijo):
    cliente = crear_demo(reloj_fijo, EN_RENDER=True).test_client()
    for numero in range(60):
        assert (
            cliente.get(
                "/api/estado",
                headers={
                    "CF-Connecting-IP": "192.0.2.1",
                    "X-Forwarded-For": f"198.51.100.{numero}",
                },
            ).status_code
            == 200
        )
    assert cliente.get("/api/estado", headers={"CF-Connecting-IP": "192.0.2.1"}).status_code == 429
    assert cliente.get("/api/estado", headers={"CF-Connecting-IP": "192.0.2.2"}).status_code == 200


def test_fuera_de_render_no_confia_en_encabezados_de_ip(reloj_fijo):
    cliente = crear_demo(reloj_fijo).test_client()
    for numero in range(60):
        assert (
            cliente.get(
                "/api/estado",
                headers={
                    "CF-Connecting-IP": f"192.0.2.{numero}",
                    "X-Forwarded-For": f"198.51.100.{numero}",
                },
            ).status_code
            == 200
        )
    assert cliente.get("/api/estado").status_code == 429


def test_render_normaliza_ipv6_y_si_no_hay_ip_valida_usa_la_conexion(reloj_fijo):
    cliente = crear_demo(reloj_fijo, EN_RENDER=True).test_client()
    for _ in range(60):
        assert cliente.get("/api/estado", headers={"CF-Connecting-IP": "2001:db8::1"}).status_code == 200
    assert cliente.get("/api/estado", headers={"CF-Connecting-IP": "2001:0db8:0:0:0:0:0:1"}).status_code == 429
    for _ in range(60):
        assert cliente.get("/api/estado", headers={"CF-Connecting-IP": "invalida"}).status_code == 200
    assert cliente.get("/api/estado").status_code == 429


def test_render_se_detecta_desde_el_entorno(monkeypatch, reloj_fijo):
    monkeypatch.setenv("RENDER", "true")
    assert crear_app({"ENTORNO": "prueba"}, reloj_fijo).config["EN_RENDER"] is True


def test_las_ip_vencidas_se_descartan_y_las_apps_no_comparten_contadores(reloj_fijo):
    app = crear_demo(reloj_fijo)
    cliente = app.test_client()
    for numero in range(20):
        cliente.get("/api/estado", environ_overrides={"REMOTE_ADDR": f"192.0.2.{numero}"})
    reloj_fijo.avanzar(timedelta(minutes=1))
    cliente.get("/api/estado")
    assert len(app.extensions["limite_demo"].solicitudes) == 1
    for _ in range(59):
        cliente.get("/api/estado")
    assert cliente.get("/api/estado").status_code == 429
    assert crear_demo(reloj_fijo).test_client().get("/api/estado").status_code == 200
