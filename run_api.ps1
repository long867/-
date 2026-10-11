# Use the project's Python, or reuse a verified MiningIntel API on this port.
param([ValidateRange(1024, 65535)][int]$Port = 8001)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'scripts/use_d_drive.ps1')
$apiUrl = "http://127.0.0.1:$Port"
$existingApi = $null
try {
    $existingApi = Invoke-RestMethod -Uri "$apiUrl/health/live" -TimeoutSec 5
}
catch {
    # The listener check below gives a concrete conflict message.
}
if ($existingApi -and $existingApi.service -eq 'miningintel') {
    Write-Host "MiningIntel API is already running: $apiUrl/docs"
    exit 0
}
if (@(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue).Count -gt 0) {
    throw "Port $Port is occupied by another service. Choose -Port 8002 and pass that URL to run_web.ps1 -ApiUrl."
}
$apiPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $apiPython -PathType Leaf)) {
    throw 'Project Python is missing. Install backend dependencies in a Python 3.12 .venv first.'
}
Push-Location -LiteralPath $PSScriptRoot
try {
    & $apiPython -X utf8 -m scripts.run_api --port $Port
    $apiExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}
exit $apiExitCode
