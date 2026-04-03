Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

$pipeline = Start-Process -FilePath "uv" -ArgumentList @("run", "python", "main.py") -PassThru -NoNewWindow

try {
    uv run uvicorn app.api_server:app --host 0.0.0.0 --port 8000
}
finally {
    if ($null -ne $pipeline -and -not $pipeline.HasExited) {
        Stop-Process -Id $pipeline.Id -Force -ErrorAction SilentlyContinue
    }
}
