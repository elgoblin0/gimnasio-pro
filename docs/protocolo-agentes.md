# Protocolo de agentes

Desde el 28/10/2026, por decisión del dueño, el trabajo corre en una cadena automática: GitHub hace de buzón y nadie copia salidas entre agentes. Reemplaza al chat de la app de Codex (27/10) y al despachador (eliminado el 27/10, último estado en el commit `1aade43`), incluidas las instrucciones operativas del ADR 0011. Los ADR de arquitectura y los frenos de seguridad conservan su vigencia.

Este documento describe la orquestación. Para implementar un issue, Codex solo necesita `AGENTS.md`.

## Cadena automática

Corre en GitHub Actions y todo queda a la vista en los comentarios de cada PR y en la pestaña Actions.

| Evento | Quién reacciona | Qué hace |
|---|---|---|
| Issue cerrado, `estado:listo` puesto o arranque manual | `cadena.yml` → `arrancar` | Reanuda los PR cuya duda resolvió Opus y pide resolver los conflictos con main. Si hay menos de dos issues en curso, toma el issue `estado:listo` + `ejecutor:codex` de número más bajo con dependencias cerradas que no comparta un `modulo:` con el que está en curso, crea `codex/issue-N` con un commit vacío `[skip ci]`, abre un PR borrador y comenta el pedido de implementar. |
| CI terminado en `codex/issue-N` | `cadena.yml` → `tras-ci` | Rojo: pide la corrección. Verde: marca el PR listo y comenta `@codex review`. |
| Respuesta de Codex en el PR | `cadena.yml` → `revision` | `NECESITA-CRITERIO:` → la copia al issue y pone `necesita-criterio`. Revisión sin hallazgos → `revisado:codex`. Con hallazgos → `correccion-pendiente` y pide la corrección. |
| `necesita-criterio` en un issue | `opus.yml` → `criterio` | Opus decide, comenta, abre un ADR provisional si hace falta y deja el issue `estado:listo`; la cadena reanuda el PR. |
| CI verde en un PR `opus/adr-*` | `cadena.yml` → `fusionar-adr` | Si el PR toca solo `docs/adr/` y `GLOSSARY.md`, activa la fusión automática con squash (el dueño revisa los ADR provisionales al cierre de la etapa). |
| `revisado:codex` en un PR sensible | `opus.yml` → `revisar` | Opus lee el diff: `revisado:opus` o hallazgos con `correccion-pendiente`. |
| `revisado:codex` (y `revisado:opus` si es sensible) | `cadena.yml` → `etiqueta` | Si está `revisado:opus`, descarta los pedidos de cambios de `claude[bot]` anteriores a esa etiqueta. Activa la fusión automática con squash, con el cuerpo del PR como mensaje; el ruleset de main espera calidad, pruebas, e2e y secretos. |
| `bloqueado` en un PR | `cadena.yml` → `etiqueta` | Avisa al dueño en el celular (ver Avisos). |
| Último issue `ejecutor:codex` de un milestone cerrado | `cadena.yml` → `cierre` | Publica el informe de la etapa (`scripts/informe_cadena.py`) en el issue «Cierre de etapa …» del milestone y avisa al dueño que toca revisar los ADR provisionales. |
| Cada 15 minutos | `cadena.yml` → `vigilar` | Si un pedido lleva 15 minutos sin que el implementador lo tome (y no está ocupado con otro PR), o lo tomó y no terminó en 75, lo comenta en el PR y avisa al dueño. También si un PR con `correccion-pendiente` tiene su último pedido cerrado sin un commit posterior y sin una duda abierta en el issue: sin commit no hay CI ni revisión nueva, y nadie la vuelve a pedir. Una vez por pedido. |

Frenos:
- Hasta dos issues en curso, y el segundo solo si no comparte `modulo:` con el primero (un issue sin `modulo:` va solo). La variable del repo `CADENA_EN_CURSO=1` vuelve a uno por vez.
- Topes de corrección por PR, separados por origen: 3 por CI en rojo, 3 por la revisión de Codex, 3 por conflictos con main y 2 por la revisión de Opus. Agotado uno, el PR queda `bloqueado` para el dueño.
- Opus con tope de turnos por corrida; los trabajos que leen comentarios solo reaccionan a la cuenta de Codex.

