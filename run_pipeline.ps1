# Launch with the project interpreter, independent of Conda and PATH.
# All arguments are passed to pipeline.run_pipeline unchanged.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'scripts/use_d_drive.ps1')
$projectRoot = $PSScriptRoot
$projectPython = Join-Path $projectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $projectPython -PathType Leaf)) {
    throw 'Project Python is missing. Create a Python 3.12 .venv and install the dependencies as described in README.md.'
}

Push-Location -LiteralPath $projectRoot
try {
    & $projectPython -X utf8 -m scripts.run_collector @args
    $pipelineExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

exit $pipelineExitCode
