"""Lectura e inserción de membresías, sin datos de salud ni tablas heredadas."""

from gimnasio.comun.ids import a_bytes


def bloquear_socio(cursor, socio_id):
    cursor.execute("SELECT rol, activo FROM usuarios WHERE id=%s FOR UPDATE", (a_bytes(socio_id),))
    return cursor.fetchone()


def ultimo_vencimiento(cursor, socio_id):
    # Lectura actual tras esperar al bloqueo del socio, incluso bajo REPEATABLE READ.
    cursor.execute(
        "SELECT hasta FROM membresias WHERE socio_id=%s ORDER BY hasta DESC LIMIT 1 FOR UPDATE", (a_bytes(socio_id),)
    )
    fila = cursor.fetchone()
    return fila["hasta"] if fila else None


def insertar_membresia(cursor, membresia_id, socio_id, pago_id, tipo_id, desde, hasta, ahora):
    cursor.execute(
        """INSERT INTO membresias (id, socio_id, pago_id, tipo_id, desde, hasta, actualizada_en)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (a_bytes(membresia_id), a_bytes(socio_id), a_bytes(pago_id), a_bytes(tipo_id), desde, hasta, ahora),
    )


def buscar_membresia_vigente(cursor, socio_id, fecha_local):
    cursor.execute(
        """SELECT m.id, m.socio_id, m.desde, m.hasta, u.rol, u.activo
           FROM membresias m JOIN usuarios u ON u.id = m.socio_id
           WHERE m.socio_id = %s AND m.desde <= %s AND m.hasta >= %s
           LIMIT 1""",
        (a_bytes(socio_id), fecha_local, fecha_local),
    )
    return cursor.fetchone()


def buscar_ultima_membresia(cursor, socio_id, fecha_local):
    cursor.execute(
        """SELECT m.desde, m.hasta, u.rol, u.activo
           FROM membresias m JOIN usuarios u ON u.id = m.socio_id
           WHERE m.socio_id = %s AND m.desde <= %s
           ORDER BY m.hasta DESC, m.desde DESC LIMIT 1""",
        (a_bytes(socio_id), fecha_local),
    )
    return cursor.fetchone()
