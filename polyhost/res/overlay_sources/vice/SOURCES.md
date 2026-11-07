# VICE overlay: sources and licences

Rebuild:

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/vice/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/vice/vice.yaml --preview /tmp/vice_preview
```

Both steps are deterministic. The icon sources are fetched from unpinned
branches, so a change there changes the PNG bytes.

## Shortcuts

VICE's default hotkeys are in `vice/data/hotkeys/*.vhk` of the VICE source
(<https://github.com/VICE-Team/svn-mirror>, the official Subversion mirror).
Read from the 3.10.0 tag; trunk at 8e45817 (2026-11-03) has the same files.
Every hotkey is `<Alt>` outside macOS and `<Command>` on macOS, so the spec
writes each binding twice. Two exceptions: Copy and Paste are `<Alt>Delete` and
`<Alt>Insert` on every platform, and the monitor is `<Command>Escape` on macOS,
which is not drawn because Esc carries the program mark.

| key (Windows, Linux) | action | file |
|---|---|---|
| Alt+A | smart-attach | hotkeys.vhk |
| Alt+H | monitor-open | hotkeys.vhk |
| Alt+F9 | machine-reset-cpu | hotkeys.vhk |
| Alt+F12 | machine-power-cycle | hotkeys.vhk |
| Alt+Q | quit | hotkeys.vhk |
| Alt+8 / 9 / 0 / 1 | drive-attach-8 / 9 / 10 / 11 | hotkeys-drive.vhk |
| Ctrl+Alt+8 / 9 / 0 / 1 | drive-detach-8 / 9 / 10 / 11 | hotkeys-drive.vhk |
| Alt+I / Alt+K | fliplist-add / fliplist-remove | hotkeys-fliplist.vhk |
| Alt+N / Shift+Alt+N | fliplist-next / fliplist-previous | hotkeys-fliplist.vhk |
| Alt+T / Shift+Alt+T | tape-attach-1 / tape-detach-1 | hotkeys-datasette.vhk |
| Alt+C / Shift+Alt+C | cart-attach / cart-detach | hotkeys-cartridge.vhk |
| Alt+Z | cart-freeze | hotkeys-cartridge.vhk |
| Alt+3 / 4 / 5 / 6 | printer-formfeed-userport / 4 / 5 / 6 | hotkeys.vhk |
| Alt+Delete / Alt+Insert | edit-copy / edit-paste | hotkeys.vhk |
| Alt+L / Alt+S | snapshot-load / snapshot-save | hotkeys-snapshot.vhk |
| Alt+F10 / Alt+F11 | snapshot-quickload / snapshot-quicksave | hotkeys-snapshot.vhk |
| Alt+E / Alt+U | history-milestone-set / history-milestone-reset | hotkeys-snapshot.vhk |
| Shift+Alt+R / Shift+Alt+S | media-record / media-stop | hotkeys-snapshot.vhk |
| Pause | screenshot-quicksave | hotkeys-snapshot.vhk |
| Alt+D / Alt+R / Alt+B | fullscreen-toggle / restore-display / fullscreen-decorations-toggle | hotkeys.vhk |
| Alt+W / Alt+P / Shift+Alt+P | warp-mode-toggle / pause-toggle / advance-frame | hotkeys.vhk |
| Alt+M / Alt+J / Shift+Alt+J | mouse-grab-toggle / swap-controlport-toggle / keyset-joystick-toggle | hotkeys.vhk |
| Alt+O / Shift+Alt+O | settings-dialog / settings-default | hotkeys-settings.vhk |

Some keys do nothing on some machines: the cartridge keys on x64dtv, xcbm5x0
and xpet (Alt+Z also on xcbm2), the tape keys on x64dtv and xscpu64, Alt+J on
xvic, xpet and xcbm2, and Alt+3 on x64dtv and xcbm5x0. One spec serves every
VICE emulator, so those keys are drawn anyway. Alt+T on xscpu64 is its speed
switch (`scpu-speed-switch-toggle`) instead of the tape.

## Icons

Microsoft Fluent UI System Icons (<https://github.com/microsoft/fluentui-system-icons>,
MIT): `copy`, `paste`, `snapload`, `snapsave`, `screenshot`, `settings`. Every
other icon is a Material Symbol (<https://fonts.google.com/icons>,
Apache-2.0); `fetch_icons.py` lists the name for each file. Both licences are
compatible with this repository's GPL-3.0-or-later.

`drive8.png` … `drive11.png`, `eject8.png` … `eject11.png` and `printer3.png` …
`printer6.png` are drawn by
`numbered()`: the drive number in Press Start 2P at 16 px (SIL OFL 1.1, the
pinned copy `retroarch/fetch_icons.py` uses) above the `driveattach` or
`eject` or `formfeed` symbol, 36 x 32 at 1 bit, placed 1:1. The keys for
drives 10 and 11 are 0 and 1, so the number says which device the key acts on.
Printers are CBM devices 4, 5 and 6 (`src/printerdrv/printer.h`); the userport
printer on key 3 has no device number, so its icon says USER (8 px, to fit).
VICE has no device 7 printer and no hotkey for it.

`composites()` draws seven more 36 x 32 icons, each placed 1:1:

| file | drawing |
|---|---|
| `monlens.png` | the `troubleshoot` symbol (a magnifier with a pulse line), for the monitor |
| `tapeattach.png` | the `tape` symbol (14 px high) above `add`, a plus (14 px) |
| `cartattach.png` | an 18 x 14 cartridge drawn pixel by pixel in `cartridge()` (a box with a label above an edge connector), above `add` (14 px) |
| `tapedetach.png` | the `tape` symbol (14 px high) above `eject` (16 px) |
| `cartdetach.png` | an 18 x 14 `cartridge()` above `eject` (16 px) |
| `swapjoy.png` | a 16 x 15 joystick drawn pixel by pixel in `joystick()`, above `swapports` (15 px) |
| `decorframe.png` | the corners of `fullscreen` around a 20 px tiled `window` |

## ESC mark

The VICE logo: `vice/data/common/vice-logo-black.svg` of the 3.10.0 release
(<https://github.com/VICE-Team/svn-mirror/blob/3.10.0/vice/data/common/vice-logo-black.svg>),
which VICE installs with every build. It carries no licence of its own, so VICE's
licence covers it: GPL-2.0-or-later (`vice/README`: "either version 2 of the
License, or (at your option) any later version"), compatible with this
repository's GPL-3.0-or-later. `vice_mark()` in `fetch_icons.py` renders the
wordmark 40 px wide (40 x 11 at 1 bit, where it still reads "VICE") and the
spec places it 1:1 at the bottom right of Esc. At 40 px its 3 px clearance
misses the Esc legend (ink x 2..27); 44 px would cut 4 of its pixels, 52 px 46. The machine icons in
`vice/data/common/icon_sources/` are not used: their README says not to ship them.

## Process names

The emulator binaries: `x64sc`, `x64`, `x128`, `xscpu64`, `x64dtv`, `xvic`,
`xplus4`, `xpet`, `xcbm2`, `xcbm5x0` (`.exe` on Windows). Not checked on a
running install. `vsid` (the SID player) is not mapped.
