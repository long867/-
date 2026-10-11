# Run in a separate PowerShell terminal; API and frontend use their own terminals.
param([switch]$InsightsOnly)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'scripts/use_d_drive.ps1')
Push-Location -LiteralPath $PSScriptRoot
try {
    $workerPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if ($InsightsOnly) {
        & $workerPython -X utf8 -m scripts.run_worker --queues=insights --loglevel=INFO
    } else {
        & $workerPython -X utf8 -m scripts.run_worker --queues=celery,nlp,insights --loglevel=INFO
    }
    $workerExit = $LASTEXITCODE
} finally { Pop-Location }
exit $workerExit
