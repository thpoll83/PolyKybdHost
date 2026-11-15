# Dolphin overlay: sources and licences

Rebuild:

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/dolphin/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/dolphin/dolphin.yaml --preview /tmp/dolphin_preview
```

Both steps are deterministic. The icon sources are fetched from unpinned branches,
so a change there changes the PNG bytes. `fetch_icons.py` uses
`retroarch/fetch_icons.py` for the button rings and the START pill, and
`pad_keys.py` for the D-pad, the sticks and the numbered icons.

## What the set loads for

| name | where it comes from |
|---|---|
| `dolphin-emu` | the CMake target and `Exec=dolphin-emu` in `Data/dolphin-emu.desktop` (Linux) |
| `org.dolphinemu.dolphin-emu` | the Flatpak id in `Flatpak/org.DolphinEmu.dolphin-emu.yml` |
| `dolphin`, on Windows and macOS only | `OUTPUT_NAME Dolphin` for Windows in `Source/Core/DolphinQt/CMakeLists.txt` (`Dolphin.exe`), and the macOS app `Dolphin` |
| `dolphinqt` | `OUTPUT_NAME DolphinQt`, the executable inside the macOS bundle |

On Linux the process `dolphin` is the KDE file manager, so the `dolphin` entry in
the mapping has only a `windows` and a `macos` branch.
Names not checked on an install.

## Shortcuts

Dolphin (<https://github.com/dolphin-emu/dolphin>), tag `2609b`, read 2026-11-14:

- `Source/Core/Core/HotkeyManager.cpp`, `HotkeyManager::LoadDefaults`: the hotkeys.
- `Source/Core/Core/HW/GCPadEmu.cpp`, `GCPad::LoadDefaults`: the GameCube
  controller of port 1 on the keyboard.

| key | hotkey id | drawn as |
|---|---|---|
| Ctrl+O | `HK_OPEN` | Open |
| F10 | `HK_PLAY_PAUSE` | Play / pause |
| Esc | `HK_STOP` | the Dolphin mark |
| Alt+Enter | `HK_FULLSCREEN` | Full screen |
| Alt+A | `HK_OPEN_ACHIEVEMENTS` | Open achievements |
| F9 | `HK_SCREENSHOT` | Screenshot |
| Tab | `HK_TOGGLE_THROTTLE` | Disable speed limit (hold) |
| Alt+F5 to Alt+F8 | `HK_WIIMOTE1_CONNECT` to `HK_WIIMOTE4_CONNECT` | Connect Wii Remote 1 to 4 |
| Alt+F9 | `HK_BALANCEBOARD_CONNECT` | Connect Balance Board |
| F1 to F8 | `HK_LOAD_STATE_SLOT_1` to `_8` | Load state slot 1 to 8 |
| Shift+F1 to Shift+F8 | `HK_SAVE_STATE_SLOT_1` to `_8` | Save state slot 1 to 8 |
| F12 / Shift+F12 | `HK_UNDO_LOAD_STATE` / `HK_UNDO_SAVE_STATE` | Undo load state / undo save state |

| key | GameCube control | drawn as |
|---|---|---|
| X, Z, C, S, D | buttons A, B, X, Y, Z | a ring with the letter |
| Q, W | triggers L, R | a ring with the letter |
| Enter | Start | the START pill |
| T, G, F, H | D-pad up, down, left, right | the D-pad with that arm filled |
| I, K, J, L | C stick up, down, left, right | a ring with "C" and an arrow |
| arrow keys | control stick up, down, left, right | a ring with a dot and an arrow |

`HK_OPEN_ACHIEVEMENTS` exists only in a build with RetroAchievements
(`USE_RETRO_ACHIEVEMENTS`), which the official builds have.

## Left out

| key | action | reason |
|---|---|---|
| F11, Shift+F10, Shift+F11, Shift+F9 | step, step over, step out, toggle breakpoint | They act only while the debugger interface is on. |
| Ctrl+Shift+O, Ctrl+Shift+W, Ctrl+Shift+R, M | load, unload and reset the GBA ROM, GBA mute | They act only in the window of the integrated Game Boy Advance. |
| keypad 1 to 4, keypad + and - | GBA window size and volume | Keypad keys have no keycap cell. |
| Ctrl+P, Ctrl+I | Skylanders portal, Infinity base | Each opens the manager of one accessory, used by a few games. |
| 1, 2, 3 | Triforce test, service, coin | Only for Triforce arcade games. |
| Shift, Ctrl | control stick modifier, C stick modifier (half tilt) | Modifier keys. Holding one would also change the layer the keycaps show. |
| the emulated Wii Remote | `WiimoteEmu.cpp`: 1, 2, Q (-), E (+), Enter (Home), arrow keys (D-pad), mouse buttons (A, B) | A Wii game uses these instead of the GameCube controller, and Q, Enter and the arrow keys then press other buttons. The host cannot tell which console the game is for, so the GameCube controller is drawn. |

## Icons

| file | source | licence |
|---|---|---|
| `pause.png`, `fullscreen.png`, `ffhold.png`, `achievements.png`, `undoload.png`, `undosave.png`, `balance.png` | [Material Symbols](https://github.com/google/material-design-icons), names in `fetch_icons.py` | [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0) |
| `open.png` (Folder Open), `screenshot.png` (Camera) | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | [MIT](https://github.com/microsoft/fluentui-system-icons/blob/main/LICENSE) |
| `load1.png` … `load8.png`, `save1.png` … `save8.png` | Fluent "Folder Open" and "Save" with the slot number, composed by `pad_keys.numbered()`; the digit in Press Start 2P by CodeMan38 (`google/fonts`, `ofl/pressstart2p`, pinned commit) | MIT; the font is [SIL OFL 1.1](https://openfontlicense.org/open-font-license-official-text/) |
| `wiimote1.png` … `wiimote4.png` | Material Symbols `settings_remote` with the number, composed the same way | Apache-2.0; the font is SIL OFL 1.1 |
| `gca.png` … `gcr.png`, `gcstart.png`, `dpad*.png`, `stick*.png`, `cstick*.png` | drawn by `retroarch/fetch_icons.py` (`ring()`, `pill()`) and `pad_keys.py` (`dpad()`, `stick()`); text in Press Start 2P | the drawing is this repo's; the font is SIL OFL 1.1 |
| `dolphin.png` | Simple Icons `dolphin` (`simple-icons/simple-icons`) | [CC0-1.0](https://creativecommons.org/publicdomain/zero/1.0/) artwork; used to identify Dolphin, no endorsement implied |

The same action has the same icon as in the RetroArch and MAME sets (pause, full
screen, screenshot, fast-forward while held, save state, load state).

## The ESC mark

Dolphin's own source is "GPLv2+" and the repository as a whole is "compatible with
the GPLv3 license" (`COPYING`), so its logo (`Data/dolphin-emu.svg`) could be used
here. The mark is the same logo as a single path from Simple Icons, which is
CC0-1.0 and needs no cut from a colour gradient.
