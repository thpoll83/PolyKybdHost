# FilmCraft overlay: sources & licenses

FilmCraft is the Premiere-like video editor of the ArtCraft "Crafting Apps" suite
(<https://getartcraft.com/apps>, <https://github.com/storytold/filmcraft>), a Rust/egui
app licensed **MIT OR Apache-2.0**. PolyKybdHost is GPL-3.0-or-later; both licences are
GPL-3.0-compatible.

Source commit: **`cee1feb185e675a108f78067f71ad86a640ace3d`**.

## Shortcuts: the app's own keymap, not Premiere's

FilmCraft ships four presets (Edit ▸ Keyboard Shortcuts…). The overlay draws the one a
fresh install uses, **FilmCraft Default** (`DEFAULT_PRESET`,
`crates/engine/src/shortcuts.rs:59`). It is assembled at startup, not written out in one
table, so it was **dumped by running the app's own code**, not read off a table:

| Piece | Where |
|---|---|
| per-command defaults of engine commands (`CommandSpec.shortcut`) | `crates/engine/src/commands.rs`, `keyboard.rs`, `multicam.rs`, `graphics.rs`, `captions.rs`, `clip_ops.rs`, `project_tools.rs`, `sequence_*.rs` |
| per-command defaults of UI commands (tools, transport, panels) | `crates/ui-egui/src/menus.rs:24` (`UI_COMMANDS`), `crates/ui-egui/src/panels/keyboard.rs:59` (`COMMANDS`), `crates/ui-egui/src/dock.rs:116` (`window_shortcut`, Shift+1..9), registered by `menus.rs:872` |
| FilmCraft's panel keys | `crates/engine/src/shortcut_presets.rs:12` (`FILMCRAFT_PANEL`), `:271` (`PREMIERE_PANEL`) |
| Premiere-table entries FilmCraft Default adopts (command has no key of its own, key free) | `shortcut_presets.rs:26` (`PREMIERE`: Tools :27, Multi-camera :41, File :65, Edit :76, Clip :90, Sequence :99, Markers :114, Window :135, Captions :152, Navigation :157, Trimming :175, Keyboard parity :185, Panels :259), filtered by `shortcuts.rs:592` (`audit_for`) |
| assembly + Ctrl/Cmd collision removal | `shortcuts.rs:615` (`builtin_for`), `:370` (`drop_control_collisions`) |

Dump recipe (in a scratch clone; `builtin_for` made `pub` there):

```rust
// crates/ui-egui/examples/dump_keys.rs
let mut s = Shortcuts::new();
s.register_external(filmcraft_ui_egui::menus::external_commands());
for p in [Platform::Windows, Platform::Mac] {
    for b in s.builtin_for(DEFAULT_PRESET, p).unwrap() { /* print keys, panel, command, label */ }
}
```

`docs/keyboard.md` describes the same tables and lists the Premiere keys FilmCraft does
not implement.

### Modifier notation

FilmCraft's canonical `Cmd` is Cmd on macOS and Ctrl elsewhere → **`CMDCTRL`**. Its
`Ctrl` is the macOS Control key, which is Ctrl on Windows/Linux too → **`CTRL`**
(literal on every OS): Ctrl+1..8 cut to camera, Ctrl+Space, Ctrl+`, Ctrl+Shift+, / .

**macOS only** (`only: [macos]`): Ctrl+9 (cut to camera 9), Ctrl+M (add range marker In
to Out), Ctrl+Shift+M (add range marker), Ctrl+T (toggle trim type). Off macOS each lands
on the same key as a Cmd binding (Ctrl+9 = toggle audio targets, Ctrl+M = Export,
Ctrl+Shift+M = previous marker, Ctrl+T = new text) and `drop_control_collisions` removes
it, which the dump confirms (Windows and macOS lists differ by exactly these four).

### Where FilmCraft Default differs from Premiere (drawn as FilmCraft does it)

- Clear In / Clear Out / Clear In and Out are **Cmd+Shift+I / O / X** (engine defaults),
  not Premiere's Alt+I / O / X (unbound in FilmCraft Default).
- Shift+E is **Clip ▸ Enable**; Export Frame has no default key.
- Bare Delete is Project ▸ Clear app-wide and Timeline Clear in the Timeline; Backspace is
  Clear. Both drawn as "Clear".
- Cmd+Shift+; is Go to previous gap, Shift+; Go to next gap.

### Context-dependent keys (one key, several panels)

The application-wide binding is drawn, except:

- Keys that exist only in one panel are drawn with that panel named in the label
  (`(Timeline)`, `(Project)`, `(Program)`, `(Text)`).
- **Timeline over graphics/text** where the global binding is a Graphics/Text command and
  the Timeline (the editing canvas) binds the same key: Alt+Up/Down (Timeline nudge up/down
  over Increase/Decrease leading), Cmd+Alt+Left/Right and Cmd+Alt+Shift+Left/Right
  (Timeline slip over Increase/Decrease font size).
- Cmd+Shift+Up/Down: Program/Properties nudge object by five (Text panel "select to
  segment end" on Cmd+Shift+Down not drawn).
- Global wins over: Cmd+R (Speed/Duration, not Program ▸ Show Rulers), Cmd+L (Link, not
  mixer Loop), Cmd+W (Close, not Timeline Close Sequence), Cmd+Shift+; (previous gap, not
  Program snap), I / O / = / - / arrows / Home / End / Shift+[ ] (not their Project/Text
  panel meanings), Left/Right (not History undo/redo), Shift+arrows (not Project/Text
  extend selection), Backspace (not Project/Text delete), Space (Metadata play is the
  same action).

### Not drawn

- **Escape**: the program-icon cell (FilmCraft binds nothing on it by default).
- **Tab**: no default chord (Project-panel Tab/Shift+Tab field navigation is a Premiere key
  FilmCraft skips, `docs/keyboard.md`).
- **Enter** variants other than bare Enter (Render Effects In to Out): none bound.

### Icon reuse that is deliberate

- Program and Source monitor zoom (Cmd+Shift+0/1 vs Cmd+Alt+Shift+0/1) share the fit /
  1:1 glyphs; the modifier says which monitor.
- Shift+Up/Down (edit point on any track) reuse the Up/Down edit-point glyphs; Shift+Home/End
  (selected clip start/end) reuse Home/End.
- Cmd+Left/Right and Cmd+Shift+Left/Right (nudge clip one / five frames) share Fluent
  `Arrow Move`; the four slip chords share the slip glyph.

## Icons

| File(s) | Source | License |
|---|---|---|
| `select trackselect rippleedit rolledit ratestretch blade slip slide pen hand zoom markin markout rev stop fwd play zoomin zoomout zoomfit newsequence newproject open save saveas import export undo redo cut copy paste selectall group ungroup link addedit speed rippledelete panelproject panelsource paneltimeline panelprogram paneleffectctl panelaudio paneleffects` | byte-identical copies of `../premiere/icons/` (Fluent MIT + `../nle_glyphs.py`) | MIT / GPL-3.0-or-later |
| `marker insert` | copies of `../resolve/icons/` (Fluent `Flag`, `Arrow Between Down`) | MIT |
| `overwrite snap trim` | drawn, `../nle_glyphs.py` | GPL-3.0-or-later |
| every other plain glyph | [Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) or `ms:` [Material Symbols](https://fonts.google.com/icons), names in `fetch_icons.py` `FLUENT` | MIT / Apache-2.0 |
| `camera1..9` | Fluent `Video` + digit (`../number_badge.py`) | MIT |
| `cutcam1..8/9` | Fluent `Square` + digit | MIT |
| `workspace0..9` | Fluent `Window` + digit | MIT |
| `clearin clearout clearinout` | `markin` / `markout` / `markclip` + strike (`fetch_icons.py`) | as base |
| `nextmarker prevmarker` | Material `flag` + chevron (`fetch_icons.py`) | Apache-2.0 |
| `trackselectback` | `trackselect` mirrored | GPL-3.0-or-later |
| `filmcraft.png` (ESC program mark) | FilmCraft's own icon, `assets/app-icon/filmcraft.ico` @ `cee1feb1`, 64 px frame | **MIT OR Apache-2.0** (`assets/app-icon/LICENSE.txt`; owl artwork by Brandon Thomas for the FilmCraft project, per the `.attribution` sidecars) |

## Program mark

FilmCraft's real icon (violet tile, engraved owl). Swept ICO frames 48/64/128/256 and the
SVG, `luma`/`bright`, thresholds 70..210 at the `[37, 32]` region: `luma` lights only the
scattered ink at low thresholds and fills the whole tile at 130+; **`bright` t110** keeps
the tile lit with the owl's head, ear tufts and eyes knocked out. Frames 64/128/256 render
within a few pixels of each other, so the 64 px frame is used. Guarded by
`program_marks.own_icon` (a committed file is never overwritten).

## Window matching

`match: [filmcraft, ai.storyteller.filmcraft]`

- Windows: `filmcraft.exe` (`packaging/windows/filmcraft.wxs`) → `filmcraft`.
- macOS: bundle name / executable `FilmCraft` (`packaging/macos/Info.plist.in`), or the
  unbundled `filmcraft` binary → `filmcraft`.
- Linux: X11 WM_CLASS / Wayland app id `ai.storyteller.filmcraft`
  (`apps/filmcraft/src/main.rs` `with_app_id(APP_ID)`, `StartupWMClass` in
  `packaging/linux/ai.storyteller.filmcraft.desktop`); the binary name `filmcraft` also
  listed.

## Regenerate

```bash
PYTHONPATH=. python polyhost/res/overlay_sources/filmcraft/fetch_icons.py
PYTHONPATH=. python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/filmcraft/bindings.yaml --preview /tmp/filmcraft_preview
```
