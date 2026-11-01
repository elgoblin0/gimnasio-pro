"""Sondeo HTTP y cierre de lectura sin depender de la disponibilidad de MySQL."""

from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from flask import g

from gimnasio import crear_app
from gimnasio.comun.ids import nuevo_id
from gimnasio.entrenador import servicio


@pytest.fixture
def sondeo(monkeypatch, reloj_fijo):
    app = crear_app({"ENTORNO": "prueba", "MODO_DEMO": False})
    socio_id, entrenador_id, aviso_id = str(nuevo_id(reloj_fijo)), str(nuevo_id(reloj_fijo)), str(nuevo_id(reloj_fijo))
    estado = {"abierta": False, "avisos": [], "rol": "entrenador"}

    @app.before_request
    def autenticar():
        g.usuario = {"id": entrenador_id, "rol": estado["rol"]}

    @contextmanager
    def lectura():
        estado["abierta"] = True
        try:
            yield object()
        finally:
            estado["abierta"] = False

    monkeypatch.setattr(servicio, "transaccion", lectura)
    monkeypatch.setattr(servicio, "listar_equipos", lambda **opciones: [])
    monkeypatch.setattr(servicio, "socios_asignados", lambda *args: [{"id": socio_id}])
    monkeypatch.setattr(servicio, "avisos_para_entrenador_por_socio", lambda cursor, ids: {ids[0]: estado["avisos"]})
    monkeypatch.setattr(servicio.repositorio, "listar_revisiones", lambda *args: [])
    monkeypatch.setattr(servicio, "revocaciones_de_salud", lambda ids, cursor: {})
    monkeypatch.setattr(servicio, "condiciones_pendientes", lambda ids, cursor: {})
    monkeypatch.setattr(servicio, "socios_con_programa", lambda cursor, ids: set())
    monkeypatch.setattr(
        servicio.repositorio,
        "fechas_asignacion_vigente",
        lambda cursor, ids, entrenador: {ids[0]: datetime(2026, 10, 30, tzinfo=UTC)},
    )
    return app.test_client(), estado, aviso_id


def test_sondeo_cierra_lectura_en_200_y_304_y_cambia_tras_aviso(sondeo):
    cliente, estado, aviso_id = sondeo
    primera = cliente.get("/api/entrenador/bandeja")
    assert primera.status_code == 200 and not estado["abierta"]
    assert "private" in primera.headers["Cache-Control"]
    assert "no-cache" in primera.headers["Cache-Control"]
    segunda = cliente.get("/api/entrenador/bandeja", headers={"If-None-Match": primera.headers["ETag"]})
    assert segunda.status_code == 304 and segunda.data == b"" and not estado["abierta"]
    estado["avisos"].append({"id": aviso_id, "freno": "dolor_reportado", "creado_en": "2026-10-30T00:00:00+00:00"})
    nueva = cliente.get("/api/entrenador/bandeja", headers={"If-None-Match": primera.headers["ETag"]})
    assert nueva.status_code == 200 and not estado["abierta"]
    assert nueva.headers["ETag"] != primera.headers["ETag"]
    motivos = nueva.json["grupos"][0]["socios"][0]["motivos"]
    assert [m["tipo"] for m in motivos] == ["aviso_seguridad", "sin_programa"]


@pytest.mark.parametrize(
    ("freno", "tipos"),
    [
        ("dolor_reportado", ["aviso_seguridad", "sin_programa"]),
        ("restriccion_salud", ["aviso_seguridad", "sin_programa"]),
        ("chequeo_desfavorable", ["aviso_progresion", "sin_programa"]),
        ("tope_semanal", ["aviso_progresion", "sin_programa"]),
        ("tope_suba_semanal", ["sin_programa"]),
    ],
)
def test_bandeja_solo_clasifica_frenos_del_motor(sondeo, freno, tipos):
    cliente, estado, aviso_id = sondeo
    estado["avisos"] = [{"id": aviso_id, "freno": freno, "creado_en": "2026-10-30T00:00:00+00:00"}]
    respuesta = cliente.get("/api/entrenador/bandeja")
    assert respuesta.status_code == 200
    socios = [socio for grupo in respuesta.json["grupos"] for socio in grupo["socios"]]
    assert [motivo["tipo"] for motivo in socios[0]["motivos"]] == tipos


@pytest.mark.parametrize("rol", ["socio", "recepcion", "administracion"])
def test_permiso_se_aplica_antes_de_leer(sondeo, rol):
    cliente, estado, _ = sondeo
    estado["rol"] = rol
    assert cliente.get("/api/entrenador/bandeja").status_code == 403
    assert not estado["abierta"]


def test_error_tambien_cierra_lectura(sondeo, monkeypatch):
    cliente, estado, _ = sondeo

    def fallar(*argumentos, **opciones):
        raise RuntimeError("Error de lectura ficticio")

    monkeypatch.setattr(servicio, "socios_con_programa", fallar)
    with pytest.raises(RuntimeError, match="Error de lectura ficticio"):
        cliente.get("/api/entrenador/bandeja")
    assert not estado["abierta"]


@pytest.mark.parametrize("pendiente", [0, 1])
@pytest.mark.parametrize("equipo_original", ["Original", "Alternativo"])
def test_motivo_solo_por_equipo_necesario_y_trabajo_pendiente(sondeo, monkeypatch, pendiente, equipo_original):
    cliente, _, ejercicio_id = sondeo
    fecha = "2026-10-30T12:00:00+00:00"
    monkeypatch.setattr(servicio, "socios_con_programa", lambda cursor, ids: set(ids))
    monkeypatch.setattr(
        servicio,
        "listar_equipos",
        lambda **opciones: [
            {"nombre": "Original", "estado": "disponible", "ultimo_cambio": "2026-10-29T12:00:00+00:00"},
            {"nombre": "Alternativo", "estado": "fuera_de_servicio", "ultimo_cambio": fecha},
        ],
    )
    monkeypatch.setattr(
        servicio,
        "consultar_propuesta",
        lambda *args, **opciones: {
            "sesion_planificada": {"id": "sesion"},
            "ejercicios": [
                {
                    "id": ejercicio_id,
                    "equipo": equipo_original,
                    "equipo_no_disponible": "Alternativo",
                    "no_disponible": True,
                    "pendiente": pendiente,
                },
            ],
        },
    )
    respuesta = cliente.get("/api/entrenador/bandeja")
    assert respuesta.status_code == 200
    socios = [s for grupo in respuesta.json["grupos"] for s in grupo["socios"]]
    if pendiente:
        assert socios[0]["motivos"] == [
            {"tipo": "ejercicio_sin_alternativa", "fecha": fecha, "ejercicio_id": ejercicio_id}
        ]
    else:
        assert socios == []
