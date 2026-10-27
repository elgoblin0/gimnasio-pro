# Prototipos de dirección visual (descartables)

Dos direcciones para el inicio del socio en el celular, con el mismo contenido para poder compararlas: saludo, chequeo del día, sesión propuesta con explicaciones, un freno de seguridad y el aforo en vivo. Abrí cada `index.html` con doble clic; se ven mejor con el navegador en vista de celular (375 px). Probá el chequeo del día: con dolor de rodilla la sesión baja o sustituye lo que carga la rodilla (y avisa al entrenador); con mal sueño o poca energía no sube nada. Las dos direcciones comparten el mismo motor mínimo (`<script id="motor">`), y `pruebas/test_prototipos.py` lo verifica con Node.

## A · Pulso nocturno (`direccion-a/`)
Fondo casi negro con un halo de luz lima y cian que respira detrás del contenido, y tarjetas de vidrio esmerilado. Tipografía condensada en mayúsculas, con números grandes y técnicos. El movimiento es enérgico: las entradas se desenfocan al aparecer y los botones responden con resorte. Transmite rendimiento, noche y concentración, como un tablero deportivo. El aforo se muestra con un anillo luminoso.

## B · Cuaderno de entrenamiento (`direccion-b/`)
Papel cálido con grano, serif editorial y cursivas en terracota, con acentos verde bosque. El chequeo del día es una frase con palabras subrayadas que se tocan para cambiarlas. La sesión parece una página numerada de cuaderno y el freno es un sello. El movimiento es sereno: trazos que se dibujan y barras que crecen. Transmite cercanía, cuidado y criterio de entrenador. El aforo se muestra como barras por hora, con el mejor horario destacado.

Al cerrar la etapa 0, el usuario elige una dirección y `gimnasio/static/estilos/tokens.css` la adopta como predeterminada. Ninguna de las dos usa librerías: el 3D llega en la etapa 2.
