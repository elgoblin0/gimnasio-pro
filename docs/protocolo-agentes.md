# Protocolo de agentes

## Método vigente

Por decisión del dueño del 27/10/2026, el trabajo se coordina desde un chat de la app de Codex. Este procedimiento reemplaza las instrucciones operativas anteriores sobre el despachador y las sesiones de Claude, incluidas las del ADR 0011. Los ADR de arquitectura y los frenos de seguridad conservan su vigencia.

El despachador se eliminó del repo el 27/10/2026; su último estado queda en el historial de git (commit `1aade43`).

## Roles

- **Opus** (sesión corta de Claude Code) decide y especifica; no implementa:
  - planifica cada etapa y crea sus issues con la plantilla `tarea.yml`, `estado:listo` y `ejecutor:codex`, con criterios de aceptación, archivos, pruebas y ADR aplicables, para que Codex no tenga que decidir;
  - decide diseño, dirección visual, modelo de datos, reglas, frenos, términos del glosario y ADR;
  - resuelve los `necesita-criterio`: decide, registra un ADR provisional si hace falta y deja el issue `estado:listo`;
  - revisa el diff de los PR que tocan rutas sensibles.
- **Codex** (app de escritorio) implementa todos los issues, `tipo:patron` incluido, y revisa todos los PR.
- **El dueño** elige cuándo abrir cada sesión, autoriza las fusiones y revisa los ADR provisionales al cierre de cada etapa.

## Planificar una etapa (Opus)

Una sola sesión de Claude Code por etapa, porque `to-spec` sintetiza la conversación sin volver a preguntar. El dueño lanza las habilidades en este orden:

1. `/mattpocock-skills:grill-with-docs`: entrevista sobre la etapa; deja los términos en `GLOSSARY.md` y las decisiones en `docs/adr/`.
2. `/mattpocock-skills:to-spec`: publica la spec de la etapa como issue.
3. `/mattpocock-skills:to-tickets`: la parte en tickets `estado:listo` + `ejecutor:codex`, con `Depende de: #N`.

Cómo usan GitHub y las etiquetas: `docs/agents/`.

Al cerrar la sesión, Opus entrega un prompt por ticket, en orden de dependencias, cada uno en su bloque para copiar:

```
Implementá el issue #N de elgoblin0/gimnasio-pro. Leelo con `gh issue view N --comments`.
Seguí AGENTS.md y docs/protocolo-agentes.md. Corré ruff y pytest,
abrí el PR con la plantilla y pedí la revisión a un subagente de Codex.
<solo si hace falta: una o dos líneas con la trampa o la decisión que el issue no alcanza a decir>
```

El dueño pega cada prompt en un chat nuevo de la app de Codex cuando el ticket anterior está fusionado.

## Ejecución

1. Revisá el estado local y GitHub antes de tocar archivos. Conservá cambios ajenos y reutilizá ramas y worktrees de los PR abiertos.
2. Leé el issue, sus comentarios, dependencias y los documentos que necesita. Trabajá un issue a la vez; empezá el siguiente cuando el anterior esté fusionado. Al retomar varios PR existentes, terminá uno antes de continuar con los demás.
3. Implementá o corregí en una rama de trabajo; integrá `origin/main` y resolvé conflictos preservando el alcance del issue.
4. Ejecutá las verificaciones pertinentes y abrí o actualizá el PR con la plantilla completa. Si cambia una capacidad, editá su archivo en `docs/capacidades/` y regenerá el mapa.
5. Pedí una revisión independiente a un subagente de Codex desde el mismo chat. Este protocolo autoriza esa delegación de revisión. Revisá el diff, el issue y el CI; corregí los hallazgos y repetí la revisión cuando corresponda.
6. Con revisión aprobada y todos los checks requeridos de GitHub en verde, fusioná con squash y cerrá el issue. Actualizá el checkout principal y continuá con el siguiente issue cuyas dependencias estén cerradas.

Las pruebas de MySQL saltadas en local no sustituyen el CI de GitHub. Se mantienen la protección de main y los checks calidad, pruebas, e2e y secretos. Las fusiones requieren autorización del dueño; su autorización para completar una etapa cubre los PR de esa etapa.

## Revisión y rutas sensibles

Otro agente de Codex revisa todos los PR. Los que tocan reglas, migraciones, permisos, salud o `comun/migrar.py` necesitan además la revisión de Opus: con `revisado:codex` puesto, quedan en `estado:revision` hasta que una sesión de Opus lea su diff y agregue `revisado:opus`.

Usá `revisado:codex` después de aprobar el estado actual. Una corrección invalida las aprobaciones afectadas y exige revisar de nuevo.

## Etiquetas y dependencias

- `estado:listo`: issue especificado y disponible.
- `estado:en-curso` y `agente:codex`: trabajo activo.
- `estado:revision`: PR abierto pendiente de CI o revisión.
- `correccion-pendiente`: corrección requerida por CI o revisión.
- `ejecutor:codex`: todo issue de implementación. `ejecutor:opus` queda para issues de planificación o de decisión, que no producen código.
- `modulo:*` y `tipo:*`: clasificación del trabajo; en un `tipo:patron`, Opus especifica el patrón en el issue y Codex lo implementa.
- `bloqueado`: impedimento externo documentado.
- `necesita-criterio`: decisión de diseño, producto, alcance o término que resuelve Opus.

Respetá `Depende de: #N, #M` en cada issue. Al fusionar, retirás las etiquetas de trabajo activo y cerrás el issue; conservás las de clasificación.

## Bloqueos y continuidad

Resolvé los problemas técnicos dentro del alcance autorizado, incluidos conflictos y fallos de CI. Documentá lo probado cuando exista un impedimento externo. Las decisiones de diseño, producto, alcance, términos y ADR son de Opus; señalalas con `necesita-criterio` y una recomendación concreta. Continuá con trabajo independiente cuando sea posible.

Si se agota el cupo, guardá los cambios y un resumen para retomar. No registres el límite como fallo de implementación ni prometas ejecución durante la inactividad del chat. Al terminar, informá PR fusionados, checks y pendientes.
