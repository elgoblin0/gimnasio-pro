# 0018. Actualizar el aforo en vivo por sondeo, sin conexiones abiertas

- Estado: aceptado
- Fecha: 2026-10-29
- Decide: usuario
- Etiquetas: modulo:visitas

## Contexto
La etapa 3 pide que recepción vea la ocupación registrada y la escena de ocupación sin recargar la pantalla. La demo corre en el servicio gratuito de Render con `gunicorn --workers 1 --threads 4` (`render.yaml`, ADR 0009). Una conexión abierta por pantalla (SSE o WebSocket) ocupa un hilo mientras dure, así que cuatro pestañas abiertas bloquearían la app.

## Decisión
- Las pantallas consultan la ocupación registrada cada ~5 s con una petición corta.
- El servidor responde «sin cambios» (304 con `ETag` u otra marca de versión) cuando la ocupación no varió desde la última consulta del cliente.
- No se usan SSE ni WebSocket.

## Consecuencias
- Cada consulta libera su hilo enseguida; la cantidad de pantallas no bloquea la app.
- La pantalla puede mostrar un cambio hasta ~5 s tarde. Quien registra la entrada o salida ve el cambio al instante, porque su propia respuesta lo trae.
- La simulación de ocupación en modo demo se calcula al llegar una consulta, no con un temporizador.
- Se verifica con una prueba de la ruta que devuelve 304 sin cambios y 200 tras una entrada.

## Alternativas descartadas
- SSE: inmediato, pero ocupa un hilo por pantalla con un solo worker.
- WebSocket: igual costo de hilos y exige un servidor asíncrono que la demo no tiene.

<!-- Un ADR "provisional" lo tomó un agente sin el usuario; se revisa en el cierre de la etapa. -->
