# Signal Desktop overlay: sources

`scripts/generate_app_overlays.py` renders `bindings.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `signal_template` (2 files) | Windows |
| `signal_template_linux` (2 files) | Linux. It differs from Windows only in Redo (Ctrl+Shift+Z, not Ctrl+Y) |
| `signal_template_mac` (3 files) | macOS |

## App names

`signal` (Windows `Signal.exe`, the macOS app "Signal", the Linux WM_CLASS
`signal`), `signal-desktop` (the Linux package and Snap command) and
`org.signal.signal` (the Flatpak app id, which Wayland readers report). These
come from the Signal Desktop packages and the Flathub listing; none was checked
on an install.

## Shortcut references

Signal Desktop is open source (signalapp/Signal-Desktop, AGPL-3.0). Every key
comes from its own source, `main` branch, read 2026-11-05:

- `ts/components/ShortcutGuide.dom.tsx`, the in-app keyboard shortcut guide
  (Ctrl+/). Its modifier tokens: `commandOrCtrl` is Cmd on macOS and Ctrl
  elsewhere (`CMDCTRL`); `optionOrAlt` is Option or Alt (`ALT`); `ctrlOrAlt` is
  Ctrl on macOS and Alt elsewhere, used by the call keys. The context menu is
  Shift+F10, and Cmd+F12 on macOS (`keysByPlatform`).
- `app/menu.std.ts`, the menu: Settings (Ctrl+,), Reset zoom / Zoom in / Zoom
  out (Ctrl+0 / Ctrl+= / Ctrl+-), Keyboard shortcuts (Ctrl+/), and on macOS
  Close window (Cmd+W). Undo, Redo, Cut, Copy, Paste, Select all and Full screen
  are Electron menu roles with no accelerator in Signal's source, so they take
  Electron's defaults: Redo is Ctrl+Y on Windows and Ctrl+Shift+Z elsewhere,
  Full screen is F11, and Ctrl+Cmd+F on macOS.

### Left out

- Enter (send), Shift+Enter (new line) and Up (edit last message): plain text
  keys in the composer.
- Shift+M, Shift+V, Shift+P and Shift+H (mute, camera, preview, raise hand):
  they act only during a call, and in the chat window Shift plus a letter types
  a capital letter.
- macOS Cmd+M (minimize), Cmd+Shift+0 (show the main window), Cmd+Q and the
  other app-menu roles: system keys that the keyboard's own hints cover.
- The debug log and developer tools menu items: no key.

## Icons

| Icon | Source | Licence |
|---|---|---|
| shortcut icons (see `FLUENT` in `fetch_icons.py`) | Microsoft Fluent UI System Icons, <https://github.com/microsoft/fluentui-system-icons> | MIT |
| `chatmenu`, `unread`, `latest`, `searchchat`, `unarchive`, `top`, `bottom`, `contextmenu`, `noattach`, `zoomreset` (`ms:` names) | Google Material Symbols, <https://github.com/google/material-design-icons> | Apache-2.0 |
| `chat1` .. `chat9` | Fluent `Chat Empty` with a Liberation Sans Bold digit (`../number_badge.py`) | MIT / SIL OFL 1.1 |
| `signal.png` (ESC program mark) | Simple Icons `signal`, <https://github.com/simple-icons/simple-icons> (`../brand_marks.py`) | CC0-1.0 |

### The program mark

Signal's own logo in the Signal-Desktop repo is under AGPL-3.0. GPLv3 §13
allows a GPL-3.0-or-later work to be combined with AGPLv3 code, but the mark is
taken from Simple Icons instead, where the same monochrome artwork is CC0-1.0,
so no AGPL file is in this repo. CC0 grants no trademark rights: the basis is
nominative use, the mark names the app this overlay is for, unchanged and with
no endorsement implied (the same basis as the other `brand_marks` logos).
Signal publishes no brand guideline that forbids this use that was found.
