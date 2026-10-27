---
name: dividir-en-tickets
description: Partir una spec o un plan de Gimnasio Pro en tickets de bala trazadora para Codex, publicarlos en GitHub con sus dependencias y entregar un prompt por ticket. Usar después de escribir-spec, o cuando el dueño pide tickets.
---

## 1. Contexto

Partí de la conversación. Si te pasan un número de issue, leelo entero con `gh issue view <n> --comments`. Si no exploraste el código, hacelo: los tickets usan los términos de `GLOSSARY.md` y respetan los ADR del área. Buscá **prefactorizaciones** que hagan fácil el cambio: «primero hacé fácil el cambio, después hacé el cambio fácil».

## 2. Rebanadas verticales

Cada ticket es una **bala trazadora**:

- atraviesa todas las capas que necesita (migración, repositorio, servicio, rutas, pantalla, pruebas): vertical, nunca una capa sola;
- terminado, se puede demostrar o verificar por sí mismo;
- cabe en un chat nuevo de Codex;
- las prefactorizaciones van primero.

Cada ticket declara sus **bloqueos**: los tickets que tienen que estar fusionados antes de empezarlo.

Excepción: un **cambio ancho** (renombrar una columna, cambiar el tipo de algo compartido) cuyo radio rompe todo de una vez no entra en una rebanada. Va como expandir–migrar–contraer: agregar la forma nueva junto a la vieja, migrar los usos por lotes (un ticket por lote, bloqueado por la expansión) y borrar la vieja en un ticket bloqueado por todos los lotes. El CI queda verde entre lote y lote.

## 3. Consultar al dueño

Mostrá la división como lista numerada; por ticket: título, bloqueos y qué comportamiento deja andando. Preguntá si la granularidad está bien, si cada bloqueo es real y si conviene unir o partir alguno. Iterá hasta que apruebe.

## 4. Publicar

Uno por ticket, en orden de dependencias (los bloqueos primero), para que cada `Depende de` cite números reales. No modifiques ni cierres la spec.

```bash
gh issue create --title "<título>" --label estado:listo --label ejecutor:codex --label modulo:<modulo> --label tipo:<tipo> --milestone "Etapa N: …" --body-file - <<'EOF'
Parte de #<spec>

## Objetivo
Qué queda funcionando, en términos del glosario.

## Especificación
Módulos, archivos existentes que conviene nombrar, firmas, reglas y ADR que aplican. Lo que no está acá no se hace: Codex no decide lo que el ticket calla.

## Criterios de aceptación
- [ ] Verificable, con su prueba.

Depende de: #N, #M

## Fuera de alcance
EOF
```

- `Depende de:` en esa forma exacta, vacío si no hay bloqueos; no uses las dependencias nativas de GitHub.
- `tipo:patron` si es la primera instancia de un patrón: la Especificación lo describe completo.
- Un `modulo:*` existente (`gh label list`); si ninguno sirve, preguntale al dueño antes de crear uno.

## 5. Prompts para Codex

Entregá un prompt por ticket, en orden de dependencias, cada uno en su propio bloque para copiar:

```
Implementá el issue #N de elgoblin0/gimnasio-pro. Leelo con `gh issue view N --comments`.
Seguí AGENTS.md y docs/protocolo-agentes.md. Corré ruff y pytest,
abrí el PR con la plantilla y pedí la revisión a un subagente de Codex.
```

Agregá una o dos líneas solo cuando haya una trampa o una decisión que el ticket no alcanza a decir. Marcá qué tickets tocan rutas sensibles: esos PR esperan además la revisión de Opus.

Terminado: todos los tickets aprobados están publicados y cada uno tiene su prompt.
