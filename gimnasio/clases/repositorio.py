"""Consultas de clases y ocurrencias en bloques."""

from gimnasio.comun.ids import a_bytes


def zona_horaria(cursor):
    cursor.execute("SELECT zona_horaria FROM sedes ORDER BY id LIMIT 1")
    return cursor.fetchone()["zona_horaria"]


def clases_del_entrenador(cursor, entrenador_id):
    cursor.execute("SELECT * FROM clases WHERE entrenador_id=%s ORDER BY id FOR UPDATE", (a_bytes(entrenador_id),))
    return cursor.fetchall()


def entrenador_con_reservas_futuras(cursor, entrenador_id, ahora_local):
    cursor.execute(
        "SELECT r.id FROM clases c JOIN ocurrencias_clase o ON o.clase_id=c.id "
        "JOIN reservas r ON r.ocurrencia_id=o.id "
        "LEFT JOIN cancelaciones_reserva x ON x.reserva_id=r.id "
        "LEFT JOIN cancelaciones_ocurrencia co ON co.ocurrencia_id=o.id "
        "WHERE c.entrenador_id=%s AND TIMESTAMP(o.fecha,o.hora_inicio)>%s "
        "AND x.id IS NULL AND co.id IS NULL LIMIT 1 FOR UPDATE",
        (a_bytes(entrenador_id), ahora_local),
    )
    return cursor.fetchone() is not None


def reservas_para_baja(cursor, socio_id):
    cursor.execute(
        "SELECT r.*, o.clase_id, o.fecha, o.hora_inicio FROM reservas r "
        "JOIN ocurrencias_clase o ON o.id=r.ocurrencia_id "
        "LEFT JOIN cancelaciones_reserva x ON x.reserva_id=r.id "
        "WHERE r.socio_id=%s AND x.id IS NULL ORDER BY o.clase_id,o.fecha,r.id FOR UPDATE",
        (a_bytes(socio_id),),
    )
    return cursor.fetchall()


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
    cursor.execute("SELECT * FROM clases WHERE id=%s FOR UPDATE", (a_bytes(identificador),))
    return cursor.fetchone()


def ocurrencias(cursor, desde, hasta):
    cursor.execute(
        "SELECT o.*, COALESCE(co.cupo,c.cupo) AS cupo, x.id IS NOT NULL AS cancelada "
        "FROM ocurrencias_clase o JOIN clases c ON c.id=o.clase_id "
        "LEFT JOIN cupos_ocurrencia co ON co.ocurrencia_id=o.id "
        "LEFT JOIN cancelaciones_ocurrencia x ON x.ocurrencia_id=o.id "
        "WHERE o.fecha BETWEEN %s AND %s",
        (desde, hasta),
    )
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


def clase_para_reserva(cursor, clase_id):
    cursor.execute("SELECT * FROM clases WHERE id=%s FOR UPDATE", (a_bytes(clase_id),))
    return cursor.fetchone()


def ocurrencia_para_reserva(cursor, clase_id, fecha):
    cursor.execute(
        "SELECT o.*, COALESCE(co.cupo,c.cupo) AS cupo, co.id AS cupo_id, x.id IS NOT NULL AS cancelada "
        "FROM ocurrencias_clase o JOIN clases c ON c.id=o.clase_id "
        "LEFT JOIN cupos_ocurrencia co ON co.ocurrencia_id=o.id "
        "LEFT JOIN cancelaciones_ocurrencia x ON x.ocurrencia_id=o.id "
        "WHERE o.clase_id=%s AND o.fecha=%s FOR UPDATE",
        (a_bytes(clase_id), fecha),
    )
    return cursor.fetchone()


def fijar_ocurrencia(cursor, ocurrencia_id, clase, fecha, ahora):
    cursor.execute(
        "INSERT INTO ocurrencias_clase (id,clase_id,fecha,hora_inicio,duracion_minutos,creada_en) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (a_bytes(ocurrencia_id), clase["id"], fecha, clase["hora_inicio"], clase["duracion_minutos"], ahora),
    )


def reservas_en_rango(cursor, desde, hasta):
    cursor.execute(
        "SELECT r.*, o.clase_id, o.fecha FROM reservas r "
        "JOIN ocurrencias_clase o ON o.id=r.ocurrencia_id "
        "LEFT JOIN cancelaciones_reserva x ON x.reserva_id=r.id "
        "WHERE o.fecha BETWEEN %s AND %s AND x.id IS NULL ORDER BY r.solicitada_en,r.id",
        (desde, hasta),
    )
    return cursor.fetchall()


def reservas_del_socio(cursor, socio_id):
    # La primera lectura consistente se abre después de bloquear socio y clase.
    cursor.execute(
        "SELECT r.*, o.fecha, o.hora_inicio, o.duracion_minutos FROM reservas r "
        "JOIN ocurrencias_clase o ON o.id=r.ocurrencia_id "
        "LEFT JOIN cancelaciones_reserva x ON x.reserva_id=r.id "
        "WHERE r.socio_id=%s AND x.id IS NULL",
        (a_bytes(socio_id),),
    )
    return cursor.fetchall()


def insertar_reserva(cursor, reserva_id, ocurrencia_id, socio_id, ahora, autor_id):
    cursor.execute(
        "INSERT INTO reservas (id,ocurrencia_id,socio_id,solicitada_en,autor_id) VALUES (%s,%s,%s,%s,%s)",
        (a_bytes(reserva_id), ocurrencia_id, a_bytes(socio_id), ahora, a_bytes(autor_id)),
    )


