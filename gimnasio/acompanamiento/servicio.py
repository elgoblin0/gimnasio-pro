"""Compone lo de cada módulo: acá no hay SQL propio ni se guarda nada."""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from gimnasio.comun.bd import transaccion
from gimnasio.comun.errores import ErrorDeDominio
from gimnasio.comun.ids import desde_texto
from gimnasio.comun.reloj import fecha_local, inicio_de_semana, reloj_actual
from gimnasio.entrenamiento.servicio import primera_sesion, sesiones_de_la_semana, socios_con_sesion
from gimnasio.programas.servicio import listar_programas, socios_con_programa
from gimnasio.reglas.acompanamiento import dia_de_incorporacion, razones_de_riesgo
from gimnasio.reglas.resumen_semanal import (
    EjercicioDeLaSemana,
    SerieDeLaSemana,
    SesionDeLaSemana,
    resumir_semana,
    ultima_semana_cerrada,
)
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


def _lunes_pedido(texto, cerrada):
    if texto is None:
        return cerrada
    try:
        lunes = date.fromisoformat(texto)
    except (TypeError, ValueError) as error:
        raise ErrorDeDominio("semana_invalida", "Indicá la semana por su lunes, como AAAA-MM-DD.", 422) from error
    if lunes.weekday() != 0:
        raise ErrorDeDominio("semana_invalida", "Indicá la semana por su lunes, como AAAA-MM-DD.", 422)
    if lunes > cerrada:
        raise ErrorDeDominio("semana_abierta", "El resumen semanal solo muestra semanas cerradas.", 422)
    return lunes


def resumen_semanal(cursor, socio_id, semana_texto=None):
    """Se calcula al consultar a partir de los hechos; no se guarda ninguna foto de la semana.

    Devuelve las razones completas: quien responde al personal filtra los datos de salud.
    """
    zona = zona_de_la_sede(cursor)
    hoy = fecha_local(reloj_actual().ahora(), zona)
    cerrada = ultima_semana_cerrada(hoy)
    lunes = _lunes_pedido(semana_texto, cerrada)
    desde = datetime.combine(lunes, time(), zona)
    hasta = datetime.combine(lunes + timedelta(days=7), time(), zona)
    planificados = {}
    planificadas = 0
    for programa in listar_programas(socio_id, cursor=cursor):
        for sesion in programa["sesiones_planificadas"]:
            planificados[sesion["id"]] = tuple(
                EjercicioDeLaSemana(e["id"], e["nombre"], e["series"]) for e in sesion["ejercicios_planificados"]
            )
        if programa["creado_en"] < hasta:
            # La semana tipo del programa vigente al cerrar la semana.
            planificadas = sum(s["semana"] in (None, 1) for s in programa["sesiones_planificadas"])
    sesiones = sesiones_de_la_semana(cursor, socio_id, desde, hasta)
    visitas = sum(desde <= momento < hasta for momento in visitas_de_socios(cursor, [socio_id]).get(socio_id, []))
    resumen = resumir_semana(
        tuple(
            SesionDeLaSemana(
                s["id"],
                planificados.get(s["sesion_planificada_id"], ()),
                tuple(
                    SerieDeLaSemana(
                        serie["ejercicio_planificado_id"],
                        serie["repeticiones"],
                        serie["duracion"],
                        Decimal(serie["distancia"]) if serie["distancia"] is not None else None,
                    )
                    for serie in s["series"]
                ),
                tuple(s["razones"]),
            )
            for s in sesiones
        ),
        visitas,
        planificadas,
    )
    alta = datos_de_acompanamiento(cursor, [socio_id])[socio_id]["alta"].replace(tzinfo=UTC)
    primera = min(filter(None, (alta, primera_sesion(cursor, socio_id))))
    return {
        "semana": {
            "lunes": lunes.isoformat(),
            "domingo": (lunes + timedelta(days=6)).isoformat(),
            "anterior": (lunes - timedelta(days=7)).isoformat()
            if lunes > inicio_de_semana(fecha_local(primera, zona))
            else None,
            "siguiente": (lunes + timedelta(days=7)).isoformat() if lunes < cerrada else None,
        },
        **resumen,
    }


def consultar_resumen_semanal_propio(usuario, semana_texto=None):
    with transaccion() as cursor:
        return resumen_semanal(cursor, desde_texto(usuario["id"]), semana_texto)
