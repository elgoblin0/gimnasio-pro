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


def revocaciones_de_socios(cursor, socio_ids):
    """Socios cuyo último consentimiento de salud es una revocación, en una sola consulta."""
    if not socio_ids:
        return []
    lugares = ",".join(["%s"] * len(socio_ids))
    cursor.execute(
        f"""SELECT c.socio_id, c.registrado_en FROM consentimientos c
            WHERE c.tipo='salud' AND NOT c.otorgado AND c.socio_id IN ({lugares})
              AND NOT EXISTS (SELECT 1 FROM consentimientos n WHERE n.socio_id=c.socio_id AND n.tipo='salud'
                              AND (n.registrado_en,n.id)>(c.registrado_en,c.id))""",
        tuple(a_bytes(socio_id) for socio_id in socio_ids),
    )
    return cursor.fetchall()