def obtener_reserva(cursor, reserva_id):
    cursor.execute(
        "SELECT r.*, o.clase_id, o.fecha FROM reservas r "
        "JOIN ocurrencias_clase o ON o.id=r.ocurrencia_id WHERE r.id=%s",
        (a_bytes(reserva_id),),
    )
    return cursor.fetchone()


def cancelacion(cursor, reserva_id):
    cursor.execute("SELECT id FROM cancelaciones_reserva WHERE reserva_id=%s FOR UPDATE", (a_bytes(reserva_id),))
    return cursor.fetchone()


def cancelar_reserva(cursor, cancelacion_id, reserva_id, autor_id, ahora):
    cursor.execute(
        "INSERT INTO cancelaciones_reserva (id,reserva_id,autor_id,registrado_en) VALUES (%s,%s,%s,%s)",
        (a_bytes(cancelacion_id), a_bytes(reserva_id), a_bytes(autor_id), ahora),
    )


def lista_reservas(cursor, clase_id, fecha):
    cursor.execute(
        "SELECT r.id,r.solicitada_en,p.nombre,COALESCE(co.cupo,c.cupo) AS cupo FROM reservas r "
        "JOIN ocurrencias_clase o ON o.id=r.ocurrencia_id "
        "JOIN clases c ON c.id=o.clase_id LEFT JOIN cupos_ocurrencia co ON co.ocurrencia_id=o.id "
        "JOIN usuarios u ON u.id=r.socio_id JOIN personas p ON p.id=u.persona_id "
        "LEFT JOIN cancelaciones_reserva x ON x.reserva_id=r.id "
        "WHERE o.clase_id=%s AND o.fecha=%s AND x.id IS NULL ORDER BY r.solicitada_en,r.id",
        (a_bytes(clase_id), fecha),
    )
    return cursor.fetchall()


def reservas_ocurrencia(cursor, ocurrencia_id):
    cursor.execute(
        "SELECT r.* FROM reservas r LEFT JOIN cancelaciones_reserva x ON x.reserva_id=r.id "
        "WHERE r.ocurrencia_id=%s AND x.id IS NULL ORDER BY r.solicitada_en,r.id FOR UPDATE",
        (ocurrencia_id,),
    )
    return cursor.fetchall()


def ocurrencias_de_clase(cursor, clase_id):
    cursor.execute(
        "SELECT o.*, COALESCE(co.cupo,c.cupo) AS cupo, co.id AS cupo_id, x.id IS NOT NULL AS cancelada "
        "FROM ocurrencias_clase o JOIN clases c ON c.id=o.clase_id "
        "LEFT JOIN cupos_ocurrencia co ON co.ocurrencia_id=o.id "
        "LEFT JOIN cancelaciones_ocurrencia x ON x.ocurrencia_id=o.id "
        "WHERE o.clase_id=%s ORDER BY o.fecha,o.id FOR UPDATE",
        (a_bytes(clase_id),),
    )
    return cursor.fetchall()


def fijar_cupo(cursor, identificador, ocurrencia_id, cupo, ahora):
    cursor.execute(
        "INSERT INTO cupos_ocurrencia (id,ocurrencia_id,cupo,registrado_en) VALUES (%s,%s,%s,%s)",
        (a_bytes(identificador), ocurrencia_id, cupo, ahora),
    )


def insertar_aviso(cursor, identificador, socio_id, ocurrencia_id, tipo, ahora):
    cursor.execute(
        "INSERT INTO avisos_socio (id,socio_id,ocurrencia_id,tipo,registrado_en) VALUES (%s,%s,%s,%s,%s)",
        (a_bytes(identificador), socio_id, ocurrencia_id, tipo, ahora),
    )


def cancelar_ocurrencia(cursor, identificador, ocurrencia_id, motivo, autor_id, ahora):
    cursor.execute(
        "INSERT INTO cancelaciones_ocurrencia (id,ocurrencia_id,motivo,autor_id,registrado_en) VALUES (%s,%s,%s,%s,%s)",
        (a_bytes(identificador), ocurrencia_id, motivo, a_bytes(autor_id), ahora),
    )


def avisos_sin_ver(cursor, socio_id):
    cursor.execute(
        "SELECT a.*,c.nombre AS clase,o.fecha,o.hora_inicio,COALESCE(co.cupo,c.cupo) AS cupo "
        "FROM avisos_socio a JOIN ocurrencias_clase o ON o.id=a.ocurrencia_id "
        "JOIN clases c ON c.id=o.clase_id LEFT JOIN cupos_ocurrencia co ON co.ocurrencia_id=o.id "
        "LEFT JOIN vistos_aviso_socio v ON v.aviso_id=a.id "
        "WHERE a.socio_id=%s AND v.id IS NULL ORDER BY a.registrado_en,a.id",
        (a_bytes(socio_id),),
    )
    return cursor.fetchall()


def aviso_propio(cursor, aviso_id, socio_id):
    cursor.execute(
        "SELECT id FROM avisos_socio WHERE id=%s AND socio_id=%s FOR UPDATE",
        (a_bytes(aviso_id), a_bytes(socio_id)),
    )
    return cursor.fetchone()


def marcar_aviso(cursor, identificador, aviso_id, ahora):
    cursor.execute(
        "INSERT INTO vistos_aviso_socio (id,aviso_id,registrado_en) "
        "SELECT %s,%s,%s WHERE NOT EXISTS (SELECT 1 FROM vistos_aviso_socio WHERE aviso_id=%s)",
        (a_bytes(identificador), a_bytes(aviso_id), ahora, a_bytes(aviso_id)),
    )
