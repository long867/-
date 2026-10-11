# Dot-source before local development: . .\scripts\use_d_drive.ps1
$ErrorActionPreference = 'Stop'
$runtimeRoot = 'D:\MiningIntelRuntime'
foreach ($folder in @('tmp', 'uv-cache', 'python', 'npm-cache', 'pip-cache', 'playwright')) {
    New-Item -ItemType Directory -Force -Path (Join-Path $runtimeRoot $folder) | Out-Null
}
$env:TEMP = Join-Path $runtimeRoot 'tmp'
$env:TMP = $env:TEMP
$env:UV_CACHE_DIR = Join-Path $runtimeRoot 'uv-cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $runtimeRoot 'python'
$env:npm_config_cache = Join-Path $runtimeRoot 'npm-cache'
$env:PIP_CACHE_DIR = Join-Path $runtimeRoot 'pip-cache'
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $runtimeRoot 'playwright'
$env:NEXT_TELEMETRY_DISABLED = '1'
Write-Host 'Project temporary files and dependency caches now use D:\MiningIntelRuntime.'
