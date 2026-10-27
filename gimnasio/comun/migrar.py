"""Aplicador de migraciones versionadas (ADR 0008).

Uso:
    python -m gimnasio.comun.migrar                # aplica las pendientes
    python -m gimnasio.comun.migrar --sin-pendientes  # falla si queda alguna por aplicar

Formato de los archivos: migraciones/NNNN_descripcion.sql. Cada sentencia termina con `;`
al final de una línea. No se admiten DELIMITER ni procedimientos almacenados.
"""

import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from gimnasio.comun.bd import conectar, parametros_desde_entorno

CARPETA = Path(__file__).resolve().parents[2] / "migraciones"
PATRON = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")
CANDADO = "gimnasio_migraciones"

TABLA_REGISTRO = """
CREATE TABLE IF NOT EXISTS migraciones_aplicadas (
    version CHAR(4) NOT NULL PRIMARY KEY,
    nombre VARCHAR(200) NOT NULL,
    sha256 CHAR(64) NOT NULL,
    aplicada_en DATETIME(6) NOT NULL DEFAULT (UTC_TIMESTAMP(6))
)
"""


class ErrorDeMigracion(Exception):
    pass


@dataclass(frozen=True)
class Migracion:
    version: str
    nombre: str
    sql: str

    @property
    def sha256(self):
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()


def leer_migraciones(carpeta=CARPETA):
    """Devuelve las migraciones ordenadas. Ignora archivos que no siguen el patrón (el heredado 001_)."""
    migraciones = {}
    for archivo in sorted(carpeta.glob("*.sql")):
        coincidencia = PATRON.match(archivo.name)
        if not coincidencia:
            continue
        version = coincidencia.group(1)
        if version in migraciones:
            raise ErrorDeMigracion(f"versión repetida {version}: {archivo.name}")
        # Se normalizan los saltos de línea para que la suma no dependa de autocrlf en Windows.
        sql = archivo.read_text(encoding="utf-8").replace("\r\n", "\n")
        migraciones[version] = Migracion(version, archivo.name, sql)
    return [migraciones[v] for v in sorted(migraciones)]


def dividir_sentencias(sql):
    """Separa el SQL en sentencias; descarta comentarios de línea completa."""
    sentencias, actual = [], []
    for linea in sql.split("\n"):
        if linea.strip().startswith("--") and not actual:
            continue
        actual.append(linea)
        if linea.rstrip().endswith(";"):
            sentencia = "\n".join(actual).strip().rstrip(";").strip()
            if sentencia:
                sentencias.append(sentencia)
            actual = []
    resto = "\n".join(actual).strip()
    if resto and not all(linea.strip().startswith("--") or not linea.strip() for linea in actual):
        raise ErrorDeMigracion("la última sentencia no termina en ';'")
    return sentencias


def aplicar(parametros=None, carpeta=CARPETA, salida=print):
    """Aplica las migraciones pendientes y devuelve las versiones aplicadas."""
    migraciones = leer_migraciones(carpeta)
    conexion = conectar(parametros or parametros_desde_entorno())
    cursor = conexion.cursor()
    try:
        cursor.execute("SELECT GET_LOCK(%s, 30)", (CANDADO,))
        if cursor.fetchone()[0] != 1:
            raise ErrorDeMigracion("otro proceso está migrando")
        cursor.execute(TABLA_REGISTRO)
        cursor.execute("SELECT version, sha256 FROM migraciones_aplicadas")
        aplicadas = dict(cursor.fetchall())
        for migracion in migraciones:
            suma = aplicadas.get(migracion.version)
            if suma is not None and suma != migracion.sha256:
                raise ErrorDeMigracion(f"{migracion.nombre} cambió después de aplicarse; creá una migración nueva")
        pendientes = [m for m in migraciones if m.version not in aplicadas]
        for migracion in pendientes:
            salida(f"Aplicando {migracion.nombre}")
            for sentencia in dividir_sentencias(migracion.sql):
                cursor.execute(sentencia)
            cursor.execute(
                "INSERT INTO migraciones_aplicadas (version, nombre, sha256) VALUES (%s, %s, %s)",
                (migracion.version, migracion.nombre, migracion.sha256),
            )
            conexion.commit()
        return [m.version for m in pendientes]
    finally:
        cursor.execute("SELECT RELEASE_LOCK(%s)", (CANDADO,))
        cursor.fetchall()
        conexion.close()


def main(argumentos):
    aplicadas = aplicar()
    print(f"Migraciones aplicadas: {len(aplicadas)}")
    if "--sin-pendientes" in argumentos and aplicadas:
        print("Se esperaba que no quedaran migraciones pendientes")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
