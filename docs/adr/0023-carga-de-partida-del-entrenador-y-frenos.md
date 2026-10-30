# 0023. Limitar la carga de partida del entrenador a no subir sobre el motor

- Estado: aceptado
- Fecha: 2026-10-30
- Decide: usuario
- Etiquetas: modulo:reglas, modulo:programas; rutas sensibles: `gimnasio/reglas/`

## Contexto
Hoy el motor usa la carga del programa solo cuando no hay historial del ejercicio. El entrenador necesita poder corregir un exceso después de revisar un aviso, pero `VISION.md` dice que los frenos no se pueden desactivar: si pudiera fijar cualquier carga, esquivaría el tope de suba semanal.

## Decisión
- Una versión del programa puede fijar una carga de partida por ejercicio. Vale hasta la primera serie registrada de ese ejercicio en esa versión.
- Con historial, el motor usa el menor valor entre la carga de partida y la que propondría. Toda suba sigue pasando por el motor.
- Sin historial, la carga de partida es libre y obligatoria si el ejercicio mide carga.
- Los frenos actúan después, igual que sobre cualquier otra prescripción.
- La explicación indica que el entrenador fijó la carga.
- Este cambio y la sustitución por equipo fuera de servicio exigen una versión mayor del motor.

## Consecuencias
El entrenador puede bajar una carga sin ninguna vía para subirla por encima de lo permitido. Para subir más rápido que el motor no hay camino, y es deliberado.

## Alternativas descartadas
- Carga libre del entrenador: esquiva el freno 3.
- Carga libre con el tope aplicado encima: mezcla dos autoridades y dificulta explicar el resultado.
- Sin carga de partida: la revisión de un aviso no podría corregir un exceso de carga.
