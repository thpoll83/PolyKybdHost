<#
    PolyKybdHost one-line installer for Windows (PowerShell).

        irm https://raw.githubusercontent.com/thpoll83/PolyKybdHost/main/scripts/install.ps1 | iex

    Clones the repo (if not already inside it), creates a virtual environment
    and installs the Python requirements. The native hidapi.dll ships with the
    repo, so no extra native install is needed on Windows.

    Override the clone location with $env:POLYKYBD_DIR = "C:\path\to\dir".
#>
$ErrorActionPreference = "Stop"

$RepoUrl   = "https://github.com/thpoll83/PolyKybdHost.git"
$TargetDir = if ($env:POLYKYBD_DIR) { $env:POLYKYBD_DIR } else { "PolyKybdHost" }

Write-Host ">> PolyKybdHost installer"

# --- get the source tree -----------------------------------------------------
if (Test-Path "polyhost/__main__.py") {
    Write-Host ">> Already inside a PolyKybdHost checkout, installing here."
    $TargetDir = "."
} elseif (Test-Path "$TargetDir/.git") {
    Write-Host ">> Updating existing checkout in '$TargetDir'."
    git -C $TargetDir pull --ff-only
} else {
    Write-Host ">> Cloning into '$TargetDir'."
    git clone $RepoUrl $TargetDir
}
Set-Location $TargetDir

# --- python virtual environment ---------------------------------------------
$py = $null
foreach ($cand in @("python", "py")) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) { $py = $cand; break }
}
if (-not $py) { throw "Python 3 not found on PATH." }

Write-Host ">> Creating virtual environment in .venv"
& $py -m venv .venv
$venvPy = Join-Path (Get-Location) ".venv\Scripts\python.exe"
& $venvPy -m pip install --upgrade pip
& $venvPy -m pip install -r requirements.txt

Write-Host ""
Write-Host ">> Done. Start PolyKybdHost with:"
Write-Host "       cd $(Get-Location); .venv\Scripts\python.exe -m polyhost"
