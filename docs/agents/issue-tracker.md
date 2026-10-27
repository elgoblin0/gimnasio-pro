# Issues: GitHub

Los issues y las specs viven en GitHub Issues de `elgoblin0/gimnasio-pro`. Todo se hace con `gh`, en español y con los términos de `GLOSSARY.md`.

- **Crear**: `gh issue create --title "..." --body-file -` con un heredoc.
- **Leer**: `gh issue view <n> --json number,title,body,labels,comments`.
- **Listar**: `gh issue list --state open --label estado:listo --json number,title,labels`.
- **Comentar, etiquetar, cerrar**: `gh issue comment`, `gh issue edit --add-label/--remove-label`, `gh issue close`.

## Spec (`to-spec`)
Las secciones de su plantilla van en español: Problema, Solución, Historias de usuario, Decisiones de implementación, Decisiones de prueba, Fuera de alcance, Notas. Etiquetas: `tipo:docs` y `ejecutor:opus`, sin `estado:listo` (reemplaza a `ready-for-agent`: la spec no se implementa), y el milestone de la etapa.

## Tickets (`to-tickets`)
El cuerpo usa las secciones de `.github/ISSUE_TEMPLATE/tarea.yml` en lugar de la plantilla de la habilidad:

```
Parte de #<spec>

## Objetivo
## Especificación
## Criterios de aceptación
Depende de: #N, #M
## Fuera de alcance
```

- **Especificación**: módulos, firmas, reglas y ADR que aplican. Nombrá archivos existentes cuando ayuden a Codex; Codex no decide lo que el ticket calla.
- **Bloqueos**: la línea exacta `Depende de: #N, #M` (vacía si no hay), no las dependencias nativas de GitHub. Un ticket está libre cuando todos sus bloqueos están cerrados.
- **Etiquetas**: `estado:listo`, `ejecutor:codex`, un `modulo:*` y un `tipo:*`, más el milestone de la etapa.
