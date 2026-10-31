"""SQL de la demo; única excepción al borrado de hechos (ADR 0003)."""

import json
from datetime import UTC

from gimnasio.comun.ids import a_bytes


def insertar_restriccion(cursor, identificador, socio_id, autor_id, ahora):
    cursor.execute(
        """INSERT INTO restricciones_salud
           (id,socio_id,zona,descripcion,registrada_en,autor_id)
           VALUES (%s,%s,'zona_lumbar','sin carga axial en zona lumbar',%s,%s)""",
        (a_bytes(identificador), a_bytes(socio_id), ahora.replace(tzinfo=None), a_bytes(autor_id)),
    )


def vaciar_datos(cursor):
    """Borra en orden de dependencias, conservando migraciones_aplicadas y las claves foráneas."""
    cursor.execute("DELETE FROM membresias")
    cursor.execute("DELETE FROM pagos")
    cursor.execute("DELETE FROM tipos_membresia")
    cursor.execute("DELETE FROM cambios_sede")
    cursor.execute("DELETE FROM simulacion_demo")
    cursor.execute("DELETE FROM solicitudes_idempotentes")
    cursor.execute("DELETE FROM cambios_estado_equipo")
    cursor.execute("DELETE FROM equipos")
    cursor.execute("DELETE FROM borrados_salud")
    while True:
        cursor.execute(
            "DELETE original FROM restricciones_salud original "
            "LEFT JOIN restricciones_salud baja ON baja.levanta_a=original.id WHERE baja.id IS NULL"
        )
        if cursor.rowcount == 0:
            break
    # Las series pueden corregir otras series: borrar primero las hojas del historial.
    while True:
        cursor.execute(
            "DELETE original FROM series_realizadas original "
            "LEFT JOIN series_realizadas correccion ON correccion.corrige_a = original.id "
            "WHERE correccion.id IS NULL"
        )
        if cursor.rowcount == 0:
            break
    cursor.execute("DELETE FROM sustituciones")
    cursor.execute("DELETE FROM dolores_reportados")
    cursor.execute("DELETE FROM revisiones_aviso")
    cursor.execute("DELETE FROM avisos_entrenador")
    cursor.execute("DELETE FROM chequeos_dia")
    cursor.execute("DELETE FROM prescripciones_efectivas")
    cursor.execute("DELETE FROM sesiones_realizadas")
    cursor.execute("DELETE FROM ejercicios_planificados")
    cursor.execute("DELETE FROM sesiones_planificadas")
    cursor.execute("DELETE FROM programas_entrenamiento")
    cursor.execute("DELETE FROM plantillas_ejercicios")
    cursor.execute("DELETE FROM plantillas_sesiones")
    cursor.execute("DELETE FROM plantillas_programa")
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
    cursor.execute("DELETE FROM perfiles_entrenamiento")
    cursor.execute("DELETE FROM usuarios")
    cursor.execute("DELETE FROM personas")
    cursor.execute("DELETE FROM sedes")


