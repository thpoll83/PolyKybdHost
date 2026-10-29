# VectorCraft overlay: sources and licences

VectorCraft is the ArtCraft "Crafting Apps" vector editor (Illustrator-like),
<https://github.com/storytold/vectorcraft>, licence **MIT OR Apache-2.0**. This host is
GPL-3.0-or-later, which can ship either.

All shortcuts and app art come from commit
**`0d0ea352df99044589a7ce0efc7004f7a5b6b7c0`** (workspace version 0.10.0).

## Shortcuts (authority: the app's source, not Illustrator's keymap)

The effective keymap is assembled in `crates/ui-egui/src/shortcuts.rs` `all_shortcuts()`
from four tables, plus keys `handle()` wires directly. Both shipped presets
("VectorCraft Defaults", "Classic Defaults", `shortcut_editor.rs:20`) are the empty
override map (`shortcut_editor.rs:378`), so there is one default keymap.

| Group | Source |
|---|---|
| Engine command chords (Undo, Copy, Group, Lock, Join, Blend, Envelope, Save As, Place, …) | `cmd!` specs under `crates/engine/src/cmd/` (`edit.rs:25-126`, `object.rs:30-135`, `select.rs:13-35`, `path.rs:62-71`, `layer.rs:24`, `live.rs:27-154`, `paint.rs:32-111`, `docmenu.rs:124-224`, `typecmd.rs:28`, `textedit.rs:70-79`, `typemenu.rs:95`, `colormgmt.rs:28,94`, `distortcmds.rs:103`, `patterncmds.rs:36`, `menucmds.rs:74`, `buildcmds.rs:55`, `views.rs:34`, `create.rs:63`, `print.rs:37`, `place/mod.rs:55`, `fileio/save.rs:695-731`) |
| UI command chords (Open, Save, View toggles, zoom, type alignment, Quit, …) | `crates/ui-egui/src/menus.rs:54-729` (`UI_COMMANDS`) |
| Panel chords (F5-F7, Shift+F3..F8, Cmd+F8..F11, Cmd+T family) | `crates/ui-egui/src/shortcut_editor.rs:103-124` (`PANEL_SHORTCUTS`) |
| Single-key tools (V, A, Y, Q, P, +, -, Shift+C, Shift+~, T, Shift+T, \, M, L, B, Shift+B, Shift+N, N, Shift+E, C, R, O, S, Shift+W, Shift+R, E, Shift+M, K, Shift+L, Shift+P, Shift+V, U, G, I, W, Shift+S, J, Shift+O, Shift+K, H, Shift+H, Z) | `crates/tools/src/catalog.rs:21-136` |
| macOS-only Cmd+, (Settings) | `crates/ui-egui/src/shortcuts.rs:84-90` (`settings_chord`) |
| Arrow nudge (bare / Shift x10 / Alt copy / Alt+Shift copy x10), Delete+Backspace clear, Enter (Move dialog for a selection tool), Tab (panels) | `crates/ui-egui/src/shortcuts.rs:239-283, 410-424`; Tab is `window.dock` at `menus.rs:291` |
| Space held = Hand, Cmd+Space = Zoom, Cmd+Alt+Space = Zoom out | `crates/ui-egui/src/canvas.rs:465-475, 592-594` |

`Cmd` in VectorCraft's chord strings parses to egui `Modifiers::COMMAND`
(`shortcuts.rs:23`): Ctrl on Windows/Linux, Cmd on macOS, so every chord is
`CMDCTRL` here. No default chord uses literal Ctrl.

Context-dependent keys, global/canvas meaning chosen:
- **Cmd+Shift+B** is Hide Bounding Box; while the Type tool edits text it is Bold
  (`shortcuts.rs` test at :495). **Cmd+Shift+I** likewise Italic vs Show Perspective Grid.
- **Enter** ends a path being drawn; idle with a selection tool it opens the Move
  dialog (Rotate/Scale/Reflect/Shear tools open theirs). Labelled "Move / tool dialog".
- **Cmd+Shift+C/L/R/J/F** align/justify paragraphs only when type is selected.

