# Entorno local (Windows)

Reproduce el CI en la máquina para detectar fallos antes de subir el PR: Python, MySQL 8.4 y Chromium funcionando juntos.

## Una sola vez
1. Python 3.13 y dependencias: `python -m venv .venv && .\.venv\Scripts\pip.exe install -r requirements-dev.txt`.
2. Chromium: `.\.venv\Scripts\playwright.exe install chromium`.
3. MySQL 8.4 portable (la misma versión que el CI, sin servicio ni administrador): descargar
   `mysql-8.4.x-winx64.zip` de <https://dev.mysql.com/downloads/mysql/> (archivo 8.4) y descomprimirlo en
   `.mysql-local/` de modo que quede `.mysql-local/mysql/bin/mysqld.exe`. La carpeta está en `.gitignore`.

## Cada sesión
```powershell
.\scripts\bd_local.ps1 iniciar                      # crea los datos la primera vez; root / solo-ci como en el CI
Invoke-Expression (.\scripts\bd_local.ps1 entorno)  # define GIMNASIO_BD_* en esta terminal
```

## Lo que corre el CI, en el mismo orden
```powershell
.\.venv\Scripts\ruff.exe check . ; .\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\python.exe scripts/mapa_capacidades.py --verificar
node --test "gimnasio/static/**/*.test.js"
.\.venv\Scripts\python.exe -m gimnasio.comun.migrar ; .\.venv\Scripts\python.exe -m gimnasio.comun.migrar --sin-pendientes
.\.venv\Scripts\python.exe -m pytest -n 6 --dist worksteal -q -rs  # toda la suite, e2e incluidos, en unos 2 minutos
```
Con más procesos que núcleos la suite tarda más. `bd_local.ps1` arranca MySQL sin binlog ni escritura a disco en cada `commit`: los datos son descartables, y el cambio rige desde el próximo `iniciar`.
En el CI, `pruebas` corre partido en dos y `e2e` en cuatro (`GIMNASIO_FRAGMENTO=k/N`, repartidos por un hash del id de cada prueba en `pruebas/conftest.py`); los trabajos `pruebas` y `e2e` son la compuerta que espera los dos. Local no hace falta: corre todo junto.

`bd_local.ps1 detener` apaga el servidor. Sin `GIMNASIO_BD_*` las pruebas con MySQL y los e2e se saltan en silencio: si ves «skipped», revisá el entorno.

## Trampas de Windows
- Al escribir archivos en pruebas, pasar `encoding="utf-8"` y `newline="\n"`; la codificación por defecto es cp1252.
- Chromium falla de vez en cuando una petición a `127.0.0.1` con `net::ERR_ADDRESS_IN_USE` (unas 4 en 8 corridas completas, con el servidor e2e en serie o con hilos) y no la reintenta. Si cae en algo que la prueba necesita, falla una prueba sin relación con tu cambio: una espera vencida o un clic de 30 s. Causa de fondo sin confirmar. Antes de investigar, repetí esa prueba sola. El CI es la puerta.

## Codex en el sandbox de Windows

Si Codex dice que `pytest` no arranca por «acceso denegado» al ejecutable de Python, es que el sandbox (grupo `CodexSandboxUsers`) no puede leer el Python base al que apunta `.venv` (`home` en `.venv\pyvenv.cfg`, normalmente bajo `AppData\Local\Programs\Python`). Una vez, el dueño le da lectura a esa carpeta:

```powershell
icacls "<carpeta del Python base>" /grant "CodexSandboxUsers:(OI)(CI)RX"
```

Para deshacerlo: `icacls "<carpeta>" /remove "CodexSandboxUsers"`. Aunque falle, el implementador local corre ruff y las pruebas del módulo tocado por su cuenta antes de subir.

## Cadena automática

Para lanzar trabajo sin la app de escritorio, consultá la sección [Cadena automática](protocolo-agentes.md#cadena-automática) del protocolo de agentes.
