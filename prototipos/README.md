# Prototipo de dirección visual (descartable)

Se conserva la dirección B, elegida en #33, para el inicio del socio en el celular: saludo, chequeo del día, sesión propuesta con explicaciones, un freno de seguridad y el aforo en vivo. Abrí `direccion-b/index.html` con doble clic; se ve mejor con el navegador en vista de celular (375 px). Probá el chequeo del día: con dolor de rodilla la sesión baja o sustituye lo que carga la rodilla (y avisa al entrenador); con mal sueño o poca energía no sube nada. `pruebas/test_prototipos.py` verifica el motor mínimo (`<script id="motor">`) con Node y que solo permanezca B.

## B · Cuaderno de entrenamiento (`direccion-b/`)
Papel cálido con grano, serif editorial y cursivas en terracota, con acentos verde bosque. El chequeo del día es una frase con palabras subrayadas que se tocan para cambiarlas. La sesión parece una página numerada de cuaderno y el freno es un sello. El movimiento es sereno: trazos que se dibujan y barras que crecen. Transmite cercanía, cuidado y criterio de entrenador. El aforo se muestra como barras por hora, con el mejor horario destacado.

La aplicación fija `data-direccion="b"` en su HTML estático y adopta sus tokens en `gimnasio/static/estilos/tokens.css`, con variante oscura según la preferencia del sistema. La dirección A fue retirada. El prototipo no usa librerías: el 3D llega en la etapa 2.

## Cuerpo 3D muscular (#81)

Dos prototipos descartables, sin integración en la app. Desde la raíz:
`python -m http.server 8081 --bind 127.0.0.1`. Abrí
http://127.0.0.1:8081/prototipos/cuerpo-3d/modelo/ (A, glTF CC0) o
http://127.0.0.1:8081/prototipos/cuerpo-3d/estilizado/ (B, primitivas).
Requieren HTTP por los módulos ES; no se abren con doble clic.

Ambos permiten rotar con arrastre, o con el control de rotación accesible,
seleccionar zonas con ratón/toque o botones y cambiar sus estados. Los ids
coinciden con `ZONAS_CUERPO`; se emite `zona-seleccionada` en `window` con
`detail.zona`. El estado está solo en memoria. La selección del diseño sigue
pendiente del dueño y el ADR corresponde a Opus. La capacidad de la app sigue
pendiente porque este issue solo compara prototipos.

`python prototipos/cuerpo-3d/verificar.py` levanta un servidor efímero, comprueba
las 14 zonas, los dos estados, selección sobre el cuerpo y ausencia de errores
en Chromium; guarda cuatro capturas y `mediciones.json`. Usa Playwright de
`requirements-dev.txt` y Chromium local. También lo ejecuta
`pruebas/test_prototipos.py` con salida temporal.

Medición: contexto nuevo por página, caché de navegador vacía, servidor HTTP
local sin compresión ni limitación de red/CPU. Peso = suma de cuerpos de
recursos y HTML (`encodedBodySize`, sin cabeceras HTTP); primer cuadro =
`performance.now()` después del primer `render`, desde inicio de navegación,
sin prometer el instante de presentación física en pantalla. FPS = intervalos
de `requestAnimationFrame` durante 3 segundos de rotación continua, con render
en cada cuadro. Celular emulado 390×844, táctil, DPR 1, mismo hardware de
escritorio; no representa rendimiento de un teléfono físico. Escritorio
1280×1000, DPR 1. Preferencia de movimiento reducido: sin giro automático en
la página; el giro de medición se solicita expresamente por el script.

Fuente, autor, licencia y búsqueda de modelos en
[cuerpo-3d/recursos/FUENTE.md](cuerpo-3d/recursos/FUENTE.md). Three.js r186 se
verificó el 28/10/2026 contra la última publicación oficial:
https://github.com/mrdoob/three.js/releases/tag/r186.
