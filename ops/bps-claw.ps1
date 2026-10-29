$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$env:PROJECT_ROOT = $ProjectRoot.Replace("\", "/")
$env:OPENCLAW_STATE_DIR   = Join-Path $ProjectRoot "agent\.openclaw_state"
$env:OPENCLAW_CONFIG_PATH = Join-Path $ProjectRoot "agent\openclaw.json"
New-Item -ItemType Directory -Force -Path $env:OPENCLAW_STATE_DIR | Out-Null
openclaw @args
exit $LASTEXITCODE