# PolyHost

Host software for the **PolyKybd** keyboard. It tracks the active window and
pushes overlay / keymap / language updates to the keyboard over HID. It can
also run as a *forwarder* that relays window info from a remote machine to the
computer the keyboard is plugged into.

## Quick install (one line)

These commands clone the repo, create a virtual environment, install the Python
requirements, and (on Linux/macOS) set up the native hidapi library and HID
permissions.

By default the app is installed into a `PolyKybdHost/` folder **in the
directory you run the command from**. The installer prints this location and
lets you type a different one (press Enter to accept the default). To pick the
location up front without the prompt, set `POLYKYBD_DIR` first — e.g.
`POLYKYBD_DIR=~/apps/polykybd` (bash) or `$env:POLYKYBD_DIR="C:\Tools\PolyKybd"`
(PowerShell).

**Linux / macOS**

```bash
curl -fsSL https://raw.githubusercontent.com/thpoll83/PolyKybdHost/main/scripts/install.sh | bash
```

**Windows (PowerShell)**

```powershell
irm https://raw.githubusercontent.com/thpoll83/PolyKybdHost/main/scripts/install.ps1 | iex
```

Then start it:

```bash
# Linux / macOS
.venv/bin/python -m polyhost
```
```powershell
# Windows
.venv\Scripts\python.exe -m polyhost
```

> The installer scripts are plain and short — read them first if you prefer not
> to pipe a script into your shell. They live in [`scripts/`](scripts/).

## Manual install

```bash
git clone https://github.com/thpoll83/PolyKybdHost.git
cd PolyKybdHost
python -m venv .venv
# activate the venv:
#   Linux/macOS:  source .venv/bin/activate
#   Windows:      .\.venv\Scripts\activate
pip install -r requirements.txt
python -m polyhost
```

On the very first launch a small bootstrap (`polyhost/_bootstrap.py`) also
checks `requirements.txt` and installs anything still missing, so the app won't
crash with an `ImportError` if a dependency slipped through.

### Platform notes

- **Windows** — the native `hidapi.dll` ships in the repo
  (`polyhost/device/win-hidapi-0-15/`) and is loaded automatically. Nothing
  extra to install.
- **Linux** — install the native hidapi library and the udev rule for non-root
  HID access:
  ```bash
  sudo apt install libhidapi-hidraw0          # or: dnf install hidapi / pacman -S hidapi
  sudo cp polyhost/device/99-hid.rules /etc/udev/rules.d/
  sudo udevadm control --reload-rules && sudo udevadm trigger
  ```
  Replug the keyboard afterwards.
- **macOS** — `brew install hidapi`.

## Running

```bash
python -m polyhost                 # normal mode
python -m polyhost --debug 1       # debug logging
python -m polyhost --portable      # skip autostart registration
```

### Forwarder mode

Run with `--host` on a *remote* machine (no keyboard attached) to relay its
active-window info to the computer the keyboard is connected to:

```bash
python -m polyhost --host IP_ADDR_OF_HOST   # or a hostname
```

On the computer with the PolyKybd connected, run without parameters and name
the remote in `overlay-mapping.poly.yaml`:

```yaml
nxplayer:
  remote: IP_ADDR_OF_REMOTE   # or NAME_OF_REMOTE
```

## Autostart

On the first normal run PolyHost registers itself to start at login:

- **Windows** — a per-user **scheduled task** that triggers *at log on*,
  launching the venv windowless via `wscript` (no console flash). A logon task
  starts earlier than a Startup-folder shortcut, which Windows throttles. If
  Task Scheduler is locked down by policy, PolyHost falls back to a
  Startup-folder shortcut, so it still autostarts without admin rights.
- **Linux** — a `.desktop` autostart entry.
- **macOS** — a `launchd` agent.

The line `Autostart in place: ...` printed at startup tells you which mechanism
is active. Run with `--portable` to skip registration; if an entry already
exists from a previous run it is removed, so a portable run leaves nothing
behind.
