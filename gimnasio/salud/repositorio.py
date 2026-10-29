"""Lectura de restricciones de salud que no tienen un registro de baja."""

from gimnasio.comun.ids import a_bytes


def restricciones_vigentes(cursor, socio_id):
    cursor.execute(
        """SELECT r.* FROM restricciones_salud r
           WHERE r.socio_id=%s AND r.levanta_a IS NULL
             AND NOT EXISTS (SELECT 1 FROM restricciones_salud baja WHERE baja.levanta_a=r.id)
           ORDER BY r.registrada_en,r.id""",
        (a_bytes(socio_id),),
    )
    return cursor.fetchall()
