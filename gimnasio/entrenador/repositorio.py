"""Constancias de avisos revisados: solo inserciones."""

from datetime import UTC

from gimnasio.comun.ids import a_bytes, desde_bytes


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


def fechas_asignacion_vigente(cursor, socio_ids, entrenador_id):
    if not socio_ids:
        return {}
    lugares = ",".join(["%s"] * len(socio_ids))
    cursor.execute(
        f"""SELECT socio_id, MIN(desde) AS desde FROM asignaciones_entrenador
            WHERE socio_id IN ({lugares}) AND entrenador_id=%s AND hasta IS NULL
            GROUP BY socio_id""",
        (*(a_bytes(socio_id) for socio_id in socio_ids), a_bytes(entrenador_id)),
    )
    return {desde_bytes(fila["socio_id"]): fila["desde"] for fila in cursor.fetchall()}
