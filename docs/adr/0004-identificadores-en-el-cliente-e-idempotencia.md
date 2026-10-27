# 0004. Generar los identificadores en el cliente y exigir claves de idempotencia

- Estado: aceptado
- Fecha: 2026-10-26
- Decide: Opus

## Contexto
La PWA registra series sin conexión y las reenvía al reconectar. Los reintentos de red o un doble toque no deben duplicar visitas ni series.

## Decisión
- Los hechos tienen un `id` UUIDv7 generado por quien lo crea: el cliente en la PWA, el servidor en lo demás. Se guarda como `BINARY(16)` y se expone en texto.
- Python 3.13 no trae `uuid7`: se implementa en `gimnasio/comun/ids.py` y en `gimnasio/static/js/comun/ids.js`, con la misma prueba de formato.
- Toda solicitud que crea o cambia algo envía `Idempotency-Key` (otro UUID).
- Tabla `solicitudes_idempotentes(clave, usuario_id, huella_cuerpo, estado_http, respuesta, creada_en)`, con clave única por usuario:
  - la misma clave con el mismo cuerpo devuelve la respuesta guardada;
  - la misma clave con otro cuerpo devuelve 422;
  - las claves se purgan a los 7 días.
- Insertar un hecho con un `id` ya existente es un éxito idempotente, no un error.

## Consecuencias
Los reintentos son seguros por diseño y la sincronización no necesita traducir identificadores. Cada `id` ocupa 16 bytes en vez de 4.

## Alternativas descartadas
- `AUTO_INCREMENT`: obliga a esperar al servidor para conocer el `id`.
- UUIDv4: no se ordena por tiempo y fragmenta los índices de InnoDB.
