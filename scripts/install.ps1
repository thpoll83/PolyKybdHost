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
$DefaultDir = Join-Path (Get-Location) "PolyKybdHost"
$TargetDir = if ($env:POLYKYBD_DIR) { $env:POLYKYBD_DIR } else { $DefaultDir }

Write-Host ">> PolyKybdHost installer"

# --- get the source tree -----------------------------------------------------
if (Test-Path "polyhost/__main__.py") {
    Write-Host ">> Already inside a PolyKybdHost checkout, installing here."
    $TargetDir = "."
} else {
    # Offer the default location and let the user pick another, unless the
    # path was pinned via POLYKYBD_DIR.
    if (-not $env:POLYKYBD_DIR) {
        $reply = Read-Host ">> Install location [$TargetDir]"
        if ($reply) { $TargetDir = $reply }
    }
    Write-Host ">> Installing into '$TargetDir'."
}

if ($TargetDir -eq ".") {
    # already inside the checkout, nothing to fetch
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

function Start-PolyKybd {
    Write-Host ">> Starting PolyKybd..."
    # Prefer pythonw.exe so the GUI/tray app launches without a console window.
    $scripts = Join-Path (Get-Location) ".venv\Scripts"
    $pyw = Join-Path $scripts "pythonw.exe"
    if (-not (Test-Path $pyw)) { $pyw = $venvPy }
    # Put the venv's Scripts dir on PATH for the launched process. Running the
    # venv interpreter WITHOUT activation drops Scripts from PATH and the app
    # dies silently on Windows (see the autostart notes in CLAUDE.md / the
    # proven .bat wrapper). Mirror what Activate.ps1 does so the install-time
    # launch behaves like a normal activated run; the child inherits this env.
    $env:VIRTUAL_ENV = Join-Path (Get-Location) ".venv"
    $env:PATH = "$scripts;" + $env:PATH
    Start-Process -FilePath $pyw -ArgumentList "-m", "polyhost" -WorkingDirectory (Get-Location)
    Write-Host ">> PolyKybd started; it also registers itself to autostart at login."
}

Write-Host ""
Write-Host ">> Done."
if ($env:POLYKYBD_NO_LAUNCH) {
    # Opt out of auto-launch (e.g. CI / headless). Don't start the app.
    Write-Host ">> POLYKYBD_NO_LAUNCH set - not starting. Launch it later with:  .venv\Scripts\python.exe -m polyhost"
} elseif ([Environment]::UserInteractive -and -not [Console]::IsInputRedirected) {
    $ans = Read-Host ">> Start PolyKybd now? [Y/n]"
    if ($ans -match '^[Nn]') {
        Write-Host ">> Not started. Launch it later with:  .venv\Scripts\python.exe -m polyhost"
    } else {
        Start-PolyKybd
    }
} else {
    # Not started interactively - start right away.
    Start-PolyKybd
}
