# Veloren overlay: sources

`scripts/generate_app_overlays.py` renders `veloren.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `veloren_template` (1 file) | Veloren, the game client Voxygen: `veloren-voxygen` (the executable, `veloren-voxygen.exe` on Windows), and `net.veloren.veloren` and `veloren` (the window's app id and instance name) |

`veloren-voxygen` is the package and default binary name in
`voxygen/Cargo.toml` and the `Exec=` line of
`assets/voxygen/net.veloren.veloren.desktop`. The window is created with the
title "Veloren" and, on Linux, the names `net.veloren.veloren` (Wayland app id,
X11 class) and `veloren` (X11 instance) in `voxygen/src/window.rs`
(`with_name("net.veloren.veloren", "veloren")`). The launcher Airshipper starts
the same executable. Names not checked on an install.

## Shortcut reference

`ControlSettings::default_binding()` in `voxygen/src/settings/control.rs` of
<https://github.com/veloren/veloren> (the mirror of
<https://gitlab.com/veloren/veloren>), release tag `v0.18.0` (commit
`b2f1060df37ba4eb2eb001ac1b115beaf404f656`), read 2026-11-14. A user who
changes a key in the game still sees the default.

The table binds logical keys. A letter is bound as its character, and Shift,
Ctrl and Alt are bound without a side; the overlay draws them on the left
keys. Camera zoom in and out are bound to the characters `)` and `(`, and map
zoom in to `+`: on a US layout these are Shift+0, Shift+9 and Shift+=, so they
are on the Shift layer. On another layout they are on other keys.

Sneak is Shift and is held while the character moves, so the movement keys and
Space are drawn on the Shift layer as well.

| Key | Action | `GameInput` |
|---|---|---|
| W / A / S / D | Move forward / left / back / right | `MoveForward`, `MoveLeft`, `MoveBack`, `MoveRight` |
| Space | Jump | `Jump` |
| Shift | Sneak | `Sneak` |
| Ctrl | Glide | `Glide` |
| B | Walk on / off | `ToggleWalk` |
| . | Auto walk | `AutoWalk` |
| K | Sit | `Sit` |
| J | Dance | `Dance` |
| H | Greet | `Greet` |
| Alt | Block | `Block` |
| R | Draw / sheathe weapon | `ToggleWield` |
| Tab | Swap loadout | `SwapLoadout` |
| E | Interact | `Interact` |
| X | Select entity | `Select` |
| G | Lantern on / off | `ToggleLantern` |
| F | Mount | `Mount` |
| V | Pet: stay / follow | `StayFollow` |
| 1 to 9 | Hotbar slot 1 to 9 | `Slot1` .. `Slot9` |
| Q | Hotbar slot 10 | `Slot10` |
| M | Map | `Map` |
| I | Inventory | `Inventory` |
| T | Trade | `Trade` |
| O | Social | `Social` |
| C | Crafting | `Crafting` |
| P | Diary | `Diary` |
| F10 | Settings | `Settings` |
| F1 | Controls | `Controls` |
| Y / N | Accept / decline a group invite | `AcceptGroupInvite`, `DeclineGroupInvite` |
| L | Free look | `FreeLook` |
| ' | Camera clamp | `CameraClamp` |
| 0 | Cycle camera | `CycleCamera` |
| Shift+0 `)` / Shift+9 `(` | Camera zoom in / out | `ZoomIn`, `ZoomOut` |
| Shift+= `+` / - | Map zoom in / out (in the map window) | `MapZoomIn`, `MapZoomOut` |
| , | Cursor on / off | `ToggleCursor` |
| F2 | Interface on / off | `ToggleInterface` |
| F3 | Debug info | `ToggleDebug` |
| F4 | Take screenshot | `Screenshot` |
| F5 | Chat on / off | `ToggleChat` |
| F6 | Name tags and speech bubbles on / off | `ToggleIngameUi` |
| F8 | Mute music | `MuteMusic` |
| F11 | Toggle fullscreen | `Fullscreen` |
| Enter | Open chat | `Chat` |
| / | Open command | `Command` |
| Esc | program mark (Esc opens the menu) | `Escape` |

Keys with a second meaning, which is not drawn:

| Key | Drawn | Other meaning |
|---|---|---|
| Space | Jump | Wall jump, swim up, and give up or respawn when the character is down (`WallJump`, `SwimUp`, `GiveUp`, `Respawn`) |
| Shift | Sneak | Swim down, stop climbing (`SwimDown`, `CancelClimb`); on macOS also roll (`Roll`) |
| Ctrl | Glide | Faster camera as a spectator (`SpectateSpeedBoost`) |
| H | Greet | Fly, for a character that is allowed to (`Fly`) |

## Left out

- **Arrow Down** (`Crawl`): the arrows keep their own legends.
- **F7** (`ToggleEguiDebug`): only in builds with the `egui-ui` feature.
- **The mute key** (`MuteMaster`, the media key): no keycap cell.
- **Not bound by default:** `ZoomLock`, `NextSlot`, `PreviousSlot`,
  `CurrentSlot`, `MuteInactiveMaster`, `MuteSfx`, `MuteAmbience`.
- **Mouse buttons** (`Primary`, `Secondary`, `Roll`, `MapSetMarker`,
  `SpectateViewpoint`): no keycap.

## Placement

As for the other game sets (`../aoe2/SOURCES.md`, Placement): every icon sits
at the right edge and uses the full height, and the firmware clears 3 px around
it, so a letter legend stays whole. F1, F2, F5, F6, F8, Left Shift, Left Ctrl
and Left Alt use a 34×40 area and F4 a 30×40 area. On the digits and on `,`
`.` `/` `'` `-` the icon erases the shifted symbol.

All icons are flat 1-bit silhouettes drawn at the size of their key area, so
the generator places them 1:1. The solid shapes fill a smaller box in the
bottom-right corner (`INK` in `fetch_icons.py`). The hotbar slots are a 36 px
square frame with the slot number; Q shows 10.

ESC shows the game's own application icon,
`assets/voxygen/net.veloren.veloren.png` at the pinned commit, reduced to 40×40
with a box filter; pixels lighter than luma 130 are lit, which keeps the V and
the rim of the tile. It sits at the right edge beside the ESC legend. Licence
reasoning: the workspace `Cargo.toml` declares `license = "GPL-3.0-or-later"`
for every crate, the README says the project is licensed under the GNU GPL
v3.0, and the icon file has no licence of its own (no `.license` file beside
it and no REUSE table in the release), so it falls under the project's licence,
which is compatible with this repository's GPL-3.0-or-later.

## Icons

Licence texts for the icon licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0

Where each icon file comes from. The icon table gives the name to put in the
URL; the same URLs are in `SOURCES` of `cnc_remastered/fetch_icons.py`.

- Font Awesome Free 6.5.2, solid (`fa:<name>`): `https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.2/svgs/solid/<name>.svg`
- game-icons.net (`gi:<author>/<name>`): `https://game-icons.net/icons/000000/transparent/1x1/<author>/<name>.svg`
- Material Design Icons (`mdi:<name>`): `https://raw.githubusercontent.com/Templarian/MaterialDesign/2424e748e0cc63ab7b9c095a099b9fe239b737c0/svg/<name>.svg`
- GPL-3.0-or-later: https://www.gnu.org/licenses/gpl-3.0.html

| File | Source | Author | Licence |
|---|---|---|---|
| `forward.png`, `left.png`, `back.png`, `right.png` | Font Awesome Free 6.5.2 `arrow-up`, `arrow-left`, `arrow-down`, `arrow-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `jump.png` | game-icons.net `delapouite/jump-across` | delapouite | CC BY 3.0 |
| `sneak.png` | Font Awesome Free 6.5.2 `user-ninja` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `glide.png` | game-icons.net `lorc/feathered-wing` | lorc | CC BY 3.0 |
| `togglewalk.png` | Font Awesome Free 6.5.2 `person-walking` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `autowalk.png` | Font Awesome Free 6.5.2 `person-walking-arrow-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `sit.png` | Font Awesome Free 6.5.2 `chair` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `dance.png` | Material Design Icons `human-female-dance` | Pictogrammers | Apache-2.0 |
| `greet.png` | Material Design Icons `hand-wave` | Pictogrammers | Apache-2.0 |
| `block.png` | Font Awesome Free 6.5.2 `shield-halved` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `wield.png` | game-icons.net `lorc/crossed-swords` | lorc | CC BY 3.0 |
| `swaploadout.png` | Font Awesome Free 6.5.2 `right-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `interact.png` | Font Awesome Free 6.5.2 `hand-pointer` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `select.png` | Font Awesome Free 6.5.2 `bullseye` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `lantern.png` | game-icons.net `lorc/candle-light` | lorc | CC BY 3.0 |
| `mount.png` | Font Awesome Free 6.5.2 `horse` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `stayfollow.png` | Font Awesome Free 6.5.2 `paw` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `slot1.png` .. `slot10.png` | drawn by `fetch_icons.py`: a frame with the number in DejaVu Sans Bold | (this repo) | |
| `map.png` | Font Awesome Free 6.5.2 `map` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `inventory.png` | game-icons.net `lorc/knapsack` | lorc | CC BY 3.0 |
| `trade.png` | Font Awesome Free 6.5.2 `handshake` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `social.png` | Font Awesome Free 6.5.2 `user-group` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `crafting.png` | Font Awesome Free 6.5.2 `hammer` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `diary.png` | Font Awesome Free 6.5.2 `book-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `settings.png` | Font Awesome Free 6.5.2 `gear` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `controls.png` | Font Awesome Free 6.5.2 `keyboard` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `accept.png`, `decline.png` | Font Awesome Free 6.5.2 `user-check`, `user-xmark` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `freelook.png` | Font Awesome Free 6.5.2 `eye` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `cameraclamp.png` | Font Awesome Free 6.5.2 `lock` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `cyclecamera.png` | Font Awesome Free 6.5.2 `street-view` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomin.png`, `zoomout.png` | Font Awesome Free 6.5.2 `magnifying-glass-plus`, `magnifying-glass-minus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mapzoomin.png`, `mapzoomout.png` | Material Design Icons `map-plus`, `map-minus` | Pictogrammers | Apache-2.0 |
| `togglecursor.png` | Font Awesome Free 6.5.2 `arrow-pointer` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `toggleinterface.png` | Font Awesome Free 6.5.2 `eye-slash` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `toggleingameui.png` | Font Awesome Free 6.5.2 `tags` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `togglechat.png` | Font Awesome Free 6.5.2 `comment-slash` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `debug.png` | Font Awesome Free 6.5.2 `bug` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fullscreen.png` | Font Awesome Free 6.5.2 `expand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mutemusic.png` | Font Awesome Free 6.5.2 `volume-xmark` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chat.png` | game-icons.net `delapouite/chat-bubble` | delapouite | CC BY 3.0 |
| `command.png` | Font Awesome Free 6.5.2 `terminal` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `program.png` | `assets/voxygen/net.veloren.veloren.png` of veloren/veloren at commit b2f1060, reduced to 1 bit by `fetch_icons.py` | the Veloren contributors | GPL-3.0-or-later |
