import platform
import os
import sys
import shlex
import subprocess
from pathlib import Path

# Name used for the autostart entry across all mechanisms (scheduled task,
# Startup-folder shortcut, .desktop file, launchd plist).
APP_NAME = "PolyHost"

def is_frozen():
    """Detect if running in PyInstaller bundle or similar."""
    return getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS')

def is_venv():
    """Detect if we are running inside a virtual environment."""
    return (
        hasattr(sys, 'real_prefix') or
        (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    )

def _icon_path():
    """Absolute path to the platform-appropriate tray/app icon."""
    icon_path = os.path.join(Path(__file__).parent.parent.resolve(), "res", "icons")
    if platform.system() == "Darwin":
        return os.path.join(icon_path, "pcolor.icns")
    if platform.system() == "Windows":
        return os.path.join(icon_path, "pcolor.ico")
    return os.path.join(icon_path, "pcolor.png")

# ---------------------------------------------------------------------------
# Windows helpers
# ---------------------------------------------------------------------------

def _win_quote_args(args):
    """Join CLI args into a single Windows command-line string.

    Note: ``shlex.quote`` always uses POSIX rules (single quotes), which is
    wrong on Windows, so we do our own minimal double-quote wrapping.
    """
    out = []
    for a in args:
        a = str(a)
        if a == "" or any(c in a for c in ' \t"'):
            out.append('"' + a.replace('"', '\\"') + '"')
        else:
            out.append(a)
    return " ".join(out)

def _win_user():
    """Return ``DOMAIN\\user`` (or bare user) for the current account."""
    domain = os.getenv("USERDOMAIN") or os.getenv("COMPUTERNAME") or ""
    user = os.getenv("USERNAME") or ""
    return f"{domain}\\{user}" if domain else user

def _no_window_kwargs():
    """Popen/run kwargs that suppress a console window for a child console
    program (powershell, schtasks) on Windows.

    The tray GUI is launched with ``pythonw.exe``, which has **no console of
    its own**. When such a process spawns a console program, Windows allocates a
    brand-new console window for the child — so every PowerShell/schtasks call
    made during autostart setup flashed a visible terminal (the user-reported
    "two terminals open and close"). CREATE_NO_WINDOW runs them windowless.
    No-op off Windows (the flag doesn't exist there)."""
    if sys.platform == "win32":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}

def _run_powershell(ps_script):
    """Run a PowerShell snippet, returning the CompletedProcess.

    ``-WindowStyle Hidden`` / ``-NonInteractive`` belt-and-suspenders the
    CREATE_NO_WINDOW creationflag: powershell.exe can still briefly flash a
    console under a consoleless (pythonw) parent with CREATE_NO_WINDOW alone, so
    asking it to start hidden closes that gap (matches WindowsInputHelper)."""
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
         "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        capture_output=True,
        text=True,
        **_no_window_kwargs(),
    )

def _ps_single_quote(value):
    """Escape a value for embedding inside a PowerShell single-quoted string."""
    return str(value).replace("'", "''")

def _appdata_dir():
    """Roaming AppData dir, falling back to ~/AppData/Roaming if %APPDATA%
    is unset (rare, but avoids constructing Path(None))."""
    appdata = os.getenv("APPDATA")
    return Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"

def _windows_startup_lnk():
    """Path to the per-user Startup-folder shortcut (the autostart fallback)."""
    startup_dir = _appdata_dir() / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return startup_dir / f"{APP_NAME}.lnk"

def _windows_startmenu_lnk():
    """Path to the Start-menu shortcut (the manual launcher, not autostart)."""
    programs_dir = _appdata_dir() / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    return programs_dir / f"{APP_NAME}.lnk"

