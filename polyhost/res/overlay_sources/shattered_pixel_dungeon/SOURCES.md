# Shattered Pixel Dungeon overlay: sources

`scripts/generate_app_overlays.py` renders `shattered_pixel_dungeon.yaml`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `shattered_pixel_dungeon_template` (1 file) | Shattered Pixel Dungeon, desktop build: the process or window class "Shattered Pixel Dungeon" (`Shattered Pixel Dungeon.exe` on Windows), the Flatpak id `com.shatteredpixel.shatteredpixeldungeon`, and `java` or `javaw` with the window title "Shattered Pixel Dungeon" |

How the desktop build runs (`desktop/build.gradle` at v4.0.2): the release
task builds a jpackage image with a bundled Java runtime, named after `appName`
in the root `build.gradle`, "Shattered Pixel Dungeon". Its launcher is
`Shattered Pixel Dungeon.exe` on Windows, `bin/Shattered Pixel Dungeon` on
Linux and `Shattered Pixel Dungeon.app` on macOS, and the launcher loads the
Java runtime into its own process. The window title is the same words
(`config.setTitle(title)` in `DesktopLauncher.java`, from the
`Specification-Title` attribute, which is `appName`), and GLFW names the X11
window class after the title. The Flatpak id is assumed to be `appPackageName`
from `build.gradle`; the Flathub manifest was not read.

The game can also be started from its `.jar` (`java -jar`, the `desktop:run`
task). The process is then `java`, or `javaw` on Windows, which the mapping
file shares with the JetBrains IDEs, Minecraft and Ghidra. The `java` and
`javaw` entries have a `titles-startswith` route for "Shattered Pixel Dungeon"
(`tests/handler/roguelike_routing_test.py` routes this title and the Minecraft
and Ghidra titles). Names not checked on an install.

## Shortcut reference

`defaultBindings` in
`core/src/main/java/com/shatteredpixel/shatteredpixeldungeon/SPDAction.java` of
<https://github.com/00-Evan/shattered-pixel-dungeon>, release tag `v4.0.2`
(commit `57a4e06a4caf162446d1c28caa7983f0493fecf0`), read 2026-11-14. All 46
entries of the keyboard table were read. The game's key bindings window changes
the keys; this overlay shows the defaults.

No default binding uses a modifier, and the game matches the key code alone, so
only the plain layer is drawn.

| Key | Game key | Action | Icon |
|---|---|---|---|
| W | `w` | Move north | `move_n.png` |
| A | `a` | Move west | `move_w.png` |
| S | `s` | Move south | `move_s.png` |
| D | `d` | Move east | `move_e.png` |
| Space | `Space` | Wait, or pick up the item here | `wait.png` |
| Z | `z` | Rest | `rest.png` |
| E | `e` | Examine | `examine.png` |
| Q | `q` | Attack the tagged enemy | `attack.png` |
| Tab | `Tab` | Tag the next enemy | `cycle.png` |
| X | `x` | Do the tagged special action | `action.png` |
| C | `c` | Pick up the tagged item | `loot.png` |
| Enter | `Enter` | Pick up the tagged item | `loot.png` |
| R | `r` | Resume the interrupted movement | `resume.png` |
| F | `f` | Open the inventory | `inventory.png` |
| I | `i` | Open the inventory | `inventory.png` |
| H | `h` | Hero information | `heroinfo.png` |
| J | `j` | Open the journal | `journal.png` |
| Backspace | `Backspace` | Go back or open the game menu | `back.png` |
| 1 | `1` | Use quickslot 1 | `slot1.png` |
| 2 | `2` | Use quickslot 2 | `slot2.png` |
| 3 | `3` | Use quickslot 3 | `slot3.png` |
| 4 | `4` | Use quickslot 4 | `slot4.png` |
| 5 | `5` | Use quickslot 5 | `slot5.png` |
| 6 | `6` | Use quickslot 6 | `slot6.png` |
| F1 | `F1` | Open bag 1 (the backpack) | `bag1.png` |
| F2 | `F2` | Open bag 2 | `bag2.png` |
| F3 | `F3` | Open bag 3 | `bag3.png` |
| F4 | `F4` | Open bag 4 | `bag4.png` |
| F5 | `F5` | Open bag 5 | `bag5.png` |
| = | `=` | Zoom in | `zoomin.png` |
| - | `-` | Zoom out | `zoomout.png` |

The same icon on two keys means the same action: F and I open the inventory, C
and Enter pick up the tagged item.

The "tagged" enemy, item and action are the indicators the game shows at the
edge of the screen (attack, loot and action tags); Tab moves the attack tag to
the next enemy in view.

Other meanings of drawn keys (not drawn):

