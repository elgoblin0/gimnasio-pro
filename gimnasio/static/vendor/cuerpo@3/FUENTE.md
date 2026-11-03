# Modelos y mapas del cuerpo 3D muscular

- Autor: **Blender Studio** y colaboradores de la comunidad de Blender.
- Obra: **Human Base Meshes** v1.4.1, figuras `GEO-body_male_realistic` y `GEO-body_female_realistic`.
- Fuente oficial: https://www.blender.org/download/demo-files/
- Licencia: **CC0 1.0 Universal**, https://creativecommons.org/publicdomain/zero/1.0/
- Obtenida el 30/10/2026.

`masculina.glb`, `femenina.glb` y sus mapas `.png` son obras derivadas, generadas con `scripts/exportar_cuerpo.py`
en Blender 4.2 LTS (el docstring del script tiene los comandos). El relieve muscular se esculpe en la malla a partir
de las formas de `scripts/musculos_cuerpo.py`; rostro y pelvis quedan suavizados: no es una referencia anatómica.
Cada modelo tiene unos 26.000 triángulos, sin materiales, texturas, normales ni esqueleto.

Cada `.png` es un mapa de datos, no una imagen: frente y espalda lado a lado, con la zona por texel en R, la
distancia al borde del músculo en G y la coordenada de fibra en B (ADR 0034). Si se regenera un modelo, hay que
regenerar su mapa, copiar los `CENTROS` que imprime el script a `FIGURAS` en `cuerpo-3d.js` y actualizar los
SHA-256 en `VERSIONES.md`.
