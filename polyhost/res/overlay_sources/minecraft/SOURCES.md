# Minecraft overlays: sources

`scripts/generate_app_overlays.py` renders `minecraft_java.yaml` and
`minecraft_bedrock.yaml`; `fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `minecraft_java_template` (1 file) | Minecraft: Java Edition. Windows `javaw.exe` or `java.exe`; Linux `java` (X11) or the window class `Minecraft 1.21.x` / `Minecraft* 1.21.x` (GNOME and KDE Wayland); macOS `java` or `Minecraft`. Only windows titled "Minecraft <version>" or "Minecraft* <version>". |
| `minecraft_bedrock_template` (2 files) | Minecraft: Bedrock Edition on Windows: `Minecraft.Windows.exe` (reported as `minecraft`), or `ApplicationFrameHost.exe` for the older UWP build. Only windows titled "Minecraft" or "Minecraft Preview". |

None of the app names or titles were checked on an install. They come from the
Minecraft Wiki and from how the host reports a process (Windows cuts the
executable name at its first dot; X11 reports the process, `ps -o comm=`; the
Wayland reporters report the window class, which GLFW sets to the first window
title). A snapshot title such as "Minecraft 25w14a" still routes by title in
`java`, `javaw` and `minecraft`, but a Wayland window class `minecraft 25w14a`
keeps its version and matches no key.

The Minecraft Launcher (title "Minecraft Launcher") gets neither set: every
route requires a version after "Minecraft" (Java) or the bare title (Bedrock).

## Shortcut reference

The default controls on <https://minecraft.wiki/w/Controls> (read 2026-10-30,
the wikitext through `?action=raw`): the *Java Edition* section (non-configurable
controls and configurable controls, with the `key.*` identifiers that
`options.txt` stores as `key_key.*`) and the *Bedrock Edition* → *Keyboard &
Mouse* section. A user who rebinds a key in the game still sees the default.

Ctrl is sprint and Shift is sneak in both editions, and both are held while the
player moves. So the sprint icon is drawn on Left Ctrl itself, with and without
Ctrl held, and the sneak icon on Left Shift, with and without Shift held. The
movement keys, Space and the hotbar digits are drawn on the Ctrl and Shift
layers as well, because they do the same thing while sprint or sneak is held.

### Java Edition

| Key | Action | Identifier |
|---|---|---|
| W / A / S / D | Walk forward / strafe left / walk backward / strafe right | `key.forward`, `key.left`, `key.back`, `key.right` |
| Space | Jump | `key.jump` |
| Left Shift | Sneak | `key.sneak` |
| Left Ctrl | Sprint | `key.sprint` |
| 1 to 9 | Hotbar slot 1 to 9 | `key.hotbar.1` .. `key.hotbar.9` |
| E | Open / close inventory | `key.inventory` |
| Q | Drop selected item | `key.drop` |
| Ctrl+Q | Drop the whole stack | (non-configurable) |
| F | Swap item with off hand | `key.swapOffhand` |
| C | Save hotbar activator (Creative) | `key.saveToolbarActivator` |
| X | Load hotbar activator (Creative) | `key.loadToolbarActivator` |
| T | Open chat | `key.chat` |
| / | Open command | `key.command` |
| Tab | List players | `key.playerlist` |
| O | Friends list (since 26.2) | `key.friends` |
| P | Social interactions (renamed Other Players in 26.4) | `key.socialInteractions` |
| Ctrl+B | Narrator on / off | (non-configurable) |
| L | Advancements | `key.advancements` |
| G | Quick actions (since 1.21.6) | `key.quickActions` |
| F1 | Hide HUD | `key.toggleGui` |
| F2 | Take screenshot | `key.screenshot` |
| F3 | Debug screen | `key.debug.overlay` |
| F4 | Toggle spectator shader effects | `key.toggleSpectatorShaderEffects` |
| F5 | Toggle perspective | `key.togglePerspective` |
| F11 | Toggle fullscreen | `key.fullscreen` |
| Esc | program mark (Esc opens the pause menu) | |

### Bedrock Edition (Windows, keyboard and mouse)

| Key | Action |
|---|---|
| W / A / S / D | Walk forward / strafe left / walk backward / strafe right |
| Space | Jump / fly up |
| Left Shift | Sneak / fly down |
| Left Ctrl | Sprint |
| 1 to 9 | Hotbar slot 1 to 9 |
| E | Inventory |
| Q | Drop item |
| Ctrl+Q | Drop the whole stack |
| Z | Mob effects |
| T, Enter | Chat |
| / | Open command |
| B | Emote |
| N | Open notification |
| Ctrl+B | Text to speech on / off |
| [ / ] | Menu tab left / right |
| Ctrl+H | Content log history |
| Ctrl+Alt+C | Copy coordinates (needs the "Copy Coordinate GUI" creator setting) |
| Ctrl+Alt+X | Copy facing coordinates (same setting) |
| F1 | Hide HUD |
| F2 | Take screenshot |
| F4 | Social drawer (since 26.10) |
| F5 | Toggle perspective |
| F8 | Paper doll on / off |
| F10 | Controller hints on / off |
| F11 | Toggle fullscreen |
| Esc | program mark (Esc opens the pause menu) |

Differences from Java Edition: Bedrock has no F3 debug screen and no F3
combinations, no advancements key (L), no player list key (Tab), no off-hand
swap key (F), no hotbar save and load keys (C, X), no friends, social
interactions or quick actions keys (O, P, G), and no F4 shader toggle. It adds
Z, B, N, `[` `]`, Ctrl+H, Ctrl+Alt+C, Ctrl+Alt+X, F4 (social drawer), F8 and
F10.

## Left out

- **The F3 debug combinations (Java).** F3 is held like a key, not a modifier:
  the keyboard has no F3 layer, so F3+A and the rest cannot be drawn on a
  modifier channel. The page lists F3+A reload chunks, F3+B hitboxes, F3+C copy
  location (held for 10 s: debug crash), F3+D clear chat, F3+G chunk borders,
  F3+H advanced tooltips, F3+I copy data, F3+L profiling, F3+N spectator mode,
  F3+P pause on lost focus, F3+S dump dynamic textures, F3+T reload resource
  packs, F3+V dump version info, F3+X improved transparency, F3+F4 game mode
  switcher, F3+F6 debug options and F3+1 to F3+4 the debug charts. F3+Q (help)
  is not on the page any more and is not drawn either.
- **C or X + a digit (Java, Creative).** The hotbar activators are also held
  keys; C and X themselves are drawn.
- **Menu-only keys:** Tab / Shift+Tab focus, Ctrl+Tab / Ctrl+Shift+Tab screen
  tabs, the arrow keys, Page Up / Page Down in chat and books, Enter in menus,
  F5 refreshing the server list, Backspace in Bedrock's Ore UI menus, and Space
  / Ctrl / Up in the credits. The keys keep their gameplay meaning on the
  overlay.
- **Enter (Java)** sends a chat message, which only matters with chat open.
  Bedrock lists Enter as a chat key, so it is drawn there.
- **Unbound by default:** Java Toggle Cinematic Camera and Highlight Players;
  Bedrock Identify and the command macros (Alt plus a key the user chooses).
- **Bedrock "Full Keyboard Gameplay"**, an option that moves the camera and
  menus onto the keyboard and the numeric keypad, which has no keycap cell.
- **Right Ctrl and Right Shift.** The Java page names the left keys only; the
  Bedrock page says Control and Shift, which was not checked on the right
  keys.
- **Mouse buttons** (attack, use, pick block): no keycap.

## Placement

As for the other game sets (`../aoe2/SOURCES.md`, Placement): every icon sits at
the right edge and uses the full height, and the firmware clears 3 px around it,
so a letter legend stays whole. F1, F2, F5, F8, Left Ctrl and Left Shift use a
34×40 area and F4 a 30×40 area, following AoE2's measured legend widths. F3,
F10 and F11 are 40×40 and cover the right part of their legend, as in the
Warcraft III set. On the digits and on `/`, `[` and `]` the icon erases the
shifted symbol, which the game does not use.

Each icon is drawn 1-bit by `fetch_icons.py` at the size of its key area, so the
generator places it 1:1. The solid icons that read heavier than the outline
ones (save, load, camera, chat bubble and others in `INK`) fill a smaller box
in the bottom-right corner of that area. The WASD arrows fill a 30×36 or 36×30
box.

The hotbar slots 1 to 9 are a square slot with a 2 px border and the digit in
Press Start 2P at three times its 8 px size, so its pixel grid stays exact. Drop
item is one block over a drawn down arrow; drop stack is three blocks over the
same arrow.

ESC shows MINECRAFT over JAVA or BEDROCK in Press Start 2P (SIL OFL 1.1,
`ofl/pressstart2p/PressStart2P-Regular.ttf` from google/fonts at commit
e7db6ca): MINECRAFT at 1x across and 2x down, the edition name at 1x. It is
drawn over the whole cell without the ESC legend (`program_icon_legend: false`,
protocol v25). The game's logo art is not used, and Simple Icons has no
Minecraft logo.

## Icons

| File | Source | Author | Licence |
|---|---|---|---|
| `forward.png`, `left.png`, `back.png`, `right.png` | Font Awesome Free 6.5.2 `arrow-up`, `arrow-left`, `arrow-down`, `arrow-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `jump.png` | game-icons.net `delapouite/jump-across` | delapouite | CC BY 3.0 |
| `sneak.png` | Font Awesome Free 6.5.2 `user-ninja` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `sprint.png` | Font Awesome Free 6.5.2 `person-running` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `inventory.png` | game-icons.net `lorc/knapsack` | lorc | CC BY 3.0 |
| `offhand.png` | Font Awesome Free 6.5.2 `right-left` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `savehotbar.png` | Font Awesome Free 6.5.2 `floppy-disk` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `loadhotbar.png` | Font Awesome Free 6.5.2 `folder-open` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `chat.png` | game-icons.net `delapouite/chat-bubble` | delapouite | CC BY 3.0 |
| `command.png` | Font Awesome Free 6.5.2 `terminal` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `playerlist.png` | Font Awesome Free 6.5.2 `users` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `friends.png` | Font Awesome Free 6.5.2 `handshake` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `socialhide.png` | Font Awesome Free 6.5.2 `user-slash` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `socialdrawer.png` | Font Awesome Free 6.5.2 `user-group` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `narrator.png` | Font Awesome Free 6.5.2 `volume-high` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `emote.png` | Font Awesome Free 6.5.2 `face-smile` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `notification.png` | Font Awesome Free 6.5.2 `bell` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `advancements.png` | Font Awesome Free 6.5.2 `trophy` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `quickactions.png` | Font Awesome Free 6.5.2 `bolt` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `effects.png` | Font Awesome Free 6.5.2 `flask` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `contentlog.png` | Font Awesome Free 6.5.2 `file-lines` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `tableft.png`, `tabright.png` | Font Awesome Free 6.5.2 `angles-left`, `angles-right` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `copycoords.png` | Font Awesome Free 6.5.2 `location-dot` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `copyfacing.png` | Font Awesome Free 6.5.2 `crosshairs` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `hidehud.png` | Font Awesome Free 6.5.2 `eye-slash` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `screenshot.png` | Font Awesome Free 6.5.2 `camera` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `debug.png` | Font Awesome Free 6.5.2 `bug` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `shader.png` | Font Awesome Free 6.5.2 `wand-magic-sparkles` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `perspective.png` | Font Awesome Free 6.5.2 `street-view` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `paperdoll.png` | Font Awesome Free 6.5.2 `person` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `controllerhints.png` | Font Awesome Free 6.5.2 `gamepad` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `fullscreen.png` | Font Awesome Free 6.5.2 `expand` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `_block.png` (part), `drop.png`, `dropstack.png` | game-icons.net `delapouite/cube`, with an arrow drawn by `fetch_icons.py` | delapouite | CC BY 3.0 |
| `slot1.png` .. `slot9.png` | drawn by `fetch_icons.py`; digits in Press Start 2P | The Press Start 2P Project Authors | SIL OFL 1.1 |
| `program_java.png`, `program_bedrock.png` | drawn by `fetch_icons.py` in Press Start 2P | The Press Start 2P Project Authors | SIL OFL 1.1 |