| Key | In the game (drawn) | Other screens |
|---|---|---|
| Backspace | Go back; with nothing open, the game menu | the same on every screen |
| W A S D | Move | none |
| Enter | Pick up the tagged item | text fields: confirm |

## Left out

- Escape: go back, the same as Backspace. ESC shows the program mark.
- The arrow keys (move): they keep their own legends.
- The keypad (move in eight directions, 5 waits): the keypad has no cell.
- `+` on the main block is Shift+`=` on the US layout: zoom in is drawn on `=`
  only.
- The actions with no default key (the diagonal moves outside the keypad, the
  inventory selectors, quickslot swap): nothing to draw.
- The controller bindings.

## Placement

As for fheroes2 (`../fheroes2/SOURCES.md`): every icon sits at the right edge
and uses the full height, and the firmware clears 3 px around it, so a letter
legend stays whole. On a digit key the shifted symbol of the legend is erased.
F1 to F5 are 34×40.

All icons are flat 1-bit silhouettes drawn at their key area, so the generator
places them 1:1. The quickslot keys 1 to 6 show a 34×34 slot frame with the
slot number (DejaVu Sans Bold, 18 px high). The bag keys F1 to F5 show the
inventory key's backpack as one filled shape with the bag number cut out. The
movement arrows are drawn by the helpers in `../dcss/fetch_icons.py`.

## ESC mark

ESC shows "Shattered", "Pixel", "Dungeon" on three lines in VT323 (SIL OFL
1.1, `ofl/vt323/VT323-Regular.ttf` from google/fonts at commit e7db6ca), at the
largest one size at which each line fits 70 px wide and all three, 1 px apart,
fit 38 px high, drawn over the whole cell without the ESC legend
(`program_icon_legend: false`, protocol v25). A pixel is lit from grey 110 of
255.

The game's own icon could be used: the source files say "either version 3 of
the License, or (at your option) any later version" (GPL-3.0-or-later), which
is this repository's licence. It was tried and is not used because it does not
read at 1 bit: `desktop/src/main/assets/icons/icon_64.png` is a 16×16 pixel-art
chest whose gold frame, green panels and dark background differ in colour more
than in brightness, and every luma threshold from 56 to 170 gave a shape that
does not look like a chest.

## Icons

Licence texts for the icon and font licences named in this file:

- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/

Where each icon file comes from. The icon table gives the name to put in the
URL; the same URLs are in `SOURCES` of `cnc_remastered/fetch_icons.py`.

- Font Awesome Free 6.5.2, solid (`fa:<name>`): `https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.2/svgs/solid/<name>.svg`
- DejaVu Fonts licence (Bitstream Vera): https://dejavu-fonts.github.io/License.html

Material Design Icons are from <https://pictogrammers.com/library/mdi/>
(Templarian/MaterialDesign at commit 2424e74).

| File | Source | Author | Licence |
|---|---|---|---|
| `wait.png` | Font Awesome Free 6.5.2 `hourglass-half` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `inventory.png` | Material Design Icons `bag-personal` | Pictogrammers | Apache-2.0 |
| `examine.png` | Font Awesome Free 6.5.2 `magnifying-glass` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `rest.png` | Font Awesome Free 6.5.2 `bed` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `attack.png` | Material Design Icons `sword-cross` | Pictogrammers | Apache-2.0 |
| `cycle.png` | Font Awesome Free 6.5.2 `arrows-rotate` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `action.png` | Font Awesome Free 6.5.2 `hand-pointer` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `loot.png` | Material Design Icons `tray-arrow-up` | Pictogrammers | Apache-2.0 |
| `resume.png` | Font Awesome Free 6.5.2 `forward` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `heroinfo.png` | Font Awesome Free 6.5.2 `id-card` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `journal.png` | Font Awesome Free 6.5.2 `book` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomin.png` | Font Awesome Free 6.5.2 `magnifying-glass-plus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `zoomout.png` | Font Awesome Free 6.5.2 `magnifying-glass-minus` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `back.png` | Font Awesome Free 6.5.2 `reply` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `move_<direction>.png` (4) | an arrow, drawn by `fetch_icons.py` | this repository | GPL-3.0-or-later |
| `bag1.png` to `bag5.png` | Material Design Icons `bag-personal`, filled, with the number cut out in DejaVu Sans Bold by `fetch_icons.py` | Pictogrammers; DejaVu Fonts (digit) | Apache-2.0; DejaVu Fonts licence |
| `slot1.png` to `slot6.png` | a frame drawn by `fetch_icons.py` with the number in DejaVu Sans Bold | this repository; DejaVu Fonts (digit) | GPL-3.0-or-later; DejaVu Fonts licence |
| `program.png` | "Shattered", "Pixel", "Dungeon" set in VT323 by `fetch_icons.py` | The VT323 Project Authors (font) | SIL OFL 1.1 |
