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

# Codex replaces the console title with its own, and its default title does
# not name it. With the Codex option the installed line sets
# $global:PolyKybdTitleCodex, and this wraps the command so that Codex's title
# starts with "codex". A codex alias or function of your own is kept, and so
# is a terminal_title you set in Codex's config.toml. The TOML array uses
# single quotes: Windows PowerShell 5.1 drops double quotes inside arguments
# to native programs.
if ($global:PolyKybdTitleCodex -and
    -not (Get-Command codex -CommandType Function, Alias -ErrorAction SilentlyContinue)) {
    function global:codex {
        $exe = Get-Command codex -CommandType Application, ExternalScript -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if (-not $exe) { Write-Error 'codex was not found on PATH'; return }
        $dir = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
        $cfg = Join-Path $dir 'config.toml'
        if ((Test-Path -LiteralPath $cfg) -and
            (Select-String -LiteralPath $cfg -Pattern '^\s*(tui\.)?terminal_title\s*=' -Quiet)) {
            & $exe.Source @args
        } else {
            & $exe.Source -c "tui.terminal_title=['app-name','activity','thread-name','project-name']" @args
        }
    }
}
