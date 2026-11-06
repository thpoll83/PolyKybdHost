# MAME overlay: sources and licences

Rebuild:

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/mame/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/mame/mame.yaml --preview /tmp/mame_preview
```

`fetch_icons.py` uses `retroarch/fetch_icons.py` for the button rings and pills.

## Shortcuts

MAME's default inputs are the `INPUT_PORT_DIGITAL_TYPE` entries of
`src/emu/inpttype.ipp` (<https://github.com/mamedev/mame/blob/master/src/emu/inpttype.ipp>,
read 2026-11-06). Several UI inputs use the same key with and without Shift
(`input_seq::not_code, KEYCODE_LSHIFT` for the plain one).

| key | input | drawn as |
|---|---|---|
| Tab | `UI_MENU` (Show/Hide Menu) | Menu |
| F2 | `SERVICE` | Service |
| F3 / Shift+F3 | `UI_SOFT_RESET` / `UI_RESET_MACHINE` | Soft reset / hard reset |
| F4 / Shift+F4 | `UI_SHOW_GFX` / `UI_REWIND_SINGLE` | Show graphics / rewind one step |
| F5 / Shift+F5 | `UI_PAUSE` / `UI_PAUSE_SINGLE` | Pause / pause and step |
| F6 / Shift+F6 | `UI_SAVE_STATE` / `UI_SAVE_STATE_QUICK` | Save state / quick save |
| F7 / Shift+F7 | `UI_LOAD_STATE` / `UI_LOAD_STATE_QUICK` | Load state / quick load |
| F8 / Shift+F8 | `UI_FRAMESKIP_DEC` / `UI_TOGGLE_CHEAT` | Frameskip down / cheats on/off |
| F9 | `UI_FRAMESKIP_INC` | Frameskip up |
| F10 | `UI_THROTTLE` | Throttle |
| F11 | `UI_SHOW_FPS` | Show FPS |
| F12 / Shift+F12 / Ctrl+Shift+F12 | `UI_SNAPSHOT` / `UI_RECORD_MNG` / `UI_RECORD_AVI` | Snapshot / record MNG / record AVI |
| Insert | `UI_FAST_FORWARD` | Fast-forward |
| `` ` `` | `UI_ON_SCREEN_DISPLAY` | On-screen display |
| T | `TILT` | Tilt |
| 1, 2 | `START1`, `START2` | 1UP, 2UP |
| 5, 6 | `COIN1`, `COIN2` | COIN, COIN2 |
| left Ctrl, left Alt, Space, left Shift, Z, X | `P1_BUTTON1` … `P1_BUTTON6` | rings 1 to 6 |
| Esc | `UI_CANCEL` (quit) | the M mark |

Not drawn: the debugger (`` ` `` also breaks into it when the debugger is on), the
UI keys that act only inside menus, `UI_TOGGLE_UI` (Scroll Lock, no keycap cell),
and players 2 to 4.

## Icons

| file | source | licence |
|---|---|---|
| `menu.png`, `pause.png`, `step.png`, `rewindstep.png`, `gfx.png`, `quicksave.png`, `quickload.png`, `softreset.png`, `hardreset.png`, `skipminus.png`, `skipplus.png`, `cheat.png`, `throttle.png`, `fps.png`, `fastfwd.png`, `recordmng.png`, `recordavi.png`, `service.png`, `tilt.png`, `osd.png` | Material Symbols (`google/material-design-icons`), names in `fetch_icons.py` | Apache-2.0 |
| `savestate.png` (Save), `loadstate.png` (Folder Open), `snapshot.png` (Camera) | Microsoft Fluent UI System Icons | MIT |
| `button1.png` … `button6.png`, `start1.png`, `start2.png`, `coin1.png`, `coin2.png` | drawn by `retroarch/fetch_icons.py`; text in Press Start 2P (SIL OFL 1.1) | the drawing is this repo's |
| `mame.png` | drawn "M" tile (`program_marks.letter_mark`) | this repo's. MAME's own icon is GPL-2.0 and "MAME" a registered trademark of Gregory Ember, so neither is copied |
