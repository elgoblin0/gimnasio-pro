"""Lectura e inserción de membresías, sin datos de salud ni tablas heredadas."""

from gimnasio.comun.ids import a_bytes

CAMPOS_PERSONALES = ("nombre", "apellido", "cedula", "telefono", "correo", "fecha_nacimiento")
CAMPOS_PERFIL = ("objetivo", "experiencia", "disponibilidad_semanal", "tiempo_por_sesion", "preferencias")


def buscar_datos_personales(cursor, socio_id, *, bloquear=False):
    cursor.execute(
        "SELECT p.id, p.nombre, p.apellido, p.cedula, p.telefono, p.correo, p.fecha_nacimiento "
        "FROM usuarios u JOIN personas p ON p.id=u.persona_id "
        "WHERE u.id=%s AND u.rol='socio' AND u.activo=TRUE" + (" FOR UPDATE" if bloquear else ""),
        (a_bytes(socio_id),),
    )
    return cursor.fetchone()


def actualizar_datos_personales(cursor, persona_id, datos, momento):
    # Los nombres de columnas salen exclusivamente de esta lista, nunca de la solicitud.
    campos = [campo for campo in CAMPOS_PERSONALES if campo in datos]
    if not campos:
        return
    cursor.execute(
        "UPDATE personas SET " + ", ".join(f"{campo}=%s" for campo in campos) + ", actualizada_en=%s WHERE id=%s",
        (*[datos[campo] for campo in campos], momento, persona_id),
    )


def buscar_perfil_entrenamiento(cursor, socio_id, *, bloquear=False):
    cursor.execute(
        "SELECT objetivo, experiencia, disponibilidad_semanal, tiempo_por_sesion, preferencias "
        "FROM perfiles_entrenamiento WHERE socio_id=%s" + (" FOR UPDATE" if bloquear else ""),
        (a_bytes(socio_id),),
    )
    return cursor.fetchone() or dict.fromkeys(CAMPOS_PERFIL)


def guardar_perfil_entrenamiento(cursor, socio_id, perfil, momento, autor_id):
    cursor.execute(
        """INSERT INTO perfiles_entrenamiento
        (socio_id,objetivo,experiencia,disponibilidad_semanal,tiempo_por_sesion,preferencias,actualizado_en,actualizado_por)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE
        objetivo=VALUES(objetivo), experiencia=VALUES(experiencia),
        disponibilidad_semanal=VALUES(disponibilidad_semanal), tiempo_por_sesion=VALUES(tiempo_por_sesion),
        preferencias=VALUES(preferencias), actualizado_en=VALUES(actualizado_en),
        actualizado_por=VALUES(actualizado_por)""",
        (a_bytes(socio_id), *[perfil[campo] for campo in CAMPOS_PERFIL], momento, a_bytes(autor_id)),
    )


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
