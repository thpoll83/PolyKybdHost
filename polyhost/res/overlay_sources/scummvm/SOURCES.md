# ScummVM overlay: sources and licences

Rebuild:

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/scummvm/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/scummvm/scummvm.yaml --preview /tmp/scummvm_preview
```

Both steps are deterministic. The action icons are fetched from unpinned branches,
so a change there changes the PNG bytes. The ESC mark is fetched from the pinned
release tag and is left as it is once committed.

## What the set loads for

| name | where it comes from |
|---|---|
| `scummvm` | `Exec=scummvm` and `StartupWMClass=scummvm` in `dists/org.scummvm.scummvm.desktop`; `scummvm.exe` on Windows; the macOS app `ScummVM` |
| `org.scummvm.scummvm` | the Flatpak id `org.scummvm.ScummVM` |

Names not checked on an install.

## Shortcuts

ScummVM (<https://github.com/scummvm/scummvm>), tag `v2.9.1`, read 2026-11-14:

- `backends/events/default/default-events.cpp`, `DefaultEventManager::getGlobalKeymap()`:
  the "Global" keymap.
- `backends/graphics/sdl/sdl-graphics.cpp`, `SdlGraphicsManager::getKeymap()`: the
  graphics keymap of the SDL builds (Windows, Linux, macOS).
- `doc/docportal/use_scummvm/keyboard_shortcuts.rst` lists the same keys.

In the source `C+` is Ctrl, `A+` is Alt and `M+` is the Command key. The same
chords are in tag `v2026.4.0`, which adds Ctrl+R (resizable window).

| key | action id | drawn as |
|---|---|---|
| Ctrl+F5 | `MENU` | Global main menu |
| Ctrl+U | `MUTE` | Mute |
| Ctrl+Q (Linux), Ctrl+Z and Alt+F4 (Windows), Cmd+Q (macOS) | `QUIT` | Quit |
| Ctrl+Alt+D | `DEBUGGER` | Open debugger |
| Alt+Enter | `FULS` | Full screen |
| Ctrl+M | `CAPT` | Capture mouse |
| Alt+S | `SCRS` | Screenshot |
| Ctrl+Alt+A | `ASPT` | Aspect ratio correction |
| Ctrl+Alt+F | `FILT` | Linear filtering |
| Ctrl+Alt+S | `STCH` | Next stretch mode |
| Ctrl+Alt+- | `SCL-` | Decrease scale factor |
| Ctrl+Alt+0 / Ctrl+Alt+9 | `FLTN` / `FLTP` | Next / previous scaler |
| Esc | `SKIP` (in a game), `CLOS` (in a dialog) | the ScummVM mark |

The quit chord is chosen at build time (`MACOSX`, `POSIX`, else), so the set has a
Windows, a Linux and a macOS version that differ only in that key.

## Left out

| key | action | reason |
|---|---|---|
| Ctrl+Alt+Plus | `SCL+`, increase the scale factor | The default is the key that sends `PLUS`, and the keypad plus. A US layout has no unshifted plus key, and the keypad has no keycap cell. |
| Ctrl+F7 | `VIRT`, display keyboard | Only in a build with the virtual keyboard. |
| F5, Space, `.`, Enter | game menu, pause, skip line, confirm (`engines/metaengine.cpp`) | The default game keymap. It applies only to an engine without its own keymap, and many engines replace it. |
| the keys of each game | verbs, inventory, movement | They are defined per engine and differ per game. |
| Ctrl+A, Ctrl+E, Ctrl+C, Ctrl+V, Ctrl+X | the text field keys of `gui/gui-manager.cpp` | They act only while a text field of the launcher has the focus. |

## Icons

| file | source | licence |
|---|---|---|
| `menu.png`, `debugger.png`, `fullscreen.png`, `grabmouse.png`, `aspect.png`, `filter.png`, `stretch.png`, `scaledown.png`, `scalernext.png`, `scalerprev.png` | Material Symbols (`google/material-design-icons`), names in `fetch_icons.py` | [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0) |
| `mute.png` (Speaker Mute), `screenshot.png` (Camera), `quit.png` (Sign Out) | Microsoft Fluent UI System Icons (`microsoft/fluentui-system-icons`) | [MIT](https://github.com/microsoft/fluentui-system-icons/blob/main/LICENSE) |
| `scummvm.png` | ScummVM's own icon, `icons/scummvm.svg` at tag `v2.9.1`, cut to 1 bit by `pad_keys.logo_mark()` | [GPL-3.0-or-later](https://github.com/scummvm/scummvm/blob/v2.9.1/COPYING) |

The same action has the same icon as in the RetroArch and MAME sets (menu, mute,
full screen, screenshot, capture mouse, next and previous).

## The ESC mark

ScummVM is licensed under GPL-3.0-or-later: `COPYING` is the GPL version 3, and
the source headers say "either version 3 of the License, or (at your option) any
later version". `icons/scummvm.svg` has no licence of its own, so the project
licence applies, and it is compatible with this repository's GPL-3.0-or-later.
The icon is a yellow-green "S" with a dark outline. The mark lights the bright
pixels, which gives the S alone, 25 x 32 px.
