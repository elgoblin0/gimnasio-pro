"""Arranque local modular: python app.py. En Render se usa gunicorn wsgi:app."""

from gimnasio import crear_app

app = crear_app()

if __name__ == "__main__":
    app.run(port=5002)
