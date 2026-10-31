# 0024. Ocultar al entrenador los datos de salud de explicaciones y notas sin consentimiento

- Estado: aceptado el 2026-10-31 por el dueño en el cierre de etapa 4 (#190)
- Fecha: 2026-10-31
- Decide: Opus
- Etiquetas: modulo:entrenador, modulo:salud

## Contexto
El ADR 0006 impide guardar dolores y restricciones sin consentimiento de salud, pero el consentimiento es revocable y los hechos anteriores quedan (ADR 0003). Los avisos al entrenador y las prescripciones efectivas guardan su explicación completa: las razones `dolor_reportado` y `restriccion_salud` llevan zonas y textos que revelan la ficha de salud, y la explicación de un aviso incluye las razones de toda la propuesta, sea cual sea su freno. La nota de un aviso revisado es texto libre del entrenador. Sin una regla, la vista del socio (#182) mostraría datos de salud con `salud: null`.

## Decisión
Mientras el socio no tenga consentimiento de salud vigente, lo que se le devuelve al entrenador:
- En toda explicación (de avisos al entrenador y de prescripciones efectivas), cada razón con `regla` `dolor_reportado` o `restriccion_salud` conserva `regla` y `version`, y de sus datos solo `ejercicio_id` y `ejercicio_hecho_id`. Se quitan los demás datos (`zonas`, `explicacion`). Las demás razones no cambian.
- El `freno` de cada aviso se muestra: dice qué regla actuó, no qué dato de salud la disparó, y la sustitución ya se ve en la prescripción.
- La `nota` de cada aviso revisado se devuelve `null`; la constancia de revisión (entrenador y fecha) se mantiene.
- Revisar un aviso no depende del consentimiento.
- Lo guardado no cambia: se filtra al leer, en el servicio. Con el consentimiento otorgado de nuevo, vuelve a verse completo.

## Consecuencias
El entrenador sabe que un freno actuó y qué cambió, sin ver zonas ni textos de salud. Se verifica con pruebas de la vista del socio que revocan el consentimiento después de un dolor reportado y de una restricción. Toda vista futura para el personal que devuelva explicaciones aplica el mismo filtro.

## Alternativas descartadas
- Ocultar los avisos de frenos de salud: el entrenador no podría revisarlos y la bandeja los arrastraría sin fin.
- Quitar enteras las razones de salud: la prescripción mostraría una sustitución sin la regla que la produjo.
- Borrar o reescribir las explicaciones al revocar: contradice el ADR 0003.

<!-- Un ADR "provisional" lo tomó un agente sin el usuario; se revisa en el cierre de la etapa. -->
