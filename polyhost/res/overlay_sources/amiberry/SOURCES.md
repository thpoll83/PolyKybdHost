# Amiberry overlay: sources and licences

Rebuild:

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/amiberry/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/amiberry/amiberry.yaml --preview /tmp/amiberry_preview
```

## Shortcuts

From <https://github.com/BlitterStudio/amiberry>, master at 7165b42
(2026-11-06; the latest release is v8.5.0):

| key | action | source |
|---|---|---|
| F12 | open the GUI | `enter_gui_key` falls back to F12 when `open_gui` is empty (`src/osdep/amiberry.cpp`) |
| Pause | Action Replay | `action_replay_key` falls back to Pause when `action_replay` is empty (same file) |
| Page Up | cartridge freeze | the key table in `src/osdep/keyboard.cpp` |

Quit, full screen, minimize and screenshot have no default key. The End+key
shortcuts are not drawn, because End is not a modifier the keyboard can show.

## Icons

Material Symbols (Apache-2.0), compatible with GPL-3.0-or-later.

## ESC mark

A drawn "AB" tile (`program_marks.ensure`).

## Process names

`amiberry` and `amiberry-lite` (the macOS application name `Amiberry` is
lower-cased by the matcher). Not checked on a running install.
