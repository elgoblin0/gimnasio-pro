# Librerías copiadas al repo (ADR 0007)

Cada librería vive en `vendor/<nombre>@<version>/` con su licencia. Sin CDN en tiempo de ejecución.

| Librería | Versión | Origen | SHA-256 del archivo principal | Licencia | ADR |
|---|---|---|---|---|---|
| Three.js `three.core.js` | r186 (0.186.0) | https://github.com/mrdoob/three.js/blob/r186/build/three.core.js | `9edde002b066a9a05676a6127f67735b62baf399bdea529f2f7e31657da769e6` | MIT | 0007; prototipo #81 |
| Three.js `three.module.js` | r186 (0.186.0) | https://github.com/mrdoob/three.js/blob/r186/build/three.module.js | `9052042d676cb0fdc1ddfefe193053f34b7ac0513a616fdac4535d49987812ea` | MIT | 0007; prototipo #81 |
| Three.js `loaders/GLTFLoader.js` | r186 (0.186.0) | https://github.com/mrdoob/three.js/blob/r186/examples/jsm/loaders/GLTFLoader.js | `131c0f78c01d19368ae495caa65b3adaa10487810a36a05bb5901b769a35ac16` | MIT | 0007; prototipo #81 |
| Three.js `utils/BufferGeometryUtils.js` | r186 (0.186.0) | https://github.com/mrdoob/three.js/blob/r186/examples/jsm/utils/BufferGeometryUtils.js | `9fb63427ce6641fa14fd0baff9cc4d1b5f9c3d85fd084bf2e90e803c44ec1797` | MIT | 0007; prototipo #81 |
| Three.js `utils/SkeletonUtils.js` | r186 (0.186.0) | https://github.com/mrdoob/three.js/blob/r186/examples/jsm/utils/SkeletonUtils.js | `b1632a703206c3d830de9fcbe515696770d04b71a15ee6b50afa6d2c3298c86f` | MIT | 0007; prototipo #81 |

| Superhero Male `cuerpo.glb` | copia 28/10/2026 | https://quaternius.com/packs/universalbasecharacters.html (conversi?n y procedencia en `cuerpo@1/FUENTE.md`) | `d6f3b64cab629f6ddca9ba063811aeffd3663a8a4e49ade47cd9505dc2bbd70f` | CC0 1.0 (`cuerpo@1/LICENCIA.txt`) | 0014; #92 |
