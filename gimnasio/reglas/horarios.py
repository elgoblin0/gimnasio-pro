"""Previsión de ocupación a partir de visitas confiables en hora local."""

from datetime import datetime, time, timedelta

from gimnasio.comun.tipos import FranjaPrevista, MejoresHorarios, MejoresHorariosDia

VERSION_MEJORES_HORARIOS = "1.0.0"


def calcular_mejores_horarios(
    visitas: tuple[tuple[datetime, datetime], ...],
    ahora_local: datetime,
    horario: tuple[tuple[int, tuple[tuple[str, str], ...]], ...],
    semanas: int = 8,
) -> MejoresHorarios:
    desde = ahora_local - timedelta(weeks=semanas)

    def calcular_dia(fecha):
        intervalos = next((intervalos for dia, intervalos in horario if dia == fecha.isoweekday()), ())
        if not intervalos:
            return MejoresHorariosDia((), cerrado=True)
        previstas = []
        suficientes = False
        for hora in range(24):
            inicio = datetime.combine(fecha, time(hora))
            fin = inicio + timedelta(hours=1)
            if not any(
                time.fromisoformat(apertura) <= inicio.time()
                and fin.date() == fecha
                and fin.time() <= time.fromisoformat(cierre)
                for apertura, cierre in intervalos
            ):
                continue
            ocupaciones = []
            for dias in range(1, semanas * 7 + 1):
                anterior = ahora_local.date() - timedelta(days=dias)
                if anterior.isoweekday() != fecha.isoweekday():
                    continue
                comienzo = datetime.combine(anterior, time(hora))
                if comienzo < desde:
                    continue
                muestras = tuple(comienzo + timedelta(minutes=minutos) for minutos in (0, 15, 30, 45))
                ocupaciones.append(
                    sum(sum(entrada <= muestra < salida for entrada, salida in visitas) for muestra in muestras) / 4
                )
            if len(ocupaciones) < 4:
                continue
            suficientes = True
            if fecha == ahora_local.date() and fin <= ahora_local:
                continue
            previstas.append(
                FranjaPrevista(
                    inicio.strftime("%H:%M"),
                    fin.strftime("%H:%M"),
                    sum(ocupaciones) / len(ocupaciones),
                    len(ocupaciones),
                )
            )
        return MejoresHorariosDia(
            tuple(sorted(previstas, key=lambda franja: (franja.prevision, franja.desde))[:3]),
            datos_insuficientes=not suficientes,
        )

    return MejoresHorarios(calcular_dia(ahora_local.date()), calcular_dia(ahora_local.date() + timedelta(days=1)))
