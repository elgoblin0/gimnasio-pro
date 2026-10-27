---
name: modelar-dominio
description: Construir y afinar el modelo de dominio de Gimnasio Pro mientras se diseña. Usar al discutir términos, editar GLOSSARY.md, o escribir o editar un ADR.
---

Disciplina activa: cuestionar términos, inventar casos borde y escribir el glosario y las decisiones en cuanto cristalizan. Solo leer el glosario para usar su vocabulario no es esta habilidad.

Un solo contexto: `GLOSSARY.md` en la raíz y `docs/adr/`.

## Durante la sesión

- **Contrastá con el glosario.** Si el dueño usa un término que choca con `GLOSSARY.md`, señalalo en el momento: «El glosario define *membresía* como X, pero parece que querés decir Y. ¿Cuál es?»
- **Afilá el lenguaje difuso.** Ante un término vago o sobrecargado, proponé uno canónico: «¿*Plan* es la membresía o el programa de entrenamiento?»
- **Escenarios concretos.** Probá las relaciones entre conceptos con casos borde que obliguen a fijar sus límites.
- **Contrastá con el código.** Si el dueño describe algo que el código contradice, mostralo.

## GLOSSARY.md

Actualizalo en cuanto se resuelve un término, sin juntarlos para el final. Seguí el formato que ya tiene:

```md
**Sesión planificada**:
Entrenamiento previsto con ejercicios, objetivos de trabajo y una fecha o posición dentro de una secuencia.
_Evitar_: Asistencia, visita.
```

- Con opinión: entre varias palabras, elegí la mejor y poné las demás en `_Evitar_`.
- Una o dos oraciones: qué *es*, no qué hace.
- Solo términos propios del gimnasio y del entrenamiento; nada de conceptos generales de programación ni detalles de implementación.
- Agrupá bajo los subtítulos existentes (`## Entrenamiento`, `## Operación`…) o uno nuevo si surge un grupo natural.

## ADR

Ofrecé un ADR solo cuando se cumplen las tres:

1. **Difícil de revertir**: cambiar de idea después cuesta.
2. **Sorprende sin contexto**: un lector futuro se preguntaría por qué.
3. **Fruto de un compromiso real**: había alternativas y se eligió una por razones concretas.

Califican: la forma de la arquitectura, tecnologías con atadura, límites de alcance (los «no» valen tanto como los «sí»), desvíos deliberados del camino obvio, restricciones que el código no muestra y alternativas descartadas por razones no obvias.

Formato: `docs/adr/0000-plantilla.md`. Número siguiente al mayor de `docs/adr/`. `Decide: usuario` si lo resolvió el dueño en la sesión; `Decide: Opus` con `Estado: provisional` si lo decidiste sin él, para revisarlo al cierre de la etapa. Si una propuesta contradice un ADR vigente, decilo explícito: _Contradice el ADR 0007, pero conviene reabrirlo porque…_
