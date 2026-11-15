# OpenGOAL overlay: sources and licences

Rebuild:

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/opengoal/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/opengoal/opengoal.yaml --preview /tmp/opengoal_preview
```

Both steps are deterministic. Every icon is drawn by `pad_keys.py`; the two fonts
are fetched from a pinned commit of `google/fonts`.

## What the set loads for

| name | where it comes from |
|---|---|
| `gk` | `add_executable(gk main.cpp)` in `game/CMakeLists.txt`: the game runtime, `gk.exe` on Windows. The OpenGOAL launcher starts it for every game (Jak 1, Jak II, Jak 3). |

Name not checked on an install.

## Shortcuts

OpenGOAL (<https://github.com/open-goal/jak-project>), tag `v0.3.9`, read
2026-11-14: `game/system/hid/input_bindings.cpp`, `DEFAULT_KEYBOARD_BINDS`. The
game reads a PlayStation 2 controller. Each key presses one control, and what the
control does depends on the game, so the keys show the control.

| key | control (`PadData`) | drawn as |
|---|---|---|
| Space, E, F, R | `CROSS`, `CIRCLE`, `SQUARE`, `TRIANGLE` | a ring with the shape |
| Q, O | `L1`, `R1` | the name in a rounded outline |
| 1, P | `L2`, `R2` | the name in a rounded outline |
| , and . | `L3`, `R3` | the name in a rounded outline |
| Enter, ' | `START`, `SELECT` | the START and SELECT pills |
| arrow keys | `DPAD_UP`, `DPAD_DOWN`, `DPAD_LEFT`, `DPAD_RIGHT` | the D-pad with that arm filled |
| W, S, A, D | `LEFT_Y` minimum, `LEFT_Y`, `LEFT_X` minimum, `LEFT_X` | left stick up, down, left, right |
| I, K, L, J | `RIGHT_Y` minimum, `RIGHT_Y`, `RIGHT_X` minimum, `RIGHT_X` | right stick up, down, left, right |

In the source L is the minimum of `RIGHT_X` (stick left) and J the maximum (stick
right), the reverse of their positions on the keyboard. The icons follow the
source.

These are all 24 default keyboard binds. Nothing is left out. The default mouse
binds are empty.

## Icons

| file | source | licence |
|---|---|---|
| `cross.png`, `circle.png`, `square.png`, `triangle.png`, `dpad*.png` | drawn by `pad_keys.py` (`shape()`, `dpad()`) | the drawing is this repo's |
| `l1.png` … `r3.png`, `start.png`, `select.png`, `lstick*.png`, `rstick*.png` | drawn by `pad_keys.py` (`shoulder()`, `stick()`) and `retroarch/fetch_icons.py` (`pill()`); text in Press Start 2P by CodeMan38 (`google/fonts`, `ofl/pressstart2p`, pinned commit) | the drawing is this repo's; the font is [SIL OFL 1.1](https://openfontlicense.org/open-font-license-official-text/) |
| `program.png` | "Open" / "GOAL" set in Russo One by Jovanny Lemonad (`google/fonts`, `ofl/russoone`, pinned commit), drawn by `pad_keys.wordmark()` | the font is SIL OFL 1.1 |

The four face-button shapes are plain geometry drawn in `pad_keys.shape()`. No
Sony artwork is copied. The pad icons are the same files as in the PCSX2 and
DuckStation sets.

## The ESC mark

OpenGOAL's code is under the ISC licence (`LICENSE`), which is compatible with
GPL-3.0-or-later. The repository's logo files were not checked for a licence of
their own, and the Jak and Daxter art belongs to Sony, so no art is copied. The
mark is the project name set in an open font.
