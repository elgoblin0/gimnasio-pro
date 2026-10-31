# Lanza el implementador local en modo --esperar (repite cada 60 segundos).
# Uso: clic derecho > Ejecutar con PowerShell, o  .\lanzar-implementador.ps1
Set-Location $PSScriptRoot

$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

# Sin GIMNASIO_BD_* la verificación previa a subir salta las pruebas con MySQL (un «skipped» no cuenta como verde).
if (Test-Path (Join-Path $PSScriptRoot ".mysql-local\mysql\bin\mysqld.exe")) {
    & (Join-Path $PSScriptRoot "scripts\bd_local.ps1") iniciar
    Invoke-Expression (& (Join-Path $PSScriptRoot "scripts\bd_local.ps1") entorno)
} else {
    Write-Host "Falta .mysql-local: las pruebas con MySQL se van a saltar (ver docs/entorno-local.md)." -ForegroundColor Yellow
}

Write-Host "Implementador en $PSScriptRoot (Ctrl+C para frenar)" -ForegroundColor Cyan
& $py scripts/implementador.py --esperar
Write-Host "El implementador terminó (código $LASTEXITCODE)." -ForegroundColor Yellow
Read-Host "Enter para cerrar"
