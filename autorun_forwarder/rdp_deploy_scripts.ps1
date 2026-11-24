# Deploys the PolyForwarder IP detection for Remote Desktop. The Windows
# counterpart of nx_deploy_scripts.sh.
# Run it ON THE REMOTE MACHINE (the one that runs the RDP server and the
# PolyForwarder, not the machine with the keyboard), as the user who runs the
# forwarder. It needs no administrator rights.
#
# What it does:
#   1. Copies rdp_ip_poll.ps1 to %USERPROFILE%\.polyhost\
#   2. Registers a scheduled task, PolyHostRdpIpPoll, that starts at this user's
#      logon and runs the poll script in a loop (every 30 seconds, hidden)
#   3. Starts the task now
#
# Then start the forwarder with:
#   python -m polyhost --host-file "%LOCALAPPDATA%\PolyHost\host_ip"
#
# Not tested on Windows by the author of this file.
$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $scriptDir 'rdp_ip_poll.ps1'
$targetDir = Join-Path $env:USERPROFILE '.polyhost'
$target = Join-Path $targetDir 'rdp_ip_poll.ps1'
$taskName = 'PolyHostRdpIpPoll'

if (-not (Test-Path -LiteralPath $source)) {
    Write-Error "rdp_ip_poll.ps1 not found in $scriptDir"
}

if (-not (Test-Path -LiteralPath $targetDir)) { New-Item -ItemType Directory -Path $targetDir -Force | Out-Null }
Copy-Item -LiteralPath $source -Destination $target -Force
Write-Host "Installed: $target"

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$target`" -Loop"
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
    -Description 'Writes the keyboard machine IP from the active RDP session for PolyForwarder' -Force | Out-Null
Write-Host "Registered scheduled task: $taskName"

Start-ScheduledTask -TaskName $taskName
Write-Host "Started: $taskName"
Write-Host ""
Write-Host "PolyForwarder must be started with:"
Write-Host "  python -m polyhost --host-file `"$env:LOCALAPPDATA\PolyHost\host_ip`""
