# Prototipo de dirección visual (descartable)

Se conserva la dirección B, elegida en #33, para el inicio del socio en el celular: saludo, chequeo del día, sesión propuesta con explicaciones, un freno de seguridad y el aforo en vivo. Abrí `direccion-b/index.html` con doble clic; se ve mejor con el navegador en vista de celular (375 px). Probá el chequeo del día: con dolor de rodilla la sesión baja o sustituye lo que carga la rodilla (y avisa al entrenador); con mal sueño o poca energía no sube nada. `pruebas/test_prototipos.py` verifica el motor mínimo (`<script id="motor">`) con Node y que solo permanezca B.

## B · Cuaderno de entrenamiento (`direccion-b/`)
Papel cálido con grano, serif editorial y cursivas en terracota, con acentos verde bosque. El chequeo del día es una frase con palabras subrayadas que se tocan para cambiarlas. La sesión parece una página numerada de cuaderno y el freno es un sello. El movimiento es sereno: trazos que se dibujan y barras que crecen. Transmite cercanía, cuidado y criterio de entrenador. El aforo se muestra como barras por hora, con el mejor horario destacado.

La aplicación fija `data-direccion="b"` en su HTML estático y adopta sus tokens en `gimnasio/static/estilos/tokens.css`, con variante oscura según la preferencia del sistema. La dirección A fue retirada. El prototipo no usa librerías: el 3D llega en la etapa 2.
