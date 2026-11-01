"""Lectura de restricciones de salud que no tienen un registro de baja."""

from gimnasio.comun.ids import a_bytes


def restricciones_vigentes(cursor, socio_id):
    cursor.execute(
        """SELECT r.* FROM restricciones_salud r
           WHERE r.socio_id=%s AND r.levanta_a IS NULL AND NOT r.anonimizada
             AND NOT EXISTS (SELECT 1 FROM restricciones_salud baja WHERE baja.levanta_a=r.id)
           ORDER BY r.registrada_en,r.id""",
        (a_bytes(socio_id),),
    )
    return cursor.fetchall()


VERSION_TEXTO = "salud-1"
TEXTO_CONSENTIMIENTO = (
    "Autorizo el tratamiento de mis condiciones de salud, restricciones de salud y dolores reportados "
    "para adaptar mi entrenamiento y aplicar los frenos de seguridad. Mi entrenador asignado puede "
    "consultar mi ficha de salud. Puedo revocar este consentimiento desde Mi ficha. "
    "Revocar conserva mis datos: mis restricciones dejan de protegerme y no tendré subas automáticas "
    "hasta que otorgue de nuevo el consentimiento."
)


def consentimiento_vigente(cursor, socio_id):
    cursor.execute(
        """SELECT otorgado, version_texto FROM consentimientos
           WHERE socio_id=%s AND tipo='salud'
           ORDER BY registrado_en DESC,id DESC LIMIT 1""",
        (a_bytes(socio_id),),
    )
    return cursor.fetchone()
