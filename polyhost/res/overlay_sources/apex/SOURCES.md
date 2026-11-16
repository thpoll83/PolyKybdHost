# Apex Legends overlay: sources

`scripts/generate_app_overlays.py` renders `apex.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `apex_template` (1 file) | Apex Legends: `r5apex.exe` and `r5apex_dx12.exe` (the DirectX 12 client) on Windows, `steam_app_1172470` under Proton |

The process names are from a reWASD profile and Steam and EA forum threads,
not from a depot manifest. None of them was checked on an install. EA ended
Linux and Steam Deck support in 2024, so the Proton name may never be seen.

## Shortcut reference

Respawn publishes no default file and no key list that could be read. The
keys are the bindings that player `settings.cfg` files published on GitHub
have in common:

- <https://github.com/Zazzop/Apex-Legends/blob/673f37c1d6319f7233f6ca73abbdafdae71215c0/settings.cfg>
  (all 24 keys of this set match)
- <https://github.com/salvatorepolverino/ApexLegends-AutoExec-Videoconfig/blob/4498fed/settings.cfg>
  (22 match; F10 is unbound there)
- <https://github.com/240hz/ApexConfigs/blob/4088cb3e11b4853d83b9947e81ac8a41479d15f3/settings.cfg>
  and <https://github.com/r1ft4469/Apex_Config/blob/e5154b7/local/settings.cfg>
  (format only; both are heavily customized)

Read 2026-11-15. A key list from Respawn, or a settings.cfg from a fresh
install, should replace this before anyone relies on it.

## The player's binds

The game keeps its binds in `Saved Games\Respawn\Apex\local\settings.cfg`
in the Windows user folder: `bind_US_standard "<key>" "<command>" <slot>`
(slot 0 is the primary key, 1 the alternate). `bind_held_US_standard` lines
are hold actions, which the overlay does not draw. `game_assets/apex_keys.py`
reads the file (also in Steam's Proton prefix), and `build.remap` moves each
icon to the player's key. It is not known that the game writes a line for a
command the player unbound, so a command with no line keeps its default key.
Not checked on an install.

## Keys

| Key | Command | Action |
|---|---|---|
| W | `+forward` | Move forward |
| A | `+moveleft` | Move left |
| S | `+backward` | Move back |
| D | `+moveright` | Move right |
| 1 | `weaponSelectPrimary0` | Weapon 1 |
| 2 | `weaponSelectPrimary1` | Weapon 2 |
| 3 | `weaponSelectPrimary2` | Holster weapons |
| Q | `+offhand1` | Tactical ability |
| Z | `+offhand4` | Ultimate ability |
| G | `weaponSelectOrdnance` | Grenade |
| B | `+scriptCommand3` | Fire select |
| R | `+reload` | Reload |
| V | `+melee` | Melee |
| N | `weapon_inspect` | Inspect weapon |
| Space | `+jump` | Jump |
| C | `+toggle_duck` | Crouch (toggle) |
| 4 | `+scriptCommand4` | Heal |
| 5 | `use_consumable HEALTH_SMALL` | Syringe |
| 6 | `use_consumable HEALTH_LARGE` | Med kit |
| 7 | `use_consumable SHIELD_SMALL` | Shield cell |
| 8 | `use_consumable SHIELD_LARGE` | Shield battery |
| 9 | `use_consumable PHOENIX_KIT` | Phoenix kit |
| E | `+use` | Interact |
| Tab | `toggle_inventory` | Inventory |
| M | `toggle_map` | Map |
| T | `+pushtotalk` | Push to talk |
| Enter | `say_team` | Team chat |
| F10 | `screenshotDevNet_noRPROF` | Screenshot |

I (`toggle_inventory`, slot 1) is the alternate inventory key. It is listed
as `undrawn` on the Tab binding, so it counts as a default key and gets no
icon.

## Left out

- Shift (`+speed`, sprint), Ctrl (`+duck`): the modifier keys have no
  overlay cell.
- The ping and attack keys: they are on the mouse.
- F1 (`+scriptCommand1`), H (`+scriptCommand5`) and X (`+use_alt`): what
  they do was not confirmed.
- Esc (`ingamemenu_activate`): ESC has the program mark.

## Placement

As for Counter-Strike 2: every icon sits at the right edge of its key and uses
the full height, and the firmware clears 3 px around the icon's ink, so a
letter legend stays whole. F-key icons use 34x40 (the area AoE2 measured for
F-key legends). The solid or wide icons (`INK` in `fetch_icons.py`) are drawn
in a smaller box inside their area. Every icon is drawn at exactly its area by
`game_set.py`, so the generator places it 1:1.

ESC shows APEX in Bebas Neue (SIL OFL 1.1, `ofl/bebasneue/BebasNeue-Regular.ttf`
from google/fonts at commit e7db6ca), centred on the whole cell and drawn
without the ESC legend (`program_icon_legend: false`, protocol v25). Respawn's
logo art is proprietary and is not used.

1 and 2 show the gun with the weapon number, so the two keys differ.

## Icons

| File | Source | Author | Licence |
|---|---|---|---|
| `weapon1.png`, `weapon2.png` | game-icons.net `john-colburn/pistol-gun` + the number drawn by `game_set.py` (DejaVu Sans Bold) | John Colburn | CC BY 3.0 |
| `tactical.png` | game-icons.net `lorc/lightning-helix` | lorc | CC BY 3.0 |
| `ultimate.png` | game-icons.net `lorc/burning-meteor` | lorc | CC BY 3.0 |
| `grenade.png` | game-icons.net `lorc/grenade` | lorc | CC BY 3.0 |
| `melee.png` | game-icons.net `lorc/punch` | lorc | CC BY 3.0 |
| `jump.png` | game-icons.net `delapouite/jump-across` | delapouite | CC BY 3.0 |
| `syringe.png` | game-icons.net `lorc/syringe` | lorc | CC BY 3.0 |
| `forward.png`, `left.png`, `back.png` | Material Symbols `arrow_upward`, `arrow_back`, `arrow_downward` | Google | Apache-2.0 |
| `right.png`, `holster.png`, `fireselect.png` | Material Symbols `arrow_forward`, `back_hand`, `repeat` | Google | Apache-2.0 |
| `reload.png`, `inspect.png`, `crouch.png` | Material Symbols `autorenew`, `visibility`, `keyboard_double_arrow_down` | Google | Apache-2.0 |
| `heal.png`, `medkit.png`, `cell.png` | Material Symbols `healing`, `medical_services`, `shield` | Google | Apache-2.0 |
| `battery.png`, `phoenix.png`, `interact.png` | Material Symbols `battery_full`, `local_fire_department`, `touch_app` | Google | Apache-2.0 |
| `inventory.png`, `map.png`, `pushtotalk.png` | Material Symbols `backpack`, `map`, `mic` | Google | Apache-2.0 |
| `chat.png`, `screenshot.png` | Material Symbols `chat`, `screenshot_monitor` | Google | Apache-2.0 |
| `program.png` | drawn by `game_set.py` in Bebas Neue | font: Dharma Type | font: SIL OFL 1.1 |
