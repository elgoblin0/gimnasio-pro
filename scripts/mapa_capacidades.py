"""Genera docs/MAPA-CAPACIDADES.md desde docs/capacidades.toml.

Uso:
    python scripts/mapa_capacidades.py             # regenera el mapa
    python scripts/mapa_capacidades.py --verificar # falla si está desactualizado o es inválido
"""

import sys
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FUENTE = RAIZ / "docs" / "capacidades.toml"
DESTINO = RAIZ / "docs" / "MAPA-CAPACIDADES.md"

NIVELES = ["pendiente", "esqueleto", "funcional", "pulida", "validada"]
DEFINICIONES = {
    "esqueleto": "Funciona de punta a punta con la semilla; lo prueba un e2e de humo.",
    "funcional": "Cumple sus reglas y casos de aceptación; lo prueban pytest o node --test.",
    "pulida": (
        "Estados vacíos, carga y error, móvil, accesibilidad y movimiento; "
        "lo prueba un e2e con chequeo de accesibilidad."
    ),
    "validada": "El usuario la aprobó en un dispositivo real en el cierre de una etapa.",
}


def validar(capacidades):
    errores = []
    for cap in capacidades:
        nombre = cap.get("id", "?")
        nivel = cap.get("nivel")
        if nivel not in NIVELES:
            errores.append(f"{nombre}: nivel desconocido {nivel!r}")
            continue
        if nivel == "pendiente":
            continue
        prueba = cap.get("prueba", "")
        if not prueba:
            errores.append(f"{nombre}: el nivel {nivel} exige una prueba")
            continue
        ruta, _, funcion = prueba.partition("::")
        archivo = RAIZ / ruta
        if not archivo.is_file():
            errores.append(f"{nombre}: no existe {ruta}")
        elif funcion and funcion not in archivo.read_text(encoding="utf-8"):
            errores.append(f"{nombre}: {ruta} no define {funcion}")
        if nivel == "validada" and not cap.get("validacion"):
            errores.append(f"{nombre}: validada exige el issue de cierre en `validacion`")
    return errores


def generar(capacidades):
    lineas = [
        "# Mapa de capacidades",
        "",
        "Generado por `scripts/mapa_capacidades.py` desde `docs/capacidades.toml`. No editar a mano.",
        "",
        "## Niveles",
        "",
    ]
    lineas += [f"- **{nivel}**: {texto}" for nivel, texto in DEFINICIONES.items()]
    # Sin línea de resumen: cambiaría en cada PR y generaría conflictos entre ramas paralelas.
    lineas.append("")
    grupos = []
    for cap in capacidades:
        if cap["grupo"] not in grupos:
            grupos.append(cap["grupo"])
    for grupo in grupos:
        lineas += [f"## {grupo}", "", "| Capacidad | Etapa | Nivel | Prueba |", "|---|---|---|---|"]
        for cap in capacidades:
            if cap["grupo"] != grupo:
                continue
            prueba = f"`{cap['prueba']}`" if cap.get("prueba") else "—"
            if cap.get("validacion"):
                prueba += f" · {cap['validacion']}"
            lineas.append(f"| {cap['nombre']} | {cap['etapa']} | {cap['nivel']} | {prueba} |")
        lineas.append("")
    return "\n".join(lineas)


def main():
    capacidades = tomllib.loads(FUENTE.read_text(encoding="utf-8"))["capacidad"]
    errores = validar(capacidades)
    if errores:
        print("\n".join(errores))
        return 1
    contenido = generar(capacidades)
    if "--verificar" in sys.argv:
        actual = DESTINO.read_text(encoding="utf-8") if DESTINO.exists() else ""
        if actual != contenido:
            print("docs/MAPA-CAPACIDADES.md está desactualizado: ejecutá python scripts/mapa_capacidades.py")
            return 1
        return 0
    DESTINO.write_text(contenido, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
