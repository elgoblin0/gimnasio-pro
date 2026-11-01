# 0027. Tratar la membresía como estado derivado del pago registrado, no como hecho

- Estado: aceptado el 2026-11-01 por el dueño en el cierre de etapa 5 (#235)
- Fecha: 2026-10-31
- Decide: Opus
- Etiquetas: modulo:pagos, modulo:socios, migraciones/

## Contexto
El issue #213 agrega `pago_id` y `tipo_id` a `membresias` y a la vez prohíbe alterar tablas de hechos (duda de Codex en el PR #243). El ADR 0003 lista como hechos los pagos registrados, pero no las membresías; la tabla `membresias` (migración 0006) tiene `actualizada_en`, como las tablas de configuración, y no figura en `HECHOS` de `scripts/verificar_pr.py`.

## Decisión
- El hecho es el **pago registrado** (`pagos`, y su anulación en `anulaciones_pago`). La **membresía** es el estado que deriva de él: la vigencia que otorga.
- `membresias` no es una tabla de hechos y no entra en `HECHOS`. Una migración puede agregarle columnas sin `-- Autoriza Opus: #N`.
- Aun así, renovar inserta una membresía nueva y no modifica las anteriores. Una anulación de pago no toca la membresía: `socios` ignora la que proviene de un pago anulado (#222).
- `pago_id` es único cuando no es NULL: un pago crea a lo sumo una membresía.

## Consecuencias
El #213 avanza sin autorización especial. La auditoría queda en `pagos`, que sí es solo INSERT. Que el código no haga `UPDATE` sobre membresías existentes no lo hace cumplir el CI, sino las pruebas del #213 («renovar una membresía anterior no la modifica») y la revisión de Opus del diff. El reinicio de la demo sigue borrando `membresias` en `gimnasio/demo/`.

## Alternativas descartadas
- Declarar `membresias` como hecho: exigiría autorizar cada migración que la toque y duplica la auditoría que ya da `pagos`.
- Guardar la vigencia solo en `pagos` y calcularla al consultar: obliga a reescribir `socios` y pierde las membresías anteriores a la etapa 5, que no tienen pago.
