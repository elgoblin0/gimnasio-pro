"""Lectura mínima de membresía, sin datos de salud ni tablas heredadas."""

from gimnasio.comun.ids import a_bytes


def buscar_membresia_vigente(cursor, socio_id, fecha_local):
    cursor.execute(
        """SELECT m.id, m.socio_id, m.desde, m.hasta, u.rol, u.activo
           FROM membresias m JOIN usuarios u ON u.id = m.socio_id
           WHERE m.socio_id = %s AND m.desde <= %s AND m.hasta >= %s
           LIMIT 1""",
        (a_bytes(socio_id), fecha_local, fecha_local),
    )
    return cursor.fetchone()
