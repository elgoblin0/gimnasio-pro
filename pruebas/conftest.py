import os
import uuid
from types import SimpleNamespace

import pytest
from fragmentos import fragmento_de

from gimnasio.comun.bd import conectar, parametros_desde_entorno


def _hay_mysql():
    return bool(os.environ.get("GIMNASIO_BD_HOST"))


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


@pytest.fixture(scope="session")
def bd_migrada():
    """Una base con todas las migraciones por proceso: migrar cuesta segundos y vaciarla, milisegundos."""
    from gimnasio.comun.migrar import aplicar

    nombre = f"gimnasio_prueba_{uuid.uuid4().hex[:10]}"
    administracion = conectar(parametros_desde_entorno(base=None) | {"database": None})
    cursor = administracion.cursor()
    cursor.execute(f"CREATE DATABASE `{nombre}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    try:
        aplicar(parametros_desde_entorno(base=nombre), salida=lambda _: None)
        cursor.execute(f"USE `{nombre}`")
        # Una prueba que deja una transacción abierta falla pronto, en vez de colgar la siguiente.
        cursor.execute("SET SESSION innodb_lock_wait_timeout = 5, foreign_key_checks = 0")
        cursor.execute("SHOW TABLES")
        tablas = [fila[0] for fila in cursor.fetchall() if fila[0] != "migraciones_aplicadas"]
        # Un pool por proceso: abrir una conexión por solicitud deja miles de puertos en TIME_WAIT en Windows.
        parametros = parametros_desde_entorno(base=nombre) | {"pool_name": uuid.uuid4().hex, "pool_size": 8}
        yield SimpleNamespace(nombre=nombre, parametros=parametros, conexion=administracion, tablas=tablas, semillas={})
    finally:
        cursor.execute("SHOW DATABASES LIKE %s", (f"{nombre}%",))
        for (base,) in cursor.fetchall():
            cursor.execute(f"DROP DATABASE IF EXISTS `{base}`")
        administracion.close()


def _vaciar(bd_migrada):
    with bd_migrada.conexion.cursor() as cursor:
        for tabla in bd_migrada.tablas:
            cursor.execute(f"DELETE FROM `{tabla}`")
    bd_migrada.conexion.commit()


@pytest.fixture
def bd_limpia(bd_migrada):
    """La base migrada de este proceso, sin filas. Las migraciones no insertan datos: equivale a recién migrada."""
    _vaciar(bd_migrada)
    return dict(bd_migrada.parametros)


def _quitar_pagos_y_clases(bd_migrada):
    with bd_migrada.conexion.cursor() as cursor:
        for tabla in (
            "vistos_aviso_socio",
            "avisos_socio",
            "cupos_ocurrencia",
            "cancelaciones_ocurrencia",
            "cancelaciones_reserva",
            "reservas",
            "ocurrencias_clase",
            "clases",
        ):
            cursor.execute(f"DELETE FROM `{tabla}`")
        cursor.execute("UPDATE membresias SET pago_id=NULL, tipo_id=NULL")
        cursor.execute("DELETE FROM pagos")
        cursor.execute("DELETE FROM tipos_membresia")
    bd_migrada.conexion.commit()


def _guardar_semilla(bd_migrada):
    """Copia a una base aparte las tablas con filas y devuelve (base, tablas)."""
    base = f"{bd_migrada.nombre}_s{len(bd_migrada.semillas)}"
    con_filas = []
    with bd_migrada.conexion.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE `{base}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        for tabla in bd_migrada.tablas:
            cursor.execute(f"SELECT EXISTS (SELECT 1 FROM `{tabla}`)")
            if cursor.fetchone()[0]:
                cursor.execute(f"CREATE TABLE `{base}`.`{tabla}` LIKE `{tabla}`")
                cursor.execute(f"INSERT INTO `{base}`.`{tabla}` SELECT * FROM `{tabla}`")
                con_filas.append(tabla)
    bd_migrada.conexion.commit()
    return base, con_filas


@pytest.fixture
def sembrar_demo(bd_migrada):
    """Deja la semilla demo en la base del proceso: la genera una vez por momento y después copia sus tablas.

    Generarla son cientos de INSERT por prueba. Solo para preparar: lo que prueba `reiniciar()` debe llamarlo.
    """
    from gimnasio.demo.servicio import reiniciar

    def sembrar(app, *, sin_pagos_ni_clases=False):
        """`sin_pagos_ni_clases` deja la base como antes de la etapa 5 para pruebas que cuentan esos hechos."""
        assert app.config["MODO_DEMO"], "reiniciar() rechaza sembrar fuera de la demo"
        ahora = app.extensions["reloj"].ahora()
        if ahora not in bd_migrada.semillas:
            with app.app_context():
                reiniciar()
            bd_migrada.semillas[ahora] = _guardar_semilla(bd_migrada)
        else:
            base, tablas = bd_migrada.semillas[ahora]
            _vaciar(bd_migrada)
            with bd_migrada.conexion.cursor() as cursor:
                for tabla in tablas:
                    cursor.execute(f"INSERT INTO `{tabla}` SELECT * FROM `{base}`.`{tabla}`")
            bd_migrada.conexion.commit()
        if sin_pagos_ni_clases:
            _quitar_pagos_y_clases(bd_migrada)

    return sembrar


@pytest.fixture
def reloj_fijo():
    from datetime import UTC, datetime

    from gimnasio.comun.reloj import RelojFijo

    return RelojFijo(datetime(2026, 10, 27, 12, 0, tzinfo=UTC))


@pytest.fixture
def app_con_bd(bd_limpia, reloj_fijo):
    """App de prueba sobre una base sin filas con todas las migraciones aplicadas y un RelojFijo."""
    from gimnasio import crear_app

    return crear_app(
        {"ENTORNO": "prueba", "SECRET_KEY": "solo-pruebas", "MODO_DEMO": False, "BD": bd_limpia}, reloj_fijo
    )
