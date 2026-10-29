# 0015. Mantener la carga cuando se llega al tope de repeticiones con RIR bajo el objetivo

- Estado: aceptado el 2026-10-29 por el dueño en el cierre de etapa 2 (#136)
- Fecha: 2026-10-28
- Decide: Opus
- Etiquetas: modulo:reglas; rutas sensibles: `gimnasio/reglas/`

## Contexto
El ADR 0012 define tres casos de la **doble progresión**: subir (tope con RIR ≥ objetivo), mantener (no se llegó al tope) y bajar (por debajo del piso dos sesiones seguidas). Al implementar el issue #83, Codex encontró un cuarto caso sin regla: todas las series llegan al tope del rango, pero alguna tiene RIR menor que el objetivo. Ejemplo: sentadilla de 3 series, rango 8–12, 40 kg, incremento 2,5 kg, RIR objetivo 2; la última sesión fue 3×12 con RIR 1. Subir no corresponde porque el esfuerzo superó lo previsto; «buscar una repetición más» tampoco, porque ya está en el tope.

## Decisión
Se completa el ADR 0012 sin cambiar ninguna de sus reglas:

- **Mantener por RIR:** si todas las series de la última sesión del ejercicio llegaron al tope y al menos una serie con RIR registrado tiene RIR < objetivo, la carga y las repeticiones propuestas se mantienen (carga igual, repeticiones en el tope). No sube ni baja.
- Solo cuentan las series con RIR registrado. Una serie sin RIR no bloquea la suba: sigue valiendo la regla «sin RIR» del ADR 0012 (se decide por repeticiones y la explicación lo dice).
- El cumplimiento del RIR se evalúa serie por serie: una sola serie con RIR bajo basta para mantener.
- El freno 3 (tope semanal) solo actúa cuando la regla habría subido la carga; con esta regla no hay suba que frenar.
- La razón usa `Razon(regla="mantener_por_rir", version, datos)` con una `explicacion` en español, por ejemplo: «Mantenés 40 kg en sentadilla: llegaste a 12 repeticiones, pero con RIR 1 y el objetivo es 2.» Los datos incluyen el RIR más bajo registrado y el RIR objetivo.
- `VERSION_REGLAS` sigue en `"2.0.0"`: la regla se estrena junto con el motor 2.0, que todavía no se publicó.

## Consecuencias
- La carga no sube cuando el socio terminó más cansado de lo planificado, lo que es coherente con usar el RIR como criterio de suba.
- Cuando el socio vuelva a llegar al tope con RIR ≥ objetivo, sube con las reglas de siempre.
- El issue #83 suma un vector de prueba para este caso y el caso mixto (serie sin RIR más serie con RIR bajo).
- Es un ADR provisional: el dueño lo revisa al cierre de la etapa 2. Si lo cambia, exige una versión mayor del motor.

## Alternativas descartadas
- Subir igual cuando se llega al tope: contradice el ADR 0012, que exige RIR ≥ objetivo.
- Bajar la carga: castiga un esfuerzo alto en una sesión, algo que el ADR 0012 rechaza para los fallos aislados.
- Exigir RIR para subir: ya descartado en el ADR 0012.
