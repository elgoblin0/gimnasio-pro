"""Ocurrencias semanales y ocurrencias con fecha fijada."""

from datetime import timedelta


def ocurrencias_en_rango(clases, ocurrencias, desde, hasta):
    por_clase = {clase["id"]: clase for clase in clases}
    resultado = {}
    for ocurrencia in ocurrencias:
        if ocurrencia["clase_id"] in por_clase and desde <= ocurrencia["fecha"] <= hasta:
            clave = (ocurrencia["clase_id"], ocurrencia["fecha"])
            resultado[clave] = {
                campo: ocurrencia[campo] for campo in ("clase_id", "fecha", "hora_inicio", "duracion_minutos")
            }
    for clase in por_clase.values():
        if clase["archivada"]:
            continue
        fecha = desde + timedelta(days=(clase["dia_semana"] - desde.isoweekday()) % 7)
        while fecha <= hasta:
            resultado.setdefault(
                (clase["id"], fecha),
                {
                    "clase_id": clase["id"],
                    "fecha": fecha,
                    "hora_inicio": clase["hora_inicio"],
                    "duracion_minutos": clase["duracion_minutos"],
                },
            )
            fecha += timedelta(days=7)
    return sorted(resultado.values(), key=lambda fila: (fila["fecha"], fila["hora_inicio"], fila["clase_id"]))


def estado_reservas(cupo, reservas_activas):
    """Quién tiene lugar y quién espera; se deriva, nunca se guarda (ADR 0002)."""
    if cupo < 1:
        raise ValueError("El cupo debe ser al menos 1.")
    ordenadas = sorted(reservas_activas, key=lambda reserva: (reserva["solicitada_en"], reserva["id"]))
    return {
        "con_lugar": [reserva["id"] for reserva in ordenadas[:cupo]],
        "en_espera": [
            {"id": reserva["id"], "posicion": posicion} for posicion, reserva in enumerate(ordenadas[cupo:], start=1)
        ],
    }


def cambios_de_estado(antes, despues):
    """Reservas que ya existían y pasaron a tener lugar o volvieron a la espera."""
    tenian_lugar = set(antes["con_lugar"])
    esperaban = {fila["id"] for fila in antes["en_espera"]}
    return {
        "pasaron_a_tener_lugar": [id_ for id_ in despues["con_lugar"] if id_ in esperaban],
        "volvieron_a_espera": [fila["id"] for fila in despues["en_espera"] if fila["id"] in tenian_lugar],
    }
