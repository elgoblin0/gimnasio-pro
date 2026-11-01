"""Compone lo de cada módulo: acá no hay SQL propio ni se guarda nada."""

from datetime import UTC

from gimnasio.comun.bd import transaccion
from gimnasio.comun.ids import desde_texto
from gimnasio.comun.reloj import fecha_local, reloj_actual
from gimnasio.entrenamiento.servicio import socios_con_sesion
from gimnasio.programas.servicio import socios_con_programa
from gimnasio.reglas.acompanamiento import dia_de_incorporacion, razones_de_riesgo
from gimnasio.socios.servicio import datos_de_acompanamiento
from gimnasio.visitas.servicio import visitas_de_socios, zona_de_la_sede


def _razon_publica(razon):
    return {"regla": razon.regla, "version": razon.version, "datos": dict(razon.datos)}


def estados_de_socios(cursor, socio_ids, zona=None):
    """Por socio: día de incorporación, riesgo y fecha de su última señal de vida.

    Las visitas simuladas solo dan movimiento a la sede: esos socios no tienen acompañamiento.
    Quien ya leyó la sede pasa su zona y se ahorra la consulta.
    """
    if not socio_ids:
        return {}
    ahora = reloj_actual().ahora()
    zona = zona or zona_de_la_sede(cursor)
    hoy = fecha_local(ahora, zona)
    datos = datos_de_acompanamiento(cursor, socio_ids)
    visitas = visitas_de_socios(cursor, socio_ids)
    estados = {}
    for socio_id in socio_ids:
        fila = datos[socio_id]
        momentos = visitas.get(socio_id, [])
        if fila["simulada"]:
            estados[socio_id] = {"dia": None, "riesgo": [], "visitas": momentos, "desde": None}
            continue
        alta = fecha_local(fila["alta"].replace(tzinfo=UTC), zona)
        dias_de_visita = tuple(fecha_local(momento, zona) for momento in momentos)
        estados[socio_id] = {
            "dia": dia_de_incorporacion(alta, hoy),
            "riesgo": [_razon_publica(r) for r in razones_de_riesgo(alta, hoy, dias_de_visita, fila["ultimo_hasta"])],
            "visitas": momentos,
            "desde": max(momentos, default=fila["alta"].replace(tzinfo=UTC)).isoformat(),
        }
    return estados


def incorporacion_de(cursor, socio_id, estado):
    """Día e hitos, o None si el socio ya no está en incorporación."""
    if estado["dia"] is None:
        return None
    return {
        "dia": estado["dia"],
        "hitos": {
            "programa_asignado": socio_id in socios_con_programa(cursor, [socio_id]),
            "primera_visita": bool(estado["visitas"]),
            "primera_sesion": socio_id in socios_con_sesion(cursor, [socio_id]),
        },
    }


def consultar_incorporacion_propia(usuario):
    """Lectura del socio: nunca incluye el riesgo de abandono."""
    socio_id = desde_texto(usuario["id"])
    with transaccion() as cursor:
        return {"incorporacion": incorporacion_de(cursor, socio_id, estados_de_socios(cursor, [socio_id])[socio_id])}
