"""El cursor de lectura repite consultas idénticas sin volver a la base."""

import pytest

from gimnasio.comun.bd import LecturaConMemoria


class CursorFicticio:
    def __init__(self):
        self.consultas = []

    def execute(self, sql, parametros=None):
        self.consultas.append((sql, parametros))

    def fetchall(self):
        return [{"consulta": len(self.consultas)}, {"consulta": len(self.consultas) + 1}]


def test_consulta_identica_no_vuelve_a_la_base():
    base = CursorFicticio()
    cursor = LecturaConMemoria(base)
    cursor.execute("SELECT 1", (1,))
    primera = cursor.fetchall()
    cursor.execute("SELECT 1", (1,))
    assert cursor.fetchall() == primera
    assert len(base.consultas) == 1


def test_otros_parametros_son_otra_consulta():
    base = CursorFicticio()
    cursor = LecturaConMemoria(base)
    cursor.execute("SELECT 1", (1,))
    cursor.execute("SELECT 1", (2,))
    assert len(base.consultas) == 2


def test_fetchone_avanza_y_termina_en_none():
    cursor = LecturaConMemoria(CursorFicticio())
    cursor.execute("SELECT 1")
    assert cursor.fetchone() == {"consulta": 1}
    assert cursor.fetchone() == {"consulta": 2}
    assert cursor.fetchone() is None


def test_modificar_una_fila_no_altera_la_proxima_lectura():
    cursor = LecturaConMemoria(CursorFicticio())
    cursor.execute("SELECT 1")
    cursor.fetchone()["consulta"] = "cambiada"
    cursor.execute("SELECT 1")
    assert cursor.fetchone() == {"consulta": 1}


@pytest.mark.parametrize("sql", ["UPDATE equipos SET nombre='x'", "  insert INTO equipos VALUES (1)", "SET @a=1"])
def test_una_escritura_se_rechaza_sin_llegar_a_la_base(sql):
    base = CursorFicticio()
    with pytest.raises(ValueError, match="solo admite lecturas"):
        LecturaConMemoria(base).execute(sql)
    assert base.consultas == []


def test_acepta_with_recursivo_y_espacios_iniciales():
    base = CursorFicticio()
    cursor = LecturaConMemoria(base)
    cursor.execute("\n  WITH RECURSIVE h AS (SELECT 1) SELECT * FROM h")
    assert len(base.consultas) == 1
