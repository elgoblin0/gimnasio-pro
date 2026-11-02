# Ideas no hechas

Pro terminó en la etapa 7 y no tiene etapa 8. Esta lista reúne lo que las especificaciones de cada etapa y los ADR dejaron fuera, para que quien retome el proyecto sepa qué se pensó y por qué no entró. Ninguna es un compromiso.

## Fuera de Pro por la VISION

- IA o modelos de lenguaje dentro del producto: las propuestas salen del motor de reglas.
- QR rotativo para la entrada.
- Múltiples sedes: el modelo guarda la sede y su zona horaria, pero hay una sola.
- App nativa: en celular se usa la misma web.
- Funcionamiento sin conexión con sincronización posterior.
- Cobros en línea: los pagos se registran, no se procesan.

## Entrenamiento y programas

- Alta y edición de ejercicios desde la app; el catálogo viene de la semilla (ADR 0021).
- Que el motor recicle la semana tipo en lugar de generar el programa desde ella (ADR 0022).
- Subir una carga por encima de lo que propone el motor cuando ya hay historial (ADR 0023).
- Corregir series realizadas de un socio desde la pantalla del entrenador.
- Reprogramar ausencias y rehacer el balance semanal.
- Récords de distancia y tiempo, y cardio en la semilla.
- Cuerpo 3D en la pantalla de progreso semanal.
- Equipos por unidad física, en lugar de por tipo.
- Asignar socios a entrenadores desde una pantalla; la asignación viene de la semilla.

## Recepción, aforo y clases

- Espera para entrar cuando se alcanza el aforo.
- Personal e invitados en el aforo, y aforo por zona de la sede.
- Cierre estimado automático de visitas abiertas.
- Escena de ocupación para el socio.
- Asistencia a clases y penalidad por faltar.
- Aforo en vivo por SSE o WebSocket en lugar de sondeo (ADR 0018).

## Pagos y membresía

- Días de gracia y pagos parciales.
- Factura legal y recibo imprimible.
- Avisos de vencimiento de la membresía.

## Socio, salud y datos personales

- Anonimizar datos personales al pedir la baja; hoy se desactiva al usuario y se conserva su historial (ADR 0025).
- Volver a pedir la aceptación cuando cambia el texto de un consentimiento (ADR 0025).
- Consentimiento de imagen.
- Contacto de emergencia.
- Generar una clave provisional nueva si la primera respuesta del alta se pierde (ADR 0031).
- Ajustes de detalle cuando salga la reglamentación de la Ley 7593/2025 (ADR 0010).

## Acompañamiento y avisos

- Correo, notificaciones push y tareas programadas.
- Avisos configurables por el gimnasio.
- Riesgo de abandono con niveles o predicción estadística; hoy son motivos con reglas fijas.
- Hitos de incorporación marcados a mano.

## Experiencia y demo

- Medir los 60 fps en el CI: corre sin GPU, así que la medición queda en los dispositivos del dueño.
- Un socio propio por cada recorrido guiado, para que dos visitantes no compartan los mismos datos (ADR 0032).
- Video o pantallas grabadas en el recorrido: se descartaron a favor de la app real.
