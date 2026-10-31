"""Consultas de clases y ocurrencias en bloques."""

from gimnasio.comun.ids import a_bytes


def listar(cursor):
    cursor.execute(
        "SELECT c.*, p.nombre AS entrenador_nombre, p.apellido AS entrenador_apellido "
        "FROM clases c JOIN usuarios u ON u.id=c.entrenador_id "
        "JOIN personas p ON p.id=u.persona_id ORDER BY c.nombre, c.id"
    )
    return cursor.fetchall()


def entrenadores(cursor):
    cursor.execute(
        "SELECT u.id, p.nombre, p.apellido FROM usuarios u "
        "JOIN personas p ON p.id=u.persona_id "
        "WHERE u.activo=TRUE AND u.rol='entrenador' ORDER BY p.nombre, u.id"
    )
    return cursor.fetchall()


def entrenador_activo(cursor, identificador):
    cursor.execute(
        "SELECT id FROM usuarios WHERE id=%s AND activo=TRUE AND rol='entrenador' FOR UPDATE",
        (a_bytes(identificador),),
    )
    return cursor.fetchone() is not None


def bloquear(cursor, identificador):
    cursor.execute("SELECT id FROM clases WHERE id=%s FOR UPDATE", (a_bytes(identificador),))
    return cursor.fetchone()


def ocurrencias(cursor, desde, hasta):
    cursor.execute("SELECT * FROM ocurrencias_clase WHERE fecha BETWEEN %s AND %s", (desde, hasta))
    return cursor.fetchall()


def guardar(cursor, identificador, datos, momento, *, nueva):
    valores = (
        datos["nombre"],
        a_bytes(datos["entrenador_id"]),
        datos["dia_semana"],
        datos["hora_inicio"],
        datos["duracion_minutos"],
        datos["cupo"],
        momento,
    )
    if nueva:
        cursor.execute(
            "INSERT INTO clases (nombre, entrenador_id, dia_semana, hora_inicio, duracion_minutos, "
            "cupo, actualizada_en, creada_en, id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (*valores, momento, a_bytes(identificador)),
        )
    else:
        cursor.execute(
            "UPDATE clases SET nombre=%s, entrenador_id=%s, dia_semana=%s, hora_inicio=%s, "
            "duracion_minutos=%s, cupo=%s, actualizada_en=%s WHERE id=%s",
            (*valores, a_bytes(identificador)),
        )


def archivar(cursor, identificador, momento):
    cursor.execute("UPDATE clases SET archivada=TRUE, actualizada_en=%s WHERE id=%s", (momento, a_bytes(identificador)))
