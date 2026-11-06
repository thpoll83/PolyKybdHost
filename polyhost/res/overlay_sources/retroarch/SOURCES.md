# RetroArch overlay: sources and licences

Rebuild:

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/retroarch/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/retroarch/retroarch.yaml --preview /tmp/retroarch_preview
```

Both steps are deterministic. The icon sources are fetched from unpinned branches,
so a change there changes the PNG bytes.

## Shortcuts

RetroArch's default keyboard binds on desktop builds are the `#else` block of
`retro_keybinds_1` in `config.def.keybinds.h`
(<https://github.com/libretro/RetroArch/blob/master/config.def.keybinds.h>, read
2026-11-06). Each entry pairs a `RETROK_*` key with a bind id. The hotkey-enable
bind is `RETROK_UNKNOWN` by default, so the hotkeys work without a modifier.

| key | bind id | drawn as |
|---|---|---|
| F1 | `RARCH_MENU_TOGGLE` | Menu |
| F2 | `RARCH_SAVE_STATE_KEY` | Save state |
| F3 | `RARCH_FPS_TOGGLE` | Show FPS |
| F4 | `RARCH_LOAD_STATE_KEY` | Load state |
| F5 | `RARCH_UI_COMPANION_TOGGLE` | Desktop menu |
| F6 / F7 | `RARCH_STATE_SLOT_MINUS` / `_PLUS` | Previous / next state slot |
| F8 | `RARCH_SCREENSHOT` | Screenshot |
| F9 | `RARCH_MUTE` | Mute |
| F11 | `RARCH_GRAB_MOUSE_TOGGLE` | Grab mouse |
| F | `RARCH_FULLSCREEN_TOGGLE_KEY` | Full screen |
| H | `RARCH_RESET` | Reset game |
| P | `RARCH_PAUSE_TOGGLE` | Pause |
| K | `RARCH_FRAMEADVANCE` | Frame advance |
| R | `RARCH_REWIND` | Rewind |
| Space | `RARCH_FAST_FORWARD_KEY` | Fast-forward (toggle) |
| L | `RARCH_FAST_FORWARD_HOLD_KEY` | Fast-forward (hold) |
| E | `RARCH_SLOWMOTION_HOLD_KEY` | Slow motion (hold) |
| , | `RARCH_SHADER_TOGGLE` | Shaders on/off |
| M / N | `RARCH_SHADER_NEXT` / `_PREV` | Next / previous shader |
| U | `RARCH_CHEAT_TOGGLE` | Cheats on/off |
| Esc | `RARCH_QUIT_KEY` | the RetroArch mark |
| Z, X, A, S, Q, W | `RETRO_DEVICE_ID_JOYPAD_B, A, Y, X, L, R` | RetroPad B, A, Y, X, L, R |
| Enter, right Shift | `RETRO_DEVICE_ID_JOYPAD_START, SELECT` | RetroPad Start, Select |

Not drawn: `RARCH_CHEAT_INDEX_PLUS/MINUS` (Y, T), `RARCH_HEADSET_VIEW_TOGGLE` (V),
`RARCH_NETPLAY_GAME_WATCH` (I), `RARCH_NETPLAY_PLAYER_CHAT` (`` ` ``),
`RARCH_GAME_FOCUS_TOGGLE` (Scroll Lock, no keycap cell), and the volume keys on
the keypad (no cell).

## Icons

| file | source | licence |
|---|---|---|
| `menu.png`, `reset.png`, `fastforward.png`, `ffhold.png`, `slowmo.png`, `rewind.png`, `pause.png`, `frameadv.png`, `mute.png`, `slotminus.png`, `slotplus.png`, `shader.png`, `shadernext.png`, `shaderprev.png`, `cheat.png`, `grabmouse.png`, `fullscreen.png`, `fps.png`, `desktopmenu.png` | Material Symbols (`google/material-design-icons`), names in `fetch_icons.py` | Apache-2.0 |
| `savestate.png` (Save), `loadstate.png` (Folder Open), `screenshot.png` (Camera) | Microsoft Fluent UI System Icons | MIT |
| `pada.png` … `padr.png`, `padstart.png`, `padselect.png` | drawn in `fetch_icons.py` (`ring()`, `pill()`); text in Press Start 2P by CodeMan38 (`google/fonts`, `ofl/pressstart2p`, pinned commit) | the drawing is this repo's; the font is SIL OFL 1.1 |
| `retroarch.png` | Simple Icons `retroarch` (`simple-icons/simple-icons`) | CC0-1.0 artwork; used to identify RetroArch, no endorsement implied |
