# 0029. Congelar el cupo de la ocurrencia empezada con un registro nuevo

- Estado: provisional
- Fecha: 2026-10-31
- Decide: Opus
- Etiquetas: modulo:clases, migraciones/

## Contexto
`ocurrencias_clase` copia la hora y la duración de la clase, pero no el cupo: el estado de las reservas (con lugar o en espera) se deriva siempre de `clases.cupo`. Al cambiar el cupo de la clase (#219) cambiaría también el estado de las ocurrencias empezadas, y el issue exige que «las ocurrencias empezadas no se tocan». No se alteran tablas existentes (ADR 0003).

## Decisión
- Tabla nueva, solo INSERT: `cupos_ocurrencia(id, ocurrencia_id UNIQUE, cupo, registrado_en)`, con `CHECK (cupo > 0)` y clave foránea a `ocurrencias_clase`.
- **Cupo vigente de una ocurrencia**: el de su fila en `cupos_ocurrencia` si existe; si no, `clases.cupo`. Toda lectura del estado de las reservas (reservar, cancelar una reserva, agenda, lista de reservas, avisos al socio) usa ese cupo, con `LEFT JOIN` y `COALESCE` en la misma consulta, sin una consulta por fila.
- Al cambiar el cupo en `PUT /api/clases/<id>`, en la misma transacción y **antes** de actualizar `clases`: para cada ocurrencia de esa clase con fila, empezada (fecha y `hora_inicio` de la ocurrencia ≤ `reloj_actual()`) y sin fila en `cupos_ocurrencia`, se inserta su cupo con el valor anterior de `clases.cupo`. Una ocurrencia sin registro siempre siguió a `clases.cupo`, así que ese valor es el que tenía.
- Las ocurrencias futuras no reciben registro: siguen a `clases.cupo` y se recalculan, con sus avisos al socio. Las canceladas no se recalculan ni generan avisos.
- Un cambio que no modifica el cupo no inserta nada. La fila es única por ocurrencia: una ocurrencia empezada no vuelve a cambiar de cupo.

## Consecuencias
El estado de las reservas de una ocurrencia empezada queda fijo y auditable sin `UPDATE`. `cupos_ocurrencia` se suma a `HECHOS` en `scripts/verificar_pr.py`. Se verifica con la prueba del caso «Una ocurrencia empezada no se recalcula ni genera avisos al cambiar el cupo», que además comprueba el estado de sus reservas después del cambio.

## Alternativas descartadas
- Columna `cupo` en `ocurrencias_clase`: obliga a alterar una tabla existente y a un `UPDATE` para fijarla después.
- Registrar el cupo al crear cada ocurrencia: no cubre las ocurrencias ya creadas y repite el dato sin necesidad.
- Prohibir cambiar el cupo mientras haya una ocurrencia empezada: no resuelve las pasadas, que también derivan su estado de `clases.cupo`.
