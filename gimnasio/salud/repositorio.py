"""Condiciones, revisiones y restricciones de salud; los hechos solo se insertan."""

from gimnasio.comun.ids import a_bytes


def insertar_consulta_ficha(cursor, identificador, socio_id, consultado_por, momento):
    cursor.execute(
        "INSERT INTO consultas_ficha (id,socio_id,consultado_por,registrada_en) VALUES (%s,%s,%s,%s)",
        (a_bytes(identificador), a_bytes(socio_id), a_bytes(consultado_por), momento),
    )


def listar_consultas_ficha(cursor, socio_id, pagina):
    cursor.execute(
        """SELECT c.id, c.registrada_en, p.nombre, p.apellido, u.rol
           FROM consultas_ficha c JOIN usuarios u ON u.id=c.consultado_por
           JOIN personas p ON p.id=u.persona_id WHERE c.socio_id=%s
           ORDER BY c.registrada_en DESC,c.id DESC LIMIT 51 OFFSET %s""",
        (a_bytes(socio_id), (pagina - 1) * 50),
    )
    return cursor.fetchall()


def datos_propios(cursor, socio_id):
    """Exportación íntegra de hechos propios, sin exigir consentimiento vigente.

    Las consultas son fijas y acotadas por socio, nunca una consulta por fila.
    No se lee usuarios salvo para localizar la persona: sus claves quedan fuera.
    """
    consultas = {
        "persona": "SELECT p.* FROM personas p JOIN usuarios u ON u.persona_id=p.id WHERE u.id=%s",
        "perfil_entrenamiento": "SELECT * FROM perfiles_entrenamiento WHERE socio_id=%s",
        "membresias": "SELECT * FROM membresias WHERE socio_id=%s",
        "pagos": "SELECT * FROM pagos WHERE socio_id=%s",
        "anulaciones_pago": "SELECT a.* FROM anulaciones_pago a JOIN pagos p ON p.id=a.pago_id WHERE p.socio_id=%s",
        "visitas": "SELECT * FROM entradas WHERE socio_id=%s",
        "salidas": "SELECT s.* FROM salidas s JOIN entradas e ON e.id=s.entrada_id WHERE e.socio_id=%s",
        "sesiones_realizadas": "SELECT * FROM sesiones_realizadas WHERE socio_id=%s",
        "series_realizadas": (
            "SELECT r.* FROM series_realizadas r JOIN sesiones_realizadas s ON s.id=r.sesion_realizada_id "
            "WHERE s.socio_id=%s"
        ),
        "reservas": "SELECT * FROM reservas WHERE socio_id=%s",
        "cancelaciones_reserva": (
            "SELECT c.* FROM cancelaciones_reserva c JOIN reservas r ON r.id=c.reserva_id WHERE r.socio_id=%s"
        ),
        "avisos_socio": "SELECT * FROM avisos_socio WHERE socio_id=%s",
        "vistos_aviso_socio": (
            "SELECT v.* FROM vistos_aviso_socio v JOIN avisos_socio a ON a.id=v.aviso_id WHERE a.socio_id=%s"
        ),
        "condiciones": "SELECT * FROM condiciones_salud WHERE socio_id=%s",
        "revisiones_condicion": (
            "SELECT r.* FROM revisiones_condicion r JOIN condiciones_salud c ON c.id=r.condicion_id WHERE c.socio_id=%s"
        ),
        "restricciones": "SELECT * FROM restricciones_salud WHERE socio_id=%s",
        "dolores": "SELECT * FROM dolores_reportados WHERE socio_id=%s",
        "consentimientos": "SELECT * FROM consentimientos WHERE socio_id=%s",
        "consultas_ficha": "SELECT * FROM consultas_ficha WHERE socio_id=%s ORDER BY registrada_en DESC,id DESC",
        "chequeos_dia": "SELECT * FROM chequeos_dia WHERE socio_id=%s",
    }
    resultado = {}
    for seccion, consulta in consultas.items():
        cursor.execute(consulta, (a_bytes(socio_id),))
        resultado[seccion] = cursor.fetchall()
    return resultado


