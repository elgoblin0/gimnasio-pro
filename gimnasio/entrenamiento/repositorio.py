"""Persistencia de hechos; recibe cursor y fechas explícitos, sin confirmar transacciones."""

import json
from datetime import UTC
from decimal import Decimal, InvalidOperation

from mysql.connector import IntegrityError, errorcode

from gimnasio.comun.ids import a_bytes, desde_bytes

MEDIDAS = ("repeticiones", "carga", "duracion", "distancia")


def socios_con_sesion(cursor, socio_ids):
    marcas = ",".join(["%s"] * len(socio_ids))
    cursor.execute(
        f"SELECT DISTINCT socio_id FROM sesiones_realizadas WHERE socio_id IN ({marcas})",
        [a_bytes(socio_id) for socio_id in socio_ids],
    )
    return cursor.fetchall()


def listar_zonas_trabajadas(cursor, socio_id, sesion_id):
    series = listar_series_vigentes(cursor, socio_id, sesion_id)
    zonas = set()
    for hecho_id in {fila["ejercicio_hecho_resuelto_id"] for fila in series}:
        cursor.execute("SELECT zona FROM zonas_ejercicio WHERE ejercicio_id=%s", (hecho_id,))
        zonas.update(fila["zona"] for fila in cursor.fetchall())
    return sorted(zonas)


def listar_sustituciones_sesion(cursor, sesion_id):
    cursor.execute(
        """SELECT s.*, e.nombre AS ejercicio_hecho_nombre, ep.nombre AS ejercicio_planificado_nombre
           FROM sustituciones s JOIN ejercicios e ON e.id=s.ejercicio_hecho_id
           JOIN ejercicios_planificados p ON p.id=s.ejercicio_planificado_id
           JOIN ejercicios ep ON ep.id=p.ejercicio_id
           WHERE s.sesion_realizada_id=%s ORDER BY s.registrada_en, s.id""",
        (a_bytes(sesion_id),),
    )
    return cursor.fetchall()


