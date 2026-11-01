# 0030. Guardar como hecho la prescripción ajustada por dolor reportado en la sesión

- Estado: provisional
- Fecha: 2026-11-01
- Decide: Opus
- Etiquetas: modulo:entrenamiento, modulo:salud; rutas sensibles: `migraciones/`, `gimnasio/salud/`

## Contexto
La prescripción efectiva se guarda una sola vez, al empezar la sesión (ADR 0012; `prescripciones_efectivas` admite una fila por `sesion_realizada_id`). Los ajustes por dolor reportado durante la sesión no se guardan: `proyectar_dolor` los recalcula en cada lectura con los dolores y las restricciones de salud. Lo hace en la sesión en curso y también en las sesiones pasadas, que acreditan el pendiente ante el motor. Con la revocación de salud, el motor deja de usar esos datos (ADR 0025), así que la proyección desaparecería: la sesión en curso perdería sus ajustes y el historial acreditaría otra cosa. El issue #224 exige que la sesión en curso conserve su prescripción efectiva (duda de Codex en el PR #256). Además, la proyección lee las restricciones de salud vigentes al momento de la lectura: una restricción registrada o levantada a mitad de la sesión la cambiaría, y el issue #225 exige que la sesión en curso conserve su prescripción (duda de Codex en el PR #258).

## Decisión
- Cada dolor reportado en la sesión guarda, en la misma transacción, la **prescripción ajustada**: los ejercicios que devuelve la proyección en ese momento, con su explicación y la versión del motor. Va en una tabla nueva, `prescripciones_ajustadas`, solo con `INSERT` (ADR 0003). Una sesión puede tener varias; la vigente es la última.
- Con consentimiento de salud vigente, la lectura se sigue proyectando con los datos de salud, pero las restricciones quedan **congeladas por sesión**: la proyección de una sesión (en curso o pasada) usa solo las restricciones vigentes al empezarla (registradas hasta su inicio y sin levantamiento registrado hasta ese momento). Una restricción registrada o levantada después no la cambia, ni al retomarla ni al otorgar de nuevo el consentimiento; actúa desde la propuesta siguiente. Los dolores de la sesión sí se proyectan en vivo.
- Sin consentimiento, toda lectura de una sesión (en curso o pasada) usa su última prescripción ajustada. Si no tiene, usa la prescripción efectiva guardada al empezar. En ningún caso lee datos de salud. Máquina ocupada y equipo fuera de servicio siguen funcionando sobre ese resultado.
- La prescripción ajustada lleva datos de salud en sus razones. Se lee con el filtro del ADR 0024, y el borrado de datos de salud (ADR 0025) la anonimiza como a las demás explicaciones guardadas.
- No se completan prescripciones ajustadas para los dolores anteriores a la tabla.

## Consecuencias
- Revocar no cambia la sesión en curso ni lo que el historial ya acreditó. Al otorgar de nuevo, los dolores vuelven a proyectarse en vivo, con las restricciones congeladas al inicio de cada sesión.
- Registrar o levantar una restricción no reescribe lo que el historial acredita: las sesiones pasadas se proyectan con sus restricciones de entonces.
- Una restricción registrada después del inicio de la sesión no entra en su proyección ni en su prescripción ajustada, haya o no consentimiento.
- Para no consultar por sesión, la lectura trae una vez todas las restricciones no anonimizadas del socio con su momento de levantamiento y filtra en memoria por el inicio de cada sesión.
- La tabla entra en la lista de hechos de `scripts/verificar_pr.py`. Se verifica con las pruebas de los casos borde del issue #224.

## Alternativas descartadas
- Seguir proyectando con los datos de salud anteriores a la revocación: mantiene el tratamiento que el socio retiró.
- Guardar una foto al revocar: salud tendría que escribir en entrenamiento, que ya depende de salud.
- Proyectar las restricciones vigentes al leer: una restricción nueva o levantada cambiaría la sesión en curso y lo que acredita el historial.
- Admitir varias filas en `prescripciones_efectivas`: altera una tabla de hechos y cambia todas sus lecturas.

<!-- Un ADR "provisional" lo tomó un agente sin el usuario; se revisa en el cierre de la etapa. -->
