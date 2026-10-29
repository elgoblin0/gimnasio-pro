# Protocolo de agentes

## Método vigente

Por decisión del dueño del 27/10/2026, el trabajo se coordina desde un chat de la app de Codex. Este procedimiento reemplaza las instrucciones operativas anteriores sobre el despachador y las sesiones de Claude, incluidas las del ADR 0011. Los ADR de arquitectura y los frenos de seguridad conservan su vigencia.

El despachador se eliminó del repo el 27/10/2026; su último estado queda en el historial de git (commit `1aade43`).

## Cadena automática

Desde el 28/10/2026, por decisión del dueño, GitHub hace de buzón y nadie copia salidas entre agentes. Corre en GitHub Actions y todo queda a la vista en los comentarios de cada PR y en la pestaña Actions.

| Evento | Quién reacciona | Qué hace |
|---|---|---|
| Issue cerrado, `estado:listo` puesto o arranque manual | `cadena.yml` → `arrancar` | Si no hay otro en curso, toma el issue `estado:listo` + `ejecutor:codex` de número más bajo con dependencias cerradas, crea `codex/issue-N`, abre un PR borrador y comenta `@codex implementá…` con el issue. |
| CI terminado en `codex/issue-N` | `cadena.yml` → `tras-ci` | Rojo: pide a Codex que lo arregle. Verde: marca el PR listo y comenta `@codex review`. |
| Respuesta de Codex en el PR | `cadena.yml` → `revision` | `NECESITA-CRITERIO:` → la copia al issue y pone `necesita-criterio`. Revisión sin hallazgos → `revisado:codex`. Con hallazgos → `correccion-pendiente` y pide la corrección. |
| `necesita-criterio` en un issue | `opus.yml` → `criterio` | Opus decide, comenta, abre un ADR provisional si hace falta y deja el issue `estado:listo`; la cadena reanuda el PR. |
| CI verde en un PR `opus/adr-*` | `cadena.yml` → `fusionar-adr` | Si el PR toca solo `docs/adr/` y `GLOSSARY.md`, activa la fusión automática con squash (el ADR provisional de Opus; el dueño los revisa al cierre de la etapa). |
| `revisado:codex` en un PR sensible | `opus.yml` → `revisar` | Opus lee el diff: `revisado:opus` o hallazgos con `correccion-pendiente`. |
| `revisado:codex` (y `revisado:opus` si es sensible) | `cadena.yml` → `etiqueta` | Activa la fusión automática con squash; el ruleset de main espera calidad, pruebas, e2e y secretos. |

Frenos: un issue a la vez; como mucho tres pedidos de corrección por PR, después `bloqueado` para el dueño; Opus con tope de turnos por corrida; los trabajos que leen comentarios solo reaccionan a la cuenta de Codex.

Requisitos (una vez, los hace el dueño): secretos `CADENA_TOKEN` (token personal *fine-grained* con Contents, Issues y Pull requests en escritura sobre este repo) y `CLAUDE_CODE_OAUTH_TOKEN` (`claude setup-token`); el repo conectado a Codex cloud con un entorno que corra ruff y pytest; «Allow auto-merge» activado en el repo.

### Implementador local (mientras Codex cloud no responda)

Codex cloud responde `@codex review` pero rechaza los demás pedidos desde GitHub con «create an environment for this repo», aunque el entorno exista ([openai/codex#20093](https://github.com/openai/codex/issues/20093)). Hasta que OpenAI lo arregle, `scripts/implementador.py` hace ese paso en la PC del dueño: toma el último `@codex implementá…` o `@codex corregí…` sin atender que dejó la cadena en un PR `codex/issue-N`, corre `codex exec` en un worktree (`.implementador/`, fuera de git), sube el resultado y comenta con la marca `<!-- implementador:hecho -->`. Una duda `NECESITA-CRITERIO:` va al issue como en la cadena. Dos fallos seguidos en un pedido dejan el PR `bloqueado`. Todo lo demás (CI, revisión, Opus, fusión) sigue igual.

```bash
python scripts/implementador.py            # atiende lo pendiente y termina
python scripts/implementador.py --esperar  # repite cada 60 segundos
python scripts/implementador.py --pr 150   # atiende solo ese PR
python scripts/implementador.py --simular  # dice qué haría, sin tocar nada
python scripts/implementador.py --estado   # en qué paso está cada PR de Codex y qué espera
```

En Windows alcanza con hacer doble clic en `lanzar-implementador.cmd` (corre `--esperar`).

Necesita `gh` autenticado y `codex.exe` (lo busca en `GIMNASIO_CODEX_BIN`, el PATH y `%LOCALAPPDATA%\OpenAI\Codex\bin`). Un issue a la vez, como la cadena: `.implementador/bloqueo.pid` impide una segunda instancia.

Qué hace además de llamar a Codex:
- Muestra cada paso con hora y la salida de Codex en vivo, y lo guarda en `.implementador/registro.log`. Avisa con pitido y globo de Windows al terminar, fallar, quedar `bloqueado` o quedarse sin cupo.
- Corta a Codex si pasa 60 minutos o 20 sin escribir nada (cuenta como fallo del pedido).
- Antes de subir verifica fuera del sandbox de Codex: `ruff format` de lo tocado, `ruff check` y las pruebas del módulo cambiado, y sube `VERSION` en `gimnasio/static/sw.js` si Codex tocó recursos de la PWA sin hacerlo. El resultado va en el comentario «hecho»; no frena la subida, el CI sigue siendo la puerta. Con pruebas saltadas por falta de `GIMNASIO_BD_*` lo avisa.
- Al terminar imprime un resumen: PR atendidos, fallos, minutos y tokens de Codex y PR fusionados desde que arrancó.

Para que el sandbox de Codex pueda correr `pytest` con el `.venv`, el grupo `CodexSandboxUsers` necesita lectura sobre el Python base del `.venv` (ver `docs/entorno-local.md`).

Para arrancar una etapa: Actions → Cadena → Run workflow. Para frenarla: deshabilitá el workflow Cadena.

## Roles

- **Opus** (sesión corta de Claude Code) decide y especifica; no implementa:
  - planifica cada etapa y crea sus issues con la plantilla `tarea.yml`, `estado:listo` y `ejecutor:codex`, con criterios de aceptación, archivos, pruebas y ADR aplicables, para que Codex no tenga que decidir;
  - decide diseño, dirección visual, modelo de datos, reglas, frenos, términos del glosario y ADR;
  - resuelve los `necesita-criterio`: decide, registra un ADR provisional si hace falta y deja el issue `estado:listo`;
  - revisa el diff de los PR que tocan rutas sensibles.
- **Codex** (Codex cloud, disparado por la cadena; o la app de escritorio a mano) implementa todos los issues, `tipo:patron` incluido, y revisa todos los PR.
- **El dueño** arranca o frena la cadena, atiende los `bloqueado` y revisa los ADR provisionales al cierre de cada etapa. Su decisión del 28/10/2026 autoriza la fusión automática de los PR de la cadena.

## Planificar una etapa (Opus)

Una sola sesión de Claude Code por etapa con la habilidad `planificar-etapa` (`.claude/skills/`, adaptadas de las de Matt Pocock): `interrogar` → `escribir-especificacion` → `dividir-en-tickets`. Termina con la especificación y los tickets publicados y un prompt por ticket. El dueño pega cada prompt en un chat nuevo de la app de Codex cuando el ticket anterior está fusionado.

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