def obtener_socio(cursor, socio_id, *, bloquear=False, bloqueo_compartido=False):
    bloqueo = " FOR UPDATE" if bloquear else " FOR SHARE" if bloqueo_compartido else ""
    cursor.execute("SELECT id, rol, activo FROM usuarios WHERE id = %s" + bloqueo, (a_bytes(socio_id),))
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
        """SELECT s.*, e.nombre AS ejercicio_hecho_nombre,
                  COALESCE(s.ejercicio_hecho_id, ep.ejercicio_id) AS ejercicio_hecho_resuelto_id
           FROM series_realizadas s JOIN ejercicios_planificados ep ON ep.id = s.ejercicio_planificado_id
           JOIN ejercicios e ON e.id = COALESCE(s.ejercicio_hecho_id, ep.ejercicio_id)
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
        "SELECT id, sesion_planificada_id, ejercicio_id FROM ejercicios_planificados WHERE id = %s",
        (a_bytes(ejercicio_id),),
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
           JOIN ejercicios e ON e.id = COALESCE(%s, ep.ejercicio_id) WHERE sr.id = %s AND ep.id = %s""",
        (
            a_bytes(ejercicio_hecho_id) if ejercicio_hecho_id else None,
            a_bytes(sesion_realizada_id),
            a_bytes(ejercicio_planificado_id),
        ),
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
           SELECT s.*, e.nombre AS ejercicio_hecho_nombre,
                  sr.sesion_planificada_id, sr.creada_en AS sesion_creada_en,
                  ep.ejercicio_id AS ejercicio_catalogo_id,
                  COALESCE(s.ejercicio_hecho_id, ep.ejercicio_id) AS ejercicio_hecho_resuelto_id FROM ordenadas s
           JOIN ejercicios_planificados ep ON ep.id = s.ejercicio_planificado_id
           JOIN sesiones_realizadas sr ON sr.id = s.sesion_realizada_id
           JOIN ejercicios e ON e.id = COALESCE(s.ejercicio_hecho_id, ep.ejercicio_id)
           WHERE s.orden = 1 AND s.anulada = FALSE
           ORDER BY s.registrada_en, s.id""",
        parametros,
    )
    return cursor.fetchall()


def listar_catalogo(cursor, ejercicio_id):
    """El original seguido de sus alternativas en el orden declarado del catálogo."""
    cursor.execute(
        """SELECT e.*, COALESCE((SELECT JSON_ARRAYAGG(z.zona) FROM zonas_ejercicio z
           WHERE z.ejercicio_id=e.id), JSON_ARRAY()) AS zonas
           FROM ejercicios e LEFT JOIN alternativas_ejercicio a
           ON a.alternativa_id=e.id AND a.ejercicio_id=%s
           WHERE e.id=%s OR a.ejercicio_id=%s
           ORDER BY CASE WHEN e.id=%s THEN 0 ELSE 1 END, a.orden, e.id""",
        (a_bytes(ejercicio_id),) * 4,
    )
    return cursor.fetchall()


def obtener_sustitucion(cursor, sustitucion_id):
    cursor.execute("SELECT * FROM sustituciones WHERE id=%s FOR SHARE", (a_bytes(sustitucion_id),))
    return cursor.fetchone()


def sustitucion_vigente(cursor, sesion_id, ejercicio_id):
    cursor.execute(
        """SELECT * FROM sustituciones WHERE sesion_realizada_id=%s AND ejercicio_planificado_id=%s
           ORDER BY registrada_en DESC, id DESC LIMIT 1 FOR SHARE""",
        (a_bytes(sesion_id), a_bytes(ejercicio_id)),
    )
    return cursor.fetchone()


def listar_sustituciones_vigentes(cursor, sesion_id):
    """Resuelve el ejercicio hecho aunque ya no sea una alternativa del planificado."""
    cursor.execute(
        """WITH ordenadas AS (
               SELECT s.*, ROW_NUMBER() OVER (
                   PARTITION BY ejercicio_planificado_id ORDER BY registrada_en DESC, id DESC
               ) AS orden
               FROM sustituciones s WHERE sesion_realizada_id=%s
           )
           SELECT s.*, e.nombre, e.medidas_aplicables
           FROM ordenadas s JOIN ejercicios e ON e.id=s.ejercicio_hecho_id
           WHERE s.orden=1""",
        (a_bytes(sesion_id),),
    )
    return cursor.fetchall()


def insertar_sustitucion(
    cursor, sustitucion_id, sesion_id, ejercicio_id, hecho_id, autor_id, ahora, motivo="maquina_ocupada"
):
    _insertar(
        cursor,
        """INSERT INTO sustituciones
           (id,sesion_realizada_id,ejercicio_planificado_id,ejercicio_hecho_id,motivo,autor_id,registrada_en)
           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        (
            a_bytes(sustitucion_id),
            a_bytes(sesion_id),
            a_bytes(ejercicio_id),
            a_bytes(hecho_id),
            motivo,
            a_bytes(autor_id),
            _fecha_utc(ahora),
        ),
    )


def listar_ejercicios_sesion(cursor, sesion_id):
    cursor.execute(
        """SELECT ep.id, ep.ejercicio_id FROM ejercicios_planificados ep
           JOIN sesiones_realizadas sr ON sr.sesion_planificada_id=ep.sesion_planificada_id
           WHERE sr.id=%s ORDER BY ep.posicion""",
        (a_bytes(sesion_id),),
    )
    return cursor.fetchall()


