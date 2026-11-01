# 0031. Guardar una respuesta saneada cuando la original lleva un secreto de un solo uso

- Estado: provisional
- Fecha: 2026-11-01
- Decide: Opus
- Etiquetas: modulo:socios, modulo:permisos

## Contexto
El ADR 0004 guarda en `solicitudes_idempotentes` la respuesta de cada escritura y la devuelve tal cual al reintentar. El alta de socio (#230) entrega una clave provisional en texto una sola vez y prohíbe volver a entregarla. Guardar esa respuesta dejaría la clave en texto en la base durante siete días y la devolvería en cada reintento.

## Decisión
- Una ruta cuya respuesta lleva un secreto de un solo uso define en `flask.g.respuesta_para_reintento` el cuerpo (un `dict`) que se guarda en lugar del real. `comun/idempotencia.py` guarda ese cuerpo serializado en JSON, con el mismo estado HTTP y los mismos encabezados que la respuesta real; si no está definido, guarda la respuesta real como hasta ahora.
- El cuerpo para el reintento es el real sin el secreto y con una marca que lo dice. En el alta de socio:
  - primera respuesta: los campos del alta (incluido `usuario_id`), `"clave_provisional": "<texto>"` y `"clave_ya_entregada": false`;
  - guardada y devuelta al reintentar: los mismos campos sin `clave_provisional` y con `"clave_ya_entregada": true`.
- En modo demo no hay clave: la respuesta no lleva `clave_provisional`, lleva `"clave_ya_entregada": false` y no se define `respuesta_para_reintento`.
- El secreto no se escribe en logs, en `solicitudes_idempotentes` ni en ninguna otra tabla en texto.
- El resto del ADR 0004 sigue igual: la misma clave con otro cuerpo da 422, y un reintento no crea otro usuario.

## Consecuencias
El reintento sigue siendo seguro y devuelve el mismo usuario, sin exponer la clave. Si la primera respuesta se pierde en la red, la clave no se recupera por reintento: generar una nueva queda fuera del alcance de #230. Se verifica con una prueba que lee la fila de `solicitudes_idempotentes` y comprueba que no contiene la clave, y otra que reintenta y recibe `clave_ya_entregada: true` sin `clave_provisional`.

## Alternativas descartadas
- Devolver la respuesta guardada completa: viola #230 y deja la clave en texto siete días.
- No guardar la respuesta del alta: el reintento volvería a ejecutar el alta y daría 409 por cédula repetida en vez del mismo usuario.
- Cifrar la clave en la fila: sigue siendo recuperable y se volvería a entregar.

<!-- Un ADR "provisional" lo tomó un agente sin el usuario; se revisa en el cierre de la etapa. -->
