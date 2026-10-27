# Protocolo de agentes

Cómo se reparte, se revisa y se paga el trabajo entre Opus y Codex. Lo lee quien planifica o escribe issues; el despachador (`scripts/despachador.py`) aplica casi todo solo. Para implementar un issue alcanza con `AGENTS.md`.

## Etiquetas
| Etiqueta | Significado |
|---|---|
| `estado:listo` | Especificado; el despachador lo puede tomar |
| `estado:en-curso` | Un agente lo tiene (ver `agente:*`) |
| `estado:revision` | PR abierto, esperando revisión o CI |
| `ejecutor:opus` / `ejecutor:codex` | Quién debe hacerlo |
| `agente:opus`, `agente:codex` | Quién lo tiene ahora (candado) |
| `correccion-pendiente` | El CI o la revisión pidió cambios; vuelve a su ejecutor |
| `revisado:codex`, `revisado:opus` (en PR) | Revisión cruzada aprobada |
| `modulo:*` | Módulo principal; un solo issue activo por módulo |
| `tipo:patron` | Primera instancia de un patrón: siempre Opus |
| `tipo:funcion`, `tipo:error`, `tipo:mantenimiento`, `tipo:docs`, `tipo:prototipo`, `tipo:cierre` | Clase de trabajo |
| `necesita-criterio` | Ambigüedad de producto; Codex se detiene y Opus decide |
| `bloqueado` | Depende de algo externo (cuentas, el usuario); ver comentario |

Dependencias: el cuerpo del issue lista `Depende de: #N, #M`. El despachador no toma un issue con dependencias abiertas.

## Opus o Codex
Va a **Opus** si cumple al menos una:
- planificación, ADR o cambio de alcance;
- modelo de datos nuevo o migración que cambia tablas de hechos;
- motor de reglas, frenos, concurrencia, sincronización, permisos o salud;
- `tipo:patron`: primera instancia de un patrón de arquitectura o de dominio;
- dirección visual o primera escena de un tipo nuevo;
- un issue `necesita-criterio`, o bloqueado que Codex ya intentó.

Va a **Codex** todo lo demás, en especial:
- repetir un patrón existente;
- CRUD, pantallas, pruebas, datos de semilla, estilos con tokens;
- documentación derivada y correcciones de CI.

Con el presupuesto de Opus agotado (ADR 0011), los issues dudosos van a Codex con más detalle.

## Revisión cruzada
- PR de Codex sin rutas sensibles: lo revisa otra corrida de Codex.
- PR de Opus, o con rutas sensibles: Codex revisa siempre; Opus revisa además lo sensible.
- La revisión lee el diff y el resumen del CI (`resumen-ci.md`), no el repo entero. Desde la segunda ronda recibe sus hallazgos anteriores y solo el diff nuevo.
- Se fusiona con squash cuando el CI está verde y la revisión aprueba. Nunca se empuja a `main`.

## Bloqueos
Codex: un intento y un reintento. Si sigue trabado, el despachador etiqueta `bloqueado` y `ejecutor:opus` con lo que probó. Opus intenta una vez; si no sale, el issue pasa al milestone de la etapa siguiente con su explicación.

## Sesiones de Claude
La cuota de Claude es lo escaso: cada turno de una sesión vuelve a leer todo su contexto, así que una sesión larga cuesta más por turno que una corta.
- **Planificar** es una sesión interactiva que termina cuando los issues están creados con `estado:listo`.
- **Implementar, corregir y revisar** lo hace el despachador: `claude -p` limpio por issue, uno a la vez, hasta tres Codex en paralelo. Corre en una terminal aparte con `--hasta-vaciar`; `--solo-codex` solo mientras haya una sesión de Claude abierta a mano.
- **Volver a Claude** cuando un issue queda `bloqueado` o `necesita-criterio`: la sesión nueva lee ese issue, su PR y `--informe`, no los logs del despachador.
- Sin capturas ni videos de rutina: la verificación visual la hace el usuario en el cierre.
- Lo determinista va a scripts y al CI (mapa de capacidades, resúmenes, etiquetas).
- Presupuesto semanal en `scripts/despachador.toml` (ADR 0011). Cuenta las corridas del despachador y las sesiones interactivas de este repo.
