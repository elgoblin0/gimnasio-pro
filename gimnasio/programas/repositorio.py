"""Lectura SQL del programa de entrenamiento, sin modificar lo planificado."""

from gimnasio.comun.ids import a_bytes


def leer_por_socio(cursor, socio_id, version=None):
    """Una consulta conserva la misma lectura para programas, sesiones y ejercicios."""
    filtro = "" if version is None else " AND p.version = %s"
    parametros = (a_bytes(socio_id),) if version is None else (a_bytes(socio_id), version)
    cursor.execute(
        """SELECT p.id AS programa_id, p.socio_id, p.version, p.creado_en,
                  s.id AS sesion_id, s.posicion AS sesion_posicion, s.nombre AS sesion_nombre,
                  ep.id AS planificado_id, ep.posicion AS ejercicio_posicion,
                  ep.series, ep.repeticiones, ep.carga, ep.duracion, ep.distancia,
                  e.id AS ejercicio_id, e.nombre AS ejercicio_nombre, e.medidas_aplicables
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
