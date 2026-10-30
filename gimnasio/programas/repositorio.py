"""Programas y catálogo; las alternativas se reemplazan y los cambios de estado se insertan."""

from gimnasio.comun.ids import a_bytes


def leer_ejercicios(cursor):
    cursor.execute(
        """SELECT e.id, e.nombre, e.medidas_aplicables, e.patron_movimiento, e.equipo, e.incremento_carga,
                  COALESCE((SELECT JSON_ARRAYAGG(z.zona) FROM zonas_ejercicio z
                            WHERE z.ejercicio_id=e.id), JSON_ARRAY()) AS zonas
           FROM ejercicios e ORDER BY e.nombre, e.id"""
    )
    return cursor.fetchall()


def leer_alternativas(cursor):
    cursor.execute("SELECT ejercicio_id, alternativa_id FROM alternativas_ejercicio ORDER BY ejercicio_id, orden")
    return cursor.fetchall()


def bloquear_ejercicio(cursor, ejercicio_id):
    cursor.execute("SELECT id FROM ejercicios WHERE id=%s FOR UPDATE", (a_bytes(ejercicio_id),))
    return cursor.fetchone()


def reemplazar_alternativas(cursor, ejercicio_id, alternativas):
    cursor.execute("DELETE FROM alternativas_ejercicio WHERE ejercicio_id=%s", (a_bytes(ejercicio_id),))
    for orden, alternativa in enumerate(alternativas, start=1):
        cursor.execute(
            "INSERT INTO alternativas_ejercicio (ejercicio_id, alternativa_id, orden) VALUES (%s,%s,%s)",
            (a_bytes(ejercicio_id), a_bytes(alternativa), orden),
        )


def leer_equipos(cursor, equipo_id=None, *, momento=None):
    filtro = " WHERE e.id = %s" if equipo_id is not None else ""
    hasta = " AND registrado_en <= %s" if momento is not None else ""
    parametros = (momento,) if momento is not None else ()
    if equipo_id is not None:
        parametros += (a_bytes(equipo_id),)
    cursor.execute(
        """SELECT e.id, e.nombre, COALESCE(c.estado, 'disponible') AS estado,
                  c.registrado_en AS ultimo_cambio, c.autor_id, c.motivo
           FROM equipos e LEFT JOIN cambios_estado_equipo c ON c.id = (
               SELECT id FROM cambios_estado_equipo WHERE equipo_id = e.id"""
        + hasta
        + " ORDER BY registrado_en DESC, id DESC LIMIT 1)"
        + filtro
        + " ORDER BY e.nombre",
        parametros,
    )
    return cursor.fetchall()


def bloquear_equipo(cursor, equipo_id):
    cursor.execute("SELECT id FROM equipos WHERE id = %s FOR UPDATE", (a_bytes(equipo_id),))
    return cursor.fetchone()


def leer_equipos_en_momentos(cursor, momentos):
    cursor.execute(
        "WITH momentos AS ("
        + " UNION ".join("SELECT CAST(%s AS DATETIME(6)) AS momento" for _ in momentos)
        + """
        ) SELECT m.momento, e.nombre FROM momentos m CROSS JOIN equipos e
          JOIN cambios_estado_equipo c ON c.id=(
              SELECT id FROM cambios_estado_equipo WHERE equipo_id=e.id AND registrado_en<=m.momento
              ORDER BY registrado_en DESC,id DESC LIMIT 1)
          WHERE c.estado='fuera_de_servicio' AND e.nombre NOT IN ('','sin equipo')""",
        tuple(momentos),
    )
    return cursor.fetchall()


def insertar_cambio_estado(cursor, cambio_id, equipo_id, estado, motivo, autor_id, momento):
    cursor.execute(
        """INSERT INTO cambios_estado_equipo (id, equipo_id, estado, motivo, autor_id, registrado_en)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (a_bytes(cambio_id), a_bytes(equipo_id), estado, motivo, a_bytes(autor_id), momento),
    )


def leer_por_socio(cursor, socio_id, version=None):
    """Una consulta conserva la misma lectura para programas, sesiones y ejercicios."""
    filtro = "" if version is None else " AND p.version = %s"
    parametros = (a_bytes(socio_id),) if version is None else (a_bytes(socio_id), version)
    cursor.execute(
        """SELECT p.id AS programa_id, p.socio_id, p.version, p.creado_en,
                  s.id AS sesion_id, s.posicion AS sesion_posicion, s.nombre AS sesion_nombre,
                  ep.id AS planificado_id, ep.posicion AS ejercicio_posicion,
                  ep.series, ep.repeticiones_minimas, ep.repeticiones_maximas, ep.rir_objetivo, ep.descanso,
                  ep.carga, ep.duracion, ep.distancia,
                  e.id AS ejercicio_id, e.nombre AS ejercicio_nombre, e.medidas_aplicables,
                  e.patron_movimiento, e.equipo, e.incremento_carga,
                  COALESCE((SELECT JSON_ARRAYAGG(z.zona) FROM zonas_ejercicio z
                            WHERE z.ejercicio_id = e.id), JSON_ARRAY()) AS zonas,
                  COALESCE((SELECT JSON_ARRAYAGG(JSON_OBJECT(
                      'ejercicio_id', LOWER(BIN_TO_UUID(a.alternativa_id)), 'orden', a.orden,
                      'nombre', alternativa.nombre, 'equipo', alternativa.equipo))
                      FROM alternativas_ejercicio a JOIN ejercicios alternativa ON alternativa.id = a.alternativa_id
                      WHERE a.ejercicio_id = e.id), JSON_ARRAY()) AS alternativas
           FROM programas_entrenamiento p
           LEFT JOIN sesiones_planificadas s ON s.programa_id = p.id
           LEFT JOIN ejercicios_planificados ep ON ep.sesion_planificada_id = s.id
           LEFT JOIN ejercicios e ON e.id = ep.ejercicio_id
           WHERE p.socio_id = %s"""
        + filtro
        + " ORDER BY p.version, s.posicion, ep.posicion",
        parametros,
    )
    return cursor.fetchall()
