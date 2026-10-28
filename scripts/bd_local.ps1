# Base MySQL local para pruebas, igual a la del CI (mysql:8.4, root / solo-ci).
# Uso: .\scripts\bd_local.ps1 iniciar | detener | estado | entorno
# Requiere el ZIP portable de MySQL 8.4 descomprimido en .mysql-local\mysql (ver docs/entorno-local.md).
param([Parameter(Mandatory)][ValidateSet("iniciar", "detener", "estado", "entorno")][string]$Accion)

$raiz = Split-Path $PSScriptRoot -Parent
$local = Join-Path $raiz ".mysql-local"
$bin = Join-Path $local "mysql\bin"
$clave = "solo-ci"

function Responde { & "$bin\mysqladmin.exe" -h 127.0.0.1 -uroot "-p$clave" ping 2>$null | Select-String "alive" }

switch ($Accion) {
    "iniciar" {
        if (Responde) { "MySQL ya está activo."; break }
        $ini = Join-Path $local "my.ini"
        $ini_texto = "[mysqld]`nbasedir=$($local -replace '\\','/')/mysql`ndatadir=$($local -replace '\\','/')/datos`nbind-address=127.0.0.1`nport=3306`nmysqlx=OFF`n"
        Set-Content -Path $ini -Value $ini_texto -Encoding ascii
        if (-not (Test-Path (Join-Path $local "datos"))) {
            & "$bin\mysqld.exe" "--defaults-file=$ini" --initialize-insecure 2>$null
            $sin_clave = $true
        }
        Start-Process "$bin\mysqld.exe" -ArgumentList "--defaults-file=$ini" -WindowStyle Hidden
        for ($i = 0; $i -lt 40; $i++) {
            Start-Sleep -Milliseconds 500
            if (& "$bin\mysqladmin.exe" -h 127.0.0.1 -uroot ping 2>$null | Select-String "alive") { break }
            if (Responde) { break }
        }
        if ($sin_clave) {
            & "$bin\mysql.exe" -h 127.0.0.1 -uroot -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '$clave'"
        }
        & "$bin\mysql.exe" -h 127.0.0.1 -uroot "-p$clave" -e "CREATE DATABASE IF NOT EXISTS gimnasio_pro" 2>$null
        if (Responde) { "MySQL activo en 127.0.0.1:3306." } else { throw "MySQL no arrancó." }
    }
    "detener" { & "$bin\mysqladmin.exe" -h 127.0.0.1 -uroot "-p$clave" shutdown }
    "estado" { if (Responde) { "activo" } else { "detenido" } }
    "entorno" {
        # Para la sesión actual:  Invoke-Expression (.\scripts\bd_local.ps1 entorno)
        '$env:GIMNASIO_BD_HOST="127.0.0.1"; $env:GIMNASIO_BD_PUERTO="3306"; $env:GIMNASIO_BD_USUARIO="root"; $env:GIMNASIO_BD_CLAVE="solo-ci"; $env:GIMNASIO_BD_NOMBRE="gimnasio_pro"'
    }
}