def register_windows_logon_task(execute, arguments, working_dir, task_name=APP_NAME):
    """Register a per-user, non-elevated "at log on" scheduled task.

    Runs in the current user's interactive context at *limited* (non-elevated)
    privilege, so it needs no admin rights and triggers no UAC prompt. Logon
    tasks are not subject to Explorer's Startup-folder/Run-key delay, so the
    app comes up noticeably earlier. Returns True on success, False if task
    creation was refused (e.g. Task Scheduler locked down by Group Policy).
    """
    user = _ps_single_quote(_win_user())
    execute = _ps_single_quote(execute)
    working_dir = _ps_single_quote(working_dir)
    task_name_q = _ps_single_quote(task_name)
    # PowerShell rejects an empty string for -Argument, so only include it when
    # there actually are arguments (the .bat launcher has none).
    arg_param = f" -Argument '{_ps_single_quote(arguments)}'" if arguments else ""

    ps = f"""
$ErrorActionPreference = 'Stop'
try {{
    $action = New-ScheduledTaskAction -Execute '{execute}'{arg_param} -WorkingDirectory '{working_dir}'
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User '{user}'
    $principal = New-ScheduledTaskPrincipal -UserId '{user}' -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)
    Register-ScheduledTask -TaskName '{task_name_q}' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
    exit 0
}} catch {{
    Write-Error $_
    exit 1
}}
"""
    completed = _run_powershell(ps)
    if completed.returncode == 0:
        print(f"Scheduled logon task '{task_name}' registered.")
        return True
    print("Could not register scheduled task (will fall back to Startup folder):\n"
          f"{(completed.stderr or completed.stdout).strip()}")
    return False

def windows_task_exists(task_name=APP_NAME):
    """Return True if a scheduled task with this name exists for the user."""
    completed = subprocess.run(
        ["schtasks", "/query", "/tn", task_name],
        capture_output=True, text=True,
        **_no_window_kwargs(),
    )
    return completed.returncode == 0

def unregister_windows_logon_task(task_name=APP_NAME):
    """Remove the scheduled task if present (no error if it doesn't exist)."""
    ps = (f"Unregister-ScheduledTask -TaskName '{_ps_single_quote(task_name)}' "
          "-Confirm:$false -ErrorAction SilentlyContinue")
    _run_powershell(ps)

def create_windows_shortcut_powershell(target_path, shortcut_path, working_dir, icon_path, arguments=""):
    """Create a .lnk shortcut via PowerShell (no pywin32 dependency).
    Returns True on success, False if PowerShell reported a failure.
    """
    if working_dir is None:
        working_dir = Path(target_path).parent
    else:
        working_dir = Path(working_dir)

    target_path = Path(target_path).resolve()
    shortcut_path = Path(shortcut_path).resolve()

    icon_line = f'$Shortcut.IconLocation = "{icon_path}"' if icon_path else ""

    ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{target_path}"
