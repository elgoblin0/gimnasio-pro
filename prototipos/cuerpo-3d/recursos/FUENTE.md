# Modelo del prototipo A

- Autor: **Quaternius**.
- Obra: **Superhero Male**, Universal Base Characters (Standard).
- Fuente oficial: https://quaternius.com/packs/universalbasecharacters.html
- Descarga oficial: https://quaternius.itch.io/universal-base-characters
- Licencia: **CC0 1.0 Universal**, https://creativecommons.org/publicdomain/zero/1.0/
- Copia glTF binaria obtenida el 28/10/2026 de https://github.com/programasweights/avatar/blob/main/public/assets/character.glb
- Procedencia de esa conversión: https://github.com/programasweights/avatar/blob/main/ASSETS.md
- `LICENCIA.txt` conserva el aviso distribuido con el modelo.

La copia conserva geometría y esqueleto, omite texturas y usa material mate.
El prototipo muestra la geometría en pose de referencia, sin animaciones.
`cuerpo.js` asigna cada triángulo a una zona por el centro de sus vértices,
en coordenadas del modelo (metros, frente +Z). No modifica el archivo glTF.
Cabeza, antebrazos y manos quedan neutros. La segmentación es aproximada:
sirve para comparar resaltado y selección, no como referencia anatómica.

## Búsqueda del 28/10/2026

Se revisaron Universal Base Characters de Quaternius y la licencia de los
modelos exportados de MakeHuman:
https://www.makehumancommunity.org/about/license.html
Ambos permiten modelos CC0; se eligió Quaternius porque hay un glTF accesible
con procedencia y licencia documentadas. No se encontró en esas fuentes un
modelo ya segmentado en las 14 zonas exactas del ADR 0013. Eso no impide A:
se segmenta la geometría disponible en el navegador.
