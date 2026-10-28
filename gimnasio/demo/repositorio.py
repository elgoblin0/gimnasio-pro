"""SQL de la demo; única excepción al borrado de hechos (ADR 0003)."""

import json

from gimnasio.comun.ids import a_bytes


def vaciar_datos(cursor):
    """Borra en orden de dependencias, conservando migraciones_aplicadas y las claves foráneas."""
    cursor.execute("DELETE FROM solicitudes_idempotentes")
    # Las series pueden corregir otras series: borrar primero las hojas del historial.
    while True:
        cursor.execute(
            "DELETE original FROM series_realizadas original "
            "LEFT JOIN series_realizadas correccion ON correccion.corrige_a = original.id "
            "WHERE correccion.id IS NULL"
        )
        if cursor.rowcount == 0:
            break
    cursor.execute("DELETE FROM sesiones_realizadas")
    cursor.execute("DELETE FROM ejercicios_planificados")
    cursor.execute("DELETE FROM sesiones_planificadas")
    cursor.execute("DELETE FROM programas_entrenamiento")
    cursor.execute("DELETE FROM alternativas_ejercicio")
    cursor.execute("DELETE FROM zonas_ejercicio")
    cursor.execute("DELETE FROM ejercicios")
    cursor.execute("DELETE FROM intentos_de_ingreso")
    # Las autorreferencias exigen borrar primero las correcciones sin sucesoras.
    # No se desactivan las FK, ni siquiera durante el reinicio de la demo.
    for tabla in ("salidas", "entradas"):
        while True:
            cursor.execute(
                f"DELETE original FROM {tabla} original "
                f"LEFT JOIN {tabla} correccion ON correccion.corrige_a = original.id "
                "WHERE correccion.id IS NULL"
            )
            if cursor.rowcount == 0:
                break
    cursor.execute("DELETE FROM consentimientos")
    cursor.execute("DELETE FROM asignaciones_entrenador")
    cursor.execute("DELETE FROM membresias")
    cursor.execute("DELETE FROM usuarios")
    cursor.execute("DELETE FROM personas")
    cursor.execute("DELETE FROM sedes")


def insertar_sede(cursor, sede_id, momento):
    cursor.execute(
        """INSERT INTO sedes (id, nombre, zona_horaria, aforo_maximo, actualizada_en)
           VALUES (%s, %s, %s, %s, %s)""",
        (a_bytes(sede_id), "Gimnasio Pro Demo · Asunción", "America/Asuncion", 60, momento),
    )


def insertar_asignacion(cursor, asignacion_id, socio_id, entrenador_id, momento):
    cursor.execute(
        """INSERT INTO asignaciones_entrenador (id, socio_id, entrenador_id, desde, hasta)
           VALUES (%s, %s, %s, %s, NULL)""",
        (a_bytes(asignacion_id), a_bytes(socio_id), a_bytes(entrenador_id), momento),
    )


def insertar_membresia(cursor, membresia_id, socio_id, desde, hasta, momento):
    cursor.execute(
        """INSERT INTO membresias (id, socio_id, desde, hasta, actualizada_en)
           VALUES (%s, %s, %s, %s, %s)""",
        (a_bytes(membresia_id), a_bytes(socio_id), desde, hasta, momento),
    )


def insertar_ejercicio(
    cursor, ejercicio_id, nombre, medidas, momento, *, patron_movimiento="", equipo="", incremento_carga=None, zonas=()
):
    cursor.execute(
        "INSERT INTO ejercicios (id,nombre,medidas_aplicables,actualizada_en,"
        "patron_movimiento,equipo,incremento_carga) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (a_bytes(ejercicio_id), nombre, json.dumps(medidas), momento, patron_movimiento, equipo, incremento_carga),
    )

    for zona in zonas:
        cursor.execute("INSERT INTO zonas_ejercicio (ejercicio_id,zona) VALUES (%s,%s)", (a_bytes(ejercicio_id), zona))


def insertar_alternativa(cursor, ejercicio_id, alternativa_id, orden):
    cursor.execute(
        "INSERT INTO alternativas_ejercicio (ejercicio_id,alternativa_id,orden) VALUES (%s,%s,%s)",
        (a_bytes(ejercicio_id), a_bytes(alternativa_id), orden),
    )


def insertar_programa(cursor, programa_id, socio_id, momento):
    cursor.execute(
        "INSERT INTO programas_entrenamiento (id,socio_id,version,creado_en) VALUES (%s,%s,1,%s)",
        (a_bytes(programa_id), a_bytes(socio_id), momento),
    )


def insertar_sesion_planificada(cursor, sesion_id, programa_id, posicion, nombre):
    cursor.execute(
        "INSERT INTO sesiones_planificadas (id,programa_id,posicion,nombre) VALUES (%s,%s,%s,%s)",
        (a_bytes(sesion_id), a_bytes(programa_id), posicion, nombre),
    )


def insertar_ejercicio_planificado(
    cursor,
    planificado_id,
    sesion_id,
    ejercicio_id,
    posicion,
    series,
    *,
    repeticiones_minimas=None,
    repeticiones_maximas=None,
    rir_objetivo=None,
    descanso=None,
    carga=None,
    duracion=None,
    distancia=None,
):
    cursor.execute(
        "INSERT INTO ejercicios_planificados "
        "(id,sesion_planificada_id,ejercicio_id,posicion,series,repeticiones_minimas,"
        "repeticiones_maximas,rir_objetivo,descanso,carga,duracion,distancia) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            a_bytes(planificado_id),
            a_bytes(sesion_id),
            a_bytes(ejercicio_id),
            posicion,
            series,
            repeticiones_minimas,
            repeticiones_maximas,
            rir_objetivo,
            descanso,
            carga,
            duracion,
            distancia,
        ),
    )


def insertar_parcial(cursor, sesion_id, serie_id, socio_id, planificada_id, ejercicio_id, momento):
    cursor.execute(
        "INSERT INTO sesiones_realizadas (id,socio_id,sesion_planificada_id,creada_en) VALUES (%s,%s,%s,%s)",
        (a_bytes(sesion_id), a_bytes(socio_id), a_bytes(planificada_id), momento),
    )
    cursor.execute(
        "INSERT INTO series_realizadas "
        "(id,sesion_realizada_id,ejercicio_planificado_id,repeticiones,carga,autor_id,registrada_en) "
        "VALUES (%s,%s,%s,10,20.50,%s,%s)",
        (a_bytes(serie_id), a_bytes(sesion_id), a_bytes(ejercicio_id), a_bytes(socio_id), momento),
    )


def insertar_historial(cursor, sesion_id, series, socio_id, planificada_id, ejercicio_id, momento, repeticiones):
    cursor.execute(
        "INSERT IGNORE INTO sesiones_realizadas (id,socio_id,sesion_planificada_id,creada_en) VALUES (%s,%s,%s,%s)",
        (a_bytes(sesion_id), a_bytes(socio_id), a_bytes(planificada_id), momento),
    )
    for serie_id in series:
        cursor.execute(
            "INSERT INTO series_realizadas "
            "(id,sesion_realizada_id,ejercicio_planificado_id,repeticiones,carga,rir,autor_id,registrada_en) "
            "VALUES (%s,%s,%s,%s,20.50,2,%s,%s)",
            (a_bytes(serie_id), a_bytes(sesion_id), a_bytes(ejercicio_id), repeticiones, a_bytes(socio_id), momento),
        )
