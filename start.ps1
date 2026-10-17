# Start IHH Care Bridge in Docker and open it in the browser.
# Inicia IHH Care Bridge en Docker y lo abre en el navegador.
#   .\start.ps1           start (or rebuild after code changes)
#   .\start.ps1 -Stop     stop the app (settings and the outcome log are kept)
param([switch]$Stop)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker is not installed. Install Docker Desktop, then run this again."
    Write-Host "Docker no esta instalado. Instale Docker Desktop y vuelva a correr esto."
    exit 1
}
if ($Stop) { docker compose down; exit $LASTEXITCODE }

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    $desktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $desktop) { Start-Process $desktop }
    Write-Host "Waiting for Docker to start... / Esperando a que Docker arranque..."
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 2
        docker info *> $null
        if ($LASTEXITCODE -eq 0) { break }
    }
    if ($LASTEXITCODE -ne 0) { Write-Host "Docker did not start. Open Docker Desktop and try again."; exit 1 }
}

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "Made .env. Add ANTHROPIC_API_KEY there to read packets (the demo works without it)."
    Write-Host "Se creo .env. Agregue ANTHROPIC_API_KEY para leer referidos (la demo funciona sin ella)."
}
New-Item -ItemType Directory -Force inbox | Out-Null

docker compose up --build -d
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$port = if ($env:CAREBRIDGE_PORT) { $env:CAREBRIDGE_PORT } else { "8780" }
$url = "http://localhost:$port/"
for ($i = 0; $i -lt 30; $i++) {
    try { Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 2 | Out-Null; break } catch { Start-Sleep -Seconds 1 }
}
Write-Host "IHH Care Bridge: $url"
Start-Process $url