def insertar_sede(cursor, sede_id, momento, horario):
    cursor.execute(
        """INSERT INTO sedes (id, nombre, zona_horaria, aforo_maximo, actualizada_en, horario)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (a_bytes(sede_id), "Gimnasio Pro Demo · Asunción", "America/Asuncion", 60, momento, json.dumps(horario)),
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


def insertar_plantilla(cursor, identificador, nombre, descripcion, momento):
    cursor.execute(
        "INSERT INTO plantillas_programa (id,nombre,descripcion,creada_en) VALUES (%s,%s,%s,%s)",
        (a_bytes(identificador), nombre, descripcion, momento),
    )


def insertar_sesion_plantilla(cursor, identificador, plantilla_id, posicion, nombre):
    cursor.execute(
        "INSERT INTO plantillas_sesiones (id,plantilla_id,posicion,nombre) VALUES (%s,%s,%s,%s)",
        (a_bytes(identificador), a_bytes(plantilla_id), posicion, nombre),
    )


def insertar_ejercicio_plantilla(cursor, identificador, sesion_id, ejercicio_id, posicion):
    cursor.execute(
        """INSERT INTO plantillas_ejercicios
           (id,sesion_id,ejercicio_id,posicion,series,repeticiones_minimas,repeticiones_maximas,rir_objetivo,descanso)
           VALUES (%s,%s,%s,%s,3,8,12,2,90)""",
        (a_bytes(identificador), a_bytes(sesion_id), a_bytes(ejercicio_id), posicion),
    )


def nombres_equipos_catalogo(cursor):
    cursor.execute("SELECT DISTINCT equipo FROM ejercicios WHERE equipo NOT IN ('', 'sin equipo') ORDER BY equipo")
    return [fila["equipo"] for fila in cursor.fetchall()]


def insertar_equipo(cursor, equipo_id, nombre, momento):
    cursor.execute(
        "INSERT INTO equipos (id, nombre, creado_en) VALUES (%s, %s, %s)",
        (a_bytes(equipo_id), nombre, momento),
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


def insertar_visitas(cursor, sede_id, autor_id, visitas, siguiente_id):
    """Carga las entradas y las salidas confirmadas en dos lotes, sin correcciones."""
    entradas, salidas = [], []
    for socio_id, entrada, salida in visitas:
        entrada_id = a_bytes(siguiente_id())
        entradas.append(
            (
                entrada_id,
                a_bytes(socio_id),
                a_bytes(sede_id),
                a_bytes(autor_id),
                entrada.astimezone(UTC).replace(tzinfo=None),
            )
        )
        salidas.append(
            (a_bytes(siguiente_id()), entrada_id, a_bytes(autor_id), salida.astimezone(UTC).replace(tzinfo=None))
        )
    cursor.executemany(
        "INSERT INTO entradas (id,socio_id,sede_id,autor_id,registrada_en) VALUES (%s,%s,%s,%s,%s)", entradas
    )
    cursor.executemany("INSERT INTO salidas (id,entrada_id,autor_id,registrada_en) VALUES (%s,%s,%s,%s)", salidas)


def marcar_simulada(cursor, usuario_id):
    cursor.execute(
        "UPDATE personas p JOIN usuarios u ON u.persona_id=p.id SET p.simulada=TRUE WHERE u.id=%s",
        (a_bytes(usuario_id),),
    )


def iniciar_simulacion(cursor, ahora):
    cursor.execute("INSERT INTO simulacion_demo (generada_hasta) VALUES (%s)", (ahora.replace(tzinfo=None),))


def bloquear_simulacion(cursor):
    cursor.execute("SELECT generada_hasta FROM simulacion_demo WHERE unica=TRUE FOR UPDATE")
    return cursor.fetchone()


def avanzar_simulacion(cursor, ahora):
    cursor.execute("UPDATE simulacion_demo SET generada_hasta=%s WHERE unica=TRUE", (ahora.replace(tzinfo=None),))


def listar_simulados(cursor):
    cursor.execute(
        "SELECT u.id FROM usuarios u JOIN personas p ON p.id=u.persona_id "
        "WHERE p.simulada=TRUE AND u.rol='socio' AND u.activo=TRUE ORDER BY u.id"
    )
    return cursor.fetchall()


def obtener_autor_simulacion(cursor):
    cursor.execute(
        "SELECT u.id FROM usuarios u JOIN personas p ON p.id=u.persona_id "
        "WHERE p.correo='simulacion@demo.gimnasio.invalid'"
    )
    return cursor.fetchone()


def insertar_aviso(cursor, aviso_id, realizada_id, socio_id, sesion_id, entrenador_id, freno, explicacion, ahora):
    cursor.execute(
        "INSERT INTO sesiones_realizadas (id,socio_id,sesion_planificada_id,creada_en) VALUES (%s,%s,%s,%s)",
        (a_bytes(realizada_id), a_bytes(socio_id), a_bytes(sesion_id), ahora),
    )
    cursor.execute(
        "INSERT INTO avisos_entrenador "
        "(id,socio_id,entrenador_id,sesion_realizada_id,freno,explicacion,creado_en) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (
            a_bytes(aviso_id),
            a_bytes(socio_id),
            a_bytes(entrenador_id),
            a_bytes(realizada_id),
            freno,
            json.dumps(explicacion, ensure_ascii=False),
            ahora,
        ),
    )


def insertar_revision_aviso(cursor, identificador, aviso_id, entrenador_id, ahora):
    cursor.execute(
        "INSERT INTO revisiones_aviso (id,aviso_id,entrenador_id,nota,revisada_en) VALUES (%s,%s,%s,%s,%s)",
        (a_bytes(identificador), a_bytes(aviso_id), a_bytes(entrenador_id), "Aviso ficticio revisado.", ahora),
    )


def insertar_equipo_fuera_de_servicio(cursor, identificador, equipo_id, entrenador_id, ahora):
    cursor.execute(
        "INSERT INTO cambios_estado_equipo (id,equipo_id,estado,autor_id,registrado_en) "
        "VALUES (%s,%s,'fuera_de_servicio',%s,%s)",
        (a_bytes(identificador), a_bytes(equipo_id), a_bytes(entrenador_id), ahora),
    )
