# DuckStation overlay: sources and licences

Rebuild:

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/duckstation/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/duckstation/duckstation.yaml --preview /tmp/duckstation_preview
```

Both steps are deterministic. The action icons are fetched from unpinned branches,
so a change there changes the PNG bytes.

## DuckStation's licence

DuckStation changed its licence from GPL-3.0 to CC BY-NC-ND 4.0 in 2024. At tag
`v0.1-12442` the `LICENSE` file is "Attribution-NonCommercial-NoDerivatives 4.0
International" and the source headers carry `SPDX-License-Identifier:
CC-BY-NC-ND-4.0`. That licence is not compatible with this repository's
GPL-3.0-or-later, so:

- Only the default keys were read from the source. Which key does what is a
  fact, and facts are not covered by copyright.
- No DuckStation art, icon, logo or text is copied into this repository. The
  action names in the table below are written here, not taken from its
  translation strings.
- The ESC mark is the name "Duck" / "Station" set in an open font. The name is
  used only to identify the program this set is for.

## What the set loads for

| name | where it comes from |
|---|---|
| `duckstation-qt` | `add_executable(duckstation-qt ...)` in `src/duckstation-qt/CMakeLists.txt` (Linux, AppImage) |
| `duckstation-qt-x64-releaseltcg`, `duckstation-qt-arm64-releaseltcg` | the Windows release executable `duckstation-qt-x64-ReleaseLTCG.exe` named in `README.md`, and its ARM64 form |
| `duckstation` | `OUTPUT_NAME DuckStation` for the macOS bundle |
| `org.duckstation.duckstation` | the Flatpak id `org.duckstation.DuckStation` named in `README.md` |

Names not checked on an install. The name of the ARM64 Windows executable is
formed after the x64 one and was not found in the source.

## Shortcuts

DuckStation (<https://github.com/stenzek/duckstation>), tag `v0.1-12442`, read
2026-11-14:

- `src/core/hotkeys.cpp`, `Settings::SetDefaultHotkeyConfig`: the hotkeys.
- `src/util/input_manager.cpp`, `InputManager::GetGenericBindingMapping`, device
  `Keyboard`: the keyboard map that `src/core/settings.cpp` gives controller 1.
  `DEFAULT_CONTROLLER_1_TYPE` in `src/core/settings.h` is the analog controller,
  so both sticks and L3 / R3 exist by default.

| key | hotkey | drawn as |
|---|---|---|
| Tab | `FastForward` | Fast-forward (hold) |
| Space | `TogglePause` | Pause |
| F10 | `Screenshot` | Screenshot |
| F11 | `ToggleFullscreen` | Full screen |
| F1 | `LoadSelectedSaveState` | Load state |
| F2 | `SaveSelectedSaveState` | Save state |
| F3 / F4 | `SelectPreviousSaveStateSlot` / `SelectNextSaveStateSlot` | Previous / next state slot |
| Esc | `OpenPauseMenu` | the mark |

| key | controller | drawn as |
|---|---|---|
| I, L, K, J | Triangle, Circle, Cross, Square | a ring with the shape |
| Q, 1, 2 | L1, L2, L3 | the name in a rounded outline |
| E, 3, 4 | R1, R2, R3 | the name in a rounded outline |
| Enter, Backspace | Start, Select | the START and SELECT pills |
| arrow keys | D-pad | the D-pad with that arm filled |
| W, S, A, D | left stick up, down, left, right | a ring with "L" and an arrow |
| T, G, F, H | right stick up, down, left, right | a ring with "R" and an arrow |

These are all the default hotkeys and all the default keyboard binds of
controller 1. Nothing is left out. The other hotkeys in `hotkeys.cpp` have no
default key.

## Icons

| file | source | licence |
|---|---|---|
| `ffhold.png`, `pause.png`, `fullscreen.png`, `slotminus.png`, `slotplus.png` | Material Symbols (`google/material-design-icons`), names in `fetch_icons.py` | [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0) |
| `loadstate.png` (Folder Open), `savestate.png` (Save), `screenshot.png` (Camera) | Microsoft Fluent UI System Icons (`microsoft/fluentui-system-icons`) | [MIT](https://github.com/microsoft/fluentui-system-icons/blob/main/LICENSE) |
| `triangle.png`, `circle.png`, `cross.png`, `square.png`, `dpad*.png` | drawn by `pad_keys.py` (`shape()`, `dpad()`) | the drawing is this repo's |
| `l1.png` … `r3.png`, `start.png`, `select.png`, `lstick*.png`, `rstick*.png` | drawn by `pad_keys.py` (`shoulder()`, `stick()`) and `retroarch/fetch_icons.py` (`pill()`); text in Press Start 2P by CodeMan38 (`google/fonts`, `ofl/pressstart2p`, pinned commit) | the drawing is this repo's; the font is [SIL OFL 1.1](https://openfontlicense.org/open-font-license-official-text/) |
| `program.png` | "Duck" / "Station" set in Russo One by Jovanny Lemonad (`google/fonts`, `ofl/russoone`, pinned commit), drawn by `pad_keys.wordmark()` | the font is [SIL OFL 1.1](https://openfontlicense.org/open-font-license-official-text/) |

The four face-button shapes are plain geometry drawn in `pad_keys.shape()`. No
Sony artwork is copied. The pad icons are the same files as in the PCSX2 set,
because both programs use the same keyboard map.

The same action has the same icon as in the RetroArch and MAME sets (save and load
state, next and previous slot, pause, fast-forward while held, full screen,
screenshot).
