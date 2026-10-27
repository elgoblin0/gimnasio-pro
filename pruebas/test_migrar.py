import pytest

from gimnasio.comun.bd import conectar
from gimnasio.comun.migrar import ErrorDeMigracion, aplicar, dividir_sentencias, leer_migraciones


def escribir(carpeta, nombre, sql):
    (carpeta / nombre).write_text(sql, encoding="utf-8")


def test_divide_sentencias_y_descarta_comentarios():
    sql = "-- comentario\nCREATE TABLE a (\n  x INT\n);\n\nINSERT INTO a VALUES (1);\n"
    assert dividir_sentencias(sql) == ["CREATE TABLE a (\n  x INT\n)", "INSERT INTO a VALUES (1)"]


def test_rechaza_sentencia_sin_punto_y_coma():
    with pytest.raises(ErrorDeMigracion):
        dividir_sentencias("CREATE TABLE a (x INT)")


def test_ignora_el_archivo_heredado_y_ordena(tmp_path):
    escribir(tmp_path, "001_dni_a_ci.sql", "ALTER TABLE socios RENAME COLUMN dni TO ci;")
    escribir(tmp_path, "0002_b.sql", "SELECT 2;")
    escribir(tmp_path, "0001_a.sql", "SELECT 1;")
    assert [m.version for m in leer_migraciones(tmp_path)] == ["0001", "0002"]


def test_rechaza_versiones_repetidas(tmp_path):
    escribir(tmp_path, "0001_a.sql", "SELECT 1;")
    escribir(tmp_path, "0001_b.sql", "SELECT 1;")
    with pytest.raises(ErrorDeMigracion):
        leer_migraciones(tmp_path)


def test_las_migraciones_del_repo_tienen_versiones_unicas():
    assert leer_migraciones()


def test_la_suma_no_depende_de_los_saltos_de_linea(tmp_path):
    escribir(tmp_path, "0001_a.sql", "SELECT 1;\n")
    unix = leer_migraciones(tmp_path)[0].sha256
    (tmp_path / "0001_a.sql").write_bytes(b"SELECT 1;\r\n")
    assert leer_migraciones(tmp_path)[0].sha256 == unix


@pytest.mark.bd
def test_aplica_en_orden_y_la_segunda_pasada_no_hace_nada(tmp_path, bd_vacia):
    escribir(tmp_path, "0001_crear.sql", "CREATE TABLE prueba (x INT NOT NULL);")
    escribir(tmp_path, "0002_cargar.sql", "INSERT INTO prueba VALUES (1);\nINSERT INTO prueba VALUES (2);")
    assert aplicar(bd_vacia, tmp_path, salida=lambda _: None) == ["0001", "0002"]
    assert aplicar(bd_vacia, tmp_path, salida=lambda _: None) == []
    conexion = conectar(bd_vacia)
    cursor = conexion.cursor()
    cursor.execute("SELECT COUNT(*) FROM prueba")
    assert cursor.fetchone()[0] == 2
    conexion.close()


@pytest.mark.bd
def test_falla_si_una_migracion_aplicada_cambio(tmp_path, bd_vacia):
    escribir(tmp_path, "0001_crear.sql", "CREATE TABLE prueba (x INT);")
    aplicar(bd_vacia, tmp_path, salida=lambda _: None)
    escribir(tmp_path, "0001_crear.sql", "CREATE TABLE prueba (x BIGINT);")
    with pytest.raises(ErrorDeMigracion):
        aplicar(bd_vacia, tmp_path, salida=lambda _: None)


@pytest.mark.bd
def test_las_migraciones_del_repo_se_aplican_sobre_una_base_vacia(bd_vacia):
    aplicar(bd_vacia, salida=lambda _: None)
    assert aplicar(bd_vacia, salida=lambda _: None) == []
