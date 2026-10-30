"""SQL de visitas; recibe el cursor de diccionarios y la transacción del servicio.

Los identificadores de entrada son UUIDv7. Las lecturas devuelven BINARY(16) y
fechas sin zona horaria en UTC, como los demás repositorios. No consulta el reloj.
"""

from datetime import UTC

from mysql.connector import IntegrityError, errorcode

from gimnasio.comun.ids import a_bytes

# Cada cadena conserva su original. Se admiten correcciones de la original y de
# otras correcciones; fecha e id desempatan igual que en los consentimientos.
_ESTADOS_VIGENTES = """
WITH RECURSIVE
historial_entradas AS (
    SELECT id AS entrada_id, id FROM entradas WHERE corrige_a IS NULL
    UNION ALL
    SELECT h.entrada_id, e.id
    FROM entradas e JOIN historial_entradas h ON e.corrige_a = h.id
),
entradas_ordenadas AS (
    SELECT h.entrada_id, e.*,
           ROW_NUMBER() OVER (PARTITION BY h.entrada_id ORDER BY e.registrada_en DESC, e.id DESC) AS orden
    FROM historial_entradas h JOIN entradas e ON e.id = h.id
),
historial_salidas AS (
    SELECT id AS salida_original_id, id FROM salidas WHERE corrige_a IS NULL
    UNION ALL
    SELECT h.salida_original_id, s.id
    FROM salidas s JOIN historial_salidas h ON s.corrige_a = h.id
),
salidas_ordenadas AS (
    SELECT s.*,
           ROW_NUMBER() OVER (PARTITION BY h.salida_original_id ORDER BY s.registrada_en DESC, s.id DESC) AS orden
    FROM historial_salidas h JOIN salidas s ON s.id = h.id
),
salidas_confirmadas AS (
    SELECT h.entrada_id, s.id, s.registrada_en,
           ROW_NUMBER() OVER (PARTITION BY h.entrada_id ORDER BY s.registrada_en DESC, s.id DESC) AS orden_visita
    FROM salidas_ordenadas s JOIN historial_entradas h ON h.id = s.entrada_id
    WHERE s.orden = 1 AND s.anulada = FALSE
),
estados_vigentes AS (
    SELECT e.entrada_id, e.id AS registro_entrada_id, e.socio_id, e.sede_id,
           e.autor_id, e.registrada_en, e.corrige_a, e.motivo, e.anulada,
           s.id AS salida_id, s.registrada_en AS salida_registrada_en,
           (e.anulada = FALSE AND s.id IS NULL) AS abierta
    FROM entradas_ordenadas e
    LEFT JOIN salidas_confirmadas s ON s.entrada_id = e.entrada_id AND s.orden_visita = 1
    WHERE e.orden = 1
)
"""


def _fecha_utc(momento):
    if momento.utcoffset() is None:
        raise ValueError("La fecha debe incluir una zona horaria")
    return momento.astimezone(UTC).replace(tzinfo=None)


def _insertar(cursor, sql, parametros):
    """Repetir un id ya registrado es un éxito sin reescribir el hecho (ADR 0004)."""
    try:
        cursor.execute(sql, parametros)
    except IntegrityError as error:
        if error.errno != errorcode.ER_DUP_ENTRY:
            raise


def insertar_entrada(
    cursor, entrada_id, socio_id, sede_id, autor_id, registrada_en, *, corrige_a=None, motivo=None, anulada=False
):
    """Agrega una entrada o una corrección completa, con fecha explícita y sin commit."""
    _insertar(
        cursor,
        """INSERT INTO entradas (id, socio_id, sede_id, autor_id, registrada_en, corrige_a, motivo, anulada)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            a_bytes(entrada_id),
            a_bytes(socio_id),
            a_bytes(sede_id),
            a_bytes(autor_id),
            _fecha_utc(registrada_en),
            a_bytes(corrige_a) if corrige_a is not None else None,
            motivo,
            anulada,
        ),
    )


def insertar_salida(
    cursor, salida_id, entrada_id, autor_id, registrada_en, *, corrige_a=None, motivo=None, anulada=False
):
    """Agrega una salida confirmada o su corrección; nunca estima una salida ausente."""
    _insertar(
        cursor,
        """INSERT INTO salidas (id, entrada_id, autor_id, registrada_en, corrige_a, motivo, anulada)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (
            a_bytes(salida_id),
            a_bytes(entrada_id),
            a_bytes(autor_id),
            _fecha_utc(registrada_en),
            a_bytes(corrige_a) if corrige_a is not None else None,
            motivo,
            anulada,
        ),
    )


