# WinUAE overlay: sources and licences

Rebuild:

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/winuae/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/winuae/winuae.yaml --preview /tmp/winuae_preview
```

## Shortcuts

From the first key table in `od-win32/keyboard_win32.cpp`
(<https://github.com/tonioni/WinUAE>, master, read 2026-11-06). WinUAE's own
shortcuts mostly use End as a qualifier (End+F1 inserts a disk in DF0, End+F6
opens the state dialog). End is not a modifier the keyboard can show, so only
the keys that need no End are drawn:

| key | action |
|---|---|
| F12 | open the GUI (`INPUTEVENT_SPC_ENTERGUI`; F12 is the default GUI key) |
| Shift+F12 | debugger |
| Ctrl+F12 | switch between full screen and window (`INPUTEVENT_SPC_TOGGLEDEFAULTSCREEN`) |
| Page Up | cartridge freeze |
| Print Screen | screenshot to the clipboard |
| Pause | pause |

## Icons

Microsoft Fluent UI System Icons (MIT): `screenshot`. The others are Material
Symbols (Apache-2.0). Both are compatible with GPL-3.0-or-later.

## ESC mark

A drawn "WU" tile (`program_marks.ensure`).

## Process names

`winuae.exe` and `winuae64.exe`. Not checked on a running install.
