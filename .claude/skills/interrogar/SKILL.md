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

Los **hechos** los buscás vos, nunca el dueño: leé el código, `VISION.md`, `ROADMAP.md`, `docs/ALCANCE-FUNCIONAL.md` y los ADR con Grep y Read. Lanzá un subagente solo para un barrido de muchos archivos: la cuota de Claude es lo escaso. Las **decisiones** son del dueño: planteá cada una y esperá.

Terminado: la frontera está vacía (cada rama del árbol visitada, nada supuesto en silencio) y el dueño confirma el entendimiento compartido. Antes de eso no actúes sobre el plan.
