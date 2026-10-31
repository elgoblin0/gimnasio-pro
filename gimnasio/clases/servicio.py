"""Configuración de clases y agenda de dos semanas en la zona de la sede."""

import re
from datetime import UTC, timedelta
from zoneinfo import ZoneInfo

from gimnasio.clases import repositorio
from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.ids import desde_bytes, desde_texto, nuevo_id
from gimnasio.comun.reloj import reloj_actual
from gimnasio.reglas.clases import ocurrencias_en_rango


def identificador(texto):
    try:
        return desde_texto(texto)
    except (ValueError, TypeError, AttributeError) as error:
        raise ErrorDeDominio("id_invalido", "El identificador debe ser un UUIDv7.", 422) from error


def validar(datos):
    if not isinstance(datos, dict):
        raise ErrorDeDominio("clase_invalida", "Enviá los datos de la clase.", 422)
    nombre = datos.get("nombre")
    if not isinstance(nombre, str) or not nombre.strip() or len(nombre.strip()) > 120:
        raise ErrorDeDominio("nombre_invalido", "El nombre admite entre 1 y 120 caracteres.", 422)
    for campo, minimo, maximo in (("dia_semana", 1, 7), ("duracion_minutos", 15, 240), ("cupo", 1, 2147483647)):
        valor = datos.get(campo)
        if type(valor) is not int or not minimo <= valor <= maximo:
            raise ErrorDeDominio("clase_invalida", f"{campo}: enviá un entero entre {minimo} y {maximo}.", 422)
    hora = datos.get("hora_inicio")
    if not isinstance(hora, str) or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", hora):
        raise ErrorDeDominio("hora_invalida", "La hora debe usar HH:MM.", 422)
    return {campo: datos[campo] for campo in ("dia_semana", "duracion_minutos", "cupo", "hora_inicio")} | {
        "nombre": nombre.strip(),
        "entrenador_id": identificador(datos.get("entrenador_id")),
    }


def _hora(valor):
    # MySQL entrega TIME como timedelta; la API usa HH:MM.
    segundos = int(valor.total_seconds())
    return f"{segundos // 3600:02d}:{segundos % 3600 // 60:02d}"


def _clases(cursor):
    return [
        dict(
            fila,
            id=str(desde_bytes(fila["id"])),
            entrenador_id=str(desde_bytes(fila["entrenador_id"])),
            hora_inicio=_hora(fila["hora_inicio"]),
            archivada=bool(fila["archivada"]),
            creada_en=fila["creada_en"].replace(tzinfo=UTC).isoformat(),
            actualizada_en=fila["actualizada_en"].replace(tzinfo=UTC).isoformat(),
        )
        for fila in repositorio.listar(cursor)
    ]


def listar():
    with transaccion() as cursor:
        return {
            "clases": _clases(cursor),
            "entrenadores": [dict(fila, id=str(desde_bytes(fila["id"]))) for fila in repositorio.entrenadores(cursor)],
        }


def agenda():
    hoy = reloj_actual().ahora().astimezone(ZoneInfo("America/Asuncion")).date()
    desde = hoy - timedelta(days=hoy.weekday())
    hasta = desde + timedelta(days=13)
    with transaccion() as cursor:
        clases = _clases(cursor)
        ocurrencias = [
            dict(fila, clase_id=str(desde_bytes(fila["clase_id"])), hora_inicio=_hora(fila["hora_inicio"]))
            for fila in repositorio.ocurrencias(cursor, desde, hasta)
        ]
    por_id = {clase["id"]: clase for clase in clases}
    resultado = []
    for fila in ocurrencias_en_rango(clases, ocurrencias, desde, hasta):
        clase = por_id[fila["clase_id"]]
        fecha = fila["fecha"].isoformat()
        resultado.append(
            dict(
                fila,
                fecha=fecha,
                identificador={"clase_id": clase["id"], "fecha": fecha},
                clase=clase["nombre"],
                entrenador_id=clase["entrenador_id"],
                entrenador=f"{clase['entrenador_nombre']} {clase['entrenador_apellido']}",
                cupo=clase["cupo"],
            )
        )
    return {"desde": desde.isoformat(), "hasta": hasta.isoformat(), "ocurrencias": resultado}


def guardar(datos, texto_id=None):
    datos = validar(datos)
    nueva = texto_id is None
    clase_id = nuevo_id() if nueva else identificador(texto_id)
    momento = reloj_actual().ahora().astimezone(UTC).replace(tzinfo=None)
    with transaccion() as cursor:
        if not nueva and repositorio.bloquear(cursor, clase_id) is None:
            raise ErrorDeDominio("clase_inexistente", "La clase no existe.", 404)
        if not repositorio.entrenador_activo(cursor, datos["entrenador_id"]):
            raise ErrorDeDominio("entrenador_invalido", "Elegí un usuario activo con rol entrenador.", 422)
        repositorio.guardar(cursor, clase_id, datos, momento, nueva=nueva)
    return {"id": str(clase_id)}


def archivar(texto_id):
    clase_id = identificador(texto_id)
    momento = reloj_actual().ahora().astimezone(UTC).replace(tzinfo=None)
    with transaccion() as cursor:
        if repositorio.bloquear(cursor, clase_id) is None:
            raise ErrorDeDominio("clase_inexistente", "La clase no existe.", 404)
        repositorio.archivar(cursor, clase_id, momento)
    return {"id": str(clase_id), "archivada": True}
