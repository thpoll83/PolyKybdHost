# 0 A.D. overlay: sources

`scripts/generate_app_overlays.py` renders `zeroad.yaml`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `zeroad_template` (2 files) | 0 A.D. 0.28.0: `pyrogenesis` on Linux, `pyrogenesis.exe` on Windows, the `0ad` launcher, the Flatpak `com.play0ad.zeroad` |

The process names come from the source, not from an install: the engine is the
premake project `pyrogenesis` (`build/premake/premake5.lua`), and
`build/resources/0ad.desktop` runs `0ad` with `StartupWMClass=pyrogenesis`.
The Flatpak app id is Flathub's. None of them was checked on an install.

## Shortcut reference

The `[hotkey]` sections of `binaries/data/config/default.cfg` in the 0 A.D.
repository (<https://gitea.wildfiregames.com/0ad/0ad>, also mirrored at
github.com/0ad/0ad) at tag `v0.28.0`, commit
a2cae4d69f816e9e9d7eecb6bf88f762afc0c90d, the newest release on 2026-10-30.
0 A.D. reads key names as scancodes (`source/ps/KeyName.cpp`), so a binding is
a key position on a US layout: `Plus` is the `=` key, `Semicolon` the `;` key.
A user's `user.cfg` and the in-game hotkey editor change these defaults; the
overlay shows the defaults.

Control groups: 1 to 0 select groups 1 to 10, Ctrl+digit saves the selection
as that group, Shift+digit adds the selection to it. Each digit has its own
unit, drawn once at full height: 1 hoplite helmet, 2 archer, 3 horse, 4 war
elephant, 5 spearman, 6 trebuchet, 7 siege tower, 8 trireme, 9 centurion
helmet, 0 citizen. The game does not tie a group number to a unit type; the
icons only suggest a habit.

Keys labelled "(hold)" are modifiers: the game reads them while the mouse is
clicked (for example G and a click on a unit guards it).

## Left out

- Z, X, C, V, B, N, M and the comma: they add the first to eighth unit of the
  selected building to its queue, so the unit depends on the selection. C is
  also the capture modifier.
- Arrow keys (scroll, and with Ctrl rotate): the arrows keep their own legends.
  W, A, S, D, Q, E and Ctrl+W/A/S/D are labelled.
- Tab, Shift+Tab and Alt+S / Alt+W as tab keys in dialogs: Shift+Tab is
  labelled as the bird's eye view, its meaning in a match.
- Ctrl+C, Ctrl+V, Ctrl+X, Ctrl+Backspace and Ctrl+Delete: text editing in
  input boxes.
- Developer and diagnostic keys: the profiler (F11, Shift+F11, Ctrl+F11),
  wireframe (Alt+Shift+W), silhouettes (Alt+Shift+S), the screenshot watermark
  (Alt+K), and the time-warp keys (Ctrl+Space, Shift+Backspace), which work
  only with time-warp mode on.
- Esc as "cancel": the ESC key shows the program mark.
- The objectives panel, game speed, formations and stances have no default
  key in `default.cfg`.

## Placement

As for Warcraft III (`../warcraft3/SOURCES.md`): every icon sits at the right
edge and uses the full height, and the firmware clears 3 px around it, so a
letter legend stays whole. The F-key areas use AoE2's measured legend widths:
F2, F3 and F5 to F8 are 34×40; F9, F10 and F12 are 40×40 and cover the right
part of their legend. The control groups are 48×40, drawn 1:1, 5 px from the
right edge; Ctrl adds a plus, Shift a plus in a ring.

All icons are flat 1-bit silhouettes, as in the Warcraft III set. Solid icons
fill a smaller box (`INK` in `fetch_icons.py`) so they do not outweigh the
outline icons. Composites drawn by `fetch_icons.py`:

- Q, E, Ctrl+A, Ctrl+D (rotate the camera): a person with an arrow round
  their feet, drawn by `warcraft3/fetch_icons.py`'s `rotate_icons()`. Q and
  Ctrl+A rotate clockwise and point left, like Ctrl+Left, which the game binds
  to the same action.
- Ctrl+F5 to Ctrl+F8 (set a camera position): the F5 to F8 pin with a plus.
- Ctrl+Shift and Ctrl+Alt with S, R, Z (scroll, rotation and zoom speed): the
  move, rotate and magnifier icons with a plus (faster) or a minus (slower).

