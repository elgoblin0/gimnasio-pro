"""Configuración vigente e historial de sede en la transacción del servicio."""

import json
from datetime import UTC

from gimnasio.comun.ids import a_bytes


def obtener_sede(cursor, *, bloquear=False):
    cursor.execute("SELECT * FROM sedes ORDER BY id LIMIT 1" + (" FOR UPDATE" if bloquear else ""))
    return cursor.fetchone()


def listar_cambios(cursor, sede_id):
    cursor.execute(
        "SELECT c.*, p.nombre AS autor FROM cambios_sede c "
        "JOIN usuarios u ON u.id = c.autor_id JOIN personas p ON p.id = u.persona_id "
        "WHERE c.sede_id = %s ORDER BY c.registrado_en DESC, c.id DESC",
        (a_bytes(sede_id),),
    )
    return cursor.fetchall()


def registrar_cambio(cursor, identificador, sede_id, aforo, horario, motivo, autor_id, ahora):
    momento = ahora.astimezone(UTC).replace(tzinfo=None)
    horario_json = json.dumps(horario)
    cursor.execute(
        "INSERT INTO cambios_sede (id, sede_id, aforo_maximo, horario, motivo, autor_id, registrado_en) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (a_bytes(identificador), a_bytes(sede_id), aforo, horario_json, motivo, a_bytes(autor_id), momento),
    )
    cursor.execute(
        "UPDATE sedes SET aforo_maximo = %s, horario = %s, actualizada_en = %s WHERE id = %s",
        (aforo, horario_json, momento, a_bytes(sede_id)),
    )
