# Unreal Tournament 2004 overlay: sources

`scripts/generate_app_overlays.py` renders `ut2004.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `ut2004_template` (1 file) | Unreal Tournament 2004: `UT2004.exe` on Windows (`ut2004`), the Linux installer's `ut2004-bin` and `ut2004-bin-linux-amd64`, `steam_app_13230` under Proton, `Unreal Tournament 2004` (assumed) on macOS |

None of the names was checked on an install.

## Keys

UT2004 binds 1 to 0 to `SwitchWeapon 1` to `SwitchWeapon 10` (0 is 10). Each
command selects the weapon whose `InventoryGroup` is that number. The groups
below were read from the stock weapon classes in `System/XWeapons.u` of the
UT2004 3369 install (2026-11-14). A class that sets no `InventoryGroup` keeps
the default 1 (the Shield Gun).

| Key | Group | Weapon (class) |
|---|---|---|
| 1 | 1 | Shield Gun (`ShieldGun`) |
| 2 | 2 | Assault Rifle (`AssaultRifle`) |
| 3 | 3 | Bio-Rifle (`BioRifle`) |
| 4 | 4 | Shock Rifle (`ShockRifle`) |
| 5 | 5 | Link Gun (`LinkGun`) |
| 6 | 6 | Minigun (`Minigun`) |
| 7 | 7 | Flak Cannon (`FlakCannon`) |
| 8 | 8 | Rocket Launcher (`RocketLauncher`) |
| 9 | 9 | Lightning Gun (`SniperRifle`) |
| 0 | 0 | Redeemer (`Redeemer`), Ion Painter (`Painter`) |

The Onslaught weapons share slots with these: the Mine Layer is in group 3,
the Grenade Launcher in 7 and the AVRiL in 8 (`System/Onslaught.u`). The
Translocator is group 10, which no digit key selects.

## Left out

- Every other key. The defaults are in `System/DefUser.ini`, which was not
  read; they are added once it is.

## Placement

The weapon keys use a 48×40 area at the right edge, so the digit legend at
the left stays whole. The shipped icons fill the 40×40 box at the right of
that area; the pictures read from the game are fitted to the whole area.

ESC shows UT2004 in Bebas Neue (SIL OFL 1.1, `ofl/bebasneue/BebasNeue-Regular.ttf`
from google/fonts at commit e7db6ca), centred on the whole cell and drawn
without the ESC legend (`program_icon_legend: false`, protocol v25). Epic's
logo art is not used.

## Drawn from the game

With the game on the machine, the ten weapon keys are redrawn from the
player's own files by the `ut2004` reader
(`polyhost/services/game_assets/unreal2/`): the weapon bar picture of each
class, at the `IconCoords` the class declares on `HUDContent.Generic.HUD`
(`Textures/HudContent.utx`, a 512×512 DXT5 texture). The picture is dithered
inside a lit outline, after 1 px is taken off its edge to drop the dark glow
the game draws round each weapon (maintainer's choice from a comparison of
0, 1 and 2 px, 2026-11-14). The `game_assets:` block in `ut2004.yaml` names
the classes; nothing read from the game is committed.

Run on the UT2004 3369 files, all ten keys were drawn. The pictures are 3D
renders; dithered at 48×40 they read as guns of different shapes, not as the
weapon's details.

## Icons

| File | Source | Author | Licence |
|---|---|---|---|
| `shieldgun.png` | game-icons.net `lorc/bolt-shield` | Lorc | CC BY 3.0 |
| `assaultrifle.png` | game-icons.net `skoll/mp5` | Skoll | CC BY 3.0 |
| `biorifle.png` | game-icons.net `lorc/goo-spurt` | Lorc | CC BY 3.0 |
| `shockrifle.png` | game-icons.net `lorc/laser-precision` | Lorc | CC BY 3.0 |
| `linkgun.png` | game-icons.net `lorc/linked-rings` | Lorc | CC BY 3.0 |
| `minigun.png` | game-icons.net `lorc/bullets` | Lorc | CC BY 3.0 |
| `flakcannon.png` | game-icons.net `lorc/striking-diamonds` | Lorc | CC BY 3.0 |
| `rocketlauncher.png` | game-icons.net `lorc/missile-swarm` | Lorc | CC BY 3.0 |
| `lightninggun.png` | game-icons.net `lorc/lightning-tear` | Lorc | CC BY 3.0 |
| `superweapon.png` | game-icons.net `lorc/mushroom-cloud` | Lorc | CC BY 3.0 |
| `program.png` | UT2004 set in Bebas Neue | Dharma Type | SIL OFL 1.1 |

game-icons.net: <https://game-icons.net>, CC BY 3.0
(<https://creativecommons.org/licenses/by/3.0/>).