def obtener_estado_vigente(cursor, entrada_id):
    """Estado de la visita identificada por su entrada original, o None si no existe.

    `registro_entrada_id` identifica la última versión, incluso anulada. `salida_id`
    es la última salida vigente sin anular, o None; una entrada anulada no está abierta.
    """
    cursor.execute(
        _ESTADOS_VIGENTES + "SELECT * FROM estados_vigentes WHERE entrada_id = %s",
        (a_bytes(entrada_id),),
    )
    return cursor.fetchone()


def contar_ocupacion_registrada(cursor, sede_id):
    """Cuenta visitas abiertas de la sede vigente; no depende de sesiones realizadas."""
    cursor.execute(
        _ESTADOS_VIGENTES + "SELECT COUNT(*) AS cantidad FROM estados_vigentes WHERE sede_id = %s AND abierta = TRUE",
        (a_bytes(sede_id),),
    )
    return int(cursor.fetchone()["cantidad"])


def bloquear_sede(cursor, sede_id):
    cursor.execute("SELECT * FROM sedes WHERE id = %s FOR UPDATE", (a_bytes(sede_id),))
    return cursor.fetchone()


def bloquear_socio(cursor, socio_id):
    cursor.execute("SELECT id, rol, activo FROM usuarios WHERE id = %s FOR UPDATE", (a_bytes(socio_id),))
    return cursor.fetchone()


def obtener_entrada(cursor, entrada_id):
    # Referencia inmutable: lectura actual sin abrir un snapshot antes del candado de sede.
    # El candado compartido nunca se promueve; los exclusivos conservan sede → socio.
    cursor.execute("SELECT * FROM entradas WHERE id = %s FOR SHARE", (a_bytes(entrada_id),))
    return cursor.fetchone()


def tiene_visita_abierta(cursor, socio_id):
    cursor.execute(
        _ESTADOS_VIGENTES + "SELECT COUNT(*) AS cantidad FROM estados_vigentes WHERE socio_id = %s AND abierta = TRUE",
        (a_bytes(socio_id),),
    )
    return cursor.fetchone()["cantidad"] > 0


def obtener_salida(cursor, salida_id):
    cursor.execute("SELECT * FROM salidas WHERE id = %s FOR SHARE", (a_bytes(salida_id),))
    return cursor.fetchone()


def listar_visitas_abiertas(cursor):
    cursor.execute(
        _ESTADOS_VIGENTES
        + """SELECT v.*, CONCAT(p.nombre, ' ', p.apellido) AS nombre, p.cedula,
                                     s.zona_horaria
                              FROM estados_vigentes v
                              JOIN usuarios u ON u.id = v.socio_id
                              JOIN personas p ON p.id = u.persona_id
                              JOIN sedes s ON s.id = v.sede_id
                              WHERE v.abierta = TRUE
                              ORDER BY v.registrada_en, v.entrada_id"""
    )
    return cursor.fetchall()


def obtener_sede(cursor):
    cursor.execute("SELECT id, aforo_maximo, zona_horaria, horario FROM sedes ORDER BY id LIMIT 1")
    return cursor.fetchone()


def listar_socios_activos(cursor):
    cursor.execute(
        """SELECT u.id, CONCAT(p.nombre, ' ', p.apellido) AS nombre, p.cedula
           FROM usuarios u JOIN personas p ON p.id = u.persona_id
           WHERE u.rol = 'socio' AND u.activo = TRUE ORDER BY p.nombre, p.apellido, u.id"""
    )
    return cursor.fetchall()


def buscar_socio_para_tarjeta(cursor, socio_id):
    cursor.execute(
        """SELECT u.id, p.nombre, p.apellido, p.cedula
           FROM usuarios u JOIN personas p ON p.id = u.persona_id
           WHERE u.id = %s AND u.rol = 'socio'""",
        (a_bytes(socio_id),),
    )
    return cursor.fetchone()


