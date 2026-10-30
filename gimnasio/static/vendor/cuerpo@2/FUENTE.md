# Modelos del cuerpo 3D

- Autor: **Blender Studio** y colaboradores de la comunidad de Blender.
- Obra: **Human Base Meshes** v1.4.1, figuras `GEO-body_male_realistic` y `GEO-body_female_realistic`.
- Fuente oficial: https://www.blender.org/download/demo-files/
- Licencia: **CC0 1.0 Universal**, https://creativecommons.org/publicdomain/zero/1.0/
- Obtenida el 30/10/2026.

`masculina.glb` y `femenina.glb` son obras derivadas, generadas con `scripts/exportar_maniqui.py` en
Blender 4.2 LTS (el docstring del script tiene los comandos). Rostro, pecho y pelvis quedan suavizados:
es un maniquí, no una referencia anatómica. Cada una tiene 20.000 triángulos, sin materiales, texturas,
normales ni esqueleto; las normales se calculan al cargar.

`cuerpo-3d.js` asigna las zonas del cuerpo por posición, con elipses propias de cada figura (ADR 0014,
ADR 0020). Si se regenera un modelo, hay que revisar esas elipses y actualizar el SHA-256 en `VERSIONES.md`.
