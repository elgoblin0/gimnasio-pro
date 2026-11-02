"""Convierte una figura de Human Base Meshes (Blender Studio, CC0) en el GLB y el mapa de músculos del cuerpo 3D.

Se ejecuta dentro de Blender 4.2 LTS, con el paquete abierto:

    blender --background human_base_meshes_bundle.blend --python scripts/exportar_cuerpo.py -- \
        GEO-body_male_realistic gimnasio/static/vendor/cuerpo@3/masculina
    blender --background human_base_meshes_bundle.blend --python scripts/exportar_cuerpo.py -- \
        GEO-body_female_realistic gimnasio/static/vendor/cuerpo@3/femenina

Las formas salen de `scripts/musculos_cuerpo.py`. El relieve se esculpe en la malla y el mapa (`.png`) guarda, por
texel, frente y espalda lado a lado: R la zona (4 bits altos) y la zona más cercana (4 bajos), G la distancia al borde
del músculo y B la coordenada de fibra. La pelvis queda suavizada; no es una referencia anatómica.
"""

import json
import pathlib
import struct
import sys
import zlib

import bpy
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from musculos_cuerpo import MUSCULOS, PARES_FEMENINA, ZONAS  # noqa: E402

ALTURA = 1.79
TRIANGULOS = 26000
# Mapa: frente y espalda ocupan ANCHO_LADO metros cada uno. Se calcula al doble y se reduce al guardar.
ANCHO_LADO, ALTO_MAPA = 0.48, 1.84
LADO_PX, ALTO_PX = 256, 1024
DISTANCIA_MAXIMA = 0.03
RADIO_MUSCULO = 0.03
HOLGURA_ENTRE_MUSCULOS = 0.008
MARGEN_PIEL = 0.012
ZONA_SIN_MARCA = 15

FIGURAS = {
    "GEO-body_male_realistic": {"relieve": 0.007, "pasadas_pecho": 12, "deformar": False},
    "GEO-body_female_realistic": {"relieve": 0.004, "pasadas_pecho": 260, "deformar": True},
}


def rampa(valor, desde, hasta):
    t = np.clip((valor - desde) / (hasta - desde), 0, 1)
    return t * t * (3 - 2 * t)


def curva_cerrada(puntos, pasos=10):
    """Catmull-Rom cerrada: los músculos se dibujan con pocos puntos."""
    p = np.array(puntos, dtype=float)
    p0, p1, p2, p3 = np.roll(p, 1, 0), p, np.roll(p, -1, 0), np.roll(p, -2, 0)
    t = (np.arange(pasos) / pasos)[None, :, None]
    p0, p1, p2, p3 = (q[:, None, :] for q in (p0, p1, p2, p3))
    curva = 0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t**2 + (3 * p1 - p0 - 3 * p2 + p3) * t**3)
    return curva.reshape(-1, 2)


def deformador(pares):
    """Spline de placa delgada que lleva puntos de la figura masculina a la femenina."""
    origen = np.array([a for a, _ in pares], dtype=float)
    destino = np.array([b for _, b in pares], dtype=float)
    # Lo espejado también se corresponde: evita que la línea media se doble.
    espejo = origen[:, 0] > 0
    origen = np.vstack([origen, origen[espejo] * [-1, 1]])
    destino = np.vstack([destino, destino[espejo] * [-1, 1]])

    def nucleo(a, b):
        r2 = ((a[:, None] - b[None]) ** 2).sum(2)
        return r2 * np.log(r2 + 1e-12) / 2

    n = len(origen)
    afin = np.hstack([np.ones((n, 1)), origen])
    sistema = np.block([[nucleo(origen, origen), afin], [afin.T, np.zeros((3, 3))]])
    sistema[:n, :n] += np.eye(n) * 1e-5
    pesos = np.linalg.solve(sistema, np.vstack([destino, np.zeros((3, 2))]))

    def aplicar_a(puntos):
        puntos = np.asarray(puntos, dtype=float)
        return nucleo(puntos, origen) @ pesos[:n] + np.hstack([np.ones((len(puntos), 1)), puntos]) @ pesos[n:]

    return aplicar_a


def adentro(curva, x, y):
    dentro = np.zeros(x.shape, bool)
    for (x1, y1), (x2, y2) in zip(curva, np.roll(curva, -1, 0), strict=True):
        cruza = (y1 > y) != (y2 > y)
        dentro ^= cruza & (x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1)
    return dentro


