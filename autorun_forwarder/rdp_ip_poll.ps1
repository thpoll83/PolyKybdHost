# Finds the keyboard machine's IP from an active Remote Desktop session and
# writes it to the PolyHost host_ip file, for `polyhost --host-file`. The Windows
# counterpart of nx_ip_poll.sh.
#
# Run it ON THE REMOTE MACHINE (the one that runs the RDP server and the
# PolyForwarder, not the machine with the keyboard). The client connects to this
# machine's RDP port (3389), so the peer address of that connection is the
# keyboard machine. With no connection the file is removed and the forwarder
# waits, the same as for NoMachine.
#
# Managed by the PolyHostRdpIpPoll scheduled task, see rdp_deploy_scripts.ps1.
# Written for Windows PowerShell 5.1 and PowerShell 7. Not tested on Windows by
# the author of this file: run it once by hand and read host_ip.
#
#   powershell -File rdp_ip_poll.ps1            one check, then exit
#   powershell -File rdp_ip_poll.ps1 -Loop      check every 30 seconds
param(
    [switch]$Loop,
    [int]$Port = 3389,
    [int]$IntervalSeconds = 30,
    [string]$HostIpFile = (Join-Path $env:LOCALAPPDATA 'PolyHost\host_ip')
)

$ErrorActionPreference = 'Stop'

function Get-RdpClientAddress {
    # The first established connection to the RDP port from a non-local peer.
    $conns = @(Get-NetTCPConnection -State Established -LocalPort $Port -ErrorAction SilentlyContinue)
    foreach ($c in $conns) {
        $addr = [string]$c.RemoteAddress
        # An IPv4 client can show as ::ffff:a.b.c.d on a dual-stack listener.
        if ($addr -like '::ffff:*') { $addr = $addr.Substring(7) }
        if ($addr -eq '127.0.0.1' -or $addr -eq '::1' -or $addr -eq '0.0.0.0' -or $addr -eq '::') { continue }
        # A link-local IPv6 address carries a %zone suffix the forwarder cannot dial.
        $addr = $addr -replace '%.*$', ''
        if ($addr) { return $addr }
    }
    return $null
}

function Update-HostIpFile {
    $addr = Get-RdpClientAddress
    if ($addr) {
        $dir = Split-Path -Parent $HostIpFile
        if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        $current = $null
        if (Test-Path -LiteralPath $HostIpFile) { $current = (Get-Content -LiteralPath $HostIpFile -Raw).Trim() }
        # ASCII on purpose: Windows PowerShell 5.1 writes a BOM with -Encoding UTF8,
        # and the forwarder would read it as part of the address.
        if ($current -ne $addr) { Set-Content -LiteralPath $HostIpFile -Value $addr -Encoding ASCII }
    }
    elseif (Test-Path -LiteralPath $HostIpFile) {
        Remove-Item -LiteralPath $HostIpFile -Force
    }
}

if ($Loop) {
    while ($true) {
        try { Update-HostIpFile } catch { }   # one bad check must not end the loop
        Start-Sleep -Seconds $IntervalSeconds
    }
}
else {
    Update-HostIpFile
}
