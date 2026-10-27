# Issues: GitHub

Los issues y las specs viven en GitHub Issues de `elgoblin0/gimnasio-pro`. Todo se hace con `gh`.

- **Crear**: `gh issue create --title "..." --body-file -` con un heredoc. Los tickets siguen las secciones de `.github/ISSUE_TEMPLATE/tarea.yml`: Objetivo, Especificación, Criterios de aceptación, Dependencias, Fuera de alcance.
- **Leer**: `gh issue view <n> --json number,title,body,labels,comments`.
- **Listar**: `gh issue list --state open --label estado:listo --json number,title,labels`.
- **Comentar, etiquetar, cerrar**: `gh issue comment`, `gh issue edit --add-label/--remove-label`, `gh issue close`.

## Spec y tickets
- La spec de `to-spec` es un issue con `tipo:docs` y `ejecutor:opus`, sin `estado:listo`: no se implementa.
- Cada ticket de `to-tickets` lleva en la primera línea `Parte de #<spec>`, y las etiquetas `estado:listo`, `ejecutor:codex`, un `modulo:*` y un `tipo:*`, más el milestone de la etapa.
- **Bloqueos**: en el cuerpo, la línea exacta `Depende de: #N, #M`. No se usan las dependencias nativas de GitHub. Un ticket está libre cuando todos sus bloqueos están cerrados.

## Cuando una habilidad dice "publicar en el tracker"
Crear un issue de GitHub como arriba.
