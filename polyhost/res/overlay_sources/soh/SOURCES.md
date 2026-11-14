# Ship of Harkinian overlay: sources and licences

Rebuild:

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/soh/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/soh/soh.yaml --preview /tmp/soh_preview
```

Both steps are deterministic. The two hotkey icons are fetched from an unpinned
branch, so a change there changes the PNG bytes.

## What the set loads for

| name | where it comes from |
|---|---|
| `soh` | the CMake target of `soh/CMakeLists.txt`; `soh.exe` on Windows |
| `soh.elf` | `OUTPUT_NAME "soh.elf"` on Linux (also the process inside the AppImage) |
| `soh-macos` | `OUTPUT_NAME "soh-macos"` on macOS |

Names not checked on an install.

## Shortcuts

Ship of Harkinian (<https://github.com/HarbourMasters/Shipwright>), tag `9.3.1`,
read 2026-11-14. The keyboard map is not in that repository. It is the default of
libultraship (<https://github.com/Kenix3/libultraship>), a git submodule of the
port that follows the branch `port-maintenance`:

- `src/libultraship/controller/controldevice/controller/mapping/ControllerDefaultMappings.cpp`,
  `SetDefaultKeyboardKeyToButtonMappings`: the buttons.
- `src/ship/controller/controldevice/controller/mapping/ControllerDefaultMappings.cpp`,
  `SetDefaultKeyboardKeyToAxisDirectionMappings`: the stick.

Both were read at commit `57e6d409ae5c6eadac45ba5ead1c090822fc7c39`, the head of
`port-maintenance` on 2026-11-14. The exact commit that tag `9.3.1` pins could not
be read here (a submodule commit is not in the raw files), so a difference between
the two is possible. `soh/soh/OTRGlobals.cpp` at `9.3.1` creates the control deck
without its own keyboard defaults, so the library's defaults apply.

| key | N64 control | drawn as |
|---|---|---|
| X, C | `BTN_A`, `BTN_B` | a ring with the letter |
| Z | `BTN_Z` | a ring with the letter |
| E, R | `BTN_L`, `BTN_R` | a ring with the letter |
| Space | `BTN_START` | the START pill |
| arrow keys | `BTN_CUP`, `BTN_CDOWN`, `BTN_CLEFT`, `BTN_CRIGHT` | a ring with "C" and an arrow |
| T, G, F, H | `BTN_DUP`, `BTN_DDOWN`, `BTN_DLEFT`, `BTN_DRIGHT` | the D-pad with that arm filled |
| W, S, A, D | left stick up, down, left, right | a ring with a dot and an arrow |

The hotkeys are in `soh/soh/OTRGlobals.cpp` at `9.3.1` (the `switch` on
`KbScancode`):

| key | action | drawn as |
|---|---|---|
| Tab | toggles `AltAssets` (while `Mods.AlternateAssetsHotkey` is on, the default) | Alternate assets on/off |
| F9 | toggles `A11yTTS` | Text to speech on/off |
| Esc | opens the port's menu (the F1 message in the source says so) | the mark |

## Left out

| key | action | reason |
|---|---|---|
| F5, F6, F7 | save state, next state slot, load state | Save states are off by default (`SaveStatesEnabled` in the Cheats menu). With the default settings the keys only show a notice. |
| F1 | shows a notice that the menu moved to Esc | Not an action. |
| the full screen key | `Window::GetFullscreenScancode()` | Its default value is set outside the files read here. |

## Icons

| file | source | licence |
|---|---|---|
| `altassets.png`, `tts.png` | Material Symbols (`google/material-design-icons`), `swap_horiz` and `record_voice_over` | [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0) |
| `btna.png`, `btnb.png`, `btnz.png`, `btnl.png`, `btnr.png`, `start.png`, `c*.png`, `stick*.png`, `dpad*.png` | drawn by `pad_keys.n64_pad()` with `retroarch/fetch_icons.py` (`ring()`, `pill()`); text in Press Start 2P by CodeMan38 (`google/fonts`, `ofl/pressstart2p`, pinned commit) | the drawing is this repo's; the font is [SIL OFL 1.1](https://openfontlicense.org/open-font-license-official-text/) |
| `program.png` | "Ship of" / "Harkinian" set in Russo One by Jovanny Lemonad (`google/fonts`, `ofl/russoone`, pinned commit), drawn by `pad_keys.wordmark()` | the font is SIL OFL 1.1 |

## The ESC mark

The port's repository has no licence file at tag `9.3.1` (`LICENSE` is not at its
root), and the game art belongs to Nintendo. No art is copied. The mark is the
port's name set in an open font. libultraship is MIT; only its default keys were
read.
