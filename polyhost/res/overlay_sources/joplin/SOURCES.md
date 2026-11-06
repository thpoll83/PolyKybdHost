# Joplin desktop overlay: sources and licences

`gen_specs.py` writes `joplin.yaml` from its table; `fetch_icons.py` rebuilds
`icons/`; `scripts/generate_app_overlays.py` renders the PNGs.

| Set | Loads for | Keys |
|---|---|---|
| `joplin_template` (3 files) | Windows and Linux | 56 |
| `joplin_template_mac` (4 files) | macOS | 56 |

Each set also has Joplin's mark on ESC.

## App names

`joplin` (Windows `Joplin.exe` and the macOS app "Joplin", both from
electron-builder's `productName`; the Linux AppImage and .deb executable
`joplin`, from `build.linux.executableName`) and `net.cozic.joplin_desktop`
(the Flathub app id, which Wayland readers report). These come from
`packages/app-desktop/package.json` at tag v3.7.22 and the Flathub listing; none
was checked on an install.

## Shortcuts

Joplin is open source (laurent22/joplin, AGPL-3.0-or-later). Every key comes
from its source at tag **v3.7.22** (the newest desktop release, 2026-10-28; the
`dev` branch has the same keymap):

- `packages/lib/services/KeymapService.ts`, `defaultKeymapItems`: the `darwin`
  list for macOS and the `default` list, which Windows and Linux share. Users
  can change these in Tools > Options > Keyboard Shortcuts; the overlay draws
  the defaults.
- `packages/app-desktop/gui/MenuBar.tsx`: Actual Size (Ctrl+0), Zoom In
  (Ctrl+= and Ctrl+Plus, the same key) and Zoom Out (Ctrl+-), all
  `CommandOrControl`, and on macOS only the `togglefullscreen` role (Electron's
  default Ctrl+Cmd+F).

Keys that are the same chord with Ctrl on Windows/Linux and Cmd on macOS are one
`CMDCTRL` binding. Keys that differ are written once per platform:

| Action | Windows / Linux | macOS |
|---|---|---|
| Search all notes | F6 | Cmd+Shift+F |
| Toggle sidebar | F10 | Cmd+Option+S |
| Toggle note list | F11 | Cmd+Option+L |
| Toggle AI chat | Ctrl+Alt+I | Cmd+Shift+I |
| Redo | Ctrl+Y | Cmd+Shift+Z |
| Sort selected lines | Ctrl+Alt+S | Cmd+Option+A |
| Quit | Ctrl+Q | not drawn (see below) |
| Toggle menu bar | Ctrl+Shift+M | no key |
| Permanently delete note | no key | Cmd+Option+Backspace |
| Full screen | no key | Ctrl+Cmd+F |

Tab moves focus is Ctrl+M on every platform, literal Ctrl on macOS too.

### Left out

- macOS Cmd+H (hide), Cmd+Q (quit) and Cmd+M (minimize): system keys that the
  keyboard's own hints cover.
- The commands with no default key (`accelerator: null`), including Back and
  Forward in the Go menu.
- Plain editor keys (Enter, Tab, arrows) and the Markdown editor's CodeMirror
  defaults, which are not in Joplin's keymap.

## Icons

| Icon | Source | Licence |
|---|---|---|
| shortcut icons (see `ICONS` in `fetch_icons.py`) | Microsoft Fluent UI System Icons, <https://github.com/microsoft/fluentui-system-icons> | MIT |
| `focustoolbar` (`toolbar`), `togglenotelist` (`view_sidebar`) | Google Material Symbols, <https://github.com/google/material-design-icons> | Apache-2.0 |
| `profile1` .. `profile3` | Fluent `Person` with a Liberation Sans Bold digit beside it (`profiles()` in `fetch_icons.py`) | MIT / SIL OFL 1.1 |
| `joplin.png` (ESC program mark) | Simple Icons `joplin`, <https://github.com/simple-icons/simple-icons> (`../brand_marks.py`) | CC0-1.0 |

`fetch_icons.py` prints which source each glyph came from. Labels that name a
shared concept (Copy, Paste, Undo, Bold, ...) are drawn by the shared renderer
instead of the PNG in `icons/` (see the skill, "A label that NAMES a concept").

### The program mark

Joplin's own icon is in its repo under AGPL-3.0-or-later. The mark is taken
from Simple Icons instead, where the same monochrome artwork is CC0-1.0, so no
AGPL file is in this repo. CC0 grants no trademark rights: the basis is
nominative use, the mark names the app this overlay is for, unchanged and with
no endorsement implied (the same basis as the other `brand_marks` logos).
`fetch_icons.py` leaves a committed `joplin.png` as it is.
