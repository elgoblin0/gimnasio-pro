# Lanza el implementador local en modo --esperar (repite cada 60 segundos).
# Uso: clic derecho > Ejecutar con PowerShell, o  .\lanzar-implementador.ps1
Set-Location $PSScriptRoot

$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

Write-Host "Implementador en $PSScriptRoot (Ctrl+C para frenar)" -ForegroundColor Cyan
& $py scripts/implementador.py --esperar
Write-Host "El implementador terminó (código $LASTEXITCODE)." -ForegroundColor Yellow
Read-Host "Enter para cerrar"
