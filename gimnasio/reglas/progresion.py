"""Doble progresión pura y explicable, según los ADR 0012, 0015 y 0016."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from gimnasio.comun.tipos import PrescripcionEjercicio, Razon

VERSION_REGLAS = "2.0.0"


def razon(regla, prescripcion, explicacion, **datos):
    return Razon(
        regla,
        VERSION_REGLAS,
        (("ejercicio_id", prescripcion.ejercicio_id),)
        + tuple((clave, str(valor)) for clave, valor in datos.items() if valor is not None)
        + (("explicacion", explicacion),),
    )


def numero(valor):
    texto = format(valor, "f") if isinstance(valor, Decimal) else str(valor)
    return (texto.rstrip("0").rstrip(".") if "." in texto else texto).replace(".", ",")


def subir_carga(prescripcion, ejercicio, ultima, piso):
    carga = prescripcion.carga + ejercicio.incremento_carga
    esfuerzo = (
        f" con RIR registrado igual o mayor que el objetivo {prescripcion.rir_objetivo}"
        " o evaluado solo por repeticiones cuando falta RIR"
        if prescripcion.rir_objetivo is not None
        else ""
    )
    return replace(prescripcion, carga=carga, repeticiones_minimas=piso), razon(
        "subir_carga",
        prescripcion,
        f"Subís {numero(ejercicio.incremento_carga)} kg en {ejercicio.nombre}: "
        f"completaste {len(ultima.series)}×{prescripcion.repeticiones_maximas}{esfuerzo}. "
        f"La carga base usada es {numero(prescripcion.carga)} kg.",
        carga_base=prescripcion.carga,
        carga_anterior=prescripcion.carga,
        carga=carga,
        incremento_carga=ejercicio.incremento_carga,
        repeticiones=prescripcion.repeticiones_maximas,
        series=len(ultima.series),
        rir_objetivo=prescripcion.rir_objetivo,
        rir_registrados=(
            tuple(s.rir for s in ultima.series if s.rir is not None) if prescripcion.rir_objetivo is not None else None
        ),
        fecha_local=ultima.fecha_local.isoformat(),
    )


def mantener_carga(prescripcion, ejercicio, ultima):
    repeticiones = min(prescripcion.repeticiones_maximas, min(s.repeticiones for s in ultima.series) + 1)
    repeticiones = max(prescripcion.repeticiones_minimas, repeticiones)
    return replace(prescripcion, repeticiones_minimas=repeticiones), razon(
        "mantener_carga",
        prescripcion,
        f"Mantenés {numero(prescripcion.carga)} kg en {ejercicio.nombre}: "
        f"todavía no completaste el tope en todas las series planificadas; buscás {repeticiones} repeticiones.",
        carga_base=prescripcion.carga,
        carga=prescripcion.carga,
        repeticiones_anteriores=tuple(s.repeticiones for s in ultima.series),
        repeticiones=repeticiones,
        tope=prescripcion.repeticiones_maximas,
        fecha_local=ultima.fecha_local.isoformat(),
    )


def series_bajo_piso(sesion, piso):
    return sum(s.repeticiones is not None and s.repeticiones < piso for s in sesion.series)


def bajar_carga(prescripcion, ejercicio, historial):
    carga = max(Decimal(0), prescripcion.carga - ejercicio.incremento_carga)
    cantidades = tuple(series_bajo_piso(h, prescripcion.repeticiones_minimas) for h in historial[-2:])
    detalle = " y ".join(
        f"{cantidad} de {len(h.series)}" for cantidad, h in zip(cantidades, historial[-2:], strict=True)
    )
    return replace(prescripcion, carga=carga), razon(
        "bajar_carga",
        prescripcion,
        f"Bajás a {numero(carga)} kg en {ejercicio.nombre}: "
        f"quedaron bajo el piso de {prescripcion.repeticiones_minimas} repeticiones "
        f"{detalle} series en las dos últimas sesiones (más de la mitad en ambas). "
        f"La carga base usada es {numero(prescripcion.carga)} kg.",
        carga_base=prescripcion.carga,
        carga_anterior=prescripcion.carga,
        carga=carga,
        incremento_carga=ejercicio.incremento_carga,
        piso=prescripcion.repeticiones_minimas,
        series_bajo_piso=cantidades,
        series_por_sesion=tuple(len(h.series) for h in historial[-2:]),
        repeticiones_anteriores=tuple(tuple(s.repeticiones for s in h.series) for h in historial[-2:]),
        fechas=tuple(h.fecha_local.isoformat() for h in historial[-2:]),
    )


def mantener_por_rir(prescripcion, ejercicio, ultima):
    rir = min(s.rir for s in ultima.series if s.rir is not None)
    return replace(prescripcion, repeticiones_minimas=prescripcion.repeticiones_maximas), razon(
        "mantener_por_rir",
        prescripcion,
        f"Mantenés {numero(prescripcion.carga)} kg en {ejercicio.nombre}: "
        f"llegaste a {prescripcion.repeticiones_maximas} repeticiones, "
        f"pero con RIR {rir} y el objetivo es {prescripcion.rir_objetivo}.",
        carga_base=prescripcion.carga,
        carga=prescripcion.carga,
        repeticiones=prescripcion.repeticiones_maximas,
        rir_minimo=rir,
        rir_objetivo=prescripcion.rir_objetivo,
        fecha_local=ultima.fecha_local.isoformat(),
    )


def sin_rir(prescripcion, ejercicio, sesiones):
    return prescripcion, razon(
        "sin_rir",
        prescripcion,
        f"En {ejercicio.nombre} hay series sin RIR: esas series se evalúan solo por repeticiones.",
        series_sin_rir=sum(s.rir is None for h in sesiones for s in h.series),
        fechas=tuple(h.fecha_local.isoformat() for h in sesiones),
    )


def aplicar_frenos(ajustada, anterior, ejercicio, entrada, hubo_suba):
    """Paso final obligatorio: el freno 3 solo actúa ante una suba propuesta."""
    subas = tuple(
        s
        for s in entrada.subas
        if s.ejercicio_id == ejercicio.ejercicio_id
        and entrada.semana_local <= s.fecha_local < entrada.semana_local + timedelta(days=7)
        and s.fecha_local <= entrada.fecha_local
    )
    if not hubo_suba or not subas:
        return ajustada, (), ()
    frenada = replace(ajustada, carga=anterior.carga, repeticiones_minimas=anterior.repeticiones_maximas)
    explicacion = razon(
        "tope_semanal",
        frenada,
        f"Mantenés {numero(anterior.carga)} kg en {ejercicio.nombre}: "
        "ya hubo una suba esta semana; el tope es un incremento por ejercicio de lunes a domingo.",
        carga=anterior.carga,
        incremento_carga=ejercicio.incremento_carga,
        semana_local=entrada.semana_local.isoformat(),
        subas=tuple(s.fecha_local.isoformat() for s in subas),
    )
    return frenada, (explicacion,), ("tope_semanal",)


def ajustar_ejercicio(planificado, entrada, sesion_planificada_id):
    prescripcion = PrescripcionEjercicio(
        planificado.ejercicio_id,
        planificado.series,
        planificado.repeticiones_minimas,
        planificado.repeticiones_maximas,
        planificado.carga,
        planificado.rir_objetivo,
        planificado.descanso,
    )
    ejercicio = next((e for e in entrada.catalogo if e.ejercicio_id == planificado.ejercicio_catalogo_id), None)
    historial = tuple(
        h
        for h in entrada.historial
        if h.ejercicio_id == planificado.ejercicio_catalogo_id
        and h.fecha_local <= entrada.fecha_local
        and h.series
        and not (h.sesion_planificada_id == sesion_planificada_id and h.fecha_local >= entrada.semana_local)
    )
    if (
        ejercicio is None
        or ejercicio.incremento_carga is None
        or prescripcion.carga is None
        or prescripcion.repeticiones_minimas is None
        or prescripcion.repeticiones_maximas is None
        or not historial
    ):
        return (
            prescripcion,
            (
                razon(
                    "respeto_programa_entrenador",
                    prescripcion,
                    "Se respeta el plan del entrenador sin ajustes de carga, repeticiones, series ni volumen.",
                ),
            ),
            (),
        )
    ultima = historial[-1]
    # Las series vigentes vienen ordenadas por sesión desde el servicio.
    if any(s.repeticiones is None or s.carga is None for s in ultima.series):
        return (
            prescripcion,
            (
                razon(
                    "respeto_programa_entrenador",
                    prescripcion,
                    "Se conserva la prescripción: el historial no tiene las medidas de carga y repeticiones.",
                ),
            ),
            (),
        )
    prescripcion = replace(prescripcion, carga=min(s.carga for s in ultima.series))
    tope = len(ultima.series) >= planificado.series and all(
        s.repeticiones >= prescripcion.repeticiones_maximas for s in ultima.series
    )
    dos_fallos = len(historial) >= 2 and all(
        series_bajo_piso(h, prescripcion.repeticiones_minimas) * 2 > len(h.series) for h in historial[-2:]
    )
    if dos_fallos:
        ajustada, explicacion = bajar_carga(prescripcion, ejercicio, historial)
        decisivas = historial[-2:]
    elif tope:
        rir_bajo = prescripcion.rir_objetivo is not None and any(
            s.rir is not None and s.rir < prescripcion.rir_objetivo for s in ultima.series
        )
        ajustada, explicacion = (
            mantener_por_rir(prescripcion, ejercicio, ultima)
            if rir_bajo
            else subir_carga(prescripcion, ejercicio, ultima, planificado.repeticiones_minimas)
        )
        decisivas = (ultima,)
    else:
        ajustada, explicacion = mantener_carga(prescripcion, ejercicio, ultima)
        decisivas = (ultima,)
    razones = (explicacion,)
    if prescripcion.rir_objetivo is not None and any(s.rir is None for h in decisivas for s in h.series):
        ajustada, explicacion_rir = sin_rir(ajustada, ejercicio, decisivas)
        razones += (explicacion_rir,)
    ajustada, razones_freno, frenos = aplicar_frenos(
        ajustada, prescripcion, ejercicio, entrada, explicacion.regla == "subir_carga"
    )
    return ajustada, razones + razones_freno, frenos
