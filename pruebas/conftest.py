import os
import uuid
import zlib

import pytest

from gimnasio.comun.bd import conectar, parametros_desde_entorno


def _hay_mysql():
    return bool(os.environ.get("GIMNASIO_BD_HOST"))


def fragmento_de(nodeid, total):
    """El fragmento (1..total) que corre esta prueba: un hash estable, igual en cada proceso y en cada máquina."""
    return zlib.crc32(nodeid.encode("utf-8")) % total + 1


def _quedarse_con_el_fragmento(config, items):
    """Con GIMNASIO_FRAGMENTO="k/N" deja solo el fragmento k de N: así el CI corre pruebas y e2e en partes a la vez."""
    pedido = os.environ.get("GIMNASIO_FRAGMENTO")
    if not pedido:
        return
    numero, total = (int(parte) for parte in pedido.split("/"))
    propias = [item for item in items if fragmento_de(item.nodeid, total) == numero]
    ajenas = [item for item in items if fragmento_de(item.nodeid, total) != numero]
    config.hook.pytest_deselected(items=ajenas)
    items[:] = propias


def pytest_collection_modifyitems(config, items):
    _quedarse_con_el_fragmento(config, items)
    if _hay_mysql():
        return
    saltar = pytest.mark.skip(reason="sin MySQL: definí GIMNASIO_BD_HOST para correr estas pruebas")
    for item in items:
        if "bd" in item.keywords:
            item.add_marker(saltar)


@pytest.fixture(scope="session", autouse=True)
def hash_de_clave_barato():
    """La semilla demo hashea una clave por persona; con scrypt eso cuesta segundos por cada base de prueba."""
    from werkzeug.security import generate_password_hash

    from gimnasio.permisos import servicio

    def barato(clave):
        return generate_password_hash(clave, method="pbkdf2:sha256:1")

    parche = pytest.MonkeyPatch()
    parche.setattr(servicio, "generate_password_hash", barato)
    yield
    parche.undo()


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


@pytest.fixture
def reloj_fijo():
    from datetime import UTC, datetime

    from gimnasio.comun.reloj import RelojFijo

    return RelojFijo(datetime(2026, 10, 27, 12, 0, tzinfo=UTC))


@pytest.fixture
def app_con_bd(bd_vacia, reloj_fijo):
    """App de prueba sobre una base vacía con todas las migraciones aplicadas y un RelojFijo."""
    from gimnasio import crear_app
    from gimnasio.comun.migrar import aplicar

    aplicar(bd_vacia, salida=lambda _: None)
    return crear_app(
        {"ENTORNO": "prueba", "SECRET_KEY": "solo-pruebas", "MODO_DEMO": False, "BD": bd_vacia}, reloj_fijo
    )
