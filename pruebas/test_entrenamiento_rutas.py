"""Las rutas de entrenamiento forman parte de la app y protegen el acceso."""

from uuid import uuid4

from gimnasio import crear_app


def test_propuesta_exige_sesion():
    cliente = crear_app({"ENTORNO": "prueba"}).test_client()
    assert cliente.get("/api/entrenamiento/propuesta").status_code == 401
    assert cliente.get("/api/entrenamiento/socios/00000000-0000-7000-8000-000000000001/propuesta").status_code == 401


def test_sesiones_y_series_exigen_sesion():
    cliente = crear_app({"ENTORNO": "prueba"}).test_client()
    identificador = "00000000-0000-7000-8000-000000000001"
    assert cliente.get(f"/api/entrenamiento/sesiones/{identificador}").status_code == 401
    assert cliente.get(f"/api/entrenamiento/sesiones/{identificador}/resumen").status_code == 401
    assert cliente.get(f"/api/entrenamiento/socios/{identificador}/sesiones/{identificador}/resumen").status_code == 401
    for ruta in ("/api/entrenamiento/sesiones", f"/api/entrenamiento/sesiones/{identificador}/series"):
        assert (
            cliente.post(ruta, json={}, headers={"X-Gimnasio": "1", "Idempotency-Key": str(uuid4())}).status_code == 401
        )
