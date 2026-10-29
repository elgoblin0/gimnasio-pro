# 0016. Carga base con cargas mixtas y cuándo una sesión queda bajo el piso

- Estado: aceptado el 2026-10-29 por el dueño en el cierre de etapa 2 (#136)
- Fecha: 2026-10-28
- Decide: Opus
- Etiquetas: modulo:reglas; rutas sensibles: `gimnasio/reglas/`

## Contexto
Al implementar el issue #83 (PR #103), la revisión de Codex encontró dos agregaciones que los ADR 0012 y 0015 no fijan: qué **carga** usar como base cuando las series de la última sesión tuvieron cargas distintas, y cuándo una sesión cuenta como «por debajo del piso» para la regla de bajar. El borrador tomaba la carga de la última serie y «alguna serie bajo el piso»; ambos criterios dependen del orden de las series o castigan un mal día aislado. La revisión de Opus encontró dos más: qué cuenta como «todas las series» y si la sesión en curso entra al historial.

## Decisión
Se completa el ADR 0012 sin cambiar sus reglas:

- **Carga base:** es la menor carga entre las series de la última sesión del ejercicio. No depende del orden de las series. Sobre esa carga se aplican subir, mantener y bajar.
- **Subir, mantener por RIR y mantener:** las condiciones de tope y de RIR se evalúan sobre todas las series de la sesión, sin importar su carga. Si suben, la carga propuesta es la carga base más un incremento.
- **Sesión bajo el piso:** una sesión cuenta como bajo el piso cuando **más de la mitad** de sus series tienen repeticiones menores al piso del rango (la mitad exacta no cuenta). Bajar exige dos sesiones seguidas del ejercicio en esa condición, como dice el ADR 0012.
- **Series completas para subir:** «todas las series» del ADR 0012 son las **series planificadas** del ejercicio. Subir y mantener por RIR exigen que la última sesión tenga registradas al menos `series` series del ejercicio planificado, todas en el tope. Si hay menos, se mantiene la carga y se busca una repetición más. La regla de bajar cuenta la mayoría sobre las series registradas.
- **Historial al proponer:** al proponer una sesión planificada, el historial de sus ejercicios **excluye** las sesiones realizadas de esa misma sesión planificada en la semana local actual (`fecha_local >= semana_local`), porque son las que acreditan sus pendientes. Las semanas anteriores de esa sesión planificada y las demás sesiones planificadas sí cuentan. Así, la prescripción no cambia mientras se entrena (ADR 0012: se fija al empezar la sesión). El freno 3 usa **el mismo historial**: las subas de las sesiones excluidas no cuentan como subas anteriores, porque son la suba que la propia sesión está realizando. Las subas de otras sesiones planificadas de la semana sí frenan.
- La explicación indica la carga base usada y, al bajar, cuántas series quedaron bajo el piso. Si el ejercicio no tiene RIR objetivo, la explicación no menciona el RIR.
- `VERSION_REGLAS` sigue en `"2.0.0"`: el motor 2.0 todavía no se publicó.

## Consecuencias
- Invertir el orden de las series de una misma sesión no cambia la próxima prescripción.
- Una serie floja aislada no baja la carga; coherente con el rechazo de «bajar tras un solo fallo» del ADR 0012.
- Con cargas mixtas la propuesta es conservadora: parte de la carga más baja.
- Vectores de prueba (en `pruebas/reglas/`):
  - Cargas (40, 45, 35) kg, 3×12 con RIR 2, objetivo 2, rango 8–12: carga base 35 kg, sube a 35 + incremento; el mismo conjunto en otro orden da el mismo resultado.
  - Dos sesiones seguidas con (7, 10, 10) y piso 8: no baja (1 de 3 bajo el piso).
  - Dos sesiones seguidas con (7, 7, 10) y piso 8: baja un incremento (2 de 3).
  - Dos sesiones seguidas con (7, 7, 10, 10): no baja (la mitad exacta no cuenta).
  - Plan 3×8–12; última sesión con una sola serie de 12: mantiene 40 kg (`mantener_carga`).
  - Plan 3×8–12; última sesión (12, 12, 12, 12) con RIR ≥ objetivo: sube un incremento.
  - Semana anterior 12/12/12 con RIR 2 en la misma sesión planificada; esta semana, una serie de 10 en curso: sube desde la semana anterior.
  - Semana anterior 10/10/10; esta semana, una serie de 12 en curso: mantiene 40 kg.
  - Semana anterior 3×12 con RIR 2 a 20,5 kg, incremento 2,5: propone 23 kg. Después de registrar la primera serie a 23 kg en esa misma sesión, la propuesta sigue en 23 kg, sin `tope_semanal`.
  - El lunes, la sesión A sube el ejercicio de 20,5 a 23 kg. El jueves, la sesión B tiene el mismo ejercicio y su historial habilita otra suba: `tope_semanal` mantiene 23 kg.
- Una sesión cortada no sube la carga, y la propuesta que el socio ve al empezar no cambia serie a serie, tampoco por el freno 3.
- Es un ADR provisional: el dueño lo revisa al cierre de la etapa 2. Si lo cambia, exige una versión mayor del motor.

## Alternativas descartadas
- Carga de la última serie: depende del orden.
- Carga máxima o promedio: pueden proponer una carga que el socio no movió en todas las series, o cifras que no existen en los discos.
- «Alguna serie bajo el piso» o «todas»: la primera castiga un mal día; la segunda casi nunca baja.
- Contar las series registradas para subir: una sesión cortada con una serie al tope subiría la carga.
- Incluir la sesión en curso en el historial: la carga cambia entre series del mismo día.
- Excluir todo el historial de la sesión planificada que se propone: perdería las semanas anteriores, que son la base de la progresión.
- Derivar las subas del freno 3 de todo el historial: la suba que la sesión está realizando se frena a sí misma y la carga baja en medio de la sesión (caso del PR #103).
