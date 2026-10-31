"""SQL de tipos de membresía y pagos; los pagos solo se insertan."""

from gimnasio.comun.ids import a_bytes


def listar_tipos(cursor, incluir_archivados):
    cursor.execute(
        "SELECT * FROM tipos_membresia WHERE archivado = FALSE OR %s ORDER BY nombre, id",
        (incluir_archivados,),
    )
    return cursor.fetchall()


def obtener_tipo(cursor, tipo_id):
    cursor.execute("SELECT * FROM tipos_membresia WHERE id = %s FOR UPDATE", (a_bytes(tipo_id),))
    return cursor.fetchone()


def insertar_tipo(cursor, tipo_id, nombre, duracion, precio, ahora):
    cursor.execute(
        """INSERT INTO tipos_membresia (id, nombre, duracion_dias, precio, creado_en, actualizado_en)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (a_bytes(tipo_id), nombre, duracion, precio, ahora, ahora),
    )


def cambiar_tipo(cursor, tipo_id, nombre, duracion, precio, ahora):
    cursor.execute(
        "UPDATE tipos_membresia SET nombre=%s, duracion_dias=%s, precio=%s, actualizado_en=%s WHERE id=%s",
        (nombre, duracion, precio, ahora, a_bytes(tipo_id)),
    )


def archivar_tipo(cursor, tipo_id, ahora):
    cursor.execute(
        "UPDATE tipos_membresia SET archivado=TRUE, actualizado_en=%s WHERE id=%s", (ahora, a_bytes(tipo_id))
    )


def insertar_pago(cursor, pago_id, socio_id, tipo_id, medio, monto, autor_id, ahora):
    cursor.execute(
        """INSERT INTO pagos (id, socio_id, tipo_id, medio, monto, autor_id, registrado_en)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (a_bytes(pago_id), a_bytes(socio_id), a_bytes(tipo_id), medio, monto, a_bytes(autor_id), ahora),
    )


def zona_sede(cursor):
    cursor.execute("SELECT zona_horaria FROM sedes ORDER BY id LIMIT 1")
    return cursor.fetchone()
