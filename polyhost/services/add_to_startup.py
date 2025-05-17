import platform
import os
import sys
import shlex
import subprocess
from pathlib import Path

def is_frozen():
    """Detect if running in PyInstaller bundle or similar."""
    return getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS')

def is_venv():
    """Detect if we are running inside a virtual environment."""
    return (
        hasattr(sys, 'real_prefix') or
        (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    )

def create_windows_bat_wrapper(venv_path, script_path, args="", wrapper_path=None):
    venv_path = Path(venv_path)
    script_path = Path(script_path)
    if wrapper_path is None:
        wrapper_path = script_path.parent / "start_polyhost.bat"

    activate_bat = venv_path / "Scripts" / "activate.bat"

    bat_content = f"""@echo off
call "{activate_bat}"
cd "{script_path.parent.parent}"
python -m polyhost {args}
"""

    wrapper_path.write_text(bat_content, encoding="utf-8")
    print(f"Windows wrapper script created at: {wrapper_path}")
    return wrapper_path

def create_unix_shell_wrapper(venv_path, script_path, args="", wrapper_path=None):
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

    wrapper_path.write_text(shell_content, encoding="utf-8")
    wrapper_path.chmod(0o755)
    print(f"Unix shell wrapper script created at: {wrapper_path}")
    return wrapper_path

def create_windows_shortcut_powershell(target_path, shortcut_path, working_dir=None):
    # Use PowerShell to create a shortcut without pywin32 dependency
    if working_dir is None:
        working_dir = Path(target_path).parent
    else:
        working_dir = Path(working_dir)

    target_path = Path(target_path).resolve()
    shortcut_path = Path(shortcut_path).resolve()

    ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{target_path}"
$Shortcut.WorkingDirectory = "{working_dir}"
$Shortcut.WindowStyle = 7
$Shortcut.Save()
'''

    # Run the PowerShell script
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        capture_output=True,
        text=True,
    )
    if completed.returncode == 0:
        print(f"Shortcut created at: {shortcut_path}")
    else:
        print(f"Failed to create shortcut. PowerShell output:\n{completed.stderr}")

def add_to_startup(wrapper_path, app_name):
    system = platform.system()
    wrapper_path = Path(wrapper_path)

    if system == "Windows":
        startup_dir = Path(os.getenv("APPDATA")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        startup_dir.mkdir(parents=True, exist_ok=True)
        shortcut_path = startup_dir / f"{app_name}.lnk"
        create_windows_shortcut_powershell(wrapper_path, shortcut_path, wrapper_path.parent)

    elif system == "Linux":
        autostart_dir = Path.home() / ".config" / "autostart"
        autostart_dir.mkdir(parents=True, exist_ok=True)
        desktop_file = autostart_dir / f"{app_name}.desktop"
        content = f"""[Desktop Entry]
Type=Application
Exec={shlex.quote(str(wrapper_path.resolve()))}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name={app_name}
"""
        desktop_file.write_text(content)
        desktop_file.chmod(0o755)
        print(f"Startup desktop entry created at: {desktop_file}")

    elif system == "Darwin":
        plist_path = Path.home() / "Library" / "LaunchAgents" / f"com.{app_name}.plist"
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
</dict>
</plist>
"""
        plist_path.write_text(plist_content)
        subprocess.run(["launchctl", "load", str(plist_path)], check=False)
        print(f"Startup plist created and loaded at: {plist_path}")

    else:
        print(f"Unsupported OS: {system}")

def setup_autostart_for_app(script_path, args):
    """
    If inside venv: create wrapper to activate venv and run script,
    else just run script directly.
    Then add to autostart.
    """
    script_path = Path(script_path).resolve()
    args = [a.strip() for a in args]
    joined_args = " ".join(shlex.quote(a.strip()) for a in args)

    if is_frozen():
        # Running from PyInstaller exe, just add the exe itself to startup
        execute_this = Path(sys.executable).resolve()
        if len(args)>0:
            execute_this = f'"{execute_this}" {joined_args}'

        print(f"Detected PyInstaller bundle: {execute_this}")

    elif is_venv():
        venv_path = Path(sys.prefix).resolve()  # current venv root
        system = platform.system()
        if system == "Windows":
            execute_this = create_windows_bat_wrapper(venv_path, script_path, joined_args)
            print(f"Windows venv wrapper created at: {execute_this}")
        else:
            execute_this = create_unix_shell_wrapper(venv_path, script_path, joined_args)
            print(f"Unix venv wrapper created at: {execute_this}")
    else:
        # Not in venv — just autostart python with script directly
        python_exe = Path(sys.executable).resolve()
        # Construct a simple wrapper script or shortcut that runs python script directly
        # For simplicity create a minimal wrapper script anyway:

        if platform.system() == "Windows":
            # Simple .bat that calls python with script
            execute_this = script_path.parent / "start_polyhost.bat"
            content = f'@echo off\n"{python_exe}" "{script_path}" {joined_args}\n'
            execute_this.write_text(content, encoding="utf-8")
            print(f"Windows simple wrapper created at: {execute_this}")
        else:
            execute_this = script_path.parent / "start_polyhost.sh"
            content = f'#!/bin/bash\n"{python_exe}" "{script_path}" {joined_args}\n'
            execute_this.write_text(content, encoding="utf-8")
            execute_this.chmod(0o755)
            print(f"Unix simple wrapper created at: {execute_this}")

    add_to_startup(execute_this, "PolyHost")