def insertar_prescripcion(cursor, prescripcion_id, sesion_id, propuesta, ahora):
    cursor.execute(
        """INSERT INTO prescripciones_efectivas
           (id, sesion_realizada_id, version_reglas, creada_en, ejercicios, explicacion, frenos)
           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        (
            a_bytes(prescripcion_id),
            a_bytes(sesion_id),
            propuesta["version_reglas"],
            _fecha_utc(ahora),
            *(
                json.dumps(propuesta[c], default=str, ensure_ascii=False)
                for c in ("ejercicios", "explicacion", "frenos")
            ),
        ),
    )


def obtener_prescripcion(cursor, sesion_id):
    cursor.execute(
        "SELECT * FROM prescripciones_efectivas WHERE sesion_realizada_id=%s FOR SHARE", (a_bytes(sesion_id),)
    )
    return cursor.fetchone()


def insertar_prescripcion_ajustada(
    cursor,
    ajustada_id,
    sesion_id,
    prescripcion_efectiva_id,
    dolor_reportado_id,
    version_reglas,
    ejercicios,
    explicacion,
    ahora,
):
    cursor.execute(
        """INSERT INTO prescripciones_ajustadas
           (id, sesion_realizada_id, prescripcion_efectiva_id, dolor_reportado_id,
            version_reglas, creada_en, ejercicios, explicacion)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
        (
            a_bytes(ajustada_id),
            a_bytes(sesion_id),
            a_bytes(prescripcion_efectiva_id),
            a_bytes(dolor_reportado_id),
            version_reglas,
            _fecha_utc(ahora),
            json.dumps(ejercicios, default=str, ensure_ascii=False),
            json.dumps(explicacion, default=str, ensure_ascii=False),
        ),
    )


def obtener_prescripcion_ajustada(cursor, sesion_id):
    """La vigente es la última de la sesión (ADR 0030)."""
    cursor.execute(
        """SELECT * FROM prescripciones_ajustadas WHERE sesion_realizada_id=%s
           ORDER BY creada_en DESC, id DESC LIMIT 1 FOR SHARE""",
        (a_bytes(sesion_id),),
    )
    return cursor.fetchone()


def listar_prescripciones(cursor, socio_id):
    cursor.execute(
        """SELECT p.*, s.sesion_planificada_id, s.creada_en AS sesion_creada_en,
                  (SELECT MAX(d.registrado_en) FROM dolores_reportados d
                   WHERE d.sesion_realizada_id=s.id AND NOT d.anonimizada) AS ultimo_dolor,
                  (SELECT a.ejercicios FROM prescripciones_ajustadas a WHERE a.sesion_realizada_id=s.id
                   ORDER BY a.creada_en DESC, a.id DESC LIMIT 1) AS ejercicios_ajustados,
                  (SELECT JSON_OBJECTAGG(LOWER(BIN_TO_UUID(v.ejercicio_planificado_id)),
                                        LOWER(BIN_TO_UUID(v.ejercicio_hecho_id)))
                   FROM sustituciones v WHERE v.sesion_realizada_id=s.id AND NOT EXISTS (
                       SELECT 1 FROM sustituciones n WHERE n.sesion_realizada_id=v.sesion_realizada_id
                       AND n.ejercicio_planificado_id=v.ejercicio_planificado_id
                       AND (n.registrada_en,n.id)>(v.registrada_en,v.id))) AS sustituciones_vigentes
           FROM prescripciones_efectivas p
           JOIN sesiones_realizadas s ON s.id=p.sesion_realizada_id WHERE s.socio_id=%s""",
        (a_bytes(socio_id),),
    )
    return cursor.fetchall()


def obtener_chequeo(cursor, socio_id, fecha):
    cursor.execute(
        """SELECT * FROM chequeos_dia WHERE socio_id=%s AND fecha_local=%s
           ORDER BY registrado_en DESC, id DESC LIMIT 1 FOR SHARE""",
        (a_bytes(socio_id), fecha),
    )
    return cursor.fetchone()


def insertar_chequeo(cursor, chequeo_id, socio_id, fecha, sueno, energia, ahora):
    cursor.execute(
        """INSERT INTO chequeos_dia (id,socio_id,fecha_local,sueno,energia,registrado_en)
           VALUES (%s,%s,%s,%s,%s,%s)""",
        (a_bytes(chequeo_id), a_bytes(socio_id), fecha, sueno, energia, _fecha_utc(ahora)),
    )


