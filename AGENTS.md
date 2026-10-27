# AGENTS.md

Instrucciones para todos los agentes (Opus y Codex). Breve a propósito: leé solo lo que tu issue necesita.

## Antes de empezar
- Fuente de verdad: `VISION.md` (meta), `GLOSSARY.md` (términos), `docs/adr/` (decisiones). El issue manda sobre tu criterio; los ADR, sobre el issue.
- Usá **solo** los términos del glosario en código, nombres, mensajes y documentos. Si falta un término, no lo inventes: etiquetá `necesita-criterio`.
- Código, identificadores, comentarios, commits y PR en español.
- Repo público: nunca escribas secretos, tokens ni datos reales. La semilla es ficticia.

## Comandos
```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt   # Windows; en Linux .venv/bin/
ruff check . && ruff format --check .
pytest                          # las pruebas con MySQL se saltan si no hay GIMNASIO_BD_*
python -m gimnasio.comun.migrar # aplica migraciones/NNNN_*.sql pendientes
node --test gimnasio/static/js  # módulos JS puros
python scripts/mapa_capacidades.py --verificar
python scripts/despachador.py --una-vuelta --simular
```
Variables de base: `GIMNASIO_BD_HOST`, `GIMNASIO_BD_PUERTO`, `GIMNASIO_BD_USUARIO`, `GIMNASIO_BD_CLAVE`, `GIMNASIO_BD_NOMBRE`.

## Estructura y dependencias (ADR 0001)
```
gimnasio/
  __init__.py      crear_app(config)
  comun/           reloj, ids, bd, formatos, errores, migrar  (no importa dominio)
  reglas/          motor puro: sin SQL, sin red, sin reloj    (solo stdlib + comun.tipos)
  <modulo>/        rutas.py → servicio.py → repositorio.py
  static/          PWA sin build: js/, estilos/, vendor/   (ADR 0007)
migraciones/       NNNN_descripcion.sql, solo hacia adelante (ADR 0008)
pruebas/           pytest; pruebas/e2e/ con Playwright
scripts/           despachador, mapa de capacidades, resumen del CI
```
- `rutas.py` no ejecuta SQL. Un módulo no importa el `repositorio` de otro.
- Tiempo: solo `reloj_actual()` en servicios; la fecha entra por parámetro en `reglas/` (ADR 0005).
- Hechos: solo `INSERT`; las correcciones agregan registros (ADR 0003).
- Ids UUIDv7 desde `comun/ids`; los POST exigen `Idempotency-Key` (ADR 0004).
- `pruebas/test_dependencias.py` hace cumplir estas reglas.

## Rutas sensibles
`gimnasio/reglas/`, `migraciones/`, `gimnasio/comun/migrar.py`, `gimnasio/sincronizacion/`, `gimnasio/permisos/`, `gimnasio/salud/`.
Todo PR que las toque necesita revisión de Opus, aunque lo haya escrito Codex.

## Definición de terminado
1. Hace lo que pide el issue, sin agregados no pedidos.
2. Pruebas nuevas que fallaban antes del cambio; `ruff` y `pytest` en verde en el CI.
3. Migraciones aplicables sobre una base vacía (el CI lo comprueba).
4. Si cambia una capacidad, se actualiza `docs/capacidades.toml` y se regenera el mapa.
5. Si mueve código citado en `INDICADORES.md`, se actualizan sus referencias.
6. PR con la plantilla completa, incluida "Notas para el próximo agente".
7. Revisión cruzada aprobada (ver abajo).

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

## Lo que Codex no hace
- Decidir producto, alcance o términos nuevos: etiqueta `necesita-criterio`, explica la duda en un comentario y se detiene.
- Escribir ADR, cambiar `VISION.md`, `GLOSSARY.md` o los frenos de seguridad.
- Crear migraciones que alteren tablas de hechos, o cambiar `reglas/` sin un issue que lo especifique.
- Tocar `.github/workflows/`, `scripts/despachador*` o la configuración de presupuesto, salvo que el issue lo autorice por escrito.
- Agregar dependencias que el issue no nombre.
- Desactivar pruebas, bajar umbrales del CI o usar `# noqa` sin explicación.

## Revisión cruzada
- PR de Codex sin rutas sensibles: lo revisa otra corrida de Codex (`codex exec review`).
- PR de Opus, o con rutas sensibles: Codex revisa siempre; Opus revisa además lo sensible.
- La revisión lee el diff y el resumen del CI (`resumen-ci.md`), no el repo entero.
- Se fusiona con squash cuando el CI está verde y la revisión aprueba. Nunca se empuja a `main`.

## Bloqueos
Codex: un intento y un reintento. Si sigue trabado, etiqueta `bloqueado` y `ejecutor:opus` y comenta qué probó. Opus intenta una vez; si no sale, el issue pasa al milestone de la etapa siguiente con su explicación.

## Cuota de Claude
- Un solo Claude a la vez; hasta tres Codex en paralelo.
- Sesiones cortas con `claude -p`, una por issue. Leé el issue, los ADR citados y el diff, no el repo entero.
- Sin capturas ni videos de rutina: la verificación visual la hace el usuario en el cierre.
- Lo determinista va a scripts y al CI (mapa de capacidades, resúmenes, etiquetas).
- Presupuesto semanal en `scripts/despachador.toml`; el despachador lo hace cumplir.

## Al terminar
Abrí el PR con `Cierra #N`. En "Notas para el próximo agente", contá qué quedó a medias, qué decidiste sin ADR y qué trampas encontraste. Si decidiste algo no cubierto por un ADR, escribí un ADR provisional (solo Opus) o etiquetá `necesita-criterio` (Codex).
