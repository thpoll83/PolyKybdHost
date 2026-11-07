# FS-UAE overlay: sources and licences

Rebuild:

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/fs_uae/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/fs_uae/fs_uae.yaml --preview /tmp/fs_uae_preview
```

Both steps are deterministic. The icon sources are fetched from unpinned
branches, so a change there changes the PNG bytes.

## Shortcuts

The default table is in `src/fs-uae/keyboard.c` of the v3.2.35 release
(<https://github.com/FrodeSolheim/fs-uae>), checked against
`docs/keyboard-shortcuts.md` on master. `MOD` there is the modifier key:
`initialize_modifier_key()` in `libfsemu/src/emu/input.c` sets left Alt, and
left Super (Command) on macOS. So each Mod binding is written twice in the spec.

| key | action |
|---|---|
| Mod+A | cycle stretch mode |
| Mod+B | zoom border |
| Mod+C | cartridge freeze (Action Replay) |
| Mod+D | debugger |
| Mod+F, Mod+Enter | full screen |
| Mod+G | grab input |
| Mod+K | full keyboard emulation |
| Mod+M | mute |
| Mod+N | mute floppy sounds |
| Mod+P, Pause | pause |
| Mod+Q, Mod+F4 | quit |
| Mod+R | soft reset |
| Mod+T | hard reset |
| Mod+S, Print Screen | screenshot |
| Mod+Z | cycle zoom |
| Mod+W | warp mode |
| Mod+Comma / Mod+Period | volume down / up |
| F11 | auto zoom (the documentation says "cycle zoom modes"; the code toggles auto zoom) |
| F12 | menu |
| Ctrl+F10 | performance graphs (`handle_shortcut` in `libfsemu/src/emu/input.c`) |

Not drawn: Mod+X (an undocumented developer function), Mod+Tab (switch window;
Windows takes Alt+Tab), Mod+arrows (the Amiga cursor keys while joystick
emulation is on), Ctrl+F9 (benchmark), the media keys (no keycap cell), and
Mod+F9 (RTG display), which the documentation lists but the 3.2.35 table does
not have.

## Icons

Microsoft Fluent UI System Icons (MIT): `screenshot`. Every other icon is a
Material Symbol (Apache-2.0); `fetch_icons.py` lists the name for each file.
Both licences are compatible with this repository's GPL-3.0-or-later.

## ESC mark

Two check marks side by side with "FS" (Press Start 2P, 8 px, SIL OFL 1.1, the
pinned copy `retroarch/fetch_icons.py` uses) at the bottom right: the motif of
FS-UAE's own icon (`.attic/share/icons/hicolor/*/apps/net.fs_uae.FS-UAE.png`
in <https://github.com/FrodeSolheim/fs-uae>). `fs_uae_mark()` in
`fetch_icons.py` draws it 37 x 32 at 1 bit, and the spec places it 1:1 at the
right of Esc. The icon file is not used: it carries no licence of its own, and
FS-UAE's `COPYING` is GPL-2.0 with no "or later" in its own sources, which is
not compatible with this repository's GPL-3.0-or-later.

## Process name

`fs-uae` (`fs-uae.exe` on Windows; the macOS application name `FS-UAE` is
lower-cased by the matcher). Not checked on a running install. The FS-UAE
Launcher is a separate program and is not mapped.
