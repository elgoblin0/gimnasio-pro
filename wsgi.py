"""Punto de entrada WSGI: `gunicorn wsgi:app` o `flask --app wsgi run --port 5002`."""

from gimnasio import crear_app

app = crear_app()