Not bound (no default, or not a cell): Escape (program-icon cell; also cancels),
keypad keys, `Item::Todo` menu entries (`Cmd+F12`, `Cmd+I`, `Cmd+Alt+R` show in the
menus but are disabled and unhandled, `menus.rs:2097,2132,2559`). The tool keys used
only while dragging (arrows change polygon sides, digits pick a perspective plane)
are transient and not drawn.

### macOS

- Cmd+H (Hide Edges) collides with the system Hide; Cmd+Q is Quit on both.
- Cmd+Space (temporary Zoom) is Spotlight by default on macOS, so it may never reach
  the app; the cell is still drawn because the app binds it.
- Cmd+Shift+/ (Search Commands) shadows the Help-menu search field.
- Cmd+, opens Settings on macOS only (`only: [macos]`).

## Icons

| Kind | Source | Licence |
|---|---|---|
| Borrowed (`select`, `pen`, `save`, … 61 files, listed in `fetch_icons.py` `BORROWED`) | `../illustrator/icons/`, i.e. MS Fluent UI System Icons or drawn in that folder's `fetch_icons.py` | MIT / GPL-3.0-or-later (this repo) |
| App (`APP` in `fetch_icons.py`) | `storytold/vectorcraft@0d0ea35` `assets/icons/*.svg`: `dc-*` are VectorCraft's own (MIT OR Apache-2.0, per `ASSETS.md`); `brush`, `shapes`, `waves`, `frame`, `slice`, `chart-column`, `spline`, `palette`, `layers`, `info`, `pilcrow`, `pen-tool-add/-delete` are Lucide as vendored by VectorCraft | MIT OR Apache-2.0 / ISC (`assets/icons/LICENSE-lucide.txt`) |
| Fluent (`FLUENT`, bare folder names) | <https://github.com/microsoft/fluentui-system-icons> via `icon_fetch` | MIT |
| Material (`FLUENT`, `ms:` names) | Google Material Symbols via `icon_fetch` (weight 300) | Apache-2.0 |
| Derived (badge composites, `transparencygrid`, `pixelpreview`) | built in `fetch_icons.py` from the above | as their inputs |

Badge convention: base glyph + bottom-right corner badge; plus = Make, minus =
Release, lock = Lock, eye / eye-off = Show / Hide, arrow = direction.

Shared concepts: labels that name a concept (New, Open, Save, Print, Close, Quit,
Undo, Redo, Cut, Copy, Paste, Lock, Select all, Zoom in/out, Save as, Paragraph,
Settings) are drawn by the shared renderer, not from `icons/`. Ctrl+3 "Hide" is
`shared: false` so it does not draw the same eye-off as Ctrl+H Hide Edges.

## Program mark (ESC)

`icons/vectorcraft.png`: the app's own icon, `assets/app-icon/vectorcraft.ico`
(256 px frame), original artwork by the project owner, **MIT OR Apache-2.0**
(`assets/app-icon/LICENSE.txt`). The engraved-dragon tile does not survive 1-bit
as-is: luma thresholds 70-130 and bright thresholds 150-210 across frames
40/48/64/128/256 gave either hatching noise or a solid tile. The mark is therefore
the dragon's **silhouette** (every pixel farther than 60 RGB units from the
`#e8573f` field, median-filtered), rendered `program_icon_mode: alpha`, region
`[40, 40]`, bottom-right, margin 0. Guarded in `fetch_icons.py`.

## Window matching

- Windows: `vectorcraft.exe` (`apps/vectorcraft/Cargo.toml` package name;
  `packaging/windows/vectorcraft.wxs:113`) -> `vectorcraft`.
- macOS: `CFBundleName` / `CFBundleDisplayName` `VectorCraft`
  (`packaging/macos/Info.plist.in:9-14`) -> `vectorcraft`.
- Linux: `with_app_id("ai.storyteller.vectorcraft")` (`apps/vectorcraft/src/main.rs:599`),
  `StartupWMClass=ai.storyteller.vectorcraft` in the `.desktop` file; the binary is
  `vectorcraft`. Both keys are listed.
