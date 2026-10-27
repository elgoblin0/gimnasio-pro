"""SQL del módulo permisos. Recibe un cursor de diccionarios abierto por el servicio."""

from gimnasio.comun.ids import a_bytes

COLUMNAS_USUARIO = """
    u.id, u.rol, u.clave_hash, u.es_demo, u.activo,
    p.id AS persona_id, p.nombre, p.apellido, p.cedula, p.correo
"""


def buscar_para_ingreso(cursor, cedula=None, correo=None):
    """Busca por cédula o correo y bloquea la fila del usuario hasta el fin de la transacción.

    Debe ser la primera lectura de la transacción: así dos ingresos simultáneos del mismo usuario se
    serializan y el segundo ve los intentos que registró el primero (InnoDB, REPEATABLE READ).
    """
    columna, valor = ("p.cedula", cedula) if cedula is not None else ("p.correo", correo)
    cursor.execute(
        f"SELECT {COLUMNAS_USUARIO} FROM usuarios u JOIN personas p ON p.id = u.persona_id "
        f"WHERE {columna} = %s FOR UPDATE",
        (valor,),
    )
    return cursor.fetchone()


def buscar_por_id(cursor, usuario_id):
    cursor.execute(
        f"SELECT {COLUMNAS_USUARIO} FROM usuarios u JOIN personas p ON p.id = u.persona_id WHERE u.id = %s",
        (a_bytes(usuario_id),),
    )
    return cursor.fetchone()


def primer_usuario_demo(cursor, rol):
    cursor.execute(
        f"""SELECT {COLUMNAS_USUARIO} FROM usuarios u JOIN personas p ON p.id = u.persona_id
            WHERE u.es_demo = TRUE AND u.activo = TRUE AND u.rol = %s
            ORDER BY u.creado_en, u.id LIMIT 1""",
        (rol,),
    )
    return cursor.fetchone()


def insertar_persona(cursor, persona_id, datos, momento):
    cursor.execute(
        """INSERT INTO personas
           (id, nombre, apellido, cedula, telefono, correo, fecha_nacimiento, creada_en, actualizada_en)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            a_bytes(persona_id),
            datos["nombre"],
            datos["apellido"],
            datos["cedula"],
            datos.get("telefono"),
            datos.get("correo"),
            datos.get("fecha_nacimiento"),
            momento,
            momento,
        ),
    )


def insertar_usuario(cursor, usuario_id, persona_id, rol, clave_hash, es_demo, momento):
    cursor.execute(
        """INSERT INTO usuarios (id, persona_id, rol, clave_hash, es_demo, activo, creado_en, actualizado_en)
           VALUES (%s, %s, %s, %s, %s, TRUE, %s, %s)""",
        (a_bytes(usuario_id), a_bytes(persona_id), rol, clave_hash, es_demo, momento, momento),
    )


def insertar_intento(cursor, intento_id, usuario_id, identificador, ip, exitoso, momento):
    cursor.execute(
        """INSERT INTO intentos_de_ingreso (id, usuario_id, identificador, ip, exitoso, ocurrido_en)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (a_bytes(intento_id), usuario_id, identificador, ip, exitoso, momento),
    )


def contar_fallidos_desde(cursor, usuario_id, identificador, ip, desde):
    """Fallidos de la cuenta (por usuario si existe, si no por identificador) y de la IP desde `desde`."""
    if usuario_id is not None:
        filtro, valor = "usuario_id = %s", usuario_id
    else:
        filtro, valor = "usuario_id IS NULL AND identificador = %s", identificador
    cursor.execute(
        "SELECT COUNT(*) AS cantidad FROM intentos_de_ingreso "
        f"WHERE exitoso = FALSE AND ocurrido_en >= %s AND {filtro}",
        (desde, valor),
    )
    por_cuenta = cursor.fetchone()["cantidad"]
    cursor.execute(
        "SELECT COUNT(*) AS cantidad FROM intentos_de_ingreso WHERE exitoso = FALSE AND ocurrido_en >= %s AND ip = %s",
        (desde, ip),
    )
    return int(por_cuenta), int(cursor.fetchone()["cantidad"])


def insertar_consentimiento(cursor, consentimiento_id, socio_id, tipo, version_texto, otorgado, autor_id, momento):
    cursor.execute(
        """INSERT INTO consentimientos
           (id, socio_id, tipo, version_texto, otorgado, registrado_por, registrado_en)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (a_bytes(consentimiento_id), a_bytes(socio_id), tipo, version_texto, otorgado, a_bytes(autor_id), momento),
    )


def consentimiento_vigente(cursor, socio_id, tipo):
    cursor.execute(
        """SELECT otorgado, version_texto FROM consentimientos
           WHERE socio_id = %s AND tipo = %s
           ORDER BY registrado_en DESC, id DESC LIMIT 1""",
        (a_bytes(socio_id), tipo),
    )
    return cursor.fetchone()


def tiene_asignacion_vigente(cursor, socio_id, entrenador_id):
    cursor.execute(
        """SELECT 1 AS vigente FROM asignaciones_entrenador a
           JOIN usuarios s ON s.id = a.socio_id AND s.rol = 'socio' AND s.activo = TRUE
           JOIN usuarios e ON e.id = a.entrenador_id AND e.rol = 'entrenador' AND e.activo = TRUE
           WHERE a.socio_id = %s AND a.entrenador_id = %s AND a.hasta IS NULL
           LIMIT 1""",
        (a_bytes(socio_id), a_bytes(entrenador_id)),
    )
    return cursor.fetchone() is not None


def adquirir_candado(cursor, nombre, segundos):
    cursor.execute("SELECT GET_LOCK(%s, %s) AS obtenido", (nombre, segundos))
    return cursor.fetchone()["obtenido"] == 1


def liberar_candado(cursor, nombre):
    cursor.execute("SELECT RELEASE_LOCK(%s) AS liberado", (nombre,))
    cursor.fetchone()
