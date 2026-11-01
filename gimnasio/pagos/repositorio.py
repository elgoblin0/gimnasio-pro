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


def obtener_pago(cursor, pago_id):
    cursor.execute("SELECT * FROM pagos WHERE id=%s", (a_bytes(pago_id),))
    return cursor.fetchone()


def ultimo_pago(cursor, socio_id):
    # El JOIN bloqueado ve anulaciones confirmadas mientras se esperaba al socio.
    # Una subconsulta sin bloqueo conservaría la lectura anterior en REPEATABLE READ.
    cursor.execute(
        """SELECT p.id FROM pagos p LEFT JOIN anulaciones_pago a ON a.pago_id=p.id
        WHERE p.socio_id=%s AND a.id IS NULL
        ORDER BY p.registrado_en DESC, p.id DESC LIMIT 1 FOR UPDATE""",
        (a_bytes(socio_id),),
    )
    return cursor.fetchone()


def insertar_anulacion(cursor, identificador, pago_id, motivo, autor_id, ahora):
    cursor.execute(
        """INSERT INTO anulaciones_pago (id,pago_id,motivo,autor_id,registrado_en)
        VALUES (%s,%s,%s,%s,%s)""",
        (a_bytes(identificador), a_bytes(pago_id), motivo, a_bytes(autor_id), ahora),
    )


def listar_pagos(cursor, desde=None, hasta=None, socio_id=None):
    condiciones, parametros = [], []
    if socio_id is not None:
        condiciones.append("p.socio_id=%s")
        parametros.append(a_bytes(socio_id))
    if desde is not None:
        condiciones.append("p.registrado_en >= %s AND p.registrado_en < %s")
        parametros.extend((desde, hasta))
    cursor.execute(
        """SELECT p.*, CONCAT(s.nombre, ' ', s.apellido) AS socio,
        t.nombre AS tipo, CONCAT(u.nombre, ' ', u.apellido) AS autor,
        a.id AS anulacion_id, a.motivo, a.autor_id AS anulacion_autor_id,
        a.registrado_en AS anulada_en
        FROM pagos p JOIN usuarios us ON us.id=p.socio_id JOIN personas s ON s.id=us.persona_id
        JOIN tipos_membresia t ON t.id=p.tipo_id
        JOIN usuarios ua ON ua.id=p.autor_id JOIN personas u ON u.id=ua.persona_id
        LEFT JOIN anulaciones_pago a ON a.pago_id=p.id"""
        + (" WHERE " + " AND ".join(condiciones) if condiciones else "")
        + " ORDER BY p.registrado_en DESC, p.id DESC",
        tuple(parametros),
    )
    return cursor.fetchall()
