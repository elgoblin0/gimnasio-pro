# 0012. Ajustar la carga con doble progresión y un tope de un incremento por semana

- Estado: aceptado
- Fecha: 2026-10-27
- Decide: usuario
- Etiquetas: modulo:reglas, modulo:entrenamiento; rutas sensibles: `gimnasio/reglas/`, `migraciones/`

## Contexto
`VISION.md` pide ajustes automáticos de carga y volumen (doble progresión + RPE/RIR + chequeo del día) con frenos fijos, y deja el valor del tope de suba semanal a un ADR del motor. El motor 1.0.0 (`gimnasio/reglas/sesion.py`) respeta la prescripción sin ajustar nada; el ejercicio planificado tiene una sola cifra de repeticiones y la serie realizada no guarda esfuerzo.

## Decisión
- El ejercicio planificado tiene un rango de repeticiones (piso y tope), un RIR objetivo y un descanso en segundos. Cada ejercicio del catálogo tiene su **incremento de carga**.
- **Subir:** si todas las series de la última sesión del ejercicio llegaron al tope del rango con RIR ≥ objetivo, la carga sube un incremento y las repeticiones vuelven al piso.
- **Mantener:** si no se llegó al tope, se mantiene la carga y se busca una repetición más.
- **Bajar:** si quedó por debajo del piso en dos sesiones seguidas de ese ejercicio, baja un incremento.
- Una serie sin RIR se evalúa solo por repeticiones, y la explicación lo dice.
- **Tope (freno 3):** como máximo un incremento de suba por ejercicio por semana (lunes a domingo, `America/Asuncion`).
- **Chequeo del día (freno 4):** sueño o energía ≤ 2 (escala de 1 a 5) quita una serie por ejercicio (mínimo una) y anula las subas de ese día. Sin chequeo, se toma como neutro.
- **Dolor reportado (freno 1):** no se sube la carga de los ejercicios que involucran esa zona del cuerpo, ni en esa sesión ni en la siguiente.
- El socio registra solo RIR; el RPE se deriva (RPE = 10 − RIR).
- Al empezar la sesión se guarda como hecho la **prescripción efectiva** (cargas, series y razones con la versión del motor). Cada freno que actúa deja un **aviso al entrenador**.
- La serie realizada guarda también el ejercicio efectivamente hecho. Las series de una alternativa acreditan el ejercicio planificado que sustituyen.

## Consecuencias
El socio ve subas pequeñas y explicables. El historial conserva qué propuso el motor aunque cambie su versión. `series_realizadas` gana columnas opcionales (RIR y ejercicio hecho) sin reescribir filas existentes; cambiar estos valores exige un ADR nuevo y una versión mayor del motor. Se verifica con pruebas del motor por cada regla y freno.

## Alternativas descartadas
- Tope en porcentaje de la carga: produce cifras con decimales que no existen en los discos del gimnasio.
- Exigir RIR para subir: frena el registro con un toque y deja la demo sin progresión.
- Bajar tras un solo fallo: castiga un mal día, que ya lo cubre el chequeo.
- Recalcular la prescripción en cada lectura sin guardarla: el historial no mostraría lo que se propuso.
