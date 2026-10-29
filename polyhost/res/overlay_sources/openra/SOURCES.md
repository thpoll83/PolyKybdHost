# OpenRA overlay: sources

`fetch_icons.py` rebuilds `icons/`, `gen_mods.py` writes `openra_cnc.yaml` from
`openra_ra.yaml`, and `scripts/generate_app_overlays.py` renders both.

| Set | Loads for |
|---|---|
| `openra_ra_template` (2 files) | OpenRA's Red Alert mod, and any OpenRA window whose title names no other mod; the Combined Arms Snap (`openra-ca-<version>`) |
| `openra_cnc_template` (2 files) | OpenRA's Tiberian Dawn mod: a title containing "Tiberian Dawn" |

The Flatpak (`net.openra.OpenRA`) reports `openra` for every mod, with the
title `OpenRA - Red Alert` (measured 2026-10-28 on Linux). The Tiberian Dawn
title is assumed to follow the same pattern; it was not seen. The Combined Arms
Snap reports `openra-ca-1.08.2` and the title `OpenRA Combined Arms`; the
matcher drops the trailing version (`overlay-mapping.md`).

## Shortcut reference

OpenRA's default hotkeys, `mods/common/hotkeys/*.yaml` in
<https://github.com/OpenRA/OpenRA> (bleed, commit cd20761, 2026-10-28). Every
mod loads these files, so the two sets differ only in the ESC mark. In OpenRA
the letter orders do not depend on the selection (A attack move, S stop, D
guard, F deploy, Alt+A/S/D/F stances), so they are labelled, unlike in the
original games.

Control groups: a digit selects the group, Ctrl creates it (a plus, as in the
C&C set), Ctrl+Shift adds the selection to it (a plus in a ring), Shift adds
the group to the selection (a plus in a square), Alt jumps to it (a sight).

## Left out

- F1 to F12 and Ctrl+F1 to Ctrl+F12: production tabs, which differ per mod.
- Pause, the media keys and Enter on the keypad (quick save): no overlay cell.
- The arrow keys and Alt+arrows (scroll, jump to the map edge): they keep their
  own legends.
- Shift+Tab (chat mode) and Tab while chatting: only active in the chat line.
- Shift+= and Alt+Shift+= (hide the interface): rarely used, and `=` keeps its
  legend.

## Icons

Drawn like the C&C Remastered set: a silhouette shaded, dithered and outlined
(`../cnc_remastered/fetch_icons.py`: `relief()`, `wz_units.keycap()`). Keys
with the same action as in that set use its icon unchanged. ESC shows the mod's
own OpenRA logo with OPEN over the mod name, over the whole cell and without
the ESC legend (protocol v25). The logos are GPL-3.0 like the rest of the
OpenRA repository, compatible with this host's GPL-3.0-or-later.

| File | Source | Author | Licence |
|---|---|---|---|
| `stop.png` | copied from `../cnc_remastered/icons/` | see `../cnc_remastered/SOURCES.md` | |
| `guard.png` | copied from `../cnc_remastered/icons/` | see `../cnc_remastered/SOURCES.md` | |
| `scatter.png` | copied from `../cnc_remastered/icons/` | see `../cnc_remastered/SOURCES.md` | |
| `selectall.png` | copied from `../cnc_remastered/icons/` | see `../cnc_remastered/SOURCES.md` | |
| `conyard.png` | copied from `../cnc_remastered/icons/` | see `../cnc_remastered/SOURCES.md` | |
| `lastevent.png` | copied from `../cnc_remastered/icons/` | see `../cnc_remastered/SOURCES.md` | |
| `tabstructures.png` | copied from `../cnc_remastered/icons/` | see `../cnc_remastered/SOURCES.md` | |
| `bookmark1.png` | copied from `../cnc_remastered/icons/` | see `../cnc_remastered/SOURCES.md` | |
| `bookmark2.png` | copied from `../cnc_remastered/icons/` | see `../cnc_remastered/SOURCES.md` | |
| `bookmark3.png` | copied from `../cnc_remastered/icons/` | see `../cnc_remastered/SOURCES.md` | |
| `bookmark4.png` | copied from `../cnc_remastered/icons/` | see `../cnc_remastered/SOURCES.md` | |
| `bookmarkset1.png` | copied from `../cnc_remastered/icons/` | see `../cnc_remastered/SOURCES.md` | |
| `bookmarkset2.png` | copied from `../cnc_remastered/icons/` | see `../cnc_remastered/SOURCES.md` | |
| `bookmarkset3.png` | copied from `../cnc_remastered/icons/` | see `../cnc_remastered/SOURCES.md` | |
| `bookmarkset4.png` | copied from `../cnc_remastered/icons/` | see `../cnc_remastered/SOURCES.md` | |
| `attackmove.png` | game-icons.net `lorc/crossed-swords` | lorc | CC BY 3.0 |
| `deploy.png` | Font Awesome Free 6.5.2 `circle-down` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `attackanything.png` | game-icons.net `lorc/sword-clash` | lorc | CC BY 3.0 |
| `defend.png` | Font Awesome Free 6.5.2 `shield` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `returnfire.png` | Font Awesome Free 6.5.2 `reply` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `holdfire.png` | Font Awesome Free 6.5.2 `ban` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `sametype.png` | Font Awesome Free 6.5.2 `object-group` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `harvesters.png` | Font Awesome Free 6.5.2 `truck` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `toselection.png` | Font Awesome Free 6.5.2 `crosshairs` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `cycleproduction.png` | Font Awesome Free 6.5.2 `industry` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `sell.png` | Font Awesome Free 6.5.2 `dollar-sign` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `repair.png` | Font Awesome Free 6.5.2 `wrench` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `beacon.png` | Font Awesome Free 6.5.2 `location-dot` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomin.png` | Font Awesome Free 6.5.2 `magnifying-glass-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomout.png` | Font Awesome Free 6.5.2 `magnifying-glass-minus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomreset.png` | Font Awesome Free 6.5.2 `magnifying-glass` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `statusbars.png` | Font Awesome Free 6.5.2 `bars-progress` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mute.png` | Font Awesome Free 6.5.2 `volume-xmark` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `teamchat.png` | game-icons.net `lorc/conversation` | lorc | CC BY 3.0 |
| `allchat.png` | game-icons.net `delapouite/megaphone` | delapouite | CC BY 3.0 |
| `group*.png`, `groupnew*.png` | copied from `../cnc_remastered/icons/` (Warzone 2100 units) | see `../cnc_remastered/SOURCES.md` | GPL-2.0-or-later |
| `groupadd*.png`, `groupcombine*.png`, `groupjump*.png` | the C&C group icons with a mark drawn by `fetch_icons.py` | | GPL-2.0-or-later |
| `program_ra.png` | OpenRA `packaging/artwork/ra_scalable.svg` (commit cd20761) + text in Black Ops One | OpenRA developers; Black Ops One by James Grieshaber | GPL-3.0; SIL OFL 1.1 |
| `program_cnc.png` | OpenRA `packaging/artwork/cnc_scalable.svg` (commit cd20761) + text in Black Ops One | OpenRA developers; Black Ops One by James Grieshaber | GPL-3.0; SIL OFL 1.1 |

