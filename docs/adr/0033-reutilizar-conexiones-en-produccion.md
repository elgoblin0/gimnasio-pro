# 0033. Reutilizar las conexiones a la base en producción con el pool del conector

- Estado: provisional
- Fecha: 2026-11-02
- Decide: Opus
- Etiquetas: modulo:comun, modulo:demo

## Contexto
Un recorrido crítico de la demo pública encontró pantallas de hasta 10 s y un recorrido guiado de 2:35 a 2:46. Medido en la demo el 02/11/2026, desde Asunción, con solicitudes simultáneas:

| Ruta | Qué hace | Una a la vez | Ocho a la vez | Rendimiento |
|---|---|---|---|---|
| `/api/estado` sin cookie | sin base | 180 ms | 180 ms | 28 por segundo |
| `/api/estado` con cookie | una conexión y una consulta | 713 ms | 5,3 s | 1,4 por segundo |
| `/api/visitas/socios` | una conexión y tres consultas | 705 ms | 5,3 s | 1,4 por segundo |
| `/api/ocupacion` | una conexión y trece consultas, con `FOR UPDATE` | 1132 ms | 5,7 s | 1,3 por segundo |

Sin base la instancia escala: no faltan hilos. Con una sola consulta ya aparece el mismo tope que con trece y con bloqueo de fila: el límite es abrir la conexión, no las consultas ni el bloqueo. En local, abrir una conexión con TLS gasta 25 ms de CPU y reutilizarla menos de 0,3 ms; el plan gratuito de Render reparte una fracción de CPU, así que ese costo se multiplica.

## Decisión
- En producción las conexiones pasan de una solicitud a otra, con el pool de `mysql.connector` (`parametros_reutilizables` en `comun/bd.py`). No se agrega ninguna dependencia ni una clase propia: es el mismo pool que ya usa toda la suite de pruebas.
- El pool tiene una conexión por hilo de gunicorn (`HILOS_EN_PRODUCCION`, igual a `--threads` en `render.yaml`; una prueba exige que coincidan), porque no espera: si se agota, falla.
- El pool reinicia la sesión al devolver cada conexión: sin transacción abierta ni lecturas consistentes viejas, sin candados con nombre y de nuevo en UTC (ADR 0005). Comprueba la conexión al entregarla y la reabre si la base la cortó.
- Fuera de producción sigue una conexión por solicitud, salvo que `app.config["BD"]` pida otra cosa.

## Consecuencias
- Cada solicitud agrega unos pocos comandos para reiniciar la sesión y comprobar la conexión. Es mucho menos que abrirla.
- La primera solicitud que toca la base tras arrancar abre las cuatro conexiones de una vez: tarda unos segundos más, sobre el arranque en frío que ya tarda cerca de un minuto (ADR 0009).
- Hay un máximo de cuatro conexiones por instancia con la base.
- Sube a `aceptado` cuando se mida el resultado en la demo, después de fusionar: desde este entorno no se puede desplegar antes.

## Alternativas descartadas
- Más hilos o procesos en gunicorn: no ayuda, el tope no son los hilos, y varios procesos gastarían más memoria y CPU en el plan gratuito.
- Una clase propia de conexiones reutilizables: ahorra algunos comandos por solicitud, a cambio de unas 50 líneas que limpian a mano lo que el pool ya limpia.
- Bajar el costo del TLS o quitar la verificación del certificado: el certificado protege las credenciales de la base.
- Cambiar de plan: la demo es gratuita por decisión (ADR 0009).
