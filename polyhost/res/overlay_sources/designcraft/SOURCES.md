# DesignCraft overlay: sources and provenance

DesignCraft is an InDesign-like page-layout app from the ArtCraft "Crafting Apps" suite
(https://getartcraft.com/apps, https://github.com/storytold/designcraft), licensed
MIT OR Apache-2.0. To rebuild, re-run `fetch_icons.py` and then
`scripts/generate_app_overlays.py` on `bindings.yaml`.

## Shortcuts

The authority is the app's own default keymap, not InDesign's. Source commit
**`e862e0a613c0793c6fea7cfd37ad4145ed6cf686`** (workspace version 0.7.1).

| Group | Where |
|---|---|
| UI commands (file dialogs, view, display, window, single-key colour commands) | `crates/ui-egui/src/menus.rs:8-199` (`UI_COMMANDS`) |
| Engine commands | `crates/engine/src/cmd/edit.rs:106-259`, `file.rs:15-104`, `find.rs:68`, `layout.rs:80,230`, `object.rs:78-610`, `overrides.rs:14`, `paths.rs:15-33`, `print.rs:15`, `select.rs:14-17`, `spelling.rs:13`, `table.rs:78`, `text.rs:154-237` |
| Tool letters | `crates/tools/src/catalog.rs:19-73` (`TOOL_GROUPS`), `tool_for_shortcut` |
| Dispatch and parsing | `crates/ui-egui/src/menus.rs:2130-2220` (`parse_shortcut`, `shortcuts`) |
| macOS native menu | `apps/designcraft/src/native_menu.rs` |

**Modifiers.** The keymap writes `Cmd`, which `parse_shortcut` maps to egui's
`command` modifier: Ctrl on Windows and Linux, Cmd on macOS. Every such chord is therefore
`CMDCTRL` here, and the generator emits a `_mac` set. Matching compares only
`command`, `alt` and `shift`. No default uses a literal Ctrl or the Win/GUI key, and no
action is remapped on macOS.

**Dispatch order.** Command shortcuts are tried first: UI_COMMANDS, then engine commands in
registration order, and the first match fires. Single-key and Shift+key tool shortcuts
come after that, and only when no text is being edited.

### Bound: 120 shortcuts plus the ESC program mark

- **No modifier (28):** tools V Selection, A Direct selection, U Gap, B Content collector,
  T Type, `\` Line, P Pen, `=` Add anchor, `-` Delete anchor, N Pencil, F Rectangle frame,
  M Rectangle, L Ellipse, C Scissors, E Free transform, R Rotate, S Scale, O Shear,
  G Gradient swatch, I Eyedropper, K Measure, H Hand, Z Zoom. Commands: W Toggle
  normal/preview, D Default fill/stroke, X Toggle fill/stroke, `/` Apply none,
  Delete Clear.
- **Shift (7):** P Page tool, T Type on a path, C Convert direction point, G Gradient
  feather, I Color theme, X Swap fill/stroke, F9 Table panel.
- **Cmd/Ctrl (33):** N O D S Q E K F Y `=` `-` 0 1 H R `;` F6 J Z A C X V W `]` `[` G L 3 B 8 P I.
- **Cmd/Ctrl+Shift (22):** S D `;` F6 Z A V P `]` `[` G O L C R J B I U K `.` `,`.
- **Cmd/Ctrl+Alt (19):** S `=` 0 `'` Y I Z H 6 F P 3 L M W U V `]` `[`.
- **Cmd/Ctrl+Alt+Shift (11):** P 0 Y Z V D L 8 `]` `[` T.

### Skipped

- **Keys with no overlay cell:** Cmd+Return (Quick Apply), Tab (Show/Hide panels),
  Shift+Tab (Hide panels except Tools), Escape (back to the Selection tool; ESC carries
  the program mark), Space (temporary Hand, `canvas.rs:331`).
- **Arrows, Home, End, Enter, Backspace** (`canvas.rs:1506-1516`): these go to the
  active tool for nudging and caret movement. They are not commands.
- **Cmd+Alt+3 "Show All on Spread"** (`object.rs:156`): it collides with
  **Transform Again** (`object.rs:78`, also Cmd+Alt+3). Transform Again is registered
  first and wins the dispatch loop, so the cell draws Transform Again. This is an
  upstream conflict. InDesign itself uses Cmd+Alt+Shift+3 for Show All.
- Duplicate definitions with the same meaning in both tables (Cmd+N/O/S/Shift+S/D,
  UI vs engine) are drawn once.
- Tools without a default key (Vertical Type, Smooth, Erase, Ellipse/Polygon Frame,
  Polygon, Note) and B's second tool (Content Placer, which shares B) are not drawn.

### macOS notes

- The native menu (`native_menu.rs`) installs the predefined **Hide (⌘H)** and
  **Hide Others (⌥⌘H)** items, and also gives ⌘H to *Show/Hide Frame Edges* and ⌥⌘H to
  *High Quality Display*. Which one wins at runtime was not checked on a Mac. The overlay
  draws the app's own default (frame edges / high quality) because that is DesignCraft's
  keymap.
- ⌘Q is wired to the app's own Quit item, so the unsaved-changes prompt still appears.

## Icons

The house style is Fluent. A glyph is copied byte-identically from the Illustrator overlay
when the action is the same, so both apps share the cell.

- **From `../illustrator/icons/` (43):** select, directselect, type, line, pen, pencil,
  rectangle, ellipse, scissors, scale, rotate, gradient, eyedropper, hand, zoom, swap,
  default, new, open, save, saveas, print, place, undo, copy, cut, paste, selectall, group,
  ungroup, lock, compound, tofront, toback, forward, backward, outlines, zoomin, zoomout,
  rulers, guides, prefs, transformagain. Each one's licence is recorded in Illustrator's
  `SOURCES.md` (Fluent MIT, or drawn).
- **Microsoft Fluent UI System Icons (MIT)**, `microsoft/fluentui-system-icons` `main`:
  the folder names in `fetch_icons.py` `GLYPHS`. Each name was probed before use.
- **Google Material Symbols (Apache-2.0)**, weight 300 via `icon_fetch` (`ms:`):
  conversion_path, crop_free, straighten, text_rotation_angleup, gradient, preview,
  flip_to_front, find_replace, vertical_align_center, format_paragraph, call_split.
- **Drawn in `fetch_icons.py` (4), `mode: alpha`:** addanchor and delanchor (the shared
  pen nib with + or -), rectframe (rectangle with an X, the placeholder frame), shear
  (parallelogram). These files are guarded, so a re-run leaves them untouched.
- Rejected after rendering: `ms:grid_guides` for Snap to Guides read as a crossed box,
  too close to the Rectangle Frame glyph. These names 404'd: Fluent `Square Dashed`,
  `Magnet`, `Snap To Grid`, and Material `skew`, `shear`, `parallelogram`, `magnet`.

Concept sharing: labels that name a shared concept (Save, Copy, Undo, Redo, Close,
Bold, …) are drawn by the shared renderer (`concept:` in the placement table).

## Program mark (ESC)

DesignCraft's **own app icon**, a calico cat in a polka-dot scarf on a green tile.
`assets/app-icon/designcraft.ico`, **64 px frame**, fetched at the pinned commit by
`program_marks.own_icon`. The file is guarded, so a re-run leaves it untouched.
Licence: **MIT OR Apache-2.0** (`assets/app-icon/LICENSE.txt`). It is original artwork
by the project owner with no third-party material, and it is compatible with this
GPL-3.0-or-later host.

Settings were chosen by sweeping ICO frames 48/64/128/256 plus the SVG, modes luma and
bright, thresholds 90 to 210, and regions [37,32] and [46,40]. The result is
`program_icon_mode: luma`, `threshold: 160`, `region: [46, 40]`, bottom-right,
margin 0. The green field (luma ≈146) lights as the tile, and the cat's head and ear
read dark against it. Smaller regions and `bright` mode broke the figure into speckle,
and frames 64, 128 and 256 render almost the same, so the smallest converged frame (64)
was taken.

## Window matching

- Windows: `designcraft.exe` (`packaging/windows/designcraft.wxs`, Cargo bin `designcraft`) → `designcraft`.
- macOS: `CFBundleName` / `CFBundleExecutable` `DesignCraft` (`packaging/macos/Info.plist.in`) → `designcraft`.
- Linux: the eframe `with_app_id("ai.storyteller.designcraft")` (`apps/designcraft/src/main.rs:218,280`)
  becomes the Wayland app id and the X11 WM_CLASS (`StartupWMClass` in
  `packaging/linux/ai.storyteller.designcraft.desktop`). The process name is `designcraft`.

## Mapping stanza

```yaml
designcraft,ai.storyteller.designcraft:
  overlay: [designcraft_template.mods.png, designcraft_template.combo.mods.png, designcraft_template.extra.mods.png]
  os:
    macos:
      overlay: [designcraft_template_mac.mods.png, designcraft_template_mac.combo.mods.png, designcraft_template_mac.extra.mods.png, designcraft_template_mac.gui.mods.png]
```
