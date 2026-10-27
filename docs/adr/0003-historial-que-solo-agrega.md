# 0003. Registrar los hechos en un historial que solo agrega

- Estado: aceptado
- Fecha: 2026-10-26
- Decide: Opus

## Contexto
Corregir una serie o una salida no debe alterar silenciosamente el historial (ver los casos de aceptación en `docs/ALCANCE-FUNCIONAL.md`). La sincronización sin conexión también necesita hechos inmutables.

## Decisión
- Las tablas de hechos (series realizadas, entradas, salidas, chequeos del día, dolores reportados, pagos registrados, consentimientos) solo reciben `INSERT`.
- Una corrección es un registro nuevo con `corrige_a`, `autor_id`, `motivo` y `registrada_en`. Una anulación es una corrección que marca `anulada`.
- El estado vigente se obtiene con consultas o vistas que toman la última corrección.
- Las tablas de configuración (aforo, clases, plantillas, equipos) sí se actualizan, con la columna `actualizada_en`.
- Una prueba del CI rechaza `UPDATE` y `DELETE` sobre tablas de hechos en el código de `gimnasio/`. El reinicio de la demo es la única excepción y vive en `gimnasio/demo/`.

## Consecuencias
Se gana auditoría y una sincronización sencilla. Las consultas del estado vigente son algo más complejas; se encapsulan en cada repositorio.

## Alternativas descartadas
- Event sourcing completo: excesivo para la demo.
- Tablas con `UPDATE` y una tabla de auditoría aparte: es fácil olvidarse de auditar.
