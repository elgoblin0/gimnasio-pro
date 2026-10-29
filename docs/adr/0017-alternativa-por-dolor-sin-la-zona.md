# 0017. Aceptar como alternativa por dolor reportado un ejercicio con solo zonas del original, sin las de dolor

- Estado: aceptado el 2026-10-29 por el dueño en el cierre de etapa 2 (#136)
- Fecha: 2026-10-29
- Decide: Opus
- Etiquetas: modulo:reglas, modulo:entrenamiento; rutas sensibles: `gimnasio/reglas/`

## Contexto
`elegir_alternativas` exige que la alternativa tenga exactamente las mismas zonas del cuerpo que el ejercicio original. En una sustitución por dolor reportado, la zona con dolor está siempre entre las del original, así que ninguna alternativa pasa el filtro y el ejercicio siempre se quita (duda de Codex en el issue #89, PR #119). El freno 1 pide sustituir «por una alternativa que no involucre la zona». El glosario definía **Alternativa** como un ejercicio que comparte patrón de movimiento y zonas del cuerpo.

## Decisión
- Sustitución por máquina ocupada (sin zonas excluidas): no cambia. La alternativa está en la lista de alternativas del original, usa otro equipo, conserva el patrón de movimiento y tiene las mismas zonas del cuerpo.
- Sustitución por dolor reportado (con zonas excluidas): la alternativa está en la lista de alternativas del original, usa otro equipo y conserva el patrón de movimiento; sus zonas del cuerpo forman un conjunto no vacío, incluido en las zonas del original y sin ninguna zona con dolor.
- Nunca se acepta una alternativa que agregue una zona que el original no involucra.
- El orden de la lista de alternativas del catálogo decide cuál se propone. Si ninguna cumple, el ejercicio se quita.
- La razón lleva el motivo de la sustitución (`maquina_ocupada` o `dolor_reportado`).

## Consecuencias
- El freno 1 puede sustituir en lugar de quitar siempre. La alternativa no carga zonas nuevas, así que no desplaza el esfuerzo hacia regiones que el entrenador no planificó.
- La definición de **Alternativa** del glosario distingue los dos casos.
- La semilla necesita al menos una alternativa con zonas reducidas para que el e2e de «me duele» muestre una sustitución.
- Se verifica con los vectores de `pruebas/reglas/test_alternativas.py` y los del freno 1 (issue #89).

## Alternativas descartadas
- Mantener zonas idénticas: el freno 1 siempre quita el ejercicio y la sustitución por dolor no existe.
- Aceptar cualquier alternativa sin la zona con dolor, aunque agregue zonas: cambia el trabajo planificado más de lo necesario y puede cargar zonas sin progresión previa.
- Cambiar el patrón de movimiento: deja de ser un reemplazo equivalente.

<!-- Un ADR "provisional" lo tomó un agente sin el usuario; se revisa en el cierre de la etapa. -->