def listar_visitas_del_socio(cursor, socio_id, hasta):
    cursor.execute(
        _ESTADOS_VIGENTES
        + """SELECT entrada_id, registrada_en, salida_registrada_en, abierta
             FROM estados_vigentes WHERE socio_id = %s AND anulada = FALSE
             AND registrada_en <= %s ORDER BY registrada_en DESC, entrada_id DESC""",
        (a_bytes(socio_id), _fecha_utc(hasta)),
    )
    return cursor.fetchall()


def listar_duraciones_confiables(cursor, sede_id, desde, hasta, socio_id=None):
    """Entrada y salida vigentes de las últimas ocho semanas, sin anulaciones.

    Solo confirmadas o corregidas: el modelo actual no registra estimadas.
    Al incorporarlas se debe conservar explícitamente su exclusión aquí.
    """
    filtro_socio = " AND socio_id = %s" if socio_id is not None else ""
    parametros = (a_bytes(sede_id), _fecha_utc(desde), _fecha_utc(hasta), _fecha_utc(hasta))
    if socio_id is not None:
        parametros += (a_bytes(socio_id),)
    cursor.execute(
        _ESTADOS_VIGENTES
        + """SELECT socio_id, TIMESTAMPDIFF(MINUTE, registrada_en, salida_registrada_en) AS minutos
             FROM estados_vigentes
             WHERE sede_id = %s AND anulada = FALSE AND salida_id IS NOT NULL
               AND registrada_en >= %s AND registrada_en <= %s
               AND salida_registrada_en <= %s AND salida_registrada_en >= registrada_en"""
        + filtro_socio,
        parametros,
    )
    return cursor.fetchall()


def obtener_version(cursor, ahora):
    """Cuenta todos los hechos, incluidas correcciones con fechas anteriores."""
    cursor.execute(
        "SELECT (SELECT COUNT(*) FROM entradas) + (SELECT COUNT(*) FROM salidas) "
        "+ (SELECT COUNT(*) FROM series_realizadas) AS hechos, "
        "(SELECT aforo_maximo FROM sedes ORDER BY id LIMIT 1) AS aforo"
    )
    fila = cursor.fetchone()
    # El minuto invalida duraciones y visitas por conciliar aunque no haya hechos nuevos.
    return f"{fila['hechos']}-{fila['aforo']}-{int(ahora.timestamp()) // 60}"


def listar_series_para_ubicacion(cursor, ahora):
    """Resuelve correcciones antes de excluir anulaciones y series antiguas."""
    cursor.execute(
        """WITH RECURSIVE historial AS (
            SELECT id AS serie_original_id, id FROM series_realizadas WHERE corrige_a IS NULL
            UNION ALL
            SELECT h.serie_original_id, s.id FROM historial h
            JOIN series_realizadas s ON s.corrige_a = h.id
        ), ordenadas AS (
            SELECT s.*, ROW_NUMBER() OVER (
                PARTITION BY h.serie_original_id ORDER BY s.registrada_en DESC, s.id DESC
            ) AS orden
            FROM historial h JOIN series_realizadas s ON s.id = h.id
        )
        SELECT sr.socio_id, s.registrada_en, e.equipo FROM ordenadas s
        JOIN sesiones_realizadas sr ON sr.id = s.sesion_realizada_id
        JOIN ejercicios_planificados ep ON ep.id = s.ejercicio_planificado_id
        JOIN ejercicios e ON e.id = COALESCE(s.ejercicio_hecho_id, ep.ejercicio_id)
        WHERE s.orden = 1 AND s.anulada = FALSE
          AND s.registrada_en BETWEEN %s - INTERVAL 20 MINUTE AND %s
        ORDER BY s.registrada_en, s.id""",
        (_fecha_utc(ahora), _fecha_utc(ahora)),
    )
    return cursor.fetchall()


def listar_visitas_confiables(cursor, sede_id, desde, hasta):
    """Visitas vigentes cerradas que se superponen al rango; sin salidas estimadas."""
    cursor.execute(
        _ESTADOS_VIGENTES
        + """SELECT registrada_en, salida_registrada_en FROM estados_vigentes
             WHERE sede_id = %s AND anulada = FALSE AND salida_id IS NOT NULL
               AND registrada_en < %s AND salida_registrada_en > %s
               AND salida_registrada_en <= %s AND salida_registrada_en > registrada_en""",
        (a_bytes(sede_id), _fecha_utc(hasta), _fecha_utc(desde), _fecha_utc(hasta)),
    )
    return cursor.fetchall()