def restricciones_con_levantamiento(cursor, socio_id):
    cursor.execute(
        """SELECT r.*, (SELECT MIN(b.registrada_en) FROM restricciones_salud b
                        WHERE b.levanta_a=r.id) AS levantada_en
           FROM restricciones_salud r
           WHERE r.socio_id=%s AND r.levanta_a IS NULL AND NOT r.anonimizada
           ORDER BY r.registrada_en,r.id""",
        (a_bytes(socio_id),),
    )
    return cursor.fetchall()


def bloquear_socio(cursor, socio_id):
    cursor.execute("SELECT id FROM usuarios WHERE id=%s FOR UPDATE", (a_bytes(socio_id),))
    return cursor.fetchone()


def obtener_condicion(cursor, identificador):
    cursor.execute("SELECT * FROM condiciones_salud WHERE id=%s", (a_bytes(identificador),))
    return cursor.fetchone()


def obtener_restriccion(cursor, identificador):
    cursor.execute("SELECT * FROM restricciones_salud WHERE id=%s", (a_bytes(identificador),))
    return cursor.fetchone()


def condiciones_vigentes(cursor, socio_id):
    cursor.execute(
        """SELECT c.*, r.id AS revision_id, r.nota, r.autor_id, r.registrada_en AS revisada_en
           FROM condiciones_salud c LEFT JOIN revisiones_condicion r ON r.condicion_id=c.id
           WHERE c.socio_id=%s AND NOT EXISTS
             (SELECT 1 FROM condiciones_salud n WHERE n.reemplaza_a=c.id)
           ORDER BY c.registrada_en,c.id""",
        (a_bytes(socio_id),),
    )
    return cursor.fetchall()


def insertar_condicion(cursor, identificador, socio_id, descripcion, reemplaza_a, momento):
    cursor.execute(
        "INSERT INTO condiciones_salud (id,socio_id,descripcion,reemplaza_a,registrada_en) VALUES (%s,%s,%s,%s,%s)",
        (
            a_bytes(identificador),
            a_bytes(socio_id),
            descripcion,
            a_bytes(reemplaza_a) if reemplaza_a else None,
            momento,
        ),
    )


def insertar_revision(cursor, identificador, condicion_id, autor_id, nota, momento):
    cursor.execute(
        "INSERT INTO revisiones_condicion (id,condicion_id,autor_id,nota,registrada_en) VALUES (%s,%s,%s,%s,%s)",
        (a_bytes(identificador), a_bytes(condicion_id), a_bytes(autor_id), nota, momento),
    )


def insertar_restriccion(cursor, identificador, socio_id, datos, autor_id, momento, levanta_a=None):
    cursor.execute(
        """INSERT INTO restricciones_salud
           (id,socio_id,ejercicio_id,patron_movimiento,zona,descripcion,autor_id,registrada_en,levanta_a)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (
            a_bytes(identificador),
            a_bytes(socio_id),
            datos.get("ejercicio_id"),
            datos.get("patron_movimiento"),
            datos.get("zona"),
            datos["descripcion"],
            a_bytes(autor_id),
            momento,
            a_bytes(levanta_a) if levanta_a else None,
        ),
    )


def condiciones_sin_revisar(cursor, socio_ids):
    if not socio_ids:
        return []
    lugares = ",".join(["%s"] * len(socio_ids))
    cursor.execute(
        f"""SELECT c.socio_id, MIN(c.registrada_en) AS registrada_en FROM condiciones_salud c
            WHERE c.socio_id IN ({lugares})
              AND NOT EXISTS (SELECT 1 FROM condiciones_salud n WHERE n.reemplaza_a=c.id)
              AND NOT EXISTS (SELECT 1 FROM revisiones_condicion r WHERE r.condicion_id=c.id)
              AND (SELECT otorgado FROM consentimientos s WHERE s.socio_id=c.socio_id AND s.tipo='salud'
                   ORDER BY s.registrado_en DESC,s.id DESC LIMIT 1)=TRUE
            GROUP BY c.socio_id""",
        tuple(a_bytes(s) for s in socio_ids),
    )
    return cursor.fetchall()


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
