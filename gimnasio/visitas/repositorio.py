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
    cursor.execute("SELECT * FROM entradas WHERE id = %s", (a_bytes(entrada_id),))
    return cursor.fetchone()


def tiene_visita_abierta(cursor, socio_id):
    cursor.execute(
        _ESTADOS_VIGENTES + "SELECT COUNT(*) AS cantidad FROM estados_vigentes WHERE socio_id = %s AND abierta = TRUE",
        (a_bytes(socio_id),),
    )
    return cursor.fetchone()["cantidad"] > 0
