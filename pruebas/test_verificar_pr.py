"""Pruebas de los controles del CI que reemplazan hallazgos mecánicos de la revisión de Codex."""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import verificar_pr as control  # noqa: E402  (necesita scripts/ en sys.path, que se agrega arriba)

MODULO = "gimnasio/reglas/dolor.py"
CODIGO = "from gimnasio.reglas.version import VERSION_REGLAS\n\n\ndef regla():\n    return VERSION_REGLAS, 1\n"
VERSION_1 = 'VERSION_REGLAS = "3.1.0"\n'
VERSION_2 = 'VERSION_REGLAS = "3.2.0"\n'


def lector(contenido):
    return contenido.get


def motor(base, pr, version_base=VERSION_1, version_pr=VERSION_1, archivos=(MODULO,)):
    return control.falta_subir_motor(
        list(archivos),
        lector({MODULO: base, control.ARCHIVO_VERSION: version_base}),
        lector({MODULO: pr, control.ARCHIVO_VERSION: version_pr}),
    )


def test_cambiar_el_motor_sin_subir_la_version_falla():
    """Fue el hallazgo de Codex en #135: prescripciones de reglas distintas con la misma versión."""
    assert "VERSION_REGLAS" in motor(CODIGO, CODIGO.replace("1", "2"))


def test_una_version_menor_tambien_falla():
    assert motor(CODIGO, CODIGO.replace("1", "2"), version_base=VERSION_2, version_pr=VERSION_1)


def test_subir_la_version_pasa():
    assert motor(CODIGO, CODIGO.replace("1", "2"), version_pr=VERSION_2) is None


def test_comentarios_y_docstrings_no_cambian_el_motor():
    documentado = '"""Módulo."""\n' + CODIGO.replace("def regla():\n", 'def regla():\n    """Explica."""\n    # nota\n')
    assert motor(CODIGO, documentado) is None


def test_un_modulo_sin_version_registrada_no_exige_subirla():
    """Como `zonas_sede.py` en #201: sus decisiones no se guardan con VERSION_REGLAS."""
    assert motor("ZONAS = 1\n", "ZONAS = 2\n") is None


def test_quitar_un_modulo_del_motor_tambien_cuenta():
    assert motor(CODIGO, None)


def test_no_tocar_reglas_pasa():
    assert motor(CODIGO, CODIGO, archivos=("gimnasio/visitas/servicio.py",)) is None


MIGRACION = "migraciones/0099_prueba.sql"


def autorizacion(sql):
    return control.falta_autorizar_hechos([MIGRACION], lector({MIGRACION: sql}))


def test_alterar_hechos_sin_autorizacion_falla():
    """Fue el hallazgo de Codex en #191, con esta misma sentencia."""
    assert "sustituciones" in autorizacion("ALTER TABLE sustituciones DROP CHECK ck_sustituciones_motivo;")


def test_cada_forma_de_escribir_en_hechos_falla():
    for sql in (
        "alter  table `series_realizadas` add column x int;",
        "ALTER TABLE gimnasio_pro.entradas ADD COLUMN x INT;",
        "UPDATE salidas SET motivo = 'x';",
        "DELETE FROM consentimientos;",
        "DROP TABLE IF EXISTS chequeos_dia;",
        "TRUNCATE dolores_reportados;",
        "RENAME TABLE sesiones_realizadas TO otra;",
    ):
        assert autorizacion(sql), sql


def test_la_autorizacion_de_opus_pasa():
    assert autorizacion("-- Autoriza Opus: #177\nALTER TABLE sustituciones ADD COLUMN x INT;") is None


def test_comentarios_valores_y_otras_tablas_no_cuentan():
    assert autorizacion("-- ALTER TABLE sustituciones\nALTER TABLE personas ADD COLUMN x INT;") is None
    assert autorizacion("UPDATE personas SET nota = 'DELETE FROM entradas';") is None
    assert autorizacion("CREATE TABLE nueva (a TIMESTAMP ON UPDATE CURRENT_TIMESTAMP);") is None


def test_solo_se_miran_las_migraciones():
    sql = {"pruebas/datos.sql": "DELETE FROM entradas;"}
    assert control.falta_autorizar_hechos(["pruebas/datos.sql"], lector(sql)) is None


PRUEBA = "pruebas/e2e/test_figura.py"


def ficha(archivos, agregados=(PRUEBA,), codigo="def test_x(): ...\n"):
    return control.falta_ficha(list(archivos), list(agregados), lector({PRUEBA: codigo}))


def test_prueba_e2e_nueva_sin_ficha_falla():
    """Fue el hallazgo de Codex en #172."""
    assert "docs/capacidades/" in ficha([PRUEBA])


def test_tocar_una_ficha_pasa():
    assert ficha([PRUEBA, "docs/capacidades/cuerpo-3d.toml"]) is None


def test_declarar_el_motivo_pasa():
    assert ficha([PRUEBA], codigo="# Sin ficha: prueba de humo de la PWA\n") is None
    assert ficha([PRUEBA], codigo="# Sin ficha: \n")


def test_otros_archivos_nuevos_no_exigen_ficha():
    assert ficha(["pruebas/test_x.py"], agregados=["pruebas/test_x.py"]) is None
    assert ficha(["pruebas/e2e/conftest.py"], agregados=["pruebas/e2e/conftest.py"]) is None
    assert ficha([PRUEBA], agregados=[]) is None
