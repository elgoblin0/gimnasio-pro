# 0014. Construir el cuerpo 3D muscular con un modelo glTF segmentado en el navegador

- Estado: aceptado
- Fecha: 2026-10-28
- Decide: usuario
- Etiquetas: modulo:frontend, modulo:diseno

## Contexto
El **cuerpo 3D muscular** resalta las **zonas del cuerpo** trabajadas o con dolor (ADR 0013). El issue #81 pidió dos prototipos para que el dueño eligiera, y el PR #99 los compara:

| Prototipo | Peso descargado | Primer cuadro (escritorio / celular emulado) | FPS al rotar |
|---|---:|---:|---:|
| A · modelo glTF | 3.043.618 bytes | 177 ms / 155 ms | 60 |
| B · cuerpo estilizado de primitivas | 2.135.493 bytes | 84 ms / 83 ms | 60 |

Mediciones de Chromium sin limitación de CPU ni de red, con el celular emulado en una PC: no miden hardware de teléfono.

El modelo de A es *Superhero Male* de Quaternius (Universal Base Characters), licencia CC0 1.0; la fuente y el aviso quedan en `prototipos/cuerpo-3d/recursos/`. No se encontró un modelo libre ya dividido en las 14 zonas, así que A asigna cada triángulo a una zona por la posición de su centro. El corte es aproximado: cabeza, antebrazos y manos quedan neutros.

El 28/10/2026 el dueño eligió A («Elijo el A»).

## Decisión
- El cuerpo 3D muscular de la app se construye con el modelo glTF CC0 y Three.js r186 copiado en `gimnasio/static/vendor/` (ADR 0007), sin CDN ni build.
- La segmentación en las 14 zonas del cuerpo se hace en el navegador, sin modificar el archivo glTF. Los identificadores de zona son los de `ZONAS_CUERPO`.
- La integración en el chequeo del día y en el resumen no forma parte de esta decisión: se especifica en sus propios issues.
- Los prototipos quedan en `prototipos/cuerpo-3d/` como evidencia de la comparación y no se integran en la app.

## Consecuencias
- Se gana un cuerpo más reconocible, con licencia libre compatible con un repo público.
- Se pierde peso y tiempo de carga frente a B: unos 0,9 MB más y el doble de tiempo hasta el primer cuadro en la medición local.
- La segmentación por posición no es anatómica. Sirve para resaltar y seleccionar zonas; no debe presentarse como referencia clínica.
- La integración debe cuidar el peso en celular real y ofrecer la alternativa sin efectos que pide VISION. Esto se verifica en el issue de integración.
- El modelo y Three.js se actualizan a mano; `VERSIONES.md` y los avisos de licencia deben mantenerse junto a los archivos.

## Alternativas descartadas
- B, cuerpo estilizado de primitivas: más liviano y acorde a la dirección visual B, pero el dueño prefirió el modelo glTF.
- Silueta SVG: fuera del alcance de #81.