ESC shows 0 A.D. in Cinzel Black (SIL OFL 1.1, the `wght` 900 instance of
`ofl/cinzel/Cinzel[wght].ttf` from google/fonts at commit e7db6ca, the font
of the Warcraft III mark), drawn over the whole cell without the ESC legend
(`program_icon_legend: false`, protocol v25). A pixel is lit from grey 90 of
255.

## The game's own art (not used)

0 A.D.'s art (`binaries/data/mods/*/art`) is CC BY-SA 3.0 (`LICENSE.md` at
v0.28.0), so its logo and unit portraits could be used, with credit to
Wildfire Games and the overlay PNGs then under CC BY-SA 3.0. This set does not
use them: every icon is from the free sets below.

## Icons

Licence texts for the icon and font licences named in this file:

- CC BY 3.0: https://creativecommons.org/licenses/by/3.0/
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

| File | Source | Author | Licence |
|---|---|---|---|
| `pause.png` | Font Awesome Free 6.5.2 `pause` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `summary.png` | Font Awesome Free 6.5.2 `chart-column` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `gamemenu.png` | Font Awesome Free 6.5.2 `bars` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `diplomacy.png` | game-icons.net `delapouite/shaking-hands` | delapouite | CC BY 3.0 |
| `barter.png` | Font Awesome Free 6.5.2 `scale-balanced` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `matchsettings.png` | Font Awesome Free 6.5.2 `sliders` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `tutorial.png` | Font Awesome Free 6.5.2 `book-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `lobby.png` | Font Awesome Free 6.5.2 `earth-europe` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `structree.png` | Font Awesome Free 6.5.2 `sitemap` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `civinfo.png` | game-icons.net `delapouite/greek-temple` | delapouite | CC BY 3.0 |
| `quicksave.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quickload.png` | Font Awesome Free 6.5.2 `folder-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `bigscreenshot.png` | Font Awesome Free 6.5.2 `image` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `mousegrab.png` | Font Awesome Free 6.5.2 `computer-mouse` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `console.png` | Font Awesome Free 6.5.2 `terminal` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fullscreen.png` | Font Awesome Free 6.5.2 `expand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fps.png` | Font Awesome Free 6.5.2 `gauge-high` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `realtime.png` | Font Awesome Free 6.5.2 `clock` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `elapsed.png` | Font Awesome Free 6.5.2 `stopwatch` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `hidegui.png` | Font Awesome Free 6.5.2 `eye-slash` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `devcommands.png` | Font Awesome Free 6.5.2 `code` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `diplocolors.png` | Font Awesome Free 6.5.2 `palette` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `attackrange.png` | Font Awesome Free 6.5.2 `bullseye` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `aurarange.png` | game-icons.net `lorc/aura` | lorc | CC BY 3.0 |
| `healrange.png` | Font Awesome Free 6.5.2 `kit-medical` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `guarded.png` | Font Awesome Free 6.5.2 `shield-heart` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `guarding.png` | Font Awesome Free 6.5.2 `user-shield` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `resetcam.png` | Font Awesome Free 6.5.2 `compass` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `lastattack.png` | Font Awesome Free 6.5.2 `triangle-exclamation` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `birdseye.png` | Font Awesome Free 6.5.2 `map` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomin.png` | Font Awesome Free 6.5.2 `magnifying-glass-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomout.png` | Font Awesome Free 6.5.2 `magnifying-glass-minus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `lookup.png` | Font Awesome Free 6.5.2 `angles-up` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `lookdown.png` | Font Awesome Free 6.5.2 `angles-down` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `scrollup.png` | Font Awesome Free 6.5.2 `arrow-up` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `scrolldown.png` | Font Awesome Free 6.5.2 `arrow-down` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `scrollleft.png` | Font Awesome Free 6.5.2 `arrow-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `scrollright.png` | Font Awesome Free 6.5.2 `arrow-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `jump.png` | Font Awesome Free 6.5.2 `location-dot` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `idlebuilder.png` | Font Awesome Free 6.5.2 `helmet-safety` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `idleworker.png` | game-icons.net `delapouite/farmer` | delapouite | CC BY 3.0 |
| `idlewarrior.png` | game-icons.net `lorc/crossed-swords` | lorc | CC BY 3.0 |
| `idleunit.png` | Font Awesome Free 6.5.2 `person-circle-question` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `idleonly.png` | Font Awesome Free 6.5.2 `hourglass-half` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `woundedonly.png` | Font Awesome Free 6.5.2 `user-injured` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `civilonly.png` | Font Awesome Free 6.5.2 `wheat-awn` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `kill.png` | Font Awesome Free 6.5.2 `skull` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `stop.png` | Font Awesome Free 6.5.2 `hand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `backtowork.png` | Font Awesome Free 6.5.2 `person-digging` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `unload.png` | Font Awesome Free 6.5.2 `arrow-right-from-bracket` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `guard.png` | Font Awesome Free 6.5.2 `shield-halved` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `patrol.png` | Font Awesome Free 6.5.2 `route` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `repair.png` | Font Awesome Free 6.5.2 `hammer` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `flare.png` | game-icons.net `delapouite/torch` | delapouite | CC BY 3.0 |
| `attack.png` | game-icons.net `lorc/broadsword` | lorc | CC BY 3.0 |
| `attackunits.png` | game-icons.net `lorc/target-arrows` | lorc | CC BY 3.0 |
| `buildccw.png` | Font Awesome Free 6.5.2 `arrow-rotate-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `buildcw.png` | Font Awesome Free 6.5.2 `arrow-rotate-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chat.png` | game-icons.net `delapouite/chat-bubble` | delapouite | CC BY 3.0 |
| `teamchat.png` | game-icons.net `lorc/conversation` | lorc | CC BY 3.0 |
| `privatechat.png` | Font Awesome Free 6.5.2 `envelope` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `jumpset.png` | Font Awesome Free 6.5.2 `location-dot` (solid), with a plus drawn by `fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `scrollfast.png`, `scrollslow.png` | Font Awesome Free 6.5.2 `arrows-up-down-left-right` (solid), with a plus or a minus | Fonticons, Inc. | CC BY 4.0 |
| `rotatefast.png`, `rotateslow.png` | Font Awesome Free 6.5.2 `rotate` (solid), with a plus or a minus | Fonticons, Inc. | CC BY 4.0 |
| `zoomfast.png`, `zoomslow.png` | Font Awesome Free 6.5.2 `magnifying-glass` (solid), with a plus or a minus | Fonticons, Inc. | CC BY 4.0 |
| `rotateleft.png`, `rotateright.png` | Font Awesome Free 6.5.2 `street-view` (solid), with an arrow drawn by `warcraft3/fetch_icons.py` | Fonticons, Inc. | CC BY 4.0 |
| `group1.png`, `groupnew1.png`, `groupadd1.png` | game-icons.net `delapouite/spartan-helmet` | delapouite | CC BY 3.0 |
| `group2.png`, `groupnew2.png`, `groupadd2.png` | game-icons.net `lorc/bowman` | lorc | CC BY 3.0 |
| `group3.png`, `groupnew3.png`, `groupadd3.png` | game-icons.net `delapouite/horse-head` | delapouite | CC BY 3.0 |
| `group4.png`, `groupnew4.png`, `groupadd4.png` | game-icons.net `delapouite/elephant` | delapouite | CC BY 3.0 |
| `group5.png`, `groupnew5.png`, `groupadd5.png` | game-icons.net `lorc/spartan` | lorc | CC BY 3.0 |
| `group6.png`, `groupnew6.png`, `groupadd6.png` | game-icons.net `delapouite/trebuchet` | delapouite | CC BY 3.0 |
| `group7.png`, `groupnew7.png`, `groupadd7.png` | game-icons.net `delapouite/siege-tower` | delapouite | CC BY 3.0 |
| `group8.png`, `groupnew8.png`, `groupadd8.png` | game-icons.net `delapouite/trireme` | delapouite | CC BY 3.0 |
| `group9.png`, `groupnew9.png`, `groupadd9.png` | game-icons.net `delapouite/centurion-helmet` | delapouite | CC BY 3.0 |
| `group0.png`, `groupnew0.png`, `groupadd0.png` | game-icons.net `delapouite/roman-toga` | delapouite | CC BY 3.0 |
| `program.png` | 0 A.D. set in Cinzel Black, google/fonts `ofl/cinzel` at e7db6ca | Natanael Gama | SIL OFL 1.1 |

Files whose name starts with `_` are the unprocessed renders the composites
and control groups are drawn from.
