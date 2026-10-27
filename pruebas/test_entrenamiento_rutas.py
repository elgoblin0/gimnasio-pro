"""Las rutas de entrenamiento forman parte de la app y protegen el acceso."""

from gimnasio import crear_app


def test_propuesta_exige_sesion():
    cliente = crear_app({"ENTORNO": "prueba"}).test_client()
    assert cliente.get("/api/entrenamiento/propuesta").status_code == 401
    assert cliente.get("/api/entrenamiento/socios/00000000-0000-7000-8000-000000000001/propuesta").status_code == 401
