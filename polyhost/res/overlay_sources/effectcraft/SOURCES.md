# EffectCraft overlay: sources and licences

EffectCraft (<https://github.com/storytold/effectcraft>, part of the ArtCraft
"Crafting Apps" suite, <https://getartcraft.com/apps>) is an open-source Rust/egui
motion graphics and VFX compositor modelled on After Effects. Licence: MIT OR
Apache-2.0, both GPL-3.0-compatible.

All shortcuts and the app icon come from commit
**`549e9d825132986d6167c1432cd3328efcbb0278`**.

## Shortcuts

The authority is EffectCraft's own keymap, the built-in read-only preset
"EffectCraft Default" (`crates/engine/src/shortcuts.rs:1-11`), not Adobe's
documentation. The preset is assembled by `shortcuts::bindables()`
(`shortcuts.rs:71-139`) from three sources:

1. **The engine menu tree**: `crates/engine/src/menus.rs` `TREE` (line 487 on;
   File 515, Edit 602, Composition 690, Layer 726, Effect 967, Animation 976,
   View 1076, Window 1167, Help 1232). Entries with bound parameters (the
   `Window` panels `Cmd+0..9`, resolutions `Cmd+J` etc., layer quality, arrange
   and transform) state their own keys there.
2. **The command registry**: the `cmd!(…, Some("<keys>"), …)` and `fe!(…)`
   rows in `crates/engine/src/commands/*.rs`, e.g. `layer.rs:1631`
   (Cmd+Up select previous layer), `layer.rs:1651` (Enter rename),
   `layer.rs:1681` (Alt+PgUp), `anim.rs:447` (Alt+Left), `time.rs:193,209`
   (in/out points, J/K), `edit.rs:875` (Delete clear), `frontend.rs:36`
   (Cmd+Shift+Space Quick Apply), `frontend.rs:105` (Tab mini-flowchart).
   Files carrying defaults: help, layer_time, three_d, prop, edit, file,
   paths, layer, anim, layer_menu, viewer_cmds, nav_more, effect, comp,
   file_more, settings, proxy, time.
3. **The frontend's `UI_COMMANDS`**: `crates/ui-egui/src/menus.rs:29-128`
   (tools, reveal keys, timeline navigation, viewer nudge, workspace keys).

Rather than transcribe ~270 chords by hand, the table was dumped by running
`bindables(&[])` in a throw-away cargo test against the clone (188 engine
bindables with keys), and `UI_COMMANDS` was parsed from source. Every chord was
then checked against `bindings.yaml`: nothing missing except the skips below.

The dispatcher (`crates/ui-egui/src/menus.rs:1697-1719` `bindings()`,
`1773-1965` `handle_shortcuts_impl`) reads exactly that table, plus one
hard-coded key: **bare Backspace runs Edit > Clear like Delete**
(`menus.rs:1924`). Space (`playback.toggle`, engine `menus.rs:703`)
runs on release; held, it is the temporary Hand tool (`menus.rs:1881-1893`).
It is bound as Preview, as in the reference set.

### Modifiers

EffectCraft's `Cmd` is egui's COMMAND modifier: Ctrl on Windows/Linux, Cmd on
macOS (`shortcuts.rs:11`, `menus.rs:1721` `mods_match`). So every `Cmd` chord is
`CMDCTRL` here. The default preset binds **no** literal-Ctrl chord.

### macOS

The native macOS menu (`crates/ui-egui/src/native_menu.rs:185`,
`apps/effectcraft/src/native_menu.rs:117-118`) inserts muda's predefined
**Hide** (Cmd+H) and **Hide Others** (Cmd+Option+H) items in the application
menu, which comes before File and Animation. They take those two key equivalents, so two
bindings are `except: [macos]`:

| Chord | Windows/Linux | macOS |
|---|---|---|
| Cmd+H | Replace Footage | Hide EffectCraft (system) |
| Cmd+Alt+H | Toggle Hold Keyframe | Hide Others (system) |

Cmd+Q is Exit on every platform. Cmd+M stays bound on macOS because EffectCraft
lists it there itself; its documented alternate Cmd+Shift+/ is drawn too.

### Context-dependent keys

The dispatcher prefers the focused panel's binding over an application one
(`menus.rs:1950-1956`). The default preset has no two commands on one chord, so
nothing had to be chosen. Bare Enter is the timeline Rename. In the Project panel
the panel renames the item itself (`menus.rs:1918`), which is the same action.

### Skipped

- **Escape** (Switch to Last 3D View) and **Shift+Escape** (Activate Most Recent
  Composition): the Escape cell is the program mark on every layer.
- **Numpad**: `Num0` / `Shift+Num0` / `Alt+Num0` (previews) and `Num*` (Add
  Marker). The keypad has no overlay cell. Space and Shift+Space carry preview.
- Commands with no default key (the bulk of the menu tree) and panel-internal
  keys not routed through the shortcut table (text editing, menu-bar Alt
  navigation in `menu_keys.rs`, dialog Escape).

## Icons

| File(s) | Source | Licence |
|---|---|---|
| 34 icons copied from `../aftereffects/icons/` (anchorpoint, position, scale, rotation, opacity, feather, effects, keyframes, select, hand, zoom, pen, shape, panbehind, gotoin, gotoout, preview, newcomp, open, save, import, compsettings, renderqueue, solid, type, undo, redo, cut, copy, paste, selectall, duplicate, splitlayer, precompose) | Microsoft Fluent UI System Icons, via the reference set; byte-identical | MIT |
| bare Fluent folder names in `fetch_icons.py` `FLUENT` | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | MIT |
| `ms:` entries in `FLUENT` | [Material Symbols](https://github.com/google/material-design-icons), weight 300 | Apache-2.0 |
| `res_*`, `ch_*`, `fp_*` badges (1/1, 1/2, 1/4, 1/n; R/G/B/A channels; FQ/AR/DR/FD/WF fast-preview modes), `keytoggle.png` (diamond + plus) | drawn in `fetch_icons.py` (Liberation Sans Bold) | GPL-3.0-or-later (this repo) |
| `effectcraft.png` (ESC program mark) | EffectCraft's own app icon, `assets/app-icon/effectcraft.ico`, 48 px frame | MIT OR Apache-2.0 |

Labels that name a shared concept (Save, Undo, Redo, Copy, Cut, Paste, Select
all, Close, Find, Help, Save as, Zoom in/out) are drawn by the shared concept
renderer, not from `icons/` (see the skill).

## Program mark

`assets/app-icon/` holds `LICENSE.txt` ("Original artwork made for this project
by the project owner in ArtCraft … Licensed like the rest of EffectCraft, under
either of Apache-2.0 / MIT"), a README, and one `.attribution` file per asset.
`effectcraft.ico.attribution` reads: author "EffectCraft contributors (drawing
by the project owner in ArtCraft)", source "original work", licence "MIT OR
Apache-2.0". No third-party material, so it ships here.

The icon is an engraved unicorn bust: three colours, a pink field (#e0368f),
a paper-coloured figure (#efe9dc) and ink linework. The sweep covered frames
32/40/48/64/128/256 × `luma`/`bright` × thresholds 60..210, rendered through the
generator's own `render_icon` at the `[40, 40]` right-anchored region. `luma`
either lights the pink field as a solid tile or keeps only scattered ink. `bright`
lights the paper figure, and the 48 px frame at t130 gives the most solid head
and horn. The hatching still leaves some stipple at 40 px; that is inherent to
the engraving.

## Window matching

| Platform | Reported name | Source |
|---|---|---|
| Windows | `effectcraft.exe` → `effectcraft` | `apps/effectcraft/Cargo.toml` package name; `packaging/windows/effectcraft.wxs:77` |
| macOS | `EffectCraft` → `effectcraft` | `packaging/macos/Info.plist.in:11` CFBundleName |
| Linux X11 | `effectcraft` (process) | `packaging/linux/ai.storyteller.effectcraft.desktop` `Exec=effectcraft` |
| Linux Wayland / GNOME wm_class | `ai.storyteller.effectcraft` | `apps/effectcraft/src/main.rs:172` `with_app_id`, `appimage.rs:12`, desktop `StartupWMClass` |

## Regenerate

```bash
PYTHONPATH=. python polyhost/res/overlay_sources/effectcraft/fetch_icons.py
PYTHONPATH=. python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/effectcraft/bindings.yaml --preview /tmp/ec_preview
```