Requisitos (una vez, los hace el dueño): secretos `CADENA_TOKEN` (token personal *fine-grained* con Contents, Issues y Pull requests en escritura sobre este repo) y `CLAUDE_CODE_OAUTH_TOKEN` (`claude setup-token`); el repo conectado a Codex cloud (responde `@codex review`); «Allow auto-merge» activado en el repo.

Para arrancar una etapa: Actions → Cadena → Run workflow. Para frenarla: deshabilitá el workflow Cadena.

### Avisos

Los comentarios de la cadena salen con el token del dueño, y GitHub no le notifica lo que «él mismo» escribe. Por eso la cadena avisa aparte, por [ntfy](https://ntfy.sh): el dueño instala la app, se suscribe a un tema con nombre difícil de adivinar y guarda su URL (`https://ntfy.sh/<tema>`) en el secreto `NOTIFICAR_URL`. Avisa cuando un PR queda `bloqueado` y cuando `vigilar` detecta un pedido demorado o una corrección parada; tocar el aviso abre el PR. Sin el secreto, los avisos solo quedan en el registro de Actions y, los de demora, en el PR. El repo es público: los avisos llevan número de PR y motivo, nada privado.

La cadena fusiona con el cuerpo del PR como mensaje, para que el `[skip ci]` del commit vacío de inicio no llegue a main. Para cubrir también las fusiones manuales, el squash del repo debe usar el título y el cuerpo del PR (Settings → General → Pull Requests → «Default to pull request title and description», o `squash_merge_commit_message: PR_BODY`). Mientras use «mensajes de los commits», al fusionar a mano hay que borrar la línea `Inicia codex/issue-N [skip ci]`: si llega a main, salta su CI.

### Informe de la etapa

`python scripts/informe_cadena.py "<milestone>"` resume los PR fusionados de la etapa: minutos de punta a punta, minutos y tokens de Codex (de la marca `<!-- implementador:codex … -->` del comentario «hecho»), correcciones por origen, dudas de criterio, avisos de demora, bloqueos y los hallazgos de las revisiones de Codex. Los hallazgos que se repiten en varios PR son candidatos a un control del CI. La cadena lo publica sola al cerrar la etapa; leerlo reemplaza revisar los PR uno por uno desde Claude.

### Implementador local (mientras Codex cloud no responda)

Codex cloud responde `@codex review` pero rechaza los demás pedidos desde GitHub con «create an environment for this repo», aunque el entorno exista ([openai/codex#20093](https://github.com/openai/codex/issues/20093)). Hasta que OpenAI lo arregle, `scripts/implementador.py` hace ese paso en la PC del dueño: toma el último pedido de implementar o corregir (marca `<!-- cadena:pedido -->` o `<!-- cadena:corregir -->`) sin atender que dejó la cadena en un PR `codex/issue-N`, corre `codex exec` en un worktree (`.implementador/`, fuera de git), sube el resultado y comenta con la marca `<!-- implementador:hecho -->`. Una duda `NECESITA-CRITERIO:` va al issue como en la cadena. Terminar sin cambios en la rama y sin esa línea cuenta como fallo del pedido, aunque Codex haya escrito el cuerpo del PR, que entonces no se publica: sin commit la cadena no puede avanzar. Por eso un pedido que solo corrige el cuerpo también termina `bloqueado` y lo resuelve el dueño. La excepción es un pedido de implementar sobre una rama que ya trae el trabajo (por ejemplo, al seguir tras una duda): sube un commit vacío para que corran el CI y la revisión. Tras un fallo, el PR espera 10 minutos antes de reintentar y mientras tanto se atienden los demás; tres fallos seguidos en un pedido lo dejan `bloqueado`. Todo lo demás (CI, revisión, Opus, fusión) sigue igual. La cadena no menciona a `@codex` en esos pedidos; `@codex review` sí se mantiene. Cuando OpenAI lo arregle, con la variable `CADENA_MENCIONAR_CODEX=1` en `cadena.yml` los pedidos vuelven a mencionarlo.

```bash
python scripts/implementador.py            # atiende lo pendiente y termina
python scripts/implementador.py --esperar  # repite cada 60 segundos
python scripts/implementador.py --pr 150   # atiende solo ese PR
python scripts/implementador.py --simular  # dice qué haría, sin tocar nada
python scripts/implementador.py --estado   # en qué paso está cada PR de Codex y qué espera
```

En Windows alcanza con hacer doble clic en `lanzar-implementador.cmd` (corre `--esperar`).

Necesita `gh` autenticado y `codex.exe` (lo busca en `GIMNASIO_CODEX_BIN`, el PATH y `%LOCALAPPDATA%\OpenAI\Codex\bin`). Atiende un pedido por vez, aunque haya dos PR en curso: `.implementador/bloqueo.pid` impide una segunda instancia.

Qué hace además de llamar a Codex:
- Muestra cada paso con hora y la salida de Codex en vivo, y lo guarda en `.implementador/registro.log`. Avisa con pitido y globo de Windows al terminar, fallar, quedar `bloqueado` o quedarse sin cupo.
- Pone 👀 en el pedido que toma, para que `vigilar` distinga un pedido sin tomar de uno en curso.
- Corre a Codex con esfuerzo bajo y sube un nivel (medio, después alto) por cada fallo del pedido y por cada corrección anterior del mismo origen: lo fácil gasta poco cupo y lo que se repite recibe más razonamiento. `GIMNASIO_CODEX_ESFUERZO` cambia el punto de partida.
- Corta a Codex si pasa 60 minutos o 20 sin escribir nada (cuenta como fallo del pedido).
- Antes de subir verifica fuera del sandbox de Codex: `ruff format` de lo tocado, `ruff check` y las pruebas del módulo cambiado, y sube `VERSION` en `gimnasio/static/sw.js` si Codex tocó recursos de la PWA sin hacerlo (el CI también lo exige, con `scripts/verificar_cache_pwa.py`; `scripts/verificar_pr.py` exige además subir `VERSION_REGLAS`, la autorización de Opus para alterar hechos y la ficha de una prueba e2e nueva). También avisa si dos archivos `test_*.py` de `pruebas/` comparten nombre (pytest no los recolecta juntos). Si algo falla, pide una corrección antes de subir, y después sube igual: el CI sigue siendo la puerta. La suite completa y los e2e no se corren aquí, son del CI. El resultado va en el comentario «hecho». Con pruebas saltadas por falta de `GIMNASIO_BD_*` lo avisa.
- Resuelve sin agente los conflictos con main que son solo de `VERSION` en `gimnasio/static/sw.js` (la mayor + 1) y de `docs/MAPA-CAPACIDADES.md` (lo regenera). Si con eso no queda ninguno y el pedido era por conflictos, sube la fusión y cierra el pedido sin gastar cupo.
- Cuando no hay trabajo, borra de `.implementador/` las carpetas de los PR ya cerrados y corre `git worktree prune`. Las que el sandbox de Codex deja trabadas las avisa una vez para borrarlas a mano.
- Al terminar imprime un resumen: PR atendidos, fallos, minutos y tokens de Codex y PR fusionados desde que arrancó.

Para que el sandbox de Codex pueda correr `pytest` con el `.venv`, el grupo `CodexSandboxUsers` necesita lectura sobre el Python base del `.venv` (ver `docs/entorno-local.md`).

## Roles

- **Opus** (sesión corta de Claude Code, o `opus.yml` en la cadena) decide y especifica; no implementa:
  - planifica cada etapa y crea sus issues con la plantilla `tarea.yml`, `estado:listo`, `ejecutor:codex` y su `modulo:`, con criterios de aceptación, archivos, pruebas y ADR aplicables, para que Codex no tenga que decidir;
  - decide diseño, dirección visual, modelo de datos, reglas, frenos, términos del glosario y ADR;
  - resuelve los `necesita-criterio`: decide, registra un ADR provisional si hace falta y deja el issue `estado:listo`;
  - revisa el diff de los PR que tocan rutas sensibles.
- **Codex** implementa todos los issues, `tipo:patron` incluido, cuando la cadena se lo pide (hoy por el implementador local), y revisa todos los PR (`@codex review`).
- **El dueño** arranca o frena la cadena, atiende los `bloqueado` y revisa los ADR provisionales al cierre de cada etapa. Su decisión del 28/10/2026 autoriza la fusión automática de los PR de la cadena.

## Planificar una etapa (Opus)

Una sola sesión de Claude Code por etapa con la habilidad `planificar-etapa` (`.claude/skills/`, adaptadas de las de Matt Pocock): `interrogar` → `escribir-especificacion` → `dividir-en-tickets`. Termina con la especificación y los tickets publicados. La cadena los toma sola en orden de dependencias; si no hay ninguno en curso, el dueño la arranca desde Actions.

## Qué hace Codex con un pedido

Implementa o corrige solo lo que pide el issue, siguiendo `AGENTS.md`, y deja el cuerpo del PR con la plantilla completa. No hace commit, push, revisiones ni fusiones: los hace la cadena. Si le falta una decisión de diseño, producto, alcance o término, no implementa y responde con una línea que empiece exactamente con `NECESITA-CRITERIO:` y su recomendación; dicha de otro modo, la duda no se reconoce.

Las pruebas de MySQL saltadas en local no sustituyen el CI de GitHub. Se mantienen la protección de main y los checks calidad, pruebas, e2e y secretos.

## Revisión y rutas sensibles

Codex revisa todos los PR. Los que tocan reglas, migraciones, permisos, salud o `comun/migrar.py` necesitan además la revisión de Opus: con `revisado:codex` puesto, `opus.yml` lee su diff y pone `revisado:opus` o deja hallazgos. Opus aprueba con la etiqueta, sin revisión formal, y un pedido de cambios vigente frena la fusión aunque el ruleset no exija aprobaciones: por eso la cadena descarta los suyos anteriores a la etiqueta, con un mensaje que cita la aprobación. Los posteriores y los de otras cuentas siguen frenando. Si pidió correcciones, deja en el PR la marca `<!-- opus:revisado <sha> -->`, y en la vuelta siguiente lee solo lo que cambió desde ese commit en los archivos del PR, no el diff entero.

Un commit nuevo invalida las aprobaciones: la cadena quita `revisado:codex` y `revisado:opus` y pide revisar de nuevo.

## Etiquetas y dependencias

- `estado:listo`: issue especificado y disponible.
- `estado:en-curso` y `agente:codex`: trabajo activo.
- `estado:revision`: PR abierto pendiente de CI o revisión.
- `correccion-pendiente`: corrección requerida por CI o revisión.
- `ejecutor:codex`: todo issue de implementación. `ejecutor:opus` queda para issues de planificación o de decisión, que no producen código.
- `modulo:*` y `tipo:*`: clasificación del trabajo; la cadena usa `modulo:*` para decidir qué issues pueden ir en paralelo. En un `tipo:patron`, Opus especifica el patrón en el issue y Codex lo implementa.
- `bloqueado`: impedimento que necesita al dueño.
- `necesita-criterio`: decisión de diseño, producto, alcance o término que resuelve Opus.

Respetá `Depende de: #N, #M` en cada issue. Al cerrarse un issue, la cadena le quita las etiquetas de estado; las de clasificación quedan.

## Bloqueos y continuidad

Las decisiones de diseño, producto, alcance, términos y ADR son de Opus; se señalan con `necesita-criterio` y una recomendación concreta. Un PR `bloqueado` espera al dueño: el implementador no lo atiende y la cadena no lo fusiona hasta que se quite la etiqueta.

Si Codex se queda sin cupo, el implementador no lo cuenta como fallo y sigue con un respaldo: un modelo de Claude (Sonnet por defecto) corriendo `claude -p` en el mismo worktree, con el mismo prompt, la misma verificación previa a subir y el mismo comentario «hecho» (con la marca `<!-- implementador:sonnet minutos=… tokens=… -->` y «Implementado en esta PC con Sonnet»). Codex se reintenta cada 15 minutos y, cuando responde de nuevo, vuelve a implementar él; un PR puede mezclar commits de los dos. El respaldo edita y corre `python`, `pytest`, `ruff`, `node` y `git` de solo lectura con el `.venv` del proyecto; no tiene `git push`, `gh`, red ni `curl`. Claude Code le niega la ruta completa al `.venv`, `Invoke-Expression`, `$env:` y `cd`, así que su prompt le indica las formas permitidas. Gasta el cupo de Claude del dueño. `GIMNASIO_RESPALDO` cambia el modelo (`opus`, `haiku`…) o lo apaga con `ninguno` (entonces espera a que Codex se renueve, como antes); `GIMNASIO_CLAUDE_BIN` fija la ruta de `claude.exe`. Si el respaldo también se queda sin cupo, el implementador espera. `scripts/informe_cadena.py` todavía no suma los minutos ni los tokens del respaldo.
