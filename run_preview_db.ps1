# Optional local PGlite preview; production uses PostgreSQL from Docker Compose.
param([ValidateRange(16, 128)][int]$MaxConnections = 64)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'scripts/use_d_drive.ps1')
$previewRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../.tools/pglite'))
$serverPath = Join-Path $previewRoot 'node_modules/@electric-sql/pglite-socket/dist/scripts/server.js'
if (-not (Test-Path -LiteralPath $serverPath)) {
    throw 'Local preview dependencies are missing. See docs/phase1-verification.md or use Docker Compose.'
}
if (Get-NetTCPConnection -LocalPort 55432 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Preview database port 55432 is already in use. Reuse that instance or stop the known preview process before restarting.'
}
$previewData = Join-Path $previewRoot 'data'
& node.exe $serverPath "--db=$previewData" --host=127.0.0.1 --port=55432 --extensions=@electric-sql/pglite-pgvector:vector,pg_trgm "--max-connections=$MaxConnections"
exit $LASTEXITCODE
