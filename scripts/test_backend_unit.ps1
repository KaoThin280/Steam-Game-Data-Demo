[CmdletBinding()]
param([switch]$InstallDependencies)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot "back_end"
$PythonPath = Join-Path $BackendDir ".venv\Scripts\python.exe"
$OriginalDebug = $env:DEBUG
$env:DEBUG = "true"

if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "Missing virtual environment. Install Python 3.11/3.12 and run: py -m venv back_end\.venv"
}

& $PythonPath -c "import sys; print(sys.executable); print(sys.version)"
if ($LASTEXITCODE -ne 0) {
    throw @"
The virtual environment points to a Python installation that no longer exists.
Reinstall Python 3.11 or 3.12, then recreate it:
  Remove-Item -Recurse -Force .\back_end\.venv
  py -3.11 -m venv .\back_end\.venv
  .\back_end\.venv\Scripts\python.exe -m pip install -r .\back_end\requirements-test.txt
"@
}

if ($InstallDependencies) {
    & $PythonPath -m pip install --disable-pip-version-check -r (Join-Path $BackendDir "requirements-test.txt")
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
}

Push-Location $BackendDir
try {
    & $PythonPath -m pytest tests -q
    if ($LASTEXITCODE -ne 0) { throw "Unit tests failed." }
}
finally {
    Pop-Location
    $env:DEBUG = $OriginalDebug
}
