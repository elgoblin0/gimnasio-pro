"""Persistencia de hechos; recibe cursor y fechas explícitos, sin confirmar transacciones."""

import json
from datetime import UTC
from decimal import Decimal, InvalidOperation

from mysql.connector import IntegrityError, errorcode

from gimnasio.comun.ids import a_bytes

MEDIDAS = ("repeticiones", "carga", "duracion", "distancia")


def obtener_socio(cursor, socio_id):
    cursor.execute("SELECT id, rol, activo FROM usuarios WHERE id = %s", (a_bytes(socio_id),))
    return cursor.fetchone()


def obtener_sede(cursor):
    cursor.execute("SELECT zona_horaria FROM sedes ORDER BY id LIMIT 1")
    return cursor.fetchone()


def validar_medidas(medidas, valores):
    """Conserva kg/segundos/metros, rechaza no aplicables, no finitos y redondeos."""
    if not isinstance(medidas, list) or any(m not in MEDIDAS for m in medidas):
        raise ValueError("Las medidas aplicables del catálogo son inválidas.")
    resultado = {}
    for medida in MEDIDAS:
        valor = valores.get(medida)
        if medida not in medidas:
            if valor is not None:
                raise ValueError("Las medidas no aplicables deben ser nulas.")
            resultado[medida] = None
            continue
        if isinstance(valor, bool) or valor is None:
            raise ValueError("Faltan medidas aplicables válidas.")
        if medida in {"repeticiones", "duracion"}:
            if type(valor) is not int or not 0 < valor <= 2147483647:
                raise ValueError("Repeticiones y duración deben ser enteros positivos.")
        else:
            try:
                valor = Decimal(str(valor))
            except (InvalidOperation, ValueError) as error:
                raise ValueError("La medida decimal es inválida.") from error
            maximo = Decimal("999999.99") if medida == "carga" else Decimal("99999999.99")
            if not valor.is_finite() or valor < 0 or valor > maximo:
                raise ValueError("La medida decimal debe ser finita y estar dentro de rango.")
            if medida == "distancia" and valor == 0:
                raise ValueError("La distancia debe ser positiva.")
            if valor != valor.quantize(Decimal("0.01")):
                raise ValueError("La medida admite como máximo dos decimales.")
        resultado[medida] = valor
    return resultado


def _fecha_utc(momento):
    if momento.utcoffset() is None:
        raise ValueError("La fecha debe incluir una zona horaria.")
    return momento.astimezone(UTC).replace(tzinfo=None)


def _insertar(cursor, sql, parametros):
    try:
        cursor.execute(sql, parametros)
    except IntegrityError as error:
        if error.errno != errorcode.ER_DUP_ENTRY:
            raise


def insertar_sesion(cursor, sesion_id, socio_id, sesion_planificada_id, creada_en):
    cursor.execute(
        """SELECT p.socio_id FROM sesiones_planificadas s
           JOIN programas_entrenamiento p ON p.id = s.programa_id WHERE s.id = %s""",
        (a_bytes(sesion_planificada_id),),
    )
    fila = cursor.fetchone()
    if fila is None or fila["socio_id"] != a_bytes(socio_id):
        raise ValueError("La sesión planificada no pertenece al socio.")
    _insertar(
        cursor,
        "INSERT INTO sesiones_realizadas (id, socio_id, sesion_planificada_id, creada_en) VALUES (%s, %s, %s, %s)",
        (a_bytes(sesion_id), a_bytes(socio_id), a_bytes(sesion_planificada_id), _fecha_utc(creada_en)),
    )


def obtener_sesion(cursor, sesion_id, *, actual=False):
    cursor.execute(
        "SELECT * FROM sesiones_realizadas WHERE id = %s" + (" FOR SHARE" if actual else ""), (a_bytes(sesion_id),)
    )
    return cursor.fetchone()


def obtener_serie(cursor, serie_id, *, actual=False):
    cursor.execute(
        """SELECT s.*, COALESCE(s.ejercicio_hecho_id, ep.ejercicio_id) AS ejercicio_hecho_resuelto_id
           FROM series_realizadas s JOIN ejercicios_planificados ep ON ep.id = s.ejercicio_planificado_id
           WHERE s.id = %s"""
        + (" FOR SHARE" if actual else ""),
        (a_bytes(serie_id),),
    )
    return cursor.fetchone()


def obtener_planificada(cursor, planificada_id):
    cursor.execute(
        """SELECT s.id, p.socio_id FROM sesiones_planificadas s
           JOIN programas_entrenamiento p ON p.id = s.programa_id WHERE s.id = %s""",
        (a_bytes(planificada_id),),
    )
    return cursor.fetchone()


