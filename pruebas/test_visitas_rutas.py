"""La entrada está registrada en la aplicación y exige sesión antes de usar la base."""

from uuid import uuid4

from gimnasio import crear_app


def test_entrada_exige_sesion():
    cliente = crear_app({"ENTORNO": "prueba"}).test_client()
    respuesta = cliente.post("/api/entradas", json={}, headers={"X-Gimnasio": "1", "Idempotency-Key": str(uuid4())})
    assert respuesta.status_code == 401
    assert respuesta.json["error"]["codigo"] == "sin_sesion"
