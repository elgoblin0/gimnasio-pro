"""Convierte una figura de Human Base Meshes (Blender Studio, CC0) en el GLB del cuerpo 3D.

Se ejecuta dentro de Blender 4.2 LTS, con el paquete abierto:

    blender --background human_base_meshes_bundle.blend --python scripts/exportar_maniqui.py -- \
        GEO-body_male_realistic gimnasio/static/vendor/cuerpo@2/masculina.glb
    blender --background human_base_meshes_bundle.blend --python scripts/exportar_maniqui.py -- \
        GEO-body_female_realistic gimnasio/static/vendor/cuerpo@2/femenina.glb

Rostro, pecho y pelvis quedan suavizados: es un maniquí, no una referencia anatómica. El resultado es
una sola superficie cerrada, a la altura que esperan la cámara y las zonas de `cuerpo-3d.js`.
"""

import sys

import bpy
import numpy as np

ALTURA = 1.79
TRIANGULOS = 20000
PASADAS_PECHO = {"GEO-body_male_realistic": 80, "GEO-body_female_realistic": 260}


def rampa(valor, desde, hasta):
    t = np.clip((valor - desde) / (hasta - desde), 0, 1)
    return t * t * (3 - 2 * t)


def leer_figura(nombre):
    origen = bpy.data.objects[nombre]
    for modificador in origen.modifiers:
        if modificador.type == "MULTIRES":
            modificador.levels = 1
    malla = bpy.data.meshes.new_from_object(origen.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    malla.transform(origen.matrix_world)
    return np.array([v.co[:] for v in malla.vertices]), [p.vertices[:] for p in malla.polygons]


def normalizar(vertices):
    """Pies en cero, centrado y orejas pegadas a la cabeza: sueltas quedan deshilachadas al reducir la malla."""
    vertices[:, 2] -= vertices[:, 2].min()
    vertices *= ALTURA / vertices[:, 2].max()
    vertices[:, 0] -= (vertices[:, 0].min() + vertices[:, 0].max()) / 2
    lateral = np.abs(vertices[:, 0])
    oreja = (vertices[:, 2] > 1.6) & (lateral > 0.075)
    vertices[oreja, 0] = np.sign(vertices[oreja, 0]) * (0.075 + (lateral[oreja] - 0.075) * 0.15)
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


def modelar_maniqui(objeto, pasadas_pecho):
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
    # Músculo menos marcado, sin encoger la figura (Taubin).
    todo = np.ones(len(puntos))
    for _ in range(12):
        puntos = suavizar(puntos, aristas, todo, 1, 0.5)
        puntos = suavizar(puntos, aristas, todo, 1, -0.53)
    # Rostro suave, sin ojos ni boca definidos: maniquí de tienda.
    cabeza = rampa(puntos[:, 2], 1.52, 1.56)
    for _ in range(14):
        puntos = suavizar(puntos, aristas, cabeza, 1, 0.5)
        puntos = suavizar(puntos, aristas, cabeza, 1, -0.53)
    # Los costados de la cabeza, donde estaban las orejas, quedan redondos.
    costados = cabeza * rampa(np.abs(puntos[:, 0]), 0.055, 0.07)
    puntos = suavizar(puntos, aristas, costados, 60)
    objeto.data.vertices.foreach_set("co", puntos.ravel())
    objeto.data.update()


def alisar_tras_reducir(objeto):
    """Reducir deja facetas que la luz de la app marca, sobre todo en la cara."""
    puntos = np.array([v.co[:] for v in objeto.data.vertices])
    aristas = np.array([e.vertices[:] for e in objeto.data.edges])
    cabeza = rampa(puntos[:, 2], 1.52, 1.56)
    for _ in range(6):
        puntos = suavizar(puntos, aristas, cabeza, 1, 0.5)
        puntos = suavizar(puntos, aristas, cabeza, 1, -0.53)
    objeto.data.vertices.foreach_set("co", puntos.ravel())
    objeto.data.update()


def principal():
    nombre, salida = sys.argv[sys.argv.index("--") + 1 :][:2]
    vertices, caras = leer_figura(nombre)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    objeto = crear_objeto(normalizar(vertices), caras)
    # El vóxel deja una superficie uniforme y cierra las cuencas de los ojos.
    rehacer = objeto.modifiers.new("rehacer", "REMESH")
    rehacer.mode = "VOXEL"
    rehacer.voxel_size = 0.005
    rehacer.adaptivity = 0
    aplicar(objeto)
    modelar_maniqui(objeto, PASADAS_PECHO[nombre])
    reducir = objeto.modifiers.new("reducir", "DECIMATE")
    reducir.ratio = TRIANGULOS / (len(objeto.data.polygons) * 2)
    aplicar(objeto)
    alisar_tras_reducir(objeto)
    objeto.data.polygons.foreach_set("use_smooth", [True] * len(objeto.data.polygons))
    bpy.context.view_layer.objects.active = objeto
    objeto.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=salida,
        export_format="GLB",
        use_selection=True,
        export_materials="NONE",
        export_normals=False,
        export_texcoords=False,
        export_apply=True,
    )


principal()