def obtener_ejercicio_planificado(cursor, ejercicio_id):
    cursor.execute(
        "SELECT id, sesion_planificada_id FROM ejercicios_planificados WHERE id = %s", (a_bytes(ejercicio_id),)
    )
    return cursor.fetchone()


def insertar_serie(
    cursor,
    serie_id,
    sesion_realizada_id,
    ejercicio_planificado_id,
    autor_id,
    registrada_en,
    *,
    repeticiones=None,
    carga=None,
    duracion=None,
    distancia=None,
    corrige_a=None,
    motivo=None,
    anulada=False,
    rir=None,
    ejercicio_hecho_id=None,
):
    cursor.execute(
        """SELECT e.medidas_aplicables FROM sesiones_realizadas sr
           JOIN ejercicios_planificados ep ON ep.sesion_planificada_id = sr.sesion_planificada_id
           JOIN ejercicios e ON e.id = ep.ejercicio_id WHERE sr.id = %s AND ep.id = %s""",
        (a_bytes(sesion_realizada_id), a_bytes(ejercicio_planificado_id)),
    )
    ejercicio = cursor.fetchone()
    if ejercicio is None:
        raise ValueError("El ejercicio planificado no pertenece a la sesión realizada.")
    if rir is not None and (type(rir) is not int or not 0 <= rir <= 10):
        raise ValueError("El RIR debe ser un entero entre 0 y 10.")
    valores = validar_medidas(
        json.loads(ejercicio["medidas_aplicables"]),
        {
            "repeticiones": repeticiones,
            "carga": carga,
            "duracion": duracion,
            "distancia": distancia,
        },
    )
    if corrige_a is not None:
        anterior = obtener_serie(cursor, corrige_a)
        if (
            anterior is None
            or anterior["sesion_realizada_id"] != a_bytes(sesion_realizada_id)
            or anterior["ejercicio_planificado_id"] != a_bytes(ejercicio_planificado_id)
        ):
            raise ValueError("La corrección debe conservar la sesión y el ejercicio planificado.")
    _insertar(
        cursor,
        """INSERT INTO series_realizadas
           (id, sesion_realizada_id, ejercicio_planificado_id, repeticiones, carga, duracion, distancia,
            autor_id, registrada_en, corrige_a, motivo, anulada, rir, ejercicio_hecho_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            a_bytes(serie_id),
            a_bytes(sesion_realizada_id),
            a_bytes(ejercicio_planificado_id),
            *(valores[m] for m in MEDIDAS),
            a_bytes(autor_id),
            _fecha_utc(registrada_en),
            a_bytes(corrige_a) if corrige_a is not None else None,
            motivo,
            anulada,
            rir,
            a_bytes(ejercicio_hecho_id) if ejercicio_hecho_id is not None else None,
        ),
    )


def listar_series_vigentes(cursor, socio_id, sesion_realizada_id=None):
    """Última corrección por serie original; una anulada no acredita trabajo."""
    filtro = "" if sesion_realizada_id is None else " AND sr.id = %s"
    parametros = (
        (a_bytes(socio_id),) if sesion_realizada_id is None else (a_bytes(socio_id), a_bytes(sesion_realizada_id))
    )
    cursor.execute(
        """WITH RECURSIVE historial AS (
               SELECT s.id AS serie_original_id, s.id FROM series_realizadas s
               JOIN sesiones_realizadas sr ON sr.id = s.sesion_realizada_id
               WHERE s.corrige_a IS NULL AND sr.socio_id = %s"""
        + filtro
        + """
               UNION ALL
               SELECT h.serie_original_id, s.id FROM historial h JOIN series_realizadas s ON s.corrige_a = h.id
           ), ordenadas AS (
               SELECT s.*, h.serie_original_id,
                      ROW_NUMBER() OVER (
                          PARTITION BY h.serie_original_id ORDER BY s.registrada_en DESC, s.id DESC
                      ) AS orden
               FROM historial h JOIN series_realizadas s ON s.id = h.id
           )
           SELECT s.*, sr.sesion_planificada_id, sr.creada_en AS sesion_creada_en,
                  ep.ejercicio_id AS ejercicio_catalogo_id,
                  COALESCE(s.ejercicio_hecho_id, ep.ejercicio_id) AS ejercicio_hecho_resuelto_id FROM ordenadas s
           JOIN ejercicios_planificados ep ON ep.id = s.ejercicio_planificado_id
           JOIN sesiones_realizadas sr ON sr.id = s.sesion_realizada_id
           WHERE s.orden = 1 AND s.anulada = FALSE
           ORDER BY s.registrada_en, s.id""",
        parametros,
    )
    return cursor.fetchall()
