# Protocolo de agentes

## Método vigente

Por decisión del dueño del 27/10/2026, el trabajo se coordina desde un chat de la app de Codex. Este procedimiento reemplaza las instrucciones operativas anteriores sobre el despachador y las sesiones de Claude, incluidas las del ADR 0011. Los ADR de arquitectura y los frenos de seguridad conservan su vigencia.

El despachador se eliminó del repo el 27/10/2026; su último estado queda en el historial de git (commit `1aade43`).

## Ejecución

1. Revisá el estado local y GitHub antes de tocar archivos. Conservá cambios ajenos y reutilizá ramas y worktrees de los PR abiertos.
2. Leé el issue, sus comentarios, dependencias y los documentos que necesita. Trabajá un issue a la vez; empezá el siguiente cuando el anterior esté fusionado. Al retomar varios PR existentes, terminá uno antes de continuar con los demás.
3. Implementá o corregí en una rama de trabajo; integrá `origin/main` y resolvé conflictos preservando el alcance del issue.
4. Ejecutá las verificaciones pertinentes y abrí o actualizá el PR con la plantilla completa. Si cambia una capacidad, editá su archivo en `docs/capacidades/` y regenerá el mapa.
5. Pedí una revisión independiente a un subagente de Codex desde el mismo chat. Este protocolo autoriza esa delegación de revisión. Revisá el diff, el issue y el CI; corregí los hallazgos y repetí la revisión cuando corresponda.
6. Con revisión aprobada y todos los checks requeridos de GitHub en verde, fusioná con squash y cerrá el issue. Actualizá el checkout principal y continuá con el siguiente issue cuyas dependencias estén cerradas.

Las pruebas de MySQL saltadas en local no sustituyen el CI de GitHub. Se mantienen la protección de main y los checks calidad, pruebas, e2e y secretos. Las fusiones requieren autorización del dueño; su autorización para completar una etapa cubre los PR de esa etapa.

## Revisión y rutas sensibles

Codex implementa y otro agente de Codex revisa todos los PR, también los que tocan reglas, migraciones, permisos, salud o `comun/migrar.py`. No se requiere saldo ni intervención de Opus.

Usá `revisado:codex` después de aprobar el estado actual. La etiqueta histórica `revisado:opus` solo se agrega si una integración existente la exige: acompañala de un comentario que cite la decisión del dueño y aclare que no hubo revisión real de Opus. Una corrección invalida las aprobaciones afectadas y exige revisar de nuevo.

## Etiquetas y dependencias

- `estado:listo`: issue especificado y disponible.
- `estado:en-curso` y `agente:codex`: trabajo activo.
- `estado:revision`: PR abierto pendiente de CI o revisión.
- `correccion-pendiente`: corrección requerida por CI o revisión.
- `ejecutor:codex`: ejecución por Codex; las etiquetas históricas de Opus no obligan a usar Claude.
- `modulo:*` y `tipo:*`: clasificación del trabajo; `tipo:patron` también puede hacerlo Codex dentro de lo especificado.
- `bloqueado`: impedimento externo documentado.
- `necesita-criterio`: decisión de producto, alcance o término que debe resolver el dueño.

Respetá `Depende de: #N, #M` en cada issue. Al fusionar, retirás las etiquetas de trabajo activo y cerrás el issue; conservás las de clasificación.

## Bloqueos y continuidad

Resolvé los problemas técnicos dentro del alcance autorizado, incluidos conflictos y fallos de CI. Documentá lo probado cuando exista un impedimento externo. Las decisiones de producto, alcance, términos y ADR siguen a cargo del dueño; señalalas con `necesita-criterio` y una recomendación concreta. Continuá con trabajo independiente cuando sea posible.

Si se agota el cupo, guardá los cambios y un resumen para retomar. No registres el límite como fallo de implementación ni prometas ejecución durante la inactividad del chat. Al terminar, informá PR fusionados, checks y pendientes.
