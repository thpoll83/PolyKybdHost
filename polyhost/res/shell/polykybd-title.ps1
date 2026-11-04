# PolyKybd title integration for PowerShell (5.1 and 7): put the running
# command line into the console window title, so that PolyKybdHost can select
# the overlay for the program running in the terminal (nano, for example).
# The title from before the command comes back at the next prompt.
#
# Installed by PolyKybdHost ("Updates > Show the running command in the
# terminal title" in the tray, or `polyctl shell-integration install`), which
# adds one line to $PROFILE that dot-sources this file. Safe to source twice.
# Needs PSReadLine (installed with PowerShell 5.1 and 7); without it nothing
# changes. This file is ASCII only: Windows PowerShell 5.1 reads a script
# without a byte order mark in the ANSI code page.

if ($global:PolyKybdTitleLoaded) { return }
if (-not (Get-Command Set-PSReadLineKeyHandler -ErrorAction SilentlyContinue)) { return }
$global:PolyKybdTitleLoaded = $true

$global:PolyBaseTitle = $Host.UI.RawUI.WindowTitle
Set-PSReadLineKeyHandler -Key Enter -ScriptBlock {
    $line = $null; $cursor = $null
    [Microsoft.PowerShell.PSConsoleReadLine]::GetBufferState([ref]$line, [ref]$cursor)
    if ($line.Trim()) {
        $Host.UI.RawUI.WindowTitle = $line.Trim() -replace '[\x00-\x1f]', ' '
    }
    [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
}
$global:PolyPrompt = $function:prompt
function global:prompt {
    $Host.UI.RawUI.WindowTitle = $global:PolyBaseTitle
    & $global:PolyPrompt
}
