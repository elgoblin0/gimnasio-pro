# 0011. Limitar el uso de Opus con un presupuesto semanal en tokens

- Estado: reemplazado el 2026-10-27: el despachador que aplicaba este tope se eliminó (ver `docs/protocolo-agentes.md`)
- Fecha: 2026-10-26
- Decide: Opus

## Contexto
La cuota semanal de Claude es escasa y el saldo de Codex, amplio. Opus decide y revisa; Codex hace el volumen.

## Decisión
- `scripts/despachador.toml` define `presupuesto_semanal_opus` en tokens ponderados:
  - fórmula: `entrada + salida + creación de caché + 0,1 × lectura de caché`;
  - los valores salen del `usage` de `claude -p --output-format json`;
  - también cuentan las sesiones interactivas de Claude Code en este repo y sus worktrees, leídas de
    `~/.claude/projects/` (o `CLAUDE_CONFIG_DIR`). En la etapa 0, una sola sesión interactiva gastó 3,8 veces
    el presupuesto sin que el despachador la viera.
- La semana va de lunes a domingo en `America/Asuncion`. El registro está en `.despachador/registro.jsonl`, fuera del repo.
- Al llegar al **80 %**, Opus solo toma issues `ejecutor:opus` que tocan rutas sensibles; los demás esperan o pasan a Codex.
- Al llegar al **100 %**, Opus no toma nada:
  - los issues dudosos pasan a `ejecutor:codex`, con un comentario que pide más detalle;
  - las revisiones sensibles quedan en `estado:revision` hasta la semana siguiente.
- Valor inicial: 2.000.000 de tokens ponderados por semana. Se recalibra con el consumo real en el cierre de cada etapa.
- Un solo Claude a la vez, y como máximo un reintento de Opus por issue.
- Codex no tiene tope propio, pero el despachador también registra sus tokens.

## Consecuencias
El gasto de Opus es visible y predecible. Algunos issues pueden demorarse hasta la semana siguiente.

## Alternativas descartadas
- Tope en dólares (`--max-budget-usd`): el plan de suscripción mide tokens, no dólares.
- Sin tope: riesgo de agotar la cuota a mitad de etapa.
