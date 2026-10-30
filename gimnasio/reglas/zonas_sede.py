"""Ubicación en la sede a partir del equipo de las series realizadas."""

from datetime import datetime, timedelta

ZONAS_SEDE = ("musculacion", "peso_libre", "cardio", "funcional")
NOMBRES_ZONAS_SEDE = {
    "musculacion": "Musculación",
    "peso_libre": "Peso libre",
    "cardio": "Cardio",
    "funcional": "Funcional",
    "en_la_sede": "En la sede",
}
ZONA_POR_EQUIPO = {
    "barra": "peso_libre",
    "mancuernas": "peso_libre",
    "cinta": "cardio",
    "sin equipo": "funcional",
    "cajon": "funcional",
}


def ubicar_en_zona(series: list[tuple[datetime, str]], ahora: datetime, desde_entrada: datetime) -> str:
    ultima = max(
        (serie for serie in series if desde_entrada <= serie[0] <= ahora), key=lambda serie: serie[0], default=None
    )
    if ultima is None or ahora - ultima[0] > timedelta(minutes=20):
        return "en_la_sede"
    return ZONA_POR_EQUIPO.get(ultima[1], "funcional")
