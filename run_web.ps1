# Start the frontend or reuse an existing MiningIntel instance.
param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 3000,
    [string]$ApiUrl = 'http://127.0.0.1:8001',
    [switch]$Production
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'scripts/use_d_drive.ps1')
$webUrl = "http://127.0.0.1:$Port/"
$existingPage = $null
try {
    $existingPage = Invoke-WebRequest -Uri $webUrl -UseBasicParsing -TimeoutSec 10
}
catch {
    # A missing server or non-success response is handled by the port check.
}

if ($existingPage -and $existingPage.Content -match '<title>MiningIntel') {
    Write-Host "MiningIntel is already running: $webUrl"
    exit 0
}

if (@(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue).Count -gt 0) {
    throw "Port $Port is in use, but the MiningIntel page is unavailable. Check the existing server or choose -Port 3001."
}

$frontendRoot = Join-Path $PSScriptRoot 'frontend'
if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot 'node_modules/.bin/next.cmd'))) {
    throw 'Frontend dependencies are missing. Run npm ci in the frontend directory first.'
}

$previousApiUrl = $env:API_INTERNAL_URL
$previousWebHost = $env:HOSTNAME
$previousWebPort = $env:PORT
$env:API_INTERNAL_URL = $ApiUrl
Push-Location -LiteralPath $frontendRoot
try {
    if ($Production) {
        if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot '.next/BUILD_ID'))) {
            throw 'Production build is missing. Run npm run build first.'
        }
        $standaloneRoot = Join-Path $frontendRoot '.next/standalone'
        Copy-Item -LiteralPath (Join-Path $frontendRoot 'public') -Destination $standaloneRoot -Recurse -Force
        Copy-Item -LiteralPath (Join-Path $frontendRoot '.next/static') -Destination (Join-Path $standaloneRoot '.next') -Recurse -Force
        $env:HOSTNAME = '127.0.0.1'
        $env:PORT = [string]$Port
        & node.exe (Join-Path $standaloneRoot 'server.js')
    }
    else {
        & npm.cmd run dev -- --hostname 127.0.0.1 --port $Port
    }
    $webExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
    $env:API_INTERNAL_URL = $previousApiUrl
    $env:HOSTNAME = $previousWebHost
    $env:PORT = $previousWebPort
}

exit $webExitCode
