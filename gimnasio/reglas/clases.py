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
