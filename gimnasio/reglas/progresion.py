"""Doble progresión pura y explicable, según los ADR 0012, 0015 y 0016."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from gimnasio.comun.tipos import PrescripcionEjercicio, Razon
from gimnasio.reglas.alternativas import elegir_alternativas
from gimnasio.reglas.dolor import aplicar_dolor
from gimnasio.reglas.restricciones import aplicar_restricciones, excluido
from gimnasio.reglas.version import VERSION_REGLAS


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


def historial_para_sesion(historial, sesion_planificada_id, semana_local):
    """Excluye solo la misma sesión planificada de esta semana (ADR 0016)."""
    return tuple(
        h for h in historial if not (h.sesion_planificada_id == sesion_planificada_id and h.fecha_local >= semana_local)
    )


def aplicar_frenos(ajustada, anterior, ejercicio, entrada, hubo_suba, sesion_planificada_id):
    """Paso final obligatorio: el freno 3 solo actúa ante una suba propuesta."""
    subas = tuple(
        s
        for s in historial_para_sesion(entrada.subas, sesion_planificada_id, entrada.semana_local)
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


def _ajustar_ejercicio(planificado, entrada, sesion_planificada_id):
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
        for h in historial_para_sesion(entrada.historial, sesion_planificada_id, entrada.semana_local)
        if h.ejercicio_id == planificado.ejercicio_catalogo_id and h.fecha_local <= entrada.fecha_local and h.series
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
        ajustada, prescripcion, ejercicio, entrada, explicacion.regla == "subir_carga", sesion_planificada_id
    )
    return ajustada, razones + razones_freno, frenos


def _aplicar_chequeo(planificado, entrada, sesion_planificada_id):
    ajustada, razones, frenos = _ajustar_ejercicio(planificado, entrada, sesion_planificada_id)
    chequeo = entrada.chequeo
    if chequeo is None:
        return (
            ajustada,
            razones + (razon("sin_chequeo", ajustada, "Sin chequeo del día: se toma como neutro."),),
            frenos,
        )
    if chequeo.sueno > 2 and chequeo.energia > 2:
        return ajustada, razones, frenos
    suba = next((r for r in razones if r.regla == "subir_carga"), None)
    if suba is not None:
        ajustada = replace(
            ajustada,
            carga=Decimal(dict(suba.datos)["carga_base"]),
            repeticiones_minimas=planificado.repeticiones_maximas,
        )
    ajustada = replace(ajustada, series=max(1, ajustada.series - 1))
    explicacion = razon(
        "chequeo_desfavorable",
        ajustada,
        "Chequeo del día desfavorable: una serie menos (mínimo una) y se anulan las subas de hoy. "
        "Se deja un aviso al entrenador al iniciar la sesión.",
        sueno=chequeo.sueno,
        energia=chequeo.energia,
        series=ajustada.series,
        suba_anulada=suba is not None,
    )
    return ajustada, razones + (explicacion,), frenos + ("chequeo_desfavorable",)


def ajustar_ejercicio(planificado, entrada, sesion_planificada_id):
    ajustada, razones, frenos = _aplicar_chequeo(planificado, entrada, sesion_planificada_id)
    ejercicio = next((e for e in entrada.catalogo if e.ejercicio_id == planificado.ejercicio_catalogo_id), None)
    if ejercicio is None:
        if any(
            r.patron_movimiento is not None
            or r.zona is not None
            or (
                r.ejercicio_id is not None
                and r.ejercicio_id in (planificado.ejercicio_catalogo_id, planificado.ejercicio_id)
            )
            for r in entrada.restricciones
        ):
            ajustada = replace(ajustada, series=0, ejercicio_hecho_id=None)
            return (
                ajustada,
                razones
                + (
                    razon(
                        "restriccion_salud",
                        ajustada,
                        "Se quita el ejercicio por una restricción registrada por tu entrenador.",
                    ),
                ),
                frenos + ("restriccion_salud",),
            )
        return ajustada, razones, frenos
    antes_frenos = ajustada
    ajustada, razones_dolor, frenos_dolor = aplicar_dolor(
        ajustada,
        ejercicio,
        entrada.catalogo,
        entrada.dolores_actuales,
        entrada.dolores_anteriores,
        razones,
        entrada.equipos_fuera_de_servicio,
    )
    ajustada, razones_salud, frenos_salud = aplicar_restricciones(
        ajustada,
        ejercicio,
        entrada.catalogo,
        entrada.restricciones,
        entrada.dolores_actuales,
        entrada.equipos_fuera_de_servicio,
    )
    if entrada.equipos_fuera_de_servicio and antes_frenos.series and not ajustada.series:
        # La falta de equipo no quita trabajo: comprobamos si existe una
        # alternativa segura aun cuando su equipo esté fuera de servicio.
        disponible, dolor_disponible, frenos_dolor_disponible = aplicar_dolor(
            antes_frenos,
            ejercicio,
            entrada.catalogo,
            entrada.dolores_actuales,
            entrada.dolores_anteriores,
            razones,
        )
        disponible, salud_disponible, frenos_salud_disponible = aplicar_restricciones(
            disponible, ejercicio, entrada.catalogo, entrada.restricciones, entrada.dolores_actuales
        )
        if disponible.series:
            ajustada = replace(disponible, ejercicio_hecho_id=None, no_disponible=True)
            razones_dolor, frenos_dolor = dolor_disponible, frenos_dolor_disponible
            razones_salud, frenos_salud = salud_disponible, frenos_salud_disponible
            razones += (
                razon(
                    "ejercicio_no_disponible",
                    ajustada,
                    "El equipo está fuera de servicio y no hay alternativa disponible. Sigue pendiente.",
                ),
            )
    razones += razones_dolor + razones_salud
    hecho = next((e for e in entrada.catalogo if e.ejercicio_id == ajustada.ejercicio_hecho_id), ejercicio)
    if ajustada.series and not ajustada.no_disponible and hecho.equipo in entrada.equipos_fuera_de_servicio:
        alternativas, explicacion = elegir_alternativas(
            ejercicio.ejercicio_id,
            entrada.catalogo,
            zonas_excluidas=entrada.dolores_actuales,
            ejercicios_excluidos=tuple(e.ejercicio_id for e in entrada.catalogo if excluido(e, entrada.restricciones)),
            motivo="equipo_fuera_de_servicio",
            equipos_fuera_de_servicio=entrada.equipos_fuera_de_servicio,
        )
        if alternativas:
            ajustada = replace(ajustada, ejercicio_hecho_id=alternativas[0].ejercicio_id)
            razones += (replace(explicacion, datos=(("ejercicio_id", ajustada.ejercicio_id),) + explicacion.datos[1:]),)
        else:
            ajustada = replace(ajustada, no_disponible=True)
            razones += (
                razon(
                    "ejercicio_no_disponible",
                    ajustada,
                    "El equipo está fuera de servicio y no hay alternativa disponible. Sigue pendiente.",
                ),
            )
    return ajustada, razones, frenos + frenos_dolor + frenos_salud
