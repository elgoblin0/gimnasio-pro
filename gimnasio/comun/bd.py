"""Conexión a MySQL desde variables de entorno.

Toda conexión trabaja en UTC (ADR 0005) y sin autocommit: el servicio decide la transacción.
"""

import os
from contextlib import contextmanager

import mysql.connector
from flask import current_app, g


def parametros_desde_entorno(base=None):
    """Arma los parámetros de conexión desde GIMNASIO_BD_*; `base` reemplaza GIMNASIO_BD_NOMBRE."""
    parametros = {
        "host": os.environ.get("GIMNASIO_BD_HOST", "localhost"),
        "port": int(os.environ.get("GIMNASIO_BD_PUERTO", "3306")),
        "user": os.environ.get("GIMNASIO_BD_USUARIO", "root"),
        "password": os.environ.get("GIMNASIO_BD_CLAVE", ""),
        "database": base or os.environ.get("GIMNASIO_BD_NOMBRE", "gimnasio_pro"),
    }
    certificado = os.environ.get("GIMNASIO_BD_CA")
    if certificado:
        parametros["ssl_ca"] = certificado
        parametros["ssl_verify_cert"] = True
    return parametros


def conectar(parametros=None):
    """Abre una conexión con la zona horaria de la sesión fijada en UTC."""
    return mysql.connector.connect(
        **(parametros or parametros_desde_entorno()),
        time_zone="+00:00",
        charset="utf8mb4",
        collation="utf8mb4_0900_ai_ci",
        autocommit=False,
        use_pure=True,
    )


def conexion_actual():
    """Una conexión por solicitud, con los parámetros de `app.config["BD"]` si existen."""
    if "bd" not in g:
        g.bd = conectar(current_app.config.get("BD"))
    return g.bd


@contextmanager
def transaccion():
    """Commit al salir, salvo que idempotencia confirme escritura y respuesta juntas."""
    conexion = conexion_actual()
    cursor = conexion.cursor(dictionary=True)
    try:
        yield cursor
        if not g.get("idempotencia_activa"):
            conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        cursor.close()


def registrar_cierre(app):
    @app.teardown_appcontext
    def cerrar_conexion(_error):
        conexion = g.pop("bd", None)
        if conexion is not None:
            conexion.close()
