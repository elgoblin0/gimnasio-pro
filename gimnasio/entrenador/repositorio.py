"""Constancias de avisos revisados: solo inserciones."""

from datetime import UTC

from gimnasio.comun.ids import a_bytes


def listar_revisiones(cursor, aviso_ids, *, actual=False):
    if not aviso_ids:
        return []
    lugares = ",".join(["%s"] * len(aviso_ids))
    cursor.execute(
        f"SELECT * FROM revisiones_aviso WHERE aviso_id IN ({lugares})" + (" FOR SHARE" if actual else ""),
        tuple(a_bytes(identificador) for identificador in aviso_ids),
    )
    return cursor.fetchall()


def insertar_revision(cursor, identificador, aviso_id, entrenador_id, nota, ahora):
    cursor.execute(
        """INSERT INTO revisiones_aviso (id,aviso_id,entrenador_id,nota,revisada_en)
           VALUES (%s,%s,%s,%s,%s)""",
        (
            a_bytes(identificador),
            a_bytes(aviso_id),
            a_bytes(entrenador_id),
            nota,
            ahora.astimezone(UTC).replace(tzinfo=None),
        ),
    )


def fecha_asignacion_vigente(cursor, socio_id, entrenador_id):
    cursor.execute(
        """SELECT MIN(desde) AS desde FROM asignaciones_entrenador
           WHERE socio_id=%s AND entrenador_id=%s AND hasta IS NULL""",
        (a_bytes(socio_id), a_bytes(entrenador_id)),
    )
    return cursor.fetchone()["desde"]
