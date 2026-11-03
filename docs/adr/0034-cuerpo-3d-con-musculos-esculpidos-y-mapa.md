# 0034. Esculpir los músculos sobre Human Base Meshes y marcar las zonas con un mapa por figura

- Estado: aceptado
- Fecha: 2026-11-02
- Decide: usuario
- Etiquetas: modulo:frontend, modulo:diseno

## Contexto
El ADR 0020 dejó dos maniquíes lisos de Human Base Meshes (CC0), con las zonas del cuerpo como elipses por figura. El pedido de #310 fue que el cuerpo 3D se lea como músculo: grupos reconocibles, zonas que se encienden con la forma del músculo y una silueta de carga que no sea de rectángulos. Ningún modelo con licencia redistribuible servía tal cual para las dos figuras con la misma calidad. El 02/11/2026 el dueño vio capturas de frente y espalda de ambas figuras, con y sin zonas marcadas, y aprobó integrarlas sin volver a esculpir.

## Decisión
- Amplía el ADR 0020: siguen la base Human Base Meshes v1.4.1, las dos figuras, la figura elegida por cada persona y Three.js en `vendor/`.
- `scripts/musculos_cuerpo.py` dibuja los músculos en metros sobre la figura masculina, cada uno con su zona del cuerpo, lado y fibra. La femenina los recibe deformados.
- `scripts/exportar_cuerpo.py` (Blender 4.2) esculpe ese relieve en la malla y hornea un mapa por figura. Ambos van en `vendor/cuerpo@3/`.
- El mapa es un PNG de datos, con frente y espalda lado a lado: R guarda la zona y la más cercana para el toque, G la distancia al borde y B la fibra. El sombreador de `cuerpo-3d.js` lo lee con `texelFetch` para dibujar surcos, relieve y el encendido de cada zona. La selección por toque lee el mismo mapa en la CPU.
- Las elipses por figura desaparecen. `FIGURAS` en `cuerpo-3d.js` solo guarda dónde va el rótulo de cada zona.
- La silueta SVG, que es la carga y la alternativa sin efectos, se genera desde los mismos músculos con `scripts/silueta_cuerpo.py`.
- El 3D se importa después del primer pintado.

## Consecuencias
- El cuerpo se lee como músculo y cada zona se enciende con su forma, de frente y de espalda.
- La silueta y el 3D comparten zonas. Si cambia un músculo, se regeneran los modelos, los mapas y la silueta; `python scripts/silueta_cuerpo.py --verificar` lo comprueba en las pruebas.
- Cada figura pesa unos 430 kB entre modelo y mapa, contra los 241 kB del ADR 0020. Entra en el presupuesto `otros` de `test_accesibilidad_y_carga.py`.
- Cambiar un modelo sigue exigiendo Blender.
- Calidad pendiente, aceptada por el dueño: la espalda masculina se ve como placas separadas, sin relieve en trapecios ni dorsales. La figura femenina tiene el pecho plano y surcos poco marcados.

## Alternativas descartadas
- Écorchés CC BY 4.0 de Sketchfab: tienen caras desolladas, calidad despareja y autoría sin confirmar en el femenino, y bajarlos exige una cuenta del dueño.
- Seguir con elipses sobre el maniquí liso: las zonas no siguen la forma del músculo.
- Enderezar los brazos para hornear el mapa: deforma las axilas y en la figura femenina aparecen «alas».
- Volver a esculpir la espalda y la figura femenina antes de integrar: el dueño prefirió integrar ya.
