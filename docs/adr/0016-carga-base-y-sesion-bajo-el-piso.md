# 0016. Carga base con cargas mixtas y cuándo una sesión queda bajo el piso

- Estado: provisional
- Fecha: 2026-10-28
- Decide: Opus
- Etiquetas: modulo:reglas; rutas sensibles: `gimnasio/reglas/`

## Contexto
Al implementar el issue #83 (PR #103), la revisión de Codex encontró dos agregaciones que los ADR 0012 y 0015 no fijan: qué **carga** usar como base cuando las series de la última sesión tuvieron cargas distintas, y cuándo una sesión cuenta como «por debajo del piso» para la regla de bajar. El borrador tomaba la carga de la última serie y «alguna serie bajo el piso»; ambos criterios dependen del orden de las series o castigan un mal día aislado.

## Decisión
Se completa el ADR 0012 sin cambiar sus reglas:

- **Carga base:** es la menor carga entre las series de la última sesión del ejercicio. No depende del orden de las series. Sobre esa carga se aplican subir, mantener y bajar.
- **Subir, mantener por RIR y mantener:** las condiciones de tope y de RIR se evalúan sobre todas las series de la sesión, sin importar su carga. Si suben, la carga propuesta es la carga base más un incremento.
- **Sesión bajo el piso:** una sesión cuenta como bajo el piso cuando **más de la mitad** de sus series tienen repeticiones menores al piso del rango (la mitad exacta no cuenta). Bajar exige dos sesiones seguidas del ejercicio en esa condición, como dice el ADR 0012.
- La explicación indica la carga base usada y, al bajar, cuántas series quedaron bajo el piso.
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
- Es un ADR provisional: el dueño lo revisa al cierre de la etapa 2. Si lo cambia, exige una versión mayor del motor.

## Alternativas descartadas
- Carga de la última serie: depende del orden.
- Carga máxima o promedio: pueden proponer una carga que el socio no movió en todas las series, o cifras que no existen en los discos.
- «Alguna serie bajo el piso» o «todas»: la primera castiga un mal día; la segunda casi nunca baja.
