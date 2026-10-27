---
name: interrogar
description: Interrogatorio por rondas para afinar un plan o un diseño de Gimnasio Pro, que deja los términos en GLOSSARY.md y las decisiones en ADR a medida que se resuelven. Usar al planear una etapa o una función, o cuando el dueño pide que lo interroguen.
---

Al empezar, invocá `modelar-dominio`: rige el glosario y los ADR durante todo el interrogatorio.

Interrogá al dueño sin tregua hasta llegar a un entendimiento compartido. Armá un **árbol de decisiones**: cada decisión abre las que dependen de ella.

Trabajá por **rondas**. La **frontera** son las decisiones cuyos requisitos ya están resueltos: lo que se puede preguntar _ahora_ sin adivinar respuestas que todavía no escuchaste. Cada ronda pregunta toda la frontera, numerada y con tu recomendación; después esperá las respuestas.

```
❓ **P1** - **<título>**: <la pregunta, con sus opciones si las hay>

➡️ <tu recomendación>

---

❓ **P2** - ...
```

Redactá cada pregunta para que «sí» acepte tu recomendación. Una pregunta que depende de otra todavía abierta va en una ronda posterior.

Los **hechos** los buscás vos, nunca el dueño. Cuando una pregunta de la frontera necesita un hecho del entorno (el código, `VISION.md`, `ROADMAP.md`, `docs/ALCANCE-FUNCIONAL.md`, los ADR), lanzá un subagente que lo busque; no le preguntes al dueño nada que puedas averiguar. No te frenes esperándolo: una búsqueda en curso es un requisito sin resolver, así que solo esperan las preguntas que dependen de ella; el resto de la frontera se pregunta ya. Las **decisiones** son del dueño: planteá cada una y esperá.

Terminado: la frontera está vacía (cada rama del árbol visitada, nada supuesto en silencio) y el dueño confirma el entendimiento compartido. Antes de eso no actúes sobre el plan.