def cerrar_huecos(ids, pasadas):
    """Dos músculos vecinos comparten un solo surco, sin una franja de piel entre ellos."""
    rectos = ((0, 1), (0, -1), (1, 1), (1, -1))
    diagonales = (((0, 1), (1, 1)), ((0, 1), (1, -1)), ((0, -1), (1, 1)), ((0, -1), (1, -1)))
    for pasada in range(pasadas):
        vacio = ids == 0
        # Alternar vecindades da un frente casi redondo, sin esquinas en rombo.
        for eje, paso in rectos:
            ids = np.where(vacio & (ids == 0), np.roll(ids, paso, eje), ids)
        if pasada % 2:
            for (eje1, paso1), (eje2, paso2) in diagonales:
                ids = np.where(vacio & (ids == 0), np.roll(np.roll(ids, paso1, eje1), paso2, eje2), ids)
    return ids


def distancia_desde(semillas):
    """Transformada de distancia en píxeles, por barridos."""
    d = np.where(semillas, 0.0, 1e6)
    columnas = np.arange(semillas.shape[1], dtype=float)
    diagonal = 2**0.5

    def barrer(fila, previa):
        fila = np.minimum(fila, previa + 1)
        fila[1:] = np.minimum(fila[1:], previa[:-1] + diagonal)
        fila[:-1] = np.minimum(fila[:-1], previa[1:] + diagonal)
        fila = np.minimum.accumulate(fila - columnas) + columnas
        return (np.minimum.accumulate((fila + columnas)[::-1]) - columnas[::-1])[::-1]

    for y in range(1, len(d)):
        d[y] = barrer(d[y], d[y - 1])
    for y in range(len(d) - 2, -1, -1):
        d[y] = barrer(d[y], d[y + 1])
    return d


def bordes_de(musculos):
    """Separa el borde entre dos músculos (lleva surco) del borde contra la piel (no lo lleva)."""
    entre_musculos = np.zeros(musculos.shape, bool)
    contra_piel = np.zeros(musculos.shape, bool)
    for eje in (0, 1):
        a = np.take(musculos, range(musculos.shape[eje] - 1), eje)
        b = np.take(musculos, range(1, musculos.shape[eje]), eje)
        distintos = a != b
        ambos = distintos & (a > 0) & (b > 0)
        piel = distintos & ~ambos
        for matriz, marca in ((entre_musculos, ambos), (contra_piel, piel)):
            if eje == 0:
                matriz[:-1] |= marca
                matriz[1:] |= marca
            else:
                matriz[:, :-1] |= marca
                matriz[:, 1:] |= marca
    # La línea media separa cada músculo de su espejo.
    entre_musculos[:, 0] |= musculos[:, 0] > 0
    return entre_musculos, contra_piel


def desenfocar(matriz, radio=3):
    nucleo = np.ones(2 * radio + 1) / (2 * radio + 1)
    for eje in (0, 1):
        matriz = np.apply_along_axis(lambda fila: np.convolve(fila, nucleo, mode="same"), eje, matriz)
    return matriz


def coordenada_fibra(fibra, puntos_curva, x, y, deformar):
    centro = puntos_curva.mean(0)
    if fibra[0] == "eje":
        angulo = np.radians(fibra[1])
        return (x - centro[0]) * -np.sin(angulo) + (y - centro[1]) * np.cos(angulo)
    foco = np.array(fibra[1:], dtype=float)
    if deformar:
        foco = deformar(foco[None])[0]
    radio = np.linalg.norm(centro - foco)
    base = np.arctan2(*(centro - foco)[::-1])
    delta = np.arctan2(y - foco[1], x - foco[0]) - base
    return np.arctan2(np.sin(delta), np.cos(delta)) * radio


