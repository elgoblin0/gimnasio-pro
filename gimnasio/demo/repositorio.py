"""SQL de la demo; única excepción al borrado de hechos (ADR 0003)."""

from gimnasio.comun.ids import a_bytes


def vaciar_datos(cursor):
    """Borra en orden de dependencias, conservando migraciones_aplicadas y las claves foráneas."""
    cursor.execute("DELETE FROM solicitudes_idempotentes")
    cursor.execute("DELETE FROM ejercicios_planificados")
    cursor.execute("DELETE FROM sesiones_planificadas")
    cursor.execute("DELETE FROM programas_entrenamiento")
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
        (a_bytes(sede_id), "Gimnasio Pro Demo", "America/Asuncion", 60, momento),
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
