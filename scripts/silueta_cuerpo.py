"""Genera `gimnasio/static/js/comun/silueta-cuerpo.js` desde `scripts/musculos_cuerpo.py`.

La silueta SVG es la carga del cuerpo 3D y su alternativa sin efectos. Dibuja la figura masculina de frente
y de espalda, con los mismos músculos que el mapa del 3D: cada zona es la unión de sus músculos, en ambos lados.

    python scripts/silueta_cuerpo.py              # escribe el módulo
    python scripts/silueta_cuerpo.py --verificar  # falla si el módulo no coincide con los músculos
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

from musculos_cuerpo import CONTORNO, MUSCULOS, ZONAS  # noqa: E402

DESTINO = RAIZ / "gimnasio/static/js/comun/silueta-cuerpo.js"
# Unidades del viewBox por metro, línea del suelo y centro de cada vista.
ESCALA = 195
SUELO = 382
CENTROS = {"f": 98, "e": 288}
# Cabeza: centro y radios en metros, sobre la línea media.
CABEZA = (1.665, 0.082, 0.112)


def punto(centro, signo, x, y):
    return f"{centro + signo * x * ESCALA:.1f} {SUELO - y * ESCALA:.1f}"


def poligono(centro, signo, puntos):
    return "M" + " L".join(punto(centro, signo, x, y) for x, y in puntos) + " Z"


def espejado(centro, puntos):
    return " ".join(poligono(centro, signo, puntos) for signo in (-1, 1))


def contorno(centro):
    # Del cuello al pie por la derecha y de vuelta por la izquierda: una sola figura cerrada.
    ida = [punto(centro, 1, x, y) for x, y in CONTORNO]
    vuelta = [punto(centro, -1, x, y) for x, y in reversed(CONTORNO)]
    return "M" + " L".join(ida + vuelta) + " Z"


def cabeza(centro):
    y, rx, ry = CABEZA
    cx, cy = centro, SUELO - y * ESCALA
    ancho, alto = rx * ESCALA, ry * ESCALA
    arco = f"a{ancho:.1f} {alto:.1f} 0 1 0"
    return f"M{cx - ancho:.1f} {cy:.1f} {arco} {2 * ancho:.1f} 0 {arco} {-2 * ancho:.1f} 0 Z"


def generar():
    zonas = {zona: [] for zona in ZONAS}
    relieve = []
    for _nombre, zona, lado, puntos, _fibra in MUSCULOS:
        trazo = espejado(CENTROS[lado], puntos)
        (zonas[zona] if zona else relieve).append(trazo)
    vacias = [zona for zona, trazos in zonas.items() if not trazos]
    if vacias:
        raise SystemExit(f"Zonas sin músculo: {', '.join(vacias)}")
    figura = " ".join(f"{cabeza(c)} {contorno(c)}" for c in CENTROS.values())
    lineas = [
        "// Generado por scripts/silueta_cuerpo.py desde scripts/musculos_cuerpo.py. No editar a mano.",
        "// Figura masculina de frente (izquierda) y de espalda (derecha), en un viewBox de 400 de alto.",
        f'export const FIGURA = "{figura}";',
        f'export const RELIEVE = "{" ".join(relieve)}";',
        "export const TRAZOS = Object.freeze({",
        *(f'  {zona}: "{" ".join(trazos)}",' for zona, trazos in zonas.items()),
        "});",
        "",
    ]
    return "\n".join(lineas)


if __name__ == "__main__":
    contenido = generar()
    if "--verificar" in sys.argv[1:]:
        if DESTINO.read_text(encoding="utf-8") != contenido:
            raise SystemExit(f"{DESTINO.relative_to(RAIZ)} no coincide: correr python scripts/silueta_cuerpo.py")
        print("Silueta al día.")
    else:
        DESTINO.write_text(contenido, encoding="utf-8", newline="\n")
        print(f"Escrito {DESTINO.relative_to(RAIZ)}.")