def hornear_lado(lado, deformar):
    alto, ancho = ALTO_PX * 2, LADO_PX * 2
    metros_x = ANCHO_LADO / ancho
    metros_y = ALTO_MAPA / alto
    musculos = np.zeros((alto, ancho), np.int16)
    codigos = [0]
    fibra = np.full((alto, ancho), 0.5)
    centros = {}
    for _nombre, zona, lado_musculo, puntos, tipo_fibra in MUSCULOS:
        if lado_musculo != lado:
            continue
        puntos = deformar(puntos) if deformar else np.array(puntos, dtype=float)
        curva = curva_cerrada(puntos)
        x0, x1 = curva[:, 0].min(), curva[:, 0].max()
        y0, y1 = curva[:, 1].min(), curva[:, 1].max()
        c0, c1 = max(int(x0 / metros_x) - 1, 0), min(int(x1 / metros_x) + 2, ancho)
        f0, f1 = max(int((ALTO_MAPA - y1) / metros_y) - 1, 0), min(int((ALTO_MAPA - y0) / metros_y) + 2, alto)
        columnas, filas = np.meshgrid(np.arange(c0, c1), np.arange(f0, f1))
        x = (columnas + 0.5) * metros_x
        y = ALTO_MAPA - (filas + 0.5) * metros_y
        dentro = adentro(curva, x, y)
        codigo = ZONAS.index(zona) + 1 if zona else ZONA_SIN_MARCA
        codigos.append(codigo)
        musculos[filas[dentro], columnas[dentro]] = len(codigos) - 1
        fibra[filas[dentro], columnas[dentro]] = np.clip(
            0.5 + coordenada_fibra(tipo_fibra, curva, x[dentro], y[dentro], deformar) / 0.24, 0, 1
        )
        if zona:
            area = dentro.sum()
            if area > centros.get(zona, (0,))[0]:
                centros[zona] = (int(area), float(curva[:, 0].mean()), float(curva[:, 1].mean()))
    musculos = cerrar_huecos(musculos, int(HOLGURA_ENTRE_MUSCULOS / metros_x))
    entre_musculos, contra_piel = bordes_de(musculos)
    metro = (metros_x + metros_y) / 2
    a_vecino = desenfocar(distancia_desde(entre_musculos) * metro)
    a_piel = desenfocar(distancia_desde(contra_piel) * metro)
    # El sombreador solo dibuja surcos entre músculos; la escultura se apaga también contra la piel.
    surco = np.minimum(a_vecino, a_piel + MARGEN_PIEL)
    escultura = np.minimum(a_vecino, a_piel)
    return np.array(codigos, np.uint8)[musculos], surco, escultura, fibra, centros


def reducir(matriz):
    return (matriz[::2, ::2] + matriz[1::2, ::2] + matriz[::2, 1::2] + matriz[1::2, 1::2]) / 4


def cercanas(ids):
    """La zona más cercana a cada texel: un toque cerca de una zona también la elige."""
    cerca = np.where(ids == ZONA_SIN_MARCA, 0, ids)
    for _ in range(24):
        vacio = cerca == 0
        for eje, paso in ((0, 1), (0, -1), (1, 1), (1, -1)):
            vecino = np.roll(cerca, paso, eje)
            cerca = np.where(vacio & (cerca == 0), vecino, cerca)
    return cerca


def hornear_mapa(deformar):
    lados = {}
    for lado in "fe":
        ids, surco, escultura, fibra, centros = hornear_lado(lado, deformar)
        id_final = ids[1::2, 1::2]
        surco_final = np.clip(reducir(surco) / DISTANCIA_MAXIMA, 0, 1) * (id_final > 0)
        escultura_final = np.clip(reducir(escultura), 0, DISTANCIA_MAXIMA) * (id_final > 0)
        lados[lado] = (id_final, surco_final, reducir(fibra), centros, escultura_final)
    ids = np.hstack([lados["f"][0], lados["e"][0]])
    surco = np.hstack([lados["f"][1], lados["e"][1]])
    fibra = np.hstack([lados["f"][2], lados["e"][2]])
    rojo = (ids.astype(np.uint16) << 4) | np.hstack([cercanas(lados["f"][0]), cercanas(lados["e"][0])])
    imagen = np.dstack([rojo, np.round(surco * 255), np.round(fibra * 255)]).astype(np.uint8)
    escultura = np.hstack([lados["f"][4], lados["e"][4]])
    return imagen, escultura, {lado: lados[lado][3] for lado in "fe"}


def guardar_png(ruta, imagen):
    alto, ancho, _ = imagen.shape
    # Filtro Sub por fila: la distancia y la fibra son gradientes.
    diferencia = imagen.copy()
    diferencia[:, 1:] = imagen[:, 1:] - imagen[:, :-1]
    crudo = b"".join(b"\x01" + fila.tobytes() for fila in diferencia)

    def bloque(tipo, datos):
        return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", zlib.crc32(tipo + datos))

    cabecera = struct.pack(">IIBBBBB", ancho, alto, 8, 2, 0, 0, 0)
    contenido = bloque(b"IHDR", cabecera) + bloque(b"IDAT", zlib.compress(crudo, 9)) + bloque(b"IEND", b"")
    pathlib.Path(ruta).write_bytes(b"\x89PNG\r\n\x1a\n" + contenido)