def insertar_avisos(cursor, socio_id, sesion_id, propuesta, ahora):
    """Un aviso por freno, sin catálogo de reglas ni ramas específicas por freno.

    El llamador comparte la transacción de la prescripción efectiva.
    """
    from gimnasio.comun.ids import nuevo_id

    cursor.execute(
        """SELECT entrenador_id FROM asignaciones_entrenador
           WHERE socio_id=%s AND hasta IS NULL ORDER BY desde DESC,id DESC LIMIT 1""",
        (a_bytes(socio_id),),
    )
    asignacion = cursor.fetchone()
    for freno in dict.fromkeys(propuesta["frenos"]):
        cursor.execute(
            """INSERT INTO avisos_entrenador
               (id,socio_id,entrenador_id,sesion_realizada_id,freno,explicacion,creado_en)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (
                a_bytes(nuevo_id()),
                a_bytes(socio_id),
                asignacion["entrenador_id"] if asignacion else None,
                a_bytes(sesion_id),
                freno,
                json.dumps(propuesta["explicacion"], ensure_ascii=False, default=str),
                _fecha_utc(ahora),
            ),
        )


def obtener_chequeo_por_id(cursor, chequeo_id):
    cursor.execute("SELECT * FROM chequeos_dia WHERE id=%s FOR SHARE", (a_bytes(chequeo_id),))
    return cursor.fetchone()


def insertar_dolor(cursor, dolor_id, socio_id, zona, ahora, *, chequeo_id=None, sesion_id=None):
    cursor.execute(
        """INSERT INTO dolores_reportados
           (id,socio_id,zona,origen,chequeo_id,sesion_realizada_id,registrado_en)
           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        (
            a_bytes(dolor_id),
            a_bytes(socio_id),
            zona,
            "chequeo" if chequeo_id else "sesion",
            a_bytes(chequeo_id) if chequeo_id else None,
            a_bytes(sesion_id) if sesion_id else None,
            _fecha_utc(ahora),
        ),
    )


def obtener_dolor(cursor, dolor_id):
    cursor.execute("SELECT * FROM dolores_reportados WHERE id=%s FOR SHARE", (a_bytes(dolor_id),))
    return cursor.fetchone()


def zonas_chequeo(cursor, chequeo_id):
    if chequeo_id is None:
        return ()
    cursor.execute(
        "SELECT zona FROM dolores_reportados WHERE chequeo_id=%s AND NOT anonimizada ORDER BY zona FOR SHARE",
        (a_bytes(chequeo_id),),
    )
    return tuple(f["zona"] for f in cursor.fetchall())


def dolores_sesion(cursor, sesion_id, fecha):
    """Incluye el chequeo vigente al iniciar, aun después de medianoche u otro chequeo."""
    cursor.execute(
        """SELECT c.id FROM chequeos_dia c JOIN sesiones_realizadas s ON s.id=%s
           WHERE c.fecha_local=%s AND c.socio_id=s.socio_id AND (c.registrado_en,c.id)<=(s.creada_en,s.id)
           ORDER BY c.registrado_en DESC,c.id DESC LIMIT 1 FOR SHARE""",
        (a_bytes(sesion_id), fecha),
    )
    chequeo = cursor.fetchone()
    cursor.execute(
        "SELECT zona FROM dolores_reportados WHERE sesion_realizada_id=%s AND NOT anonimizada FOR SHARE",
        (a_bytes(sesion_id),),
    )
    zonas = {f["zona"] for f in cursor.fetchall()}
    if chequeo:
        zonas.update(zonas_chequeo(cursor, desde_bytes(chequeo["id"])))
    return tuple(sorted(zonas))


def ultimo_momento_dolor(cursor, sesion_id):
    cursor.execute(
        "SELECT MAX(registrado_en) AS momento FROM dolores_reportados WHERE sesion_realizada_id=%s AND NOT anonimizada",
        (a_bytes(sesion_id),),
    )
    return cursor.fetchone()["momento"]


