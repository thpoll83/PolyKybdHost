# PPSSPP overlay: sources and licences

Rebuild:

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/ppsspp/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/ppsspp/ppsspp.yaml --preview /tmp/ppsspp_preview
```

Both steps are deterministic. The action icons are fetched from unpinned branches,
so a change there changes the PNG bytes. The ESC mark is fetched from the pinned
release tag and is left as it is once committed.

## What the set loads for

| name | where it comes from |
|---|---|
| `ppssppwindows64`, `ppssppwindows`, `ppssppwindowsarm64` | `TargetName` in `Windows/PPSSPP.vcxproj` (`PPSSPPWindows64.exe` and so on) |
| `ppssppsdl`, `ppssppqt`, `ppssppgold` | `TargetBin` in `CMakeLists.txt`: the SDL build (Linux, macOS), the Qt build, PPSSPP Gold |
| `ppsspp` | the macOS app name and the iOS/macOS `TargetBin` |
| `org.ppsspp.ppsspp` | the Flatpak id `org.ppsspp.PPSSPP` |

Names not checked on an install.

## Shortcuts

PPSSPP (<https://github.com/hrydgard/ppsspp>), tag `v1.20.4`, read 2026-11-14:

- `Core/KeyMapDefaults.cpp`, `defaultQwertyKeyboardKeyMap`: the PSP controls and
  the emulator keys on a QWERTY keyboard. `NKCODE_DEL` is Backspace.
- `Windows/ppsspp.rc`, `IDR_ACCELS`: the accelerators of the Windows menu.
- `SDL/SDLMain.cpp`: the SDL build (Linux, macOS) has Ctrl+W alone.

The accelerators and Ctrl+W act while "Enable standard shortcut keys"
(`bSystemControls`) is on.

| key | id | drawn as |
|---|---|---|
| A, S, X, Z | `CTRL_SQUARE`, `CTRL_TRIANGLE`, `CTRL_CIRCLE`, `CTRL_CROSS` | a ring with the shape |
| Q, W | `CTRL_LTRIGGER`, `CTRL_RTRIGGER` | a ring with L, R |
| Space | `CTRL_START` | the START pill |
| V (Windows), Enter (Linux, macOS) | `CTRL_SELECT` | the SELECT pill |
| arrow keys | `CTRL_UP`, `CTRL_DOWN`, `CTRL_LEFT`, `CTRL_RIGHT` | the D-pad with that arm filled |
| I, K, J, L | `VIRTKEY_AXIS_Y_MAX`, `_Y_MIN`, `_X_MIN`, `_X_MAX` | analog stick up, down, left, right |
| left Shift | `VIRTKEY_RAPID_FIRE` | Rapid fire (hold) |
| Tab | `VIRTKEY_FASTFORWARD` | Fast-forward (hold) |
| `` ` `` | `VIRTKEY_SPEED_TOGGLE` | Alternate speed on/off |
| Backspace | `VIRTKEY_REWIND` | Rewind |
| F8 | `VIRTKEY_PAUSE_NO_MENU` | Pause without menu |
| F12 | `VIRTKEY_TOGGLE_DEBUGGER` | Debugger on/off |
| Esc | `VIRTKEY_PAUSE` | the PPSSPP mark |
| Ctrl+W | `ID_EMULATION_STOP`; `SDLK_w` with Ctrl in the SDL build | Stop the game |
| F2, F4 (Windows) | `ID_FILE_QUICKSAVESTATE_HC`, `ID_FILE_QUICKLOADSTATE_HC` | Save state, load state |
| F3 (Windows) | `ID_FILE_SAVESTATE_NEXT_SLOT_HC` | Next state slot |
| Ctrl+O (Windows) | `ID_FILE_LOAD` | Load a game |
| Ctrl+B (Windows) | `ID_EMULATION_RESET` | Reset game |
| Ctrl+T (Windows) | `ID_EMULATION_CHEATS` | Cheats |
| Ctrl+1 (Windows) | `ID_OPTIONS_RESOLUTIONDUMMY` | Next rendering resolution |
| Alt+Enter, F11 (Windows) | `ID_OPTIONS_FULLSCREEN` | Full screen |

The Windows set has 32 keys; the Linux and macOS sets have the 23 keys of the
keyboard map and Ctrl+W.

## Left out

| key | action | reason |
|---|---|---|
| right Shift | `VIRTKEY_ANALOG_LIGHTLY`, analog limiter | A modifier for the stick keys with no clear picture. |
| Ctrl+C (Windows) | `ID_EMULATION_CHAT` | Acts only with network chat on, in a game. |
| Ctrl+D, Ctrl+G, Ctrl+L, Ctrl+M (Windows) | disassembly, GE debugger, log console, memory view | Debugger windows. |
| Ctrl+I (Windows) | open a new instance | Not a key of the running game. |
| the `IDR_DEBUGACCELS` table | step, breakpoints | Acts only in the debugger window. |
| the AZERTY and QWERTZ maps | `defaultAzertyKeyboardKeyMap`, `defaultQwertzKeyboardKeyMap` | PPSSPP chooses them from the system layout; they differ from QWERTY in Q/A, W/Z and Y/Z only. The QWERTY map is drawn. |

## Icons

| file | source | licence |
|---|---|---|
| `ffhold.png`, `speed.png`, `rewind.png`, `pause.png`, `rapidfire.png`, `debugger.png`, `slotplus.png`, `open.png`, `stop.png`, `reset.png`, `cheat.png`, `resolution.png`, `fullscreen.png` | [Material Symbols](https://github.com/google/material-design-icons), names in `fetch_icons.py` | [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0) |
| `savestate.png` (Save), `loadstate.png` (Folder Open) | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | [MIT](https://github.com/microsoft/fluentui-system-icons/blob/main/LICENSE) |
| `square.png`, `triangle.png`, `circle.png`, `cross.png`, `dpad*.png`, `stick*.png` | drawn by `pad_keys.py` (`shape()`, `dpad()`, `stick()`) | the drawing is this repo's |
| `pspl.png`, `pspr.png`, `pspstart.png`, `pspselect.png` | drawn by `retroarch/fetch_icons.py` (`ring()`, `pill()`); text in Press Start 2P by CodeMan38 (`google/fonts`, `ofl/pressstart2p`, pinned commit) | the drawing is this repo's; the font is [SIL OFL 1.1](https://openfontlicense.org/open-font-license-official-text/) |
| `ppsspp.png` | PPSSPP's own icon, `icons/icon-512.svg` at tag `v1.20.4`, cut to 1 bit by `pad_keys.logo_mark()` | [GPL-2.0-or-later](https://github.com/hrydgard/ppsspp/blob/v1.20.4/LICENSE.TXT) |

The four face-button shapes are plain geometry (a square, a triangle, a circle and
a cross in a ring), drawn in `pad_keys.shape()`. No Sony artwork is copied.

The same action has the same icon as in the RetroArch and MAME sets (pause,
fast-forward while held, rewind, save and load state, next slot, reset, cheats,
full screen, speed).

## The ESC mark

PPSSPP's source headers say "the GNU General Public License ... version 2.0 or
later versions", and `LICENSE.TXT` is the GPL version 2 with the "or any later
version" text. `icons/icon-512.svg` has no licence of its own, so the project
licence applies, and "or later" makes it compatible with this repository's
GPL-3.0-or-later. The icon is four light buttons on a blue tile. The mark lights
the bright pixels, which gives the four buttons, 32 x 32 px.
