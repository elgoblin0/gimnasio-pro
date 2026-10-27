import os
import uuid

import pytest

from gimnasio.comun.bd import conectar, parametros_desde_entorno


def _hay_mysql():
    return bool(os.environ.get("GIMNASIO_BD_HOST"))


def pytest_collection_modifyitems(config, items):
    if _hay_mysql():
        return
    saltar = pytest.mark.skip(reason="sin MySQL: definí GIMNASIO_BD_HOST para correr estas pruebas")
    for item in items:
        if "bd" in item.keywords:
            item.add_marker(saltar)


@pytest.fixture
def bd_vacia():
    """Crea una base vacía y única para la prueba y la borra al terminar."""
    nombre = f"gimnasio_prueba_{uuid.uuid4().hex[:10]}"
    administracion = conectar(parametros_desde_entorno(base=None) | {"database": None})
    cursor = administracion.cursor()
    cursor.execute(f"CREATE DATABASE `{nombre}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    try:
        yield parametros_desde_entorno(base=nombre)
    finally:
        cursor.execute(f"DROP DATABASE IF EXISTS `{nombre}`")
        administracion.close()
