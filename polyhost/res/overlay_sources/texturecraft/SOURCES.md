# TextureCraft overlay: sources and licences

TextureCraft (<https://github.com/storytold/texturecraft>, one of the ArtCraft
"Crafting Apps", <https://getartcraft.com/apps/texturecraft>) is an open-source
3D texture painting app in Rust/egui, a Substance 3D Painter work-alike,
licensed **MIT OR Apache-2.0**. PolyKybdHost is GPL-3.0-or-later, and both
licences are GPLv3-compatible.

## Shortcuts

Everything here was read from the app's source at commit
**`42c8ea5b3c3a4cabdda03f535355cd61ac756479`**. That source is TextureCraft's own
keymap, not Adobe's. Paths are relative to the repo root.

How a key is resolved: `crates/ui-egui/src/keymap.rs::bindings` lists the menu
catalog (`crates/ui-egui/src/menus.rs:37` `CATALOG`) first and then every engine
command with a default shortcut (`crates/engine/src/commands.rs:51`
`command_specs`). craft-keymap (storytold/craft-libs `6e03f65b`, MIT OR
Apache-2.0) dispatches them from `menus.rs:321` `shortcuts`, which also handles
the fixed brush keys `[` and `]` (`menus.rs:357-364`).

**Modifiers.** `keymap.rs:71` `crate_text` hands the text `Ctrl` to craft-keymap
as `Cmd`, which is ⌘ on macOS and Ctrl on Windows and Linux. So every Ctrl chord
is written `CMDCTRL` here.

| Group | Source |
|---|---|
| New project (Ctrl+N), Close (Ctrl+F4), Quit (Ctrl+Q), Export textures (Ctrl+Shift+E) | `crates/ui-egui/src/menus.rs:38-54` |
| Mode keys F8 bake / F9 paint / F10 render, Tab hide UI | `crates/ui-egui/src/menus.rs:61-63,78` |
| M display material, C / Shift+C channel, B / Shift+B mesh map, F show entire mesh, F1/F2/F3 view layout, Y / U / Ctrl+Shift+I quick mask | `crates/ui-egui/src/menus.rs:80-95` |
| Tools 1..6 and 8, P color picker, X invert mask value | `crates/engine/src/tool_cmds.rs:17-24,56` |
| Tool 7 (Path) | `crates/engine/src/path_tool.rs:141` |
| Open, Save, Save as, Close, Reimport mesh (Ctrl+Shift+R) | `crates/engine/src/file_cmds.rs:26-31` |
| Undo (Ctrl+Z), Redo (Ctrl+Y) | `crates/engine/src/view_cmds.rs:38,50` |
| Remove layer (Delete), Duplicate (Ctrl+D), Group (Ctrl+G) | `crates/engine/src/layer_cmds.rs:17-19` |
| Copy / Cut / Paste layer (Ctrl+C/X/V), Flatten (Ctrl+M), Instantiate across texture sets (Ctrl+Shift+D) | `crates/engine/src/layer_ops.rs:14-26` |
| Go to camera 1..9 (Ctrl+1..9) | `crates/engine/src/camera_cmds.rs:31-39` |
| `[` / `]` brush size | `crates/ui-egui/src/menus.rs:357-364` |

Context-dependent behaviour that the overlay does not show: Ctrl+C/X/D/Delete
act on the selected effect instead of its layer when an effect is selected, and
Ctrl+V pastes a copied effect (`menus.rs` `effect_command`). The tool keys and
the quick-mask keys run only in Painting mode (`menus.rs` `enabled`).

### Skipped

- **Escape** cancels a stroke or closes a popup (`menus.rs:366-374`); it is the
  program-mark cell.
- **S held** (move the projection stencil) and **V held** with the Clone tool (set
  the clone source) work only with that tool or a stencil active
  (`crates/ui-egui/src/viewport.rs:490,1489`).
- **Shift+Delete** and **Shift+Insert** become Ctrl+X and Ctrl+V when nothing is
  bound to them (`menus.rs` `clipboard_key`); they are the same actions.

## macOS

From one spec (`CMDCTRL`), the generator writes `texturecraft_template_mac.*`.
Nothing is remapped. The macOS app menu (`craft_menu::mac::install_app_menu`,
called from `apps/texturecraft/src/main.rs:235`) adds Hide (Cmd+H), Hide Others
(Cmd+Alt+H) and Quit (Cmd+Q); TextureCraft binds no Cmd+H, and Quit is the same
action. Close stays Cmd+F4.

## Icons

| File(s) | Source | Licence |
|---|---|---|
| `hideui, mode_bake, mode_paint, render, tool_paint, tool_eraser, tool_projection, fill, tool_smudge, tool_clone, brushinc, brushdec, eyedropper, invertgray, material, channel_next, channel_prev, meshmap_next, meshmap_prev, frame_all, layout_3d2d, layout_3d, layout_2d, br_mask, mask_invert, delete, undo, redo, open, save, new, copy, cut, paste, duplicate, group, close, quit, export` | byte-identical copies of `../substancepainter/icons/` (the same actions; see `../substancepainter/SOURCES.md`) | as listed there |
| `mergedown, saveas, quickmask` | byte-identical copies of `../photocraft/icons/` (see `../photocraft/SOURCES.md`) | as listed there |
| `tool_path` (Bezier Curve Square), `tool_geomask` (Cube), `reimport` (Arrow Sync) | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | MIT |
| `instantiate` | [Material Symbols](https://fonts.google.com/icons) `dynamic_feed` (weight 300) | Apache-2.0 |
| `camera1..camera9` | `../number_badge.py` composite: Fluent `Video` plus the digit | MIT + GPL-3.0-or-later |
| `texturecraft.png` (ESC program mark) | TextureCraft's own icon, `assets/app-icon/texturecraft.ico` @ `42c8ea5b`, 128 px frame | **MIT OR Apache-2.0** |

`assets/app-icon/LICENSE.txt` states the icon is the project owner's original
artwork ("no third-party material"), licensed like the rest of TextureCraft, MIT
OR Apache-2.0. It is not the ArtCraft brand mark (`NOTICE` keeps the ArtCraft
name and marks out of the licence; nothing from `docs/brand/` is used). If the
icon changes upstream, delete `icons/texturecraft.png`, update
`TEXTURECRAFT_SHA` and re-run.

### Program-mark sweep

Frames 48/64/128/256 against `luma` t80-160 and `bright` t140-225, region
[40,40] right. `luma` t110 lights the ink: the zebra's stripes, eye and muzzle
read as white stripes on black. From t125 the field is lit too (a lit tile with
the stripes cut out), and `bright` keeps only a scatter of the paper-coloured
stripes. Settings: `program_icon_mode: luma`, `threshold: 110`,
`region: [40, 40]`, `anchor: right`, `margin: 0`.

## Regenerate

```bash
PYTHONPATH=. python polyhost/res/overlay_sources/texturecraft/fetch_icons.py
PYTHONPATH=. python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/texturecraft/bindings.yaml --preview /tmp/texturecraft_preview
```

## ESC mark: silhouette

The ESC key shows `icons/texturecraft_mark.png`, made from the app's own icon `icons/texturecraft.png`
by `program_marks.silhouette_mark(..., cut=95)` in `fetch_icons.py`. The animal is
cut off the coloured tile as one solid shape, fitted into 40 x 40 (36 x 40), and
interior pixels darker than luma 95 at that size are cut back out (eyes, mouth,
lines). The spec places it 1:1 (`program_icon_region: [36, 40]`). The
generator's thresholds turned the engraving into dither at keycap size.
