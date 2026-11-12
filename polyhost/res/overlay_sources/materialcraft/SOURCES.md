# MaterialCraft overlay: sources and licences

MaterialCraft (<https://github.com/storytold/materialcraft>, one of the ArtCraft
"Crafting Apps", <https://getartcraft.com/apps/materialcraft>) is an open-source,
node-based procedural material editor in Rust/egui, a Substance 3D Designer
work-alike, licensed **MIT OR Apache-2.0**. PolyKybdHost is GPL-3.0-or-later,
and both licences are GPLv3-compatible.

## Shortcuts

Everything here was read from the app's source at commit
**`b73facdc7b8b5ce102cd9e14d964058a15182dc0`**. That source is MaterialCraft's
own keymap, not Adobe's. Paths are relative to the repo root.

How a key is resolved: `crates/ui-egui/src/menus.rs:265` `shortcut_table` lists
the menu catalog (`menus.rs:88` `CATALOG`) first and then every engine command
with a default shortcut that the catalog does not list (`crates/engine/src/`
`cmd!` specs). craft-keymap (storytold/craft-libs `6e03f65b`, MIT OR Apache-2.0)
dispatches them from `menus.rs:417` `shortcuts`. The graph canvas reads Space,
Tab and F itself.

**Modifiers.** `menus.rs:254` `parse_shortcut` turns the text `Ctrl` into
craft-keymap's `Cmd`, which is ⌘ on macOS and Ctrl on Windows and Linux. So
every Ctrl chord is written `CMDCTRL` here.

| Group | Source |
|---|---|
| New graph (Ctrl+N), Open, Save, Save as, Export outputs (Ctrl+Shift+E), Exit (Ctrl+Q) | `crates/ui-egui/src/menus.rs:89-105` |
| Undo, Redo (Ctrl+Y), Copy, Cut, Paste, Duplicate, Delete, Delete and relink (Backspace), Select all, Edit node graph (Ctrl+E), Parent graph (Alt+Left) | `crates/ui-egui/src/menus.rs:106-117` |
| Clear node thumbnails (F5), Previous pin (Shift+F2), Next pin (F2) | `crates/ui-egui/src/menus.rs:123-125` |
| Paste without links (Ctrl+Shift+V), Duplicate without links (Ctrl+Shift+D) | `crates/engine/src/edit_cmds.rs:27,40` |
| Disable selection (Shift+D) | `crates/engine/src/node_cmds.rs:26` |
| Space / Tab over the graph: add a node from the search menu | `crates/ui-egui/src/graph/input.rs:277-283` |
| F over the graph: frame the selection, or everything | `crates/ui-egui/src/graph/graph_camera.rs:55-58`, `graph/input.rs:284` |

The engine registry repeats several catalog keys (`file_cmds.rs:15-36`,
`edit_cmds.rs:15-63`, `document_history_commands.rs:45,50`,
`node_graph_commands.rs:7`); the catalog entry is listed first and takes
priority. Ctrl+N is "New graph" (`ui.newGraph`), not the registry's `file.new`.

Context-dependent behaviour that the overlay does not show: Ctrl+E edits an
embedded graph only (`graph/editor_actions.rs:4` `shortcut_enabled`). Over the
Explorer panel, Enter opens, F2 renames and Delete removes the selected item
instead (`crates/ui-egui/src/explorer.rs:120-140`).

### Skipped

- **X** swaps two selected wires, and **Delete / Backspace** delete selected
  wires, only while wires are selected (`graph/wire_actions.rs:78-92`).
- **Escape** closes dialogs and cancels gestures; it is the program-mark cell.

## macOS

From one spec (`CMDCTRL`), the generator writes `materialcraft_template_mac.*`.
Nothing is remapped. The macOS app menu (`craft_menu::mac::install_app_menu`,
called from `apps/materialcraft/src/main.rs:127`) adds Hide (Cmd+H), Hide Others
(Cmd+Alt+H) and Quit (Cmd+Q); MaterialCraft binds no Cmd+H, and Quit is the same
action as its Exit.

## Icons

| File(s) | Source | Licence |
|---|---|---|
| `newgraph, open, save, saveas, export, quit, undo, redo, copy, cut, paste, duplicate, delete, selectall, disable` | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) (the `FLUENT` map in `fetch_icons.py`) | MIT |
| `pastenolinks, dupnolinks, deleterelink, editgraph, parentgraph, nextpin, prevpin, clearthumbs` | [Material Symbols](https://fonts.google.com/icons) (`ms:`, weight 300) | Apache-2.0 |
| `nodesearch` | byte-identical copy of `../nuke/icons/` (Material `manage_search`; the same action, add a node from a search menu) | Apache-2.0 |
| `frame_all` | byte-identical copy of `../substancepainter/icons/` | as listed in `../substancepainter/SOURCES.md` |
| `materialcraft.png` (ESC program mark) | MaterialCraft's own icon, `assets/app-icon/materialcraft.ico` @ `b73facdc`, 128 px frame | **MIT OR Apache-2.0** |

`assets/app-icon/LICENSE.txt` states the icon is the project owner's original
artwork ("no third-party material"), licensed like the rest of MaterialCraft,
MIT OR Apache-2.0. It is not the ArtCraft brand mark (`NOTICE` keeps the
ArtCraft name and marks out of the licence; nothing from `docs/brand/` is used).
If the icon changes upstream, delete `icons/materialcraft.png`, update
`MATERIALCRAFT_SHA` and re-run.

### Program-mark sweep

Frames 48/64/128/256 against `luma` t80-160 and `bright` t125-225, region
[40,40] right. `luma` up to t100 lights only scattered ink; t110-160 lights the
field and the ink, a lit tile in which the dark head loses its horn. `bright`
t140 lights the paper-coloured figure: the rhino head on black, facing right,
with the horn and the ear readable; t125 merges the horn into the head, t155
breaks it up. Settings: `program_icon_mode: bright`, `threshold: 140`,
`region: [40, 40]`, `anchor: right`, `margin: 0`.

## Regenerate

```bash
PYTHONPATH=. python polyhost/res/overlay_sources/materialcraft/fetch_icons.py
PYTHONPATH=. python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/materialcraft/bindings.yaml --preview /tmp/materialcraft_preview
```

## ESC mark: silhouette

The ESC key shows `icons/materialcraft_mark.png`, made from the app's own icon `icons/materialcraft.png`
by `program_marks.silhouette_mark(..., cut=95)` in `fetch_icons.py`. The animal is
cut off the coloured tile as one solid shape, fitted into 40 x 40 (32 x 40), and
interior pixels darker than luma 95 at that size are cut back out (eyes, mouth,
lines). The source is cropped to (40, 0, 128, 112): the head, without the neck. The spec places it 1:1 (`program_icon_region: [32, 40]`). The
generator's thresholds turned the engraving into dither at keycap size.