def listar_dolores_socio(cursor, socio_id):
    """Dolores en sesión y chequeos, incluso neutros para no recuperar un dolor previo."""
    cursor.execute(
        """SELECT NULL AS sesion_realizada_id, c.id AS chequeo_id, c.fecha_local, c.registrado_en, d.zona
           FROM chequeos_dia c LEFT JOIN dolores_reportados d ON d.chequeo_id=c.id AND NOT d.anonimizada
           WHERE c.socio_id=%s
           UNION ALL
           SELECT d.sesion_realizada_id, NULL, NULL, NULL, d.zona
           FROM dolores_reportados d WHERE d.socio_id=%s AND d.origen='sesion' AND NOT d.anonimizada""",
        (a_bytes(socio_id),) * 2,
    )
    return cursor.fetchall()


def ultima_sesion(cursor, socio_id, sesion=None):
    filtro = " AND (creada_en,id)<(%s,%s)" if sesion else ""
    parametros = (a_bytes(socio_id),) + ((sesion["creada_en"], sesion["id"]) if sesion else ())
    cursor.execute(
        "SELECT * FROM sesiones_realizadas WHERE socio_id=%s"
        + filtro
        + " ORDER BY creada_en DESC,id DESC LIMIT 1 FOR SHARE",
        parametros,
    )
    return cursor.fetchone()


def ultimas_sesiones(cursor, socio_id):
    cursor.execute(
        "SELECT * FROM sesiones_realizadas WHERE socio_id=%s ORDER BY creada_en DESC,id DESC LIMIT 10",
        (a_bytes(socio_id),),
    )
    return cursor.fetchall()


def listar_avisos(cursor, socio_id, *, bloquear=False):
    cursor.execute(
        "SELECT * FROM avisos_entrenador WHERE socio_id=%s ORDER BY creado_en DESC,id DESC"
        + (" FOR UPDATE" if bloquear else ""),
        (a_bytes(socio_id),),
    )
    return cursor.fetchall()


def listar_avisos_de_socios(cursor, socio_ids):
    if not socio_ids:
        return []
    lugares = ",".join(["%s"] * len(socio_ids))
    cursor.execute(
        f"SELECT * FROM avisos_entrenador WHERE socio_id IN ({lugares}) ORDER BY creado_en DESC,id DESC",
        tuple(a_bytes(socio_id) for socio_id in socio_ids),
    )
    return cursor.fetchall()


def listar_dolores(cursor, socio_id):
    cursor.execute(
        "SELECT id,zona,registrado_en FROM dolores_reportados WHERE socio_id=%s AND NOT anonimizada "
        "ORDER BY registrado_en DESC,id DESC",
        (a_bytes(socio_id),),
    )
    return cursor.fetchall()


def listar_sesiones_entre(cursor, socio_id, desde, hasta):
    """Sesiones realizadas en [desde, hasta) con la explicación efectiva y la de su última prescripción ajustada."""
    cursor.execute(
        """SELECT s.id, s.sesion_planificada_id, s.creada_en, p.explicacion,
                  (SELECT a.explicacion FROM prescripciones_ajustadas a WHERE a.sesion_realizada_id=s.id
                   ORDER BY a.creada_en DESC, a.id DESC LIMIT 1) AS explicacion_ajustada
           FROM sesiones_realizadas s LEFT JOIN prescripciones_efectivas p ON p.sesion_realizada_id=s.id
           WHERE s.socio_id=%s AND s.creada_en>=%s AND s.creada_en<%s ORDER BY s.creada_en, s.id""",
        (a_bytes(socio_id), _fecha_utc(desde), _fecha_utc(hasta)),
    )
    return cursor.fetchall()


def primera_sesion(cursor, socio_id):
    cursor.execute(
        "SELECT MIN(creada_en) AS creada_en FROM sesiones_realizadas WHERE socio_id=%s", (a_bytes(socio_id),)
    )
    return cursor.fetchone()["creada_en"]
