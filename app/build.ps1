# Builds app\dist\ihh-care-bridge.exe.
#   .\build.ps1                      # makes a build venv in app\build\venv
#   .\build.ps1 -Python C:\path\python.exe   # use an existing Python with the build requirements
param([string]$Python = "")

# Not "Stop": Windows PowerShell treats native tools' stderr logging as errors. Exit codes are checked.
$ErrorActionPreference = "Continue"
$App = $PSScriptRoot
Set-Location $App

if (-not $Python) {
    $venv = Join-Path $App "build\venv"
    if (-not (Test-Path "$venv\Scripts\python.exe")) {
        py -3.12 -m venv $venv
        if (-not $?) { python -m venv $venv }
    }
    $Python = "$venv\Scripts\python.exe"
    & $Python -m pip install -q --upgrade pip
    & $Python -m pip install -q -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
}

& $Python build_stage.py
if ($LASTEXITCODE -ne 0) { throw "staging failed" }

& $Python -m PyInstaller --noconfirm --clean --distpath dist --workpath build\pyinstaller carebridge.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$exe = Join-Path $App "dist\ihh-care-bridge.exe"
"{0}  {1:N1} MB" -f $exe, ((Get-Item $exe).Length / 1MB)
