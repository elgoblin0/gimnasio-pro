"""SQL del módulo permisos. Recibe un cursor de diccionarios abierto por el servicio."""

from gimnasio.comun.ids import a_bytes

COLUMNAS_USUARIO = """
    u.id, u.rol, u.clave_hash, u.es_demo, u.activo,
    p.id AS persona_id, p.nombre, p.apellido, p.cedula, p.correo
"""


def buscar_por_cedula(cursor, cedula):
    cursor.execute(
        f"SELECT {COLUMNAS_USUARIO} FROM usuarios u JOIN personas p ON p.id = u.persona_id WHERE p.cedula = %s",
        (cedula,),
    )
    return cursor.fetchone()


def buscar_por_correo(cursor, correo):
    cursor.execute(
        f"SELECT {COLUMNAS_USUARIO} FROM usuarios u JOIN personas p ON p.id = u.persona_id WHERE p.correo = %s",
        (correo,),
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


def insertar_intento(cursor, intento_id, identificador, ip, exitoso, momento):
    cursor.execute(
        "INSERT INTO intentos_de_ingreso (id, identificador, ip, exitoso, ocurrido_en) VALUES (%s, %s, %s, %s, %s)",
        (a_bytes(intento_id), identificador, ip, exitoso, momento),
    )


def contar_fallidos_desde(cursor, identificador, ip, desde):
    cursor.execute(
        """SELECT
             SUM(identificador = %s) AS por_identificador,
             SUM(ip = %s) AS por_ip
           FROM intentos_de_ingreso
           WHERE exitoso = FALSE AND ocurrido_en >= %s AND (identificador = %s OR ip = %s)""",
        (identificador, ip, desde, identificador, ip),
    )
    fila = cursor.fetchone()
    return int(fila["por_identificador"] or 0), int(fila["por_ip"] or 0)


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
