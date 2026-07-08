$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Venv = Join-Path $Root ".venv-win-runtime"
$Python = Join-Path $Venv "Scripts\python.exe"

Push-Location $Root
try {
    mise exec -- python -m venv $Venv
    & $Python -m pip install --upgrade pip setuptools wheel
    & $Python -m pip install -r (Join-Path $Root "server\requirements.txt")
}
finally {
    Pop-Location
}
