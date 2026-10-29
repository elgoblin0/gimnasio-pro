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
.\.venv\Scripts\python.exe -m pytest -q            # unitarias y con MySQL
.\.venv\Scripts\python.exe -m pytest -m e2e -q -rs # Chromium contra el servidor demo
```
`bd_local.ps1 detener` apaga el servidor. Sin `GIMNASIO_BD_*` las pruebas con MySQL y los e2e se saltan en silencio: si ves «skipped», revisá el entorno.

## Trampas de Windows
- Al escribir archivos en pruebas, pasar `encoding="utf-8"` y `newline="\n"`; la codificación por defecto es cp1252.

## Cadena automática

Para lanzar trabajo sin la app de escritorio, consultá la sección [Cadena automática](protocolo-agentes.md#cadena-automática) del protocolo de agentes.
