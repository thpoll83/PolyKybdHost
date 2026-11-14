# PCSX2 overlay: sources and licences

Rebuild:

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/pcsx2/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/pcsx2/pcsx2.yaml --preview /tmp/pcsx2_preview
```

Both steps are deterministic. The action icons are fetched from unpinned branches,
so a change there changes the PNG bytes. The ESC mark is fetched from the pinned
release tag and is left as it is once committed.

## What the set loads for

| name | where it comes from |
|---|---|
| `pcsx2-qt` | `add_executable(pcsx2-qt)` in `pcsx2-qt/CMakeLists.txt`: `pcsx2-qt` on Linux, `pcsx2-qt.exe` on Windows; also the Flatpak `command` |
| `pcsx2` | the macOS app `PCSX2` |
| `net.pcsx2.pcsx2` | the Flatpak id `net.pcsx2.PCSX2` (`.github/workflows/scripts/linux/flatpak/net.pcsx2.PCSX2.json`) |

Names not checked on an install.

## Shortcuts

PCSX2 (<https://github.com/PCSX2/pcsx2>), tag `v2.8.2` (the latest stable 2.x
release; the 2.9 tags are nightly builds), read 2026-11-14:

- `pcsx2/SIO/Pad/Pad.cpp`, `Pad::SetDefaultHotkeyConfig`: the hotkeys.
- `pcsx2/Input/InputManager.cpp`, `InputManager::GetGenericBindingMapping`, device
  `Keyboard`: the keyboard map that `Pad::SetDefaultControllerConfig` gives
  controller 1.

| key | hotkey | drawn as |
|---|---|---|
| F1 | `SaveStateToSlot` | Save state |
| F2 / Shift+F2 | `NextSaveStateSlot` / `PreviousSaveStateSlot` | Next / previous state slot |
| F3 | `LoadStateFromSlot` | Load state |
| F4 | `ToggleFrameLimit` | Frame limit on/off |
| Space | `TogglePause` | Pause |
| Tab | `ToggleTurbo` | Turbo (toggle) |
| . | `HoldTurbo` | Turbo (hold) |
| Shift+Tab | `ToggleSlowMotion` | Slow motion (toggle) |
| Alt+Enter | `ToggleFullscreen` | Full screen |
| F5 | `CycleInterlaceMode` | Next deinterlace mode |
| F6 | `CycleAspectRatio` | Next aspect ratio |
| F8 | `Screenshot` | Screenshot |
| Shift+F8 | `GSDumpSingleFrame` | Save GS dump (one frame) |
| Ctrl+Shift+F8 | `GSDumpMultiFrame` | Save GS dump (several frames) |
| F9 | `ToggleSoftwareRendering` | Software renderer on/off |
| Insert | `ToggleMipmapMode` | Mipmapping on/off |
| Ctrl+- | `ZoomOut` | Zoom out |
| Esc | `OpenPauseMenu` | the PCSX2 mark |

| key | DualShock 2 control | drawn as |
|---|---|---|
| I, L, K, J | Triangle, Circle, Cross, Square | a ring with the shape |
| Q, 1, 2 | L1, L2, L3 | the name in a rounded outline |
| E, 3, 4 | R1, R2, R3 | the name in a rounded outline |
| Enter, Backspace | Start, Select | the START and SELECT pills |
| arrow keys | D-pad | the D-pad with that arm filled |
| W, S, A, D | left stick up, down, left, right | a ring with "L" and an arrow |
| T, G, F, H | right stick up, down, left, right | a ring with "R" and an arrow |

## Left out

| key | action | reason |
|---|---|---|
| Ctrl+Plus | `ZoomIn` | The default is the key that sends `Plus`. A US layout has no unshifted plus key. |
| Shift+R | `InputRecToggleMode` | Acts only while an input recording is open. |
| the hotkeys marked `TBD` in the source | `ResetVM`, `FrameAdvance`, `IncreaseSpeed` and others | They have no default key. |

## Icons

| file | source | licence |
|---|---|---|
| `slotplus.png`, `slotminus.png`, `framelimit.png`, `pause.png`, `turbo.png`, `ffhold.png`, `slowmo.png`, `fullscreen.png`, `aspect.png`, `interlace.png`, `mipmap.png`, `software.png`, `gsdump.png`, `gsdumpmulti.png`, `zoomout.png` | Material Symbols (`google/material-design-icons`), names in `fetch_icons.py` | [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0) |
| `savestate.png` (Save), `loadstate.png` (Folder Open), `screenshot.png` (Camera) | Microsoft Fluent UI System Icons (`microsoft/fluentui-system-icons`) | [MIT](https://github.com/microsoft/fluentui-system-icons/blob/main/LICENSE) |
| `triangle.png`, `circle.png`, `cross.png`, `square.png`, `dpad*.png` | drawn by `pad_keys.py` (`shape()`, `dpad()`) | the drawing is this repo's |
| `l1.png` … `r3.png`, `start.png`, `select.png`, `lstick*.png`, `rstick*.png` | drawn by `pad_keys.py` (`shoulder()`, `stick()`) and `retroarch/fetch_icons.py` (`pill()`); text in Press Start 2P by CodeMan38 (`google/fonts`, `ofl/pressstart2p`, pinned commit) | the drawing is this repo's; the font is [SIL OFL 1.1](https://openfontlicense.org/open-font-license-official-text/) |
| `pcsx2.png` | PCSX2's own icon, `bin/resources/icons/AppIconLarge.png` at tag `v2.8.2`, cut to 1 bit by `pad_keys.logo_mark()` | [GPL-3.0-or-later](https://github.com/PCSX2/pcsx2/blob/v2.8.2/COPYING.GPLv3) |

The four face-button shapes are plain geometry drawn in `pad_keys.shape()`. No
Sony artwork is copied.

The same action has the same icon as in the RetroArch and MAME sets (save and load
state, next and previous slot, pause, fast-forward toggle and hold, slow motion,
full screen, screenshot, speed).

## The ESC mark

PCSX2's source files carry `SPDX-License-Identifier: GPL-3.0+`, and the repository
has `COPYING.GPLv3`. The icon file has no licence of its own, so the project
licence applies, and it is compatible with this repository's GPL-3.0-or-later. The
mark lights every opaque pixel of the icon, 37 x 31 px.
