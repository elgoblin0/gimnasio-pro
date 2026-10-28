"""Lectura por socio y versión para entrenamiento, sin rutas de edición."""

import json
from datetime import UTC

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import desde_bytes
from gimnasio.programas import repositorio

MEDIDAS = ("repeticiones", "carga", "duracion", "distancia")
OBJETIVOS = (
    "repeticiones_minimas",
    "repeticiones_maximas",
    "rir_objetivo",
    "descanso",
    "carga",
    "duracion",
    "distancia",
)


def validar_medidas_aplicables(medidas):
    """El catálogo usa una lista JSON de nombres; carga en kg, duración en s y distancia en m."""
    if not isinstance(medidas, list) or any(not isinstance(medida, str) or medida not in MEDIDAS for medida in medidas):
        raise ValueError("Las medidas aplicables deben ser una lista de repeticiones, carga, duracion o distancia.")


def listar_programas(socio_id):
    """Devuelve todas las versiones del socio en orden ascendente, con sesiones y ejercicios por posición.

    Uso interno desde servicios de entrenamiento: el llamador controla el acceso al socio.
    Los identificadores se devuelven en texto, las fechas en UTC y los decimales sin redondear.
    """
    return _leer(socio_id)


def obtener_programa(socio_id, version):
    """Lee una versión explícita, o None si no existe para ese socio; nunca elige otra versión."""
    if type(version) is not int:
        raise ValueError("La versión del programa de entrenamiento debe ser un entero.")
    programas = _leer(socio_id, version)
    return programas[0] if programas else None


def _leer(socio_id, version=None):
    with transaccion() as cursor:
        filas = repositorio.leer_por_socio(cursor, socio_id, version)
    programas = {}
    sesiones = {}
    for fila in filas:
        programa_id = str(desde_bytes(fila["programa_id"]))
        if programa_id not in programas:
            programas[programa_id] = {
                "id": programa_id,
                "socio_id": str(desde_bytes(fila["socio_id"])),
                "version": fila["version"],
                "creado_en": fila["creado_en"].replace(tzinfo=UTC),
                "sesiones_planificadas": [],
            }
        if fila["sesion_id"] is None:
            continue
        sesion_id = str(desde_bytes(fila["sesion_id"]))
        if sesion_id not in sesiones:
            sesiones[sesion_id] = {
                "id": sesion_id,
                "posicion": fila["sesion_posicion"],
                "nombre": fila["sesion_nombre"],
                "ejercicios_planificados": [],
            }
            programas[programa_id]["sesiones_planificadas"].append(sesiones[sesion_id])
        if fila["planificado_id"] is None:
            continue
        medidas = json.loads(fila["medidas_aplicables"])
        validar_medidas_aplicables(medidas)
        if any(
            fila[campo] is not None
            for medida in MEDIDAS
            if medida not in medidas
            for campo in (("repeticiones_minimas", "repeticiones_maximas") if medida == "repeticiones" else (medida,))
        ):
            raise ValueError("Las medidas no aplicables del ejercicio planificado deben ser NULL.")
        sesiones[sesion_id]["ejercicios_planificados"].append(
            {
                "id": str(desde_bytes(fila["planificado_id"])),
                "ejercicio_id": str(desde_bytes(fila["ejercicio_id"])),
                "nombre": fila["ejercicio_nombre"],
                "posicion": fila["ejercicio_posicion"],
                "medidas_aplicables": medidas,
                "series": fila["series"],
                **{medida: fila[medida] for medida in OBJETIVOS},
                "patron_movimiento": fila["patron_movimiento"],
                "equipo": fila["equipo"],
                "incremento_carga": fila["incremento_carga"],
                "zonas": sorted(json.loads(fila["zonas"])),
                "alternativas": sorted(json.loads(fila["alternativas"]), key=lambda a: (a["orden"], a["ejercicio_id"])),
            }
        )
    return list(programas.values())
