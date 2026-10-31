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
node --test "gimnasio/static/**/*.test.js"  # módulos JS puros (Node 24)
python scripts/mapa_capacidades.py --verificar
```
Variables de base: `GIMNASIO_BD_HOST`, `GIMNASIO_BD_PUERTO`, `GIMNASIO_BD_USUARIO`, `GIMNASIO_BD_CLAVE`, `GIMNASIO_BD_NOMBRE`.

## Entorno local (Windows): corré todo antes de subir el PR
MySQL 8.4 portable + Chromium + `.venv`, igual al CI. Detalle en `docs/entorno-local.md`.
```powershell
.\scripts\bd_local.ps1 iniciar                      # MySQL en 127.0.0.1:3306 (root / solo-ci); si `estado` dice activo, no hace falta
Invoke-Expression (.\scripts\bd_local.ps1 entorno)  # define GIMNASIO_BD_* en ESTA terminal; repetir en cada terminal nueva
.\.venv\Scripts\python.exe -m pytest -q             # unitarias + MySQL
.\.venv\Scripts\python.exe -m pytest -m e2e -q -rs  # Chromium contra el servidor demo
```
- Sin `GIMNASIO_BD_*` las pruebas con MySQL y los e2e se **saltan sin fallar**: un «skipped» no cuenta como verde. Pegá en el PR el conteo de `passed`/`skipped`.
- Si falta `.mysql-local/mysql/bin/mysqld.exe`, no lo descargues vos: etiquetá `necesita-criterio` o pedíselo al dueño.
- Al escribir archivos desde pruebas usá `encoding="utf-8", newline="\n"` (Windows usa cp1252).
- No commitees `.mysql-local/`. Si no podés correr algo local, decilo en "Notas para el próximo agente"; anotarlo no vuelve el PR apto para fusionar: el CI en verde sigue siendo obligatorio.

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
scripts/           mapa de capacidades, resumen del CI, etiquetas de GitHub
```
- `rutas.py` no ejecuta SQL. Un módulo no importa el `repositorio` de otro.
- Tiempo: solo `reloj_actual()` en servicios; la fecha entra por parámetro en `reglas/` (ADR 0005).
- Hechos: solo `INSERT`; las correcciones agregan registros (ADR 0003).
- Ids UUIDv7 desde `comun/ids`; los POST exigen `Idempotency-Key` (ADR 0004).
- `pruebas/test_dependencias.py` hace cumplir estas reglas.

## Rutas sensibles
`gimnasio/reglas/`, `migraciones/`, `gimnasio/comun/migrar.py`, `gimnasio/permisos/`, `gimnasio/salud/`.
Todo PR que las toque necesita, además de la revisión de Codex, la de Opus sobre el diff.

## Definición de terminado
1. Hace lo que pide el issue, sin agregados no pedidos.
2. Pruebas nuevas que fallaban antes del cambio; `ruff` y `pytest` en verde en el CI.
3. Migraciones aplicables sobre una base vacía (el CI lo comprueba).
4. Si cambia una capacidad, se edita su `docs/capacidades/<id>.toml` (ver docstring de `scripts/mapa_capacidades.py`) y se regenera el mapa. El CI exige la ficha con cada prueba e2e nueva, salvo `# Sin ficha: <motivo>` en la prueba. Si cambia un módulo de `reglas/` que registra `VERSION_REGLAS`, se sube (`scripts/verificar_pr.py`).
5. Si mueve código citado en `INDICADORES.md`, se actualizan sus referencias.
6. PR con la plantilla completa, incluida "Notas para el próximo agente".
7. Revisión cruzada aprobada.

## Protocolo
Opus planifica, decide y escribe los issues; Codex los implementa cuando la cadena automática se lo pide en el PR. Para implementar alcanza con este archivo. La orquestación (cadena, etiquetas, revisión, bloqueos) está en `docs/protocolo-agentes.md`: leelo al planificar, escribir un issue o tocar la cadena.

## Lo que Codex no hace
- Decidir diseño, producto, alcance o términos nuevos: etiqueta `necesita-criterio`, explica la duda en un comentario y se detiene; decide Opus.
- Escribir ADR, cambiar `VISION.md`, `GLOSSARY.md` o los frenos de seguridad.
- Crear migraciones que alteren tablas de hechos (el CI las rechaza sin `-- Autoriza Opus: #N`, línea que solo escribe Opus), o cambiar `reglas/` sin un issue que lo especifique.
- Tocar `.github/workflows/`, salvo que el issue lo autorice por escrito.
- Agregar dependencias que el issue no nombre.
- Desactivar pruebas, bajar umbrales del CI o usar `# noqa` sin explicación.

## Al terminar
El PR empieza con `Closes #N` (en inglés: GitHub solo reconoce sus palabras clave). En "Notas para el próximo agente", contá qué quedó a medias, qué decidiste sin ADR y qué trampas encontraste. Si decidiste algo no cubierto por un ADR, escribí un ADR provisional (solo Opus) o etiquetá `necesita-criterio` (Codex).
