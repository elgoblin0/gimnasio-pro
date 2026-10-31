# 0025. Separar la revocación de salud del borrado de datos de salud

- Estado: aceptado
- Fecha: 2026-10-31
- Decide: usuario
- Etiquetas: modulo:salud, modulo:permisos

## Contexto
El ADR 0010 pide que la revocación detenga el tratamiento y anonimice los datos de salud. El ADR 0024 conserva los datos y los vuelve a mostrar si el socio otorga de nuevo el consentimiento: los dos no pueden valer a la vez. Además, el ADR 0003 prohíbe reescribir hechos, y el punto provisional del ADR 0006 (sin subas automáticas sin consentimiento) todavía no está en el código.

## Decisión
- La **revocación de salud** es reversible. No se guardan datos nuevos, el personal deja de verlos (ADR 0024) y el motor no aplica subas automáticas, y se lo explica al socio. Queda confirmado el punto provisional del ADR 0006.
- Mientras dure la revocación, los frenos por dolor reportado y restricción de salud dejan de usar esos datos: un ejercicio antes excluido puede volver a proponerse. La carga y las repeticiones objetivo quedan congeladas, el socio lo confirma antes de revocar con una advertencia explícita, y el entrenador ve el motivo «sin consentimiento de salud» en su bandeja, sin datos de salud. Si el socio otorga de nuevo y no hubo borrado, los frenos vuelven enseguida.
- Revocar `datos_personales` equivale a pedir la baja en recepción: desactiva al usuario y conserva su historial. Anonimizar datos personales queda fuera de la etapa 5. Un texto nuevo de consentimiento no vuelve a pedir aceptación; es un límite aceptado de la demo.
- El **borrado de datos de salud** es un acto aparte e irreversible que pide el socio, solo con el consentimiento ya revocado. Anonimiza condiciones, restricciones, dolores y los textos de salud de las explicaciones ya guardadas.
- Ese borrado es la única excepción autorizada al ADR 0003. Reemplaza la anonimización automática al revocar del ADR 0010.

## Consecuencias
Un socio que cambia de idea recupera sus datos y sus frenos con solo otorgar de nuevo. Borrar exige un segundo paso explícito. Las tablas de hechos de salud necesitan una vía de anonimización acotada, cubierta por pruebas.

## Alternativas descartadas
- Anonimizar al revocar, como decía el ADR 0010: una revocación por error destruiría datos que sostienen los frenos.
- No anonimizar nunca: el socio no tendría cómo eliminar datos sensibles, y el diseño dejaría de ser defendible ante la Ley 7593/2025.
- Seguir aplicando restricciones y dolores después de revocar: mantendría el tratamiento que el socio retiró.
