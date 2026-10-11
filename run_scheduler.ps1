# Start exactly one Beat scheduler, with Redis running.
param([switch]$InsightsOnly)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'scripts/use_d_drive.ps1')
Push-Location -LiteralPath $PSScriptRoot
try {
    $schedulerPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if ($InsightsOnly) {
        & $schedulerPython -X utf8 -m scripts.run_scheduler --insights-only
    } else {
        & $schedulerPython -X utf8 -m scripts.run_scheduler
    }
    $schedulerExit = $LASTEXITCODE
} finally { Pop-Location }
exit $schedulerExit