$Shortcut.Arguments = '{_ps_single_quote(arguments)}'
$Shortcut.WorkingDirectory = "{working_dir}"
{icon_line}
$Shortcut.WindowStyle = 7
$Shortcut.Save()
'''

    # Run the PowerShell script
    completed = _run_powershell(ps_script)
    if completed.returncode == 0:
        print(f"Shortcut created at: {shortcut_path}")
        return True
    print(f"Failed to create shortcut. PowerShell output:\n{completed.stderr}")
    return False

def create_windows_bat_wrapper(venv_path, script_path, args="", wrapper_path=None):
    """Create the proven venv-activating launcher.

    Activates the venv, cd's to the repo root and runs the app in the
    foreground. When triggered via autostart this .bat is launched windowless
    through wscript + a hidden .vbs (see ``create_windows_hidden_vbs``), so
    ``python`` runs inside that already-hidden console with no flash. (It does
    *not* spawn its own ``powershell -WindowStyle Hidden`` — that briefly
    creates a visible conhost window before hiding, which was the residual
    flash.)
    """
    venv_path = Path(venv_path)
    script_path = Path(script_path)
    if wrapper_path is None:
        wrapper_path = script_path.parent / "start_polyhost.bat"

    activate_bat = venv_path / "Scripts" / "activate.bat"

    # Use pythonw (no console subsystem) for the tray GUI so it never opens or
    # owns a console window — `python.exe` allocates one, and closing that window
    # kills the app (the user-reported "console opens, closing it drops the
    # connection"). The `call activate.bat` above keeps the venv Scripts dir on
    # PATH, so pythonw resolves — the documented "don't call pythonw WITHOUT
    # activation" regression doesn't apply here (we activate first).
    interp = "pythonw" if (venv_path / "Scripts" / "pythonw.exe").exists() else "python"

    bat_content = f"""@echo off
call "{activate_bat}"
cd "{script_path.parent.parent}"
{interp} -m polyhost {args}
"""

    wrapper_path.write_text(bat_content, encoding="utf-8")
    print(f"Windows wrapper script created at: {wrapper_path}")
    return wrapper_path

def _wscript_path():
    """Full path to wscript.exe (the windowless Windows Script Host)."""
    windir = os.getenv("WINDIR") or r"C:\Windows"
    return str(Path(windir) / "System32" / "wscript.exe")

def create_windows_hidden_vbs(bat_path, vbs_path=None):
    """Write a tiny VBScript that launches the .bat with a hidden window.

    Running the launcher via ``wscript.exe`` (which itself has no console)
    with window style 0 means no console window flashes at logon or on a
    manual launch, while the proven .bat launcher underneath is unchanged.
    """
    bat_path = Path(bat_path)
    if vbs_path is None:
        vbs_path = bat_path.with_name("start_polyhost_hidden.vbs")
    # In a VBScript double-quoted literal, embedded quotes are doubled ("").
    vbs_content = (
        'CreateObject("Wscript.Shell").Run '
        f'"cmd /c ""{bat_path}""", 0, False\r\n'
    )
    Path(vbs_path).write_text(vbs_content, encoding="utf-8")
    print(f"Windows hidden-launch script created at: {vbs_path}")
    return str(vbs_path)

def _windows_hidden_invocation(execute, arguments):
    """Wrap a .bat launcher so it runs without a console window.

    Returns the (execute, arguments) to actually register. For a .bat this is
    ``wscript.exe "<vbs>"``; a frozen exe is already windowless and returned
    unchanged.
    """
    if str(execute).lower().endswith(".bat"):
        vbs = create_windows_hidden_vbs(execute)
        return _wscript_path(), f'"{vbs}"'
    return execute, arguments

def _windows_launch_target(script_path, args):
    """Resolve (executable, arguments, working_dir) for launching on Windows.

    Uses the same proven launcher the app has always used (a venv-activating
    ``.bat`` wrapper, or the PyInstaller exe when frozen) — what changes vs.
    before is only *how* it is triggered: a logon scheduled task instead of a
    throttled Startup-folder shortcut. The launch mechanism itself is
    unchanged, so this can't regress whether the app actually starts.
    """
    win_args = _win_quote_args(args)
    repo_root = str(script_path.parent.parent)

    if is_frozen():
        execute = str(Path(sys.executable).resolve())
        return execute, win_args, str(Path(execute).parent)

    if is_venv():
        venv_path = Path(sys.prefix).resolve()
        wrapper = create_windows_bat_wrapper(venv_path, script_path, win_args)
        return str(wrapper), "", repo_root

    # System Python (no venv): run the package as a module from the repo root
    # (`-m polyhost`, not the script by path — the latter breaks `polyhost.*`
    # imports because the package dir, not its parent, lands on sys.path).
    python_exe = Path(sys.executable).resolve()
    # Prefer pythonw.exe (no console window) for the tray GUI; fall back to
    # python.exe if it's somehow absent.
    launcher = python_exe.with_name("pythonw.exe")
    if not launcher.exists():
        launcher = python_exe
    wrapper = script_path.parent / "start_polyhost.bat"
    content = f'@echo off\ncd "{repo_root}"\n"{launcher}" -m polyhost {win_args}\n'
    wrapper.write_text(content, encoding="utf-8")
    print(f"Windows simple wrapper created at: {wrapper}")
    return str(wrapper), "", repo_root

def _install_windows_autostart(execute, win_args, working_dir, icon_path):
    """Install Windows autostart, preferring a logon task, falling back to a
    Startup-folder shortcut. Always (re)creates the Start-menu launcher.
    Returns a short string naming the mechanism actually in place.
    """
    startup_lnk = _windows_startup_lnk()
    startup_lnk.parent.mkdir(parents=True, exist_ok=True)

    # Run the launcher windowless (wscript + hidden .vbs for a .bat) so no
    # console flashes — at logon or on a manual launch.
    run_exec, run_args = _windows_hidden_invocation(execute, win_args)

    # Convenience Start-menu entry for manual launching (not autostart).
    startmenu_lnk = _windows_startmenu_lnk()
    startmenu_lnk.parent.mkdir(parents=True, exist_ok=True)
    create_windows_shortcut_powershell(run_exec, startmenu_lnk, working_dir, icon_path, run_args)

    if register_windows_logon_task(run_exec, run_args, working_dir):
        # Remove any stale Startup-folder shortcut to avoid a double launch.
        if startup_lnk.exists():
            startup_lnk.unlink()
        return "scheduled task (at logon)"

    # Fallback: Startup-folder shortcut (needs no special rights).
    if create_windows_shortcut_powershell(run_exec, startup_lnk, working_dir, icon_path, run_args):
        return "Startup folder shortcut (fallback)"
    return "none"  # both the task and the fallback shortcut failed

# ---------------------------------------------------------------------------
# Unix / macOS helpers (wrapper-script based)
# ---------------------------------------------------------------------------

def _write_executable_if_changed(path, content):
    """Write `content` to `path` (mode 0755) only if it differs from what's
    already there. Rewriting the launcher on every startup changes the file a
    registered macOS LaunchAgent points at, which makes macOS re-fire its
    "Background Items Added" notification each launch — so leave it untouched
    when nothing changed."""
    path = Path(path)
    try:
        if path.read_text(encoding="utf-8") == content:
            return False
    except OSError:
        pass
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)
    return True


def create_unix_shell_wrapper(venv_path, script_path, args="", wrapper_path=None):
    """Create a shell launcher that activates the venv and runs the app."""
    venv_path = Path(venv_path)
    script_path = Path(script_path)
    if wrapper_path is None:
        wrapper_path = script_path.parent / "start_polyhost.sh"

    activate_sh = venv_path / "bin" / "activate"

    shell_content = f"""#!/bin/bash
source "{activate_sh}"
cd "{script_path.parent.parent}"
python -m polyhost {args}
"""

    if _write_executable_if_changed(wrapper_path, shell_content):
        print(f"Unix shell wrapper script created at: {wrapper_path}")
    return wrapper_path

def create_linux_shortcut_desktop(app_name, autostart_dir, wrapper_path, icon_path):
    """Write a freedesktop .desktop entry pointing at the launcher wrapper."""
    desktop_file = autostart_dir / f"{app_name}.desktop"
    content = f"""[Desktop Entry]
Type=Application
Exec={shlex.quote(str(wrapper_path.resolve()))}
Hidden=false
NoDisplay=false
Icon={icon_path or ''}
X-GNOME-Autostart-enabled=true
Name={app_name}
"""
    desktop_file.write_text(content)
    desktop_file.chmod(0o755)
    print(f"Startup desktop entry created at: {desktop_file}")

def _linux_autostart_files(app_name=APP_NAME):
    """The .desktop files this app writes (autostart dir + applications dir)."""
    return [
        Path.home() / ".config" / "autostart" / f"{app_name}.desktop",
        Path.home() / ".local" / "share" / "applications" / f"{app_name}.desktop",
    ]

def _macos_plist_path(app_name=APP_NAME):
    """Path to this app's launchd LaunchAgent plist."""
    return Path.home() / "Library" / "LaunchAgents" / f"com.{app_name}.plist"

def add_to_startup(wrapper_path, app_name, icon_path):
    """Register autostart on Linux/macOS (Windows is handled separately)."""
    system = platform.system()
    wrapper_path = Path(wrapper_path)

    if system == "Linux":
        autostart_dir = Path.home() / ".config" / "autostart"
        autostart_dir.mkdir(parents=True, exist_ok=True)
        create_linux_shortcut_desktop(app_name, autostart_dir, wrapper_path, icon_path)
        autostart_dir = Path.home() / ".local" / "share" / "applications"
        autostart_dir.mkdir(parents=True, exist_ok=True)
        create_linux_shortcut_desktop(app_name, autostart_dir, wrapper_path, icon_path)

    elif system == "Darwin":
        plist_path = _macos_plist_path(app_name)
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
"http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.{app_name}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{str(wrapper_path.resolve())}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>CFBundleIconFile</key>
    <string>{icon_path}</string>
</dict>
</plist>
"""
        # Idempotent: if an identical plist is already loaded, do nothing.
        # Rewriting the plist and re-running `launchctl load` on every launch
        # re-registers the login item, which makes macOS (Ventura+) pop up
        # "Background Items Added" each time. Only touch it when it's missing or
        # its content actually changed (e.g. the wrapper path moved).
        try:
            already = plist_path.read_text()
        except OSError:
            already = None
        if already == plist_content:
            print(f"Startup plist already up to date: {plist_path}")
            return
        # ~/Library/LaunchAgents does not exist on a fresh macOS account until
        # the first LaunchAgent is installed; write_text() would raise
        # FileNotFoundError otherwise (seen in the field on a clean install).
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        # Unload an existing (stale) definition first so launchd picks up the
        # new content cleanly instead of keeping the old registration.
        if already is not None:
            subprocess.run(["launchctl", "unload", str(plist_path)], check=False)
        plist_path.write_text(plist_content)
        subprocess.run(["launchctl", "load", str(plist_path)], check=False)
        print(f"Startup plist created and loaded at: {plist_path}")

    else:
        print(f"Unsupported OS: {system}")

# ---------------------------------------------------------------------------
# Status / removal (cross-platform)
# ---------------------------------------------------------------------------

def get_autostart_status(app_name=APP_NAME):
    """Return a human-readable description of what autostart entry, if any, is
    currently registered for this app. Useful to verify which mechanism is in
    place after an upgrade.
    """
    system = platform.system()
    found = []
    if system == "Windows":
        # Reports autostart mechanisms only — the Start-menu shortcut is a
        # manual launcher, not autostart, so it is intentionally not listed.
        if windows_task_exists(app_name):
            found.append("scheduled task (at logon)")
        startup_lnk = _windows_startup_lnk()
        if startup_lnk.exists():
            found.append(f"Startup folder shortcut ({startup_lnk})")
    elif system == "Linux":
        for f in _linux_autostart_files(app_name):
            if f.exists():
                found.append(f"desktop entry ({f})")
    elif system == "Darwin":
        plist = _macos_plist_path(app_name)
        if plist.exists():
            found.append(f"launchd plist ({plist})")

    if not found:
        return "none"
    return ", ".join(found)

def remove_autostart(app_name=APP_NAME):
    """Remove any autostart entry this app may have registered (all mechanisms).
    Safe to call when nothing is installed.
    """
    system = platform.system()
    if system == "Windows":
        unregister_windows_logon_task(app_name)
        # Remove both the autostart Startup-folder shortcut and the manual
        # Start-menu launcher so teardown leaves nothing behind.
        for lnk in (_windows_startup_lnk(), _windows_startmenu_lnk()):
            if lnk.exists():
                lnk.unlink()
                print(f"Removed shortcut: {lnk}")
    elif system == "Linux":
        for f in _linux_autostart_files(app_name):
            if f.exists():
                f.unlink()
                print(f"Removed desktop entry: {f}")
    elif system == "Darwin":
        plist = _macos_plist_path(app_name)
        if plist.exists():
            subprocess.run(["launchctl", "unload", str(plist)], check=False)
            plist.unlink()
            print(f"Removed launchd plist: {plist}")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def setup_autostart_for_app(script_path, args):
    """Register the app to start automatically at login.

    Windows: a non-elevated "at log on" scheduled task (falling back to a
    Startup-folder shortcut) that triggers the proven venv-activating launcher
    earlier than the throttled Startup folder would.
    Linux/macOS: a venv-activating wrapper script referenced from the
    autostart directory / launchd. Returns a string describing the mechanism
    that ended up in place.
    """
    script_path = Path(script_path).resolve()
    args = [a.strip() for a in args]
    icon_path = _icon_path()

    if platform.system() == "Windows":
        execute, win_args, working_dir = _windows_launch_target(script_path, args)
        if is_frozen():
            print(f"Detected PyInstaller bundle: {execute} {win_args}")
        method = _install_windows_autostart(execute, win_args, working_dir, icon_path)
        print(f"Autostart in place: {method}")
        return method

    # Unix / macOS: wrapper-script based.
    joined_args = " ".join(shlex.quote(a) for a in args)
    if is_frozen():
        execute_this = Path(sys.executable).resolve()
        print(f"Detected PyInstaller bundle: {execute_this}")
    elif is_venv():
        venv_path = Path(sys.prefix).resolve()
        execute_this = create_unix_shell_wrapper(venv_path, script_path, joined_args)
        print(f"Unix venv wrapper created at: {execute_this}")
    else:
        # Run the package as a module from the repo root (`-m polyhost`, not
        # the script by path — the latter breaks `polyhost.*` imports).
        python_exe = Path(sys.executable).resolve()
        execute_this = script_path.parent / "start_polyhost.sh"
        content = (f'#!/bin/bash\ncd "{script_path.parent.parent}"\n'
                   f'"{python_exe}" -m polyhost {joined_args}\n')
        if _write_executable_if_changed(execute_this, content):
            print(f"Unix simple wrapper created at: {execute_this}")

    add_to_startup(execute_this, APP_NAME, icon_path)
    status = get_autostart_status()
    print(f"Autostart in place: {status}")
    return status