def leer_escultura(escultura, x, altura, lado):
    """Distancia al borde en metros, con interpolación bilineal."""
    col = (np.clip(np.abs(x) / ANCHO_LADO, 0, 0.999) + lado) * LADO_PX - 0.5
    fila = (1 - np.clip(altura / ALTO_MAPA, 0, 0.999)) * ALTO_PX - 0.5
    c0, f0 = np.floor(col).astype(int), np.floor(fila).astype(int)
    fc, ff = col - c0, fila - f0
    c1 = np.clip(c0 + 1, 0, escultura.shape[1] - 1)
    f1 = np.clip(f0 + 1, 0, escultura.shape[0] - 1)
    c0, f0 = np.clip(c0, 0, escultura.shape[1] - 1), np.clip(f0, 0, escultura.shape[0] - 1)
    arriba = escultura[f0, c0] * (1 - fc) + escultura[f0, c1] * fc
    abajo = escultura[f1, c0] * (1 - fc) + escultura[f1, c1] * fc
    return arriba * (1 - ff) + abajo * ff


def leer_figura(nombre):
    origen = bpy.data.objects[nombre]
    for modificador in origen.modifiers:
        if modificador.type == "MULTIRES":
            modificador.levels = 2
    malla = bpy.data.meshes.new_from_object(origen.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    malla.transform(origen.matrix_world)
    return np.array([v.co[:] for v in malla.vertices]), [p.vertices[:] for p in malla.polygons]


def normalizar(vertices):
    """Pies en cero, centrado y orejas pegadas a la cabeza: sueltas quedan deshilachadas al reducir la malla."""
    vertices[:, 2] -= vertices[:, 2].min()
    vertices *= ALTURA / vertices[:, 2].max()
    vertices[:, 0] -= (vertices[:, 0].min() + vertices[:, 0].max()) / 2
    lateral = np.abs(vertices[:, 0])
    oreja = (vertices[:, 2] > 1.58) & (vertices[:, 2] < 1.7) & (lateral > 0.088)
    vertices[oreja, 0] = np.sign(vertices[oreja, 0]) * (0.088 + (lateral[oreja] - 0.088) * 0.35)
    return vertices


def crear_objeto(vertices, caras):
    malla = bpy.data.meshes.new("cuerpo")
    malla.from_pydata(vertices.tolist(), [], caras)
    objeto = bpy.data.objects.new("cuerpo", malla)
    bpy.context.scene.collection.objects.link(objeto)
    return objeto


def aplicar(objeto):
    resultado = bpy.data.meshes.new_from_object(objeto.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    objeto.modifiers.clear()
    objeto.data = resultado


def suavizar(puntos, aristas, pesos, pasadas, factor=0.5):
    grados = np.zeros(len(puntos))
    np.add.at(grados, aristas[:, 0], 1)
    np.add.at(grados, aristas[:, 1], 1)
    for _ in range(pasadas):
        suma = np.zeros_like(puntos)
        np.add.at(suma, aristas[:, 0], puntos[aristas[:, 1]])
        np.add.at(suma, aristas[:, 1], puntos[aristas[:, 0]])
        puntos = puntos + (factor * pesos)[:, None] * (suma / grados[:, None] - puntos)
    return puntos


def taubin(puntos, aristas, pesos, pasadas):
    """Quita ruido sin encoger."""
    for _ in range(pasadas):
        puntos = suavizar(puntos, aristas, pesos, 1, 0.5)
        puntos = suavizar(puntos, aristas, pesos, 1, -0.53)
    return puntos


def modelar_figura(objeto, pasadas_pecho):
    puntos = np.array([v.co[:] for v in objeto.data.vertices])
    aristas = np.array([e.vertices[:] for e in objeto.data.edges])
    x, y, z = np.abs(puntos[:, 0]), puntos[:, 1], puntos[:, 2]
    # Las figuras miran hacia -y.
    delante = 1 - rampa(y, -0.04, 0.0)
    cuello = rampa(z, 1.48, 1.53) * (1 - rampa(z, 1.52, 1.55))
    puntos = suavizar(puntos, aristas, cuello, 10)
    pelvis = (1 - rampa(x, 0.07, 0.13)) * rampa(z, 0.72, 0.8) * (1 - rampa(z, 0.9, 0.98)) * (1 - rampa(y, -0.03, 0.03))
    puntos = suavizar(puntos, aristas, pelvis, 240)
    pecho = (1 - rampa(x, 0.14, 0.19)) * rampa(z, 1.14, 1.2) * (1 - rampa(z, 1.4, 1.46)) * delante
    puntos = suavizar(puntos, aristas, pecho, pasadas_pecho)
    puntos = taubin(puntos, aristas, np.ones(len(puntos)), 3)
    # Rostro de estatua: rasgos suaves, sin ojos ni labios marcados.
    cabeza = rampa(puntos[:, 2], 1.52, 1.56)
    puntos = taubin(puntos, aristas, cabeza, 3)
    objeto.data.vertices.foreach_set("co", puntos.ravel())
    objeto.data.update()


def esculpir_relieve(objeto, escultura, relieve):
    """Infla cada músculo desde sus bordes, para que la luz y el contorno lo acusen."""
    malla = objeto.data
    malla.update()
    puntos = np.array([v.co[:] for v in malla.vertices])
    normales = np.array([v.normal[:] for v in malla.vertices])
    aristas = np.array([e.vertices[:] for e in malla.edges])
    frente = rampa(-normales[:, 1], -0.25, 0.25)
    distancia = frente * leer_escultura(escultura, puntos[:, 0], puntos[:, 2], 0) + (1 - frente) * leer_escultura(
        escultura, puntos[:, 0], puntos[:, 2], 1
    )
    domo = 1 - (1 - np.clip(distancia / RADIO_MUSCULO, 0, 1)) ** 2
    puntos += normales * (relieve * domo)[:, None]
    puntos = taubin(puntos, aristas, np.ones(len(puntos)), 1)
    malla.vertices.foreach_set("co", puntos.ravel())
    malla.update()


def alisar_tras_reducir(objeto):
    """Reducir deja facetas que la luz de la app marca, sobre todo en la cara."""
    puntos = np.array([v.co[:] for v in objeto.data.vertices])
    aristas = np.array([e.vertices[:] for e in objeto.data.edges])
    puntos = taubin(puntos, aristas, rampa(puntos[:, 2], 1.52, 1.56), 2)
    objeto.data.vertices.foreach_set("co", puntos.ravel())
    objeto.data.update()


def centros_de_rotulos(objeto, centros):
    """Dónde va el rótulo de cada zona: x, y, z del cuerpo en la app (y arriba, z hacia el frente)."""
    puntos = np.array([v.co[:] for v in objeto.data.vertices])
    salida = {}
    for lado, signo in (("f", 1), ("e", -1)):
        for zona, (_area, x, altura) in centros[lado].items():
            cercanos = (puntos[:, 0] - x) ** 2 + (puntos[:, 2] - altura) ** 2 < 0.03**2
            profundidad = (-puntos[cercanos, 1]).max() if signo > 0 else (-puntos[cercanos, 1]).min()
            salida.setdefault(zona, []).append([round(x, 3), round(altura, 3), round(float(profundidad), 3)])
    return salida


def principal():
    nombre, salida = sys.argv[sys.argv.index("--") + 1 :][:2]
    figura = FIGURAS[nombre]
    imagen, escultura, centros = hornear_mapa(deformador(PARES_FEMENINA) if figura["deformar"] else None)
    guardar_png(f"{salida}.png", imagen)
    vertices, caras = leer_figura(nombre)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    objeto = crear_objeto(normalizar(vertices), caras)
    # El vóxel deja una superficie uniforme y cierra las cuencas de los ojos.
    rehacer = objeto.modifiers.new("rehacer", "REMESH")
    rehacer.mode = "VOXEL"
    rehacer.voxel_size = 0.005
    rehacer.adaptivity = 0
    aplicar(objeto)
    modelar_figura(objeto, figura["pasadas_pecho"])
    esculpir_relieve(objeto, escultura, figura["relieve"])
    reducir_malla = objeto.modifiers.new("reducir", "DECIMATE")
    reducir_malla.ratio = TRIANGULOS / (len(objeto.data.polygons) * 2)
    aplicar(objeto)
    alisar_tras_reducir(objeto)
    print("CENTROS", json.dumps(centros_de_rotulos(objeto, centros)))
    objeto.data.polygons.foreach_set("use_smooth", [True] * len(objeto.data.polygons))
    bpy.context.view_layer.objects.active = objeto
    objeto.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=f"{salida}.glb",
        export_format="GLB",
        use_selection=True,
        export_materials="NONE",
        export_normals=False,
        export_texcoords=False,
        export_apply=True,
    )


principal()
