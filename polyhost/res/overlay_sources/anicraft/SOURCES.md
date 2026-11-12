# AniCraft overlay: sources and licences

AniCraft (<https://github.com/storytold/anicraft>, one of the ArtCraft "Crafting
Apps", <https://getartcraft.com/apps/anicraft>) is an open-source 2D vector
animation editor in Rust/egui, a clean-room Adobe Animate work-alike, licensed
**MIT OR Apache-2.0**. PolyKybdHost is GPL-3.0-or-later, and both licences are
GPLv3-compatible.

## Shortcuts

Everything here was read from the app's source at commit
**`9e49ae93a7ee167f19e0b7035eb3ebed0ccbe805`**. That source is AniCraft's own
keymap, not Adobe's. Paths are relative to the repo root.

How a key is resolved: `src/keymap.rs` builds one table from the engine command
registry (`crates/engine/src/lib.rs::commands`, each spec's `shortcut`), the
registry's second keys (`SHORTCUT_ALIASES`, `lib.rs:163`), the tools
(`src/app.rs:98` `Tool::shortcut`) and the view keys (`src/app.rs:490`
`VIEW_SHORTCUTS`). `src/app.rs:2350-2470` dispatches that table, after the keys
it handles itself (palette, shortcut editor, preferences, quit) and before
Enter (play) and Space (pan).

**Modifiers.** `src/keymap.rs:142` parses the text `Ctrl` to egui
`Modifiers::COMMAND`, which is Cmd on macOS and Ctrl elsewhere, so every Ctrl
chord is written `CMDCTRL` here.

| Group | Source |
|---|---|
| Tools V A Q U M P T Shift+Y B Y E R O N K S I C H Z | `src/app.rs:98-121` (`Tool::shortcut`; PolyStar has no key) |
| `[` `]` brush size, Ctrl+2 fit stage, Alt+Shift+O onion skin, Ctrl+Alt+A select all frames, Ctrl+Alt+8 align to stage, Ctrl+F6 / Ctrl+Shift+F6 next / previous panel, F9 actions, F3 / Shift+F3 find next / previous, Alt+F3 movie explorer | `src/app.rs:490-506` (`VIEW_SHORTCUTS`) |
| New, Open, Save, Save As, Import to Stage (Ctrl+R), Undo, Redo (Ctrl+Y) | `crates/engine/src/cmds_file.rs:14-32,113-114` |
| Publish (Shift+F12), Publish Settings (Ctrl+Shift+F12) | `crates/engine/src/publish.rs:24,42` |
| F5 / Shift+F5 frame, F6 / Shift+F6 / F7 keyframes, `,` `.` previous / next frame, Home / End first / last frame | `crates/engine/src/cmds_timeline.rs:12-32` |
| Shift+`,` / Shift+`.` first / last frame, Backspace = Clear | `crates/engine/src/lib.rs:163-170` (`SHORTCUT_ALIASES`) |
| Shift+PageUp / PageDown previous / next scene | `crates/engine/src/cmds_scene.rs:20-21` |
| Ctrl+Alt+X/C/V cut / copy / paste frames | `crates/engine/src/cmds_frames.rs:26-28` |
| Select All, Deselect All, Duplicate, Clear (Delete), Snap to Objects (Ctrl+Shift+/), Object Drawing (J), Arrange (Ctrl(+Shift)+Up/Down), Break Apart (Ctrl+B), Convert to Symbol (F8) | `crates/engine/src/cmds_draw.rs:17-53` |
| Cut, Copy, Paste in Center, Paste in Place, Rotate 90° CW / CCW (Ctrl+Shift+9 / 7), Remove Transform (Ctrl+Shift+Z), Align (Ctrl+Alt+1..6) | `crates/engine/src/cmds_modify.rs:14-29` |
| Add Shape Hint (Ctrl+Shift+H) | `crates/engine/src/cmds_hints.rs:18` |
| Edit Symbols (Ctrl+E) | `crates/engine/src/editing.rs:25` |
| Find and Replace (Ctrl+F) | `crates/engine/src/find.rs:26` |
| Test Movie (Ctrl+Enter) | `crates/engine/src/cmds_actions.rs:20` |
| Command palette (Ctrl+K, Ctrl+Shift+P), shortcut editor (F1, Ctrl+Alt+Shift+K), Preferences (Ctrl+U, Ctrl+,), Quit (Ctrl+Q) | `src/app.rs:2362-2371`, also listed as reserved in `src/keymap.rs:16-28` |
| Enter play / stop, Space pan (held) | `src/app.rs:2436-2442` |
| Ctrl+= / Ctrl+- zoom, Ctrl+0 fit, Ctrl+1 100% | `src/stage.rs:219-224` |

Context-dependent behaviour that the overlay does not show: Ctrl+X/C/V act on
frames when the timeline was used last and has a frame selection
(`src/app.rs:2058` `invoke`). Ctrl+Shift+Z is Remove Transform (Animate's), not
Redo; Redo is Ctrl+Y.

### Skipped

- **Alt+letter** opens a menu (`src/menus.rs`, `MenuKeys`); these are menu
  access keys, not commands.
- **Arrow keys** nudge the selection, or move the playhead and the active layer
  on a focused timeline (`src/app.rs:2443-2455`). Their meaning changes with
  focus, so they are not drawn.
- **Tab** moves between fields; **Escape** cancels (the program-mark cell).
- Tool-local keys (`src/pathtools.rs`, `src/motion_path.rs`, `src/widthtool.rs`,
  `src/bone_tool.rs`, `src/library.rs`): Delete, Enter, F2 and the arrows only
  while that tool or panel has the keyboard.
- `Ctrl+Shift+?`, the second spelling of Snap to Objects for layouts where `/`
  and `?` share a key, is the same key as Ctrl+Shift+/.

## macOS

From one spec (`CMDCTRL`), the generator writes `anicraft_template_mac.*`.
Everything that is Cmd on macOS is Ctrl on Windows and Linux. No action is
remapped: the macOS application menu (`src/menus.rs:23-38`) lists Settings
(Cmd+,) and Quit (Cmd+Q), the same keys. AniCraft binds no Cmd+H or Cmd+M.

## Icons

| File(s) | Source | Licence |
|---|---|---|
| Most glyphs (the `FLUENT` map in `fetch_icons.py` without an `ms:` prefix) | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | MIT |
| `bone, inkbottle, objectdrawing, onion, selectallframes, cutframes, copyframes, pasteframes, convertsymbol, shapehint, alignleft, alignhcenter, alignright, aligntop, alignvcenter, alignbottom, aligntostage, publishsettings, nextpanel, prevpanel, editsymbol` | [Material Symbols](https://fonts.google.com/icons) (`ms:`, weight 300) | Apache-2.0 |
| `select, directselect, freetransform, width, pen, type, pencil, paintbrush, blobbrush, eraser, rectangle, ellipse, line, eyedropper, hand, zoom, new, open, save, saveas, undo, redo, cut, copy, paste, pasteinplace, selectall, deselect, clear, bringforward, sendbackward, tofront, toback, zoomin, zoomout, fitall, actualsize, place, snaptopoint, prefs, quit` | byte-identical copies of `../vectorcraft/icons/` (see `../vectorcraft/SOURCES.md`) | as listed there (MIT, ISC, Apache-2.0, GPL-3.0-or-later drawn) |
| `brushdec, brushinc, fill` | byte-identical copies of `../photocraft/icons/` | as listed there |
| `prevframe, nextframe` | byte-identical copies of `../effectcraft/icons/` (Fluent) | MIT |
| `rtz, goend, play` | byte-identical copies of `../soundcraft/icons/` (Fluent) | MIT |
| `insertframe, removeframe, keyframe, blankkeyframe, clearkeyframe` | drawn in `fetch_icons.py::_cell` (a timeline frame cell with its mark) | GPL-3.0-or-later |
| `anicraft.png` (ESC program mark) | AniCraft's own icon, `assets/app-icon/anicraft.ico` @ `9e49ae93`, 128 px frame | **MIT OR Apache-2.0** |

`assets/app-icon/LICENSE.txt` states the icon is the project owner's original
artwork ("no third-party material"), licensed like the rest of AniCraft, MIT OR
Apache-2.0. It is not the ArtCraft brand mark: `NOTICE` keeps the ArtCraft name
and marks out of the licence, and nothing from `docs/brand/` is used. If the icon
changes upstream, delete `icons/anicraft.png`, update `ANICRAFT_SHA` and re-run.

### Program-mark sweep

Frames 48/64/128/256 against `luma` t80-160 and `bright` t140-225, region
[40,40] right. `luma` lights the ink, which is a scatter of engraving strokes up
to t125 and a noisy blob at t160. `bright` t170 lights the yellow field
(luma ~182) and the paper (~241), so the rabbit is a dark silhouette with both
ears in a lit tile; t140 fills the rabbit in, t200 drops the field. Settings:
`program_icon_mode: bright`, `threshold: 170`, `region: [40, 40]`,
`anchor: right`, `margin: 0`.

## Regenerate

```bash
PYTHONPATH=. python polyhost/res/overlay_sources/anicraft/fetch_icons.py
PYTHONPATH=. python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/anicraft/bindings.yaml --preview /tmp/anicraft_preview
```
