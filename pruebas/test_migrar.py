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


def test_el_catalogo_del_repo_tiene_versiones_unicas():
    migraciones = leer_migraciones()
    assert migraciones
    assert len({m.version for m in migraciones}) == len(migraciones)


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


@pytest.mark.bd
def test_catalogo_y_rango_conserva_semilla_etapa_uno(tmp_path, bd_vacia, reloj_fijo):
    """Aplica 0010 a la semilla anterior, incluidos sus hechos de entrenamiento."""
    from gimnasio import crear_app
    from gimnasio.comun.bd import transaccion
    from gimnasio.comun.ids import a_bytes, nuevo_id
    from gimnasio.demo import repositorio, servicio
    from gimnasio.permisos.servicio import crear_usuario

    migraciones = leer_migraciones()
    for migracion in migraciones:
        if migracion.version < "0010":
            (tmp_path / migracion.nombre).write_text(migracion.sql, encoding="utf-8", newline="\n")
    aplicar(bd_vacia, tmp_path, salida=lambda _: None)
    app = crear_app({"ENTORNO": "prueba", "SECRET_KEY": "solo-pruebas", "MODO_DEMO": True, "BD": bd_vacia}, reloj_fijo)
    # Prescripción y sesión parcial de la semilla de etapa 1, antes de agregar el rango.
    with app.app_context(), transaccion() as cursor:
        socio = crear_usuario(cursor, {"nombre": "Lucía", "apellido": "Ficticia", "cedula": "9900001"}, "socio")
        programa, sesion, fuerza, cardio, planificado = (nuevo_id(reloj_fijo) for _ in range(5))
        ahora = reloj_fijo.ahora()
        repositorio.insertar_programa(cursor, programa, socio, ahora)
        repositorio.insertar_sesion_planificada(cursor, sesion, programa, 1, "Fuerza y cardio")
        for identificador, nombre, medidas in (
            (fuerza, "Sentadilla ficticia", '["repeticiones","carga"]'),
            (cardio, "Caminata ficticia", '["duracion","distancia"]'),
        ):
            cursor.execute(
                "INSERT INTO ejercicios (id,nombre,medidas_aplicables,actualizada_en) VALUES (%s,%s,%s,%s)",
                (a_bytes(identificador), nombre, medidas, ahora),
            )
        cursor.execute(
            "INSERT INTO ejercicios_planificados "
            "(id,sesion_planificada_id,ejercicio_id,posicion,series,repeticiones,carga) "
            "VALUES (%s,%s,%s,1,2,10,20.50)",
            (a_bytes(planificado), a_bytes(sesion), a_bytes(fuerza)),
        )
        cursor.execute(
            "INSERT INTO ejercicios_planificados "
            "(id,sesion_planificada_id,ejercicio_id,posicion,series,duracion,distancia) "
            "VALUES (%s,%s,%s,2,1,120,1500.25)",
            (a_bytes(nuevo_id(reloj_fijo)), a_bytes(sesion), a_bytes(cardio)),
        )
        repositorio.insertar_parcial(
            cursor, nuevo_id(reloj_fijo), nuevo_id(reloj_fijo), socio, sesion, planificado, ahora
        )
    conexion = conectar(bd_vacia)
    cursor = conexion.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, repeticiones FROM ejercicios_planificados ORDER BY id")
        anteriores = cursor.fetchall()
        cursor.execute("SELECT * FROM series_realizadas ORDER BY id")
        hechos = cursor.fetchall()
        conexion.commit()
        assert aplicar(bd_vacia, salida=lambda _: None) == ["0010", "0011", "0012", "0013", "0014"]
        cursor.execute("SELECT id, repeticiones_minimas, repeticiones_maximas FROM ejercicios_planificados ORDER BY id")
        assert cursor.fetchall() == [
            {"id": f["id"], "repeticiones_minimas": f["repeticiones"], "repeticiones_maximas": f["repeticiones"]}
            for f in anteriores
        ]
        cursor.execute("SELECT * FROM series_realizadas ORDER BY id")
        ampliados = cursor.fetchall()
        assert [
            {k: v for k, v in fila.items() if k not in {"rir", "ejercicio_hecho_id"}} for fila in ampliados
        ] == hechos
        assert all(fila["rir"] is None and fila["ejercicio_hecho_id"] is None for fila in ampliados)
        cursor.execute("SELECT patron_movimiento, equipo, incremento_carga FROM ejercicios")
        assert all(f == {"patron_movimiento": "", "equipo": "", "incremento_carga": None} for f in cursor.fetchall())
        conexion.commit()
        with app.app_context():
            servicio.reiniciar()
        assert aplicar(bd_vacia, salida=lambda _: None) == []
    finally:
        conexion.close()
