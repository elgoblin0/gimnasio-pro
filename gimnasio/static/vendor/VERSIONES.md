# Librerías copiadas al repo (ADR 0007)

Cada librería vive en `vendor/<nombre>@<version>/` con su licencia. Sin CDN en tiempo de ejecución.

| Librería | Versión | Origen | SHA-256 del archivo principal | Licencia | ADR |
|---|---|---|---|---|---|
| Three.js `three.core.js` | r186 (0.186.0) | https://github.com/mrdoob/three.js/blob/r186/build/three.core.js | `9edde002b066a9a05676a6127f67735b62baf399bdea529f2f7e31657da769e6` | MIT | 0007; prototipo #81 |
| Three.js `three.module.js` | r186 (0.186.0) | https://github.com/mrdoob/three.js/blob/r186/build/three.module.js | `9052042d676cb0fdc1ddfefe193053f34b7ac0513a616fdac4535d49987812ea` | MIT | 0007; prototipo #81 |
| Three.js `loaders/GLTFLoader.js` | r186 (0.186.0) | https://github.com/mrdoob/three.js/blob/r186/examples/jsm/loaders/GLTFLoader.js | `131c0f78c01d19368ae495caa65b3adaa10487810a36a05bb5901b769a35ac16` | MIT | 0007; prototipo #81 |
| Three.js `utils/BufferGeometryUtils.js` | r186 (0.186.0) | https://github.com/mrdoob/three.js/blob/r186/examples/jsm/utils/BufferGeometryUtils.js | `9fb63427ce6641fa14fd0baff9cc4d1b5f9c3d85fd084bf2e90e803c44ec1797` | MIT | 0007; prototipo #81 |
| Three.js `utils/SkeletonUtils.js` | r186 (0.186.0) | https://github.com/mrdoob/three.js/blob/r186/examples/jsm/utils/SkeletonUtils.js | `b1632a703206c3d830de9fcbe515696770d04b71a15ee6b50afa6d2c3298c86f` | MIT | 0007; prototipo #81 |

| Human Base Meshes `masculina.glb` | v1.4.1, derivado 02/11/2026 | https://www.blender.org/download/demo-files/ (conversión y procedencia en `cuerpo@3/FUENTE.md`) | `d8358debbbdf6626f564a8b7890d09eacff2d15d651a9db8ae549ae2454358c0` | CC0 1.0 (`cuerpo@3/LICENCIA.txt`) | 0020; 0034 |
| Human Base Meshes `masculina.png` | v1.4.1, derivado 02/11/2026 | https://www.blender.org/download/demo-files/ (conversión y procedencia en `cuerpo@3/FUENTE.md`) | `049776592f1f662c4e5339cb10c49076f7234f84acbc88904bb1c45aa301b3d7` | CC0 1.0 (`cuerpo@3/LICENCIA.txt`) | 0020; 0034 |
| Human Base Meshes `femenina.glb` | v1.4.1, derivado 02/11/2026 | https://www.blender.org/download/demo-files/ (conversión y procedencia en `cuerpo@3/FUENTE.md`) | `31904705b571775149e4a89c091651fc519d1795b1d9dc64dfdde7e171a6bbb7` | CC0 1.0 (`cuerpo@3/LICENCIA.txt`) | 0020; 0034 |
| Human Base Meshes `femenina.png` | v1.4.1, derivado 02/11/2026 | https://www.blender.org/download/demo-files/ (conversión y procedencia en `cuerpo@3/FUENTE.md`) | `e7e6917c3a4fbfc006c80f6f597b50f8471b447b1c0b57b647823e3cdbe4bedd` | CC0 1.0 (`cuerpo@3/LICENCIA.txt`) | 0020; 0034 |

| Newsreader `newsreader.woff2` | v26 (Google Fonts), recortada 02/11/2026 | https://github.com/productiontype/Newsreader (instancia wght 300–600 y opsz 16–72, subconjunto latín + ₲) | `ca011e085dff77eb22082578a0b6acdd536339ff960791288d0e0b3e6163941a` | OFL 1.1 (`newsreader@v26/OFL.txt`) | 0007; #292 |
| Newsreader `newsreader-italica.woff2` | v26 (Google Fonts), recortada 02/11/2026 | https://github.com/productiontype/Newsreader (mismo recorte, cursiva) | `5576d5a2d5c802e9f019c2856d6fc0292dbb165182f30b338cf637d039d1e051` | OFL 1.1 (`newsreader@v26/OFL.txt`) | 0007; #292 |
