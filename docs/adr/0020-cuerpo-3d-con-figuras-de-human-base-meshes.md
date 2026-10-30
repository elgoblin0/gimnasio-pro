# 0020. Mostrar el cuerpo 3D con figuras masculina y femenina de Human Base Meshes

- Estado: aceptado
- Fecha: 2026-10-30
- Decide: usuario
- Etiquetas: modulo:frontend, modulo:diseno, modulo:permisos

## Contexto
El modelo del ADR 0014, *Superhero Male*, tiene proporciones de superhéroe, y al quitarle la cara en el navegador quedaba un borde irregular entre cuello y cabeza. El 30/10/2026 el dueño comparó capturas en la app con *Human Base Meshes* de Blender Studio (CC0) y eligió este modelo, con rostro suavizado y una figura femenina para las socias. Hasta ahora la app no guardaba ningún dato sobre el sexo o el género de las personas.

## Decisión
- Reemplaza al modelo del ADR 0014; sigue vigente el resto de esa decisión: Three.js en `vendor/` y zonas por posición, sin modificar el glTF en el navegador.
- `vendor/cuerpo@2/` guarda `masculina.glb` y `femenina.glb`, generadas con `scripts/exportar_maniqui.py`: una superficie cerrada de 20.000 triángulos y unos 241 kB cada una, con rostro suave.
- Cada figura define en `cuerpo-3d.js` sus propias elipses de zona y su giro de brazos.
- La **figura del cuerpo** se guarda en `personas.figura_cuerpo` y la elige cada persona en la pantalla del cuerpo 3D. No se pide ni se guarda el sexo o el género: es una preferencia de imagen, y el formulario declara esa finalidad (ADR 0010).
- Sin elección (`NULL`) se muestra la figura masculina, sin marcarla como elegida.
- El cuerpo muestra la figura de quien tiene la sesión. La figura no entra en reglas, zonas del cuerpo ni historial.
- En la demo, Lucía tiene la figura femenina.

## Consecuencias
- Se gana una figura creíble y más liviana: de 741 kB a 241 kB por modelo descargado.
- El modelo ya no se limpia al cargar: cambiarlo exige Blender y volver a revisar las elipses.
- Quedan dos juegos de elipses por mantener.
- La exportación de datos del socio (ADR 0010) tendrá que incluir este campo cuando exista.

## Alternativas descartadas
- Universal Base Characters «Regular»: mismo estilo caricaturesco, posible costo y sin ganancia clara.
- MakeHuman: exige instalar el programa, y no se confirmó su exportación a glTF.
- Prototyping Mannequin: los cortes visibles en las uniones molestan para marcar zonas.
- Guardar la figura solo en el dispositivo: no pide datos personales, pero hay que elegirla en cada celular.
- Guardar el sexo y deducir la figura: pide un dato más sensible del que la imagen necesita.
- Nariz añadida a una cabeza lisa: se ve artificial.
