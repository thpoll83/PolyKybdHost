<#
    PolyKybdHost one-line installer for Windows (PowerShell).

        irm https://raw.githubusercontent.com/thpoll83/PolyKybdHost/main/scripts/install.ps1 | iex

    Clones the repo (if not already inside it), creates a virtual environment
    and installs the Python requirements. The native hidapi.dll ships with the
    repo, so no extra native install is needed on Windows.

    Override the clone location with $env:POLYKYBD_DIR = "C:\path\to\dir".
    $env:POLYKYBD_NO_LAUNCH = "1" skips starting the app at the end.
    $env:POLYKYBD_REPO_URL and $env:POLYKYBD_REF clone another repository or
    branch instead of main; .github/workflows/windows-installer.yml uses them
    to install a pull request's own code.
#>
$ErrorActionPreference = "Stop"

$RepoUrl   = if ($env:POLYKYBD_REPO_URL) { $env:POLYKYBD_REPO_URL } else { "https://github.com/thpoll83/PolyKybdHost.git" }
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
    if ($LASTEXITCODE -ne 0) { throw "git pull failed." }
} else {
    Write-Host ">> Cloning into '$TargetDir'."
    # Only the latest commit: the full history is 47 MB.
    # `git pull` still updates it. Run `git fetch --unshallow` for the history.
    # The sparse checkout leaves out what the app never reads: tests/ and the
    # overlay build inputs in polyhost/res/overlay_sources/ except the per-app
    # YAML specs. That is about 10,000 of 12,000 files, and the blobs are not
    # downloaded either (--filter=blob:none). `git sparse-checkout disable`
    # brings them back. The patterns are SPARSE_PATTERNS in
    # polyhost/services/updater.py, which the updater applies too.
    $cloneArgs = @("clone", "--depth", "1", "--filter=blob:none", "--sparse")
    if ($env:POLYKYBD_REF) { $cloneArgs += @("--branch", $env:POLYKYBD_REF) }
    git @cloneArgs $RepoUrl $TargetDir
    if ($LASTEXITCODE -ne 0) { throw "git clone failed." }
    # Through stdin, so no shell or C runtime expands the * in a pattern.
    @(
        '/*'
        '!/tests/'
        '!/polyhost/res/overlay_sources/**'
        '/polyhost/res/overlay_sources/*/*.yaml'
    ) | git -C $TargetDir sparse-checkout set --no-cone --stdin
    # Without the patterns a --sparse clone has only the top-level files.
    if ($LASTEXITCODE -ne 0) { throw "git sparse-checkout failed." }
}
Set-Location $TargetDir

# --- python virtual environment ---------------------------------------------
$py = $null
foreach ($cand in @("python", "py")) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) { $py = $cand; break }
}
if (-not $py) { throw "Python 3 not found on PATH." }

Write-Host ">> Creating virtual environment in .venv"
# $ErrorActionPreference does not stop on a native command's exit code in
# Windows PowerShell 5.1, so each step checks $LASTEXITCODE itself. Without
# the checks a failed pip install still ended with ">> Done.".
& $py -m venv .venv
if ($LASTEXITCODE -ne 0) { throw "Creating the virtual environment failed." }
$venvPy = Join-Path (Get-Location) ".venv\Scripts\python.exe"
& $venvPy -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip install --upgrade pip failed." }
& $venvPy -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install -r requirements.txt failed." }
# Editable install too, so the `polyctl` console script lands in .venv\Scripts
# (deps are already satisfied above; this just adds the package link + script).
& $venvPy -m pip install -e .
if ($LASTEXITCODE -ne 0) { throw "pip install -e . failed." }

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
