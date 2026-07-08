$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $Root ".venv-win-runtime\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Missing .venv-win-runtime. Run `mise run setup:server:win` first."
}

$env:OVRTX_SKIP_USD_CHECK = "1"
$env:XDG_CACHE_HOME = Join-Path $Root ".cache"
$env:CUDA_CACHE_PATH = Join-Path $Root ".cache\cuda"
$env:__GL_SHADER_DISK_CACHE_PATH = Join-Path $Root ".cache\gl"
$env:npm_config_cache = Join-Path $Root ".cache\npm"

New-Item -ItemType Directory -Force `
    -Path $env:XDG_CACHE_HOME, $env:CUDA_CACHE_PATH, $env:__GL_SHADER_DISK_CACHE_PATH, $env:npm_config_cache, (Join-Path $Root "logs"), (Join-Path $Root "data\generated") `
    | Out-Null

Push-Location $Root
try {
    & $Python -m server.ov_web_viewer_server @args
}
finally {
    Pop-Location
}
