# 0030. Guardar como hecho la prescripción ajustada por dolor reportado en la sesión

- Estado: provisional
- Fecha: 2026-11-01
- Decide: Opus
- Etiquetas: modulo:entrenamiento, modulo:salud; rutas sensibles: `migraciones/`, `gimnasio/salud/`

## Contexto
La prescripción efectiva se guarda una sola vez, al empezar la sesión (ADR 0012; `prescripciones_efectivas` admite una fila por `sesion_realizada_id`). Los ajustes por dolor reportado durante la sesión no se guardan: `proyectar_dolor` los recalcula en cada lectura con los dolores y las restricciones de salud. Lo hace en la sesión en curso y también en las sesiones pasadas, que acreditan el pendiente ante el motor. Con la revocación de salud, el motor deja de usar esos datos (ADR 0025), así que la proyección desaparecería: la sesión en curso perdería sus ajustes y el historial acreditaría otra cosa. El issue #224 exige que la sesión en curso conserve su prescripción efectiva (duda de Codex en el PR #256).

## Decisión
- Cada dolor reportado en la sesión guarda, en la misma transacción, la **prescripción ajustada**: los ejercicios que devuelve la proyección en ese momento, con su explicación y la versión del motor. Va en una tabla nueva, `prescripciones_ajustadas`, solo con `INSERT` (ADR 0003). Una sesión puede tener varias; la vigente es la última.
- Con consentimiento de salud vigente, la lectura no cambia: se sigue proyectando con los datos de salud.
- Sin consentimiento, toda lectura de una sesión (en curso o pasada) usa su última prescripción ajustada. Si no tiene, usa la prescripción efectiva guardada al empezar. En ningún caso lee datos de salud. Máquina ocupada y equipo fuera de servicio siguen funcionando sobre ese resultado.
- La prescripción ajustada lleva datos de salud en sus razones. Se lee con el filtro del ADR 0024, y el borrado de datos de salud (ADR 0025) la anonimiza como a las demás explicaciones guardadas.
- No se completan prescripciones ajustadas para los dolores anteriores a la tabla.

## Consecuencias
- Revocar no cambia la sesión en curso ni lo que el historial ya acreditó. Al otorgar de nuevo, los frenos vuelven a proyectarse en vivo.
- Si una restricción se registra después del último dolor de la sesión, no entra en su prescripción ajustada: sin consentimiento, no se aplica a esa sesión. Es coherente con la revocación.
- La tabla entra en la lista de hechos de `scripts/verificar_pr.py`. Se verifica con las pruebas de los casos borde del issue #224.

## Alternativas descartadas
- Seguir proyectando con los datos de salud anteriores a la revocación: mantiene el tratamiento que el socio retiró.
- Guardar una foto al revocar: salud tendría que escribir en entrenamiento, que ya depende de salud.
- Admitir varias filas en `prescripciones_efectivas`: altera una tabla de hechos y cambia todas sus lecturas.

<!-- Un ADR "provisional" lo tomó un agente sin el usuario; se revisa en el cierre de la etapa. -->