## Keys drawn from the game files

When OpenRA has installed the original game files, the host draws 57 keys of
each overlay from the game's own sprites instead. The shipped files above stay
the fallback and are the only art in the repository. The game's sprites are
never shipped: the host reads them from the user's machine, writes the patched
copies to the user's cache directory, and sends them only to the keyboard.

The mapping entries opt in with `game_assets: openra/openra_ra.yaml` and
`openra/openra_cnc.yaml`. The Red Alert set uses the `westwood_ra` reader; the
Tiberian Dawn set uses `westwood_td`, the reader of the C&C Remastered overlay,
with that overlay's units (`cnc_game_assets.yaml`, which `gen_mods.py` puts in
`openra_cnc.yaml`).

| Keys | From the game |
|---|---|
| 1 to 0 with no modifier, Ctrl, Shift, Alt and Ctrl+Shift | map sprites of the chosen faction, with the same marks as above |
| Tab, H, Space, N | construction yard, radar dome (Red Alert) or communications center (Tiberian Dawn), harvester |
| S, D, Ctrl+X | mouse cursors |

| Group | Allies | Soviets |
|---|---|---|
| 1 | riflemen | riflemen |
| 2 | ranger | V2 rocket launcher |
| 3 | APC | heavy tank |
| 4 | light tank | mammoth tank |
| 5 | medium tank | submarine |
| 6 | artillery | supply truck |
| 7 | destroyer | MiG |
| 8 | spies | Yak |
| 9 | Longbow | Hind |
| 0 | harvester | harvester |

The Red Alert reader needs `conquer.mix`, `hires.mix` and `local.mix` (any
case); `hires.mix` and `local.mix` are encrypted, and the reader decrypts their
headers. It looks in this order:

1. the folder in the `game_ra_data_dir` setting, when set;
2. `Content/ra/v2/` in OpenRA's support folder: `Support/` beside the game
   (a portable install), `%APPDATA%\OpenRA`, `~/Library/Application
   Support/OpenRA`, `~/.config/openra`, `~/.openra`, and the copies kept by
   Flatpak (`~/.var/app/*/config/openra`) and Snap
   (`~/snap/*/current/.config/openra`);
3. any folder up to three levels below each `Content/` folder that has the
   three files. The Combined Arms content folder was not checked on an install.

The Tiberian Dawn reader adds `Content/cnc/` of the same support folders after
the C&C Remastered installs.

| Setting | Default | Meaning |
|---|---|---|
| `game_ra_data_dir` | empty | a folder with the Red Alert MIX files; empty searches as above |
| `game_ra_faction` | `allies` | `allies` or `soviets` |
| `game_cnc_faction` | `gdi` | `gdi` or `nod`, shared with the C&C Remastered overlay |

The mouse cursors on S, D and Ctrl+X are the game's own and differ from the
shipped icons.
