<#
    PolyKybdHost installer for Windows that needs neither git nor Python.

        irm https://raw.githubusercontent.com/thpoll83/PolyKybdHost/main/scripts/install-app.ps1 | iex

    Downloads uv (one checksum-verified binary, deleted afterwards), lets uv
    download Python 3.13 into <install dir>\.python, then runs
    scripts/install_app.py with it. That script downloads the latest release,
    creates .venv, installs the requirements and starts the app. Nothing is
    added to PATH or the registry: deleting the install folder removes it all.

    The developer install (git clone of main, your own Python) is
    scripts/install.ps1.

    $env:POLYKYBD_DIR       install folder (default %LOCALAPPDATA%\PolyKybdHost)
    $env:POLYKYBD_NO_LAUNCH "1" skips starting the app at the end
    $env:POLYKYBD_REPO      owner/name to install from (default thpoll83/PolyKybdHost)
    $env:POLYKYBD_REF       branch, tag or commit instead of the latest release;
                            install_app.py is then taken from that ref too.
                            .github/workflows/app-installer.yml uses these two.
#>
# `irm | iex` runs this in the user's own session. The script block keeps
# $ErrorActionPreference, $ProgressPreference and the script's variables out
# of that session; the UV_* variables are process-wide and are restored in
# the finally block below.
& {
$ErrorActionPreference = "Stop"
# Invoke-WebRequest in Windows PowerShell 5.1 is many times slower with the
# progress bar on.
$ProgressPreference = "SilentlyContinue"

$UvVersion = "0.13.5"
# From https://astral.sh/uv/0.13.5/install.sh. Change them with $UvVersion.
$UvSha256 = @{
    "uv-x86_64-pc-windows-msvc.zip"  = "a38b8d1902b7cfbc76b423ba1bb456f623f42064cdc72628b6075b89afd1019a"
    "uv-aarch64-pc-windows-msvc.zip" = "09f47edf90726084a70f9426f6e3ca4f46e9bf7cbf23b1716ec64d60b055fae3"
}
$PythonVersion = "3.13"

$Repo = if ($env:POLYKYBD_REPO) { $env:POLYKYBD_REPO } else { "thpoll83/PolyKybdHost" }
$ScriptRef = if ($env:POLYKYBD_REF) { $env:POLYKYBD_REF } else { "main" }
$TargetDir = if ($env:POLYKYBD_DIR) { $env:POLYKYBD_DIR } else { Join-Path $env:LOCALAPPDATA "PolyKybdHost" }

Write-Host ">> PolyKybdHost installer"
if (-not $env:POLYKYBD_DIR -and [Environment]::UserInteractive -and -not [Console]::IsInputRedirected) {
    $reply = Read-Host ">> Install location [$TargetDir]"
    if ($reply) { $TargetDir = $reply }
}
if (Test-Path (Join-Path $TargetDir ".git")) {
    throw "'$TargetDir' is a git checkout from the developer installer. Update it with git pull, or choose another folder."
}
New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
$TargetDir = (Resolve-Path $TargetDir).Path

$arch = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
$uvAsset = if ($arch -eq "ARM64") { "uv-aarch64-pc-windows-msvc.zip" } else { "uv-x86_64-pc-windows-msvc.zip" }

$tmp = Join-Path ([IO.Path]::GetTempPath()) ("polykybd-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp | Out-Null
$uvVars = @("UV_PYTHON_INSTALL_DIR", "UV_CACHE_DIR", "UV_PYTHON_PREFERENCE",
            "UV_PYTHON_INSTALL_BIN", "UV_PYTHON_INSTALL_REGISTRY")
$savedEnv = @{}
foreach ($name in $uvVars) { $savedEnv[$name] = [Environment]::GetEnvironmentVariable($name, "Process") }
try {
    # --- uv ------------------------------------------------------------------
    Write-Host ">> Downloading uv $UvVersion"
    $zip = Join-Path $tmp $uvAsset
    Invoke-WebRequest -UseBasicParsing -Uri "https://releases.astral.sh/github/uv/releases/download/$UvVersion/$uvAsset" -OutFile $zip
    $hash = (Get-FileHash -Algorithm SHA256 -Path $zip).Hash.ToLower()
    if ($hash -ne $UvSha256[$uvAsset]) { throw "uv download has the wrong SHA-256 ($hash)." }
    Expand-Archive -Path $zip -DestinationPath (Join-Path $tmp "uv")
    $uv = (Get-ChildItem -Path (Join-Path $tmp "uv") -Recurse -Filter "uv.exe" | Select-Object -First 1).FullName
    if (-not $uv) { throw "uv.exe not found in $uvAsset." }

    # --- Python --------------------------------------------------------------
    # Only uv's own Python, kept inside the install folder. No python.exe in
    # %USERPROFILE%\.local\bin and no registry entry (PEP 514).
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $TargetDir ".python"
    $env:UV_CACHE_DIR = Join-Path $tmp "cache"
    $env:UV_PYTHON_PREFERENCE = "only-managed"
    $env:UV_PYTHON_INSTALL_BIN = "0"
    $env:UV_PYTHON_INSTALL_REGISTRY = "0"
    Write-Host ">> Downloading Python $PythonVersion"
    & $uv python install $PythonVersion
    if ($LASTEXITCODE -ne 0) { throw "uv python install $PythonVersion failed." }
    # Read all of the output before taking the first line. In Windows
    # PowerShell 5.1 `| Select-Object -First 1` stops the native process
    # early, and $LASTEXITCODE is then not 0 (CI, 2026-11-14).
    $found = @(& $uv python find $PythonVersion)
    if ($LASTEXITCODE -ne 0 -or $found.Count -eq 0) { throw "uv python find $PythonVersion failed." }
    $py = "$($found[0])".Trim()

    # --- install ---------------------------------------------------------------
    $script = Join-Path $tmp "install_app.py"
    Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/$Repo/$ScriptRef/scripts/install_app.py" -OutFile $script
    $installArgs = @($script, "--target", $TargetDir, "--repo", $Repo)
    if ($env:POLYKYBD_REF) { $installArgs += @("--ref", $env:POLYKYBD_REF) }
    # install_app.py reads POLYKYBD_NO_LAUNCH itself.
    & $py @installArgs
    if ($LASTEXITCODE -ne 0) { throw "install_app.py failed." }
} finally {
    # A $null value removes the variable, as before the installer ran.
    foreach ($name in $uvVars) { [Environment]::SetEnvironmentVariable($name, $savedEnv[$name], "Process") }
    Remove-Item -Recurse -Force -Path $tmp -ErrorAction SilentlyContinue
}
}
