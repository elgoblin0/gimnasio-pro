# 0013. Adelantar a la etapa 2 el catálogo estructurado y las restricciones, solo como datos

- Estado: aceptado; el ADR 0021 recorta la gestión del catálogo prevista para la etapa 4
- Fecha: 2026-10-27
- Decide: usuario
- Etiquetas: modulo:entrenamiento, modulo:reglas; rutas sensibles: `migraciones/`, `gimnasio/salud/`

## Contexto
La etapa 2 trae «me duele», «máquina ocupada», los frenos y el cuerpo 3D. Todos necesitan saber qué zonas del cuerpo involucra un ejercicio, qué alternativas tiene y qué restricciones de salud pesan sobre el socio. El ROADMAP ubica equipos y alternativas en la etapa 4, y la ficha de salud en la 5.

## Decisión
- Desde la etapa 2, el catálogo de ejercicios guarda:
  - zonas del cuerpo, de esta lista fija: pecho, espalda alta, dorsales, hombros, bíceps, tríceps, abdomen, glúteos, cuádriceps, isquiotibiales, pantorrillas, zona lumbar, rodillas y cuello;
  - patrón de movimiento;
  - equipo;
  - incremento de carga;
  - alternativas.
- Las restricciones de salud existen como datos de la semilla, sin pantalla.
- La gestión del catálogo, de los equipos y de las alternativas por el entrenador sigue en la etapa 4.
- La ficha completa, el consentimiento de salud y la pantalla de restricciones siguen en la etapa 5.
- La bandeja que muestra los avisos al entrenador sigue en la etapa 4.

## Consecuencias
Los frenos 1, 2 y 5 tienen pruebas en esta etapa. Las etapas 4 y 5 construyen pantallas sobre tablas que ya existen. Mientras tanto, nadie edita estos datos dentro de la app. Las restricciones de la semilla son ficticias y no requieren consentimiento real.

## Alternativas descartadas
- Respetar el orden del ROADMAP: el freno 2 y «máquina ocupada» quedarían sin datos hasta la etapa 4 o 5.
- Adelantar también las pantallas de gestión: suma trabajo sin impacto en la demo del socio.
