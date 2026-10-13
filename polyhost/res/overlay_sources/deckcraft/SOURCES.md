# DeckCraft overlay: sources and provenance

DeckCraft is the presentation app (PowerPoint-like) of the ArtCraft "Crafting Apps"
suite: <https://github.com/storytold/deckcraft>, licence **MIT OR Apache-2.0**.
Everything below was read at commit **`457406a7a5b62425e915926c8ccb0984e61a198c`**.

To rebuild: run `fetch_icons.py`, then `scripts/generate_app_overlays.py` on `bindings.yaml`.

## Shortcuts: DeckCraft's own keymap

The bindings come from DeckCraft's source, not from PowerPoint's documentation. Key
dispatch is in `crates/ui-egui/src/lib.rs:910-922`. `menus::ui_shortcut` runs first and
consumes what it handles. Everything else goes to `Session::key`
(`crates/engine/src/keys.rs:50`): the text-editing and plain-key handling first, then the
command registry, where the first spec whose `shortcut` matches wins.

**The modifier.** Mods are `cmd: modifiers.command || modifiers.ctrl` (lib.rs:912). The
registry strings say `Cmd+…`, and `shortcut_matches` (keys.rs:10) treats `cmd` and `ctrl`
alike. So every chord here is Ctrl on Windows/Linux and Cmd on macOS, written as
`CMDCTRL`. DeckCraft has no separate macOS keymap: `mac_keys` changes only caret
movement while editing text (keys.rs:160-200), and the native macOS menu reuses the
registry's shortcuts. One spec renders both sets.

| Group | Chords | Source |
|---|---|---|
| File | Ctrl+N New, O Open, S Save, Shift+S Save as, W Close, `` ` `` Next window | `crates/engine/src/cmd/file.rs:11-44`; S, Shift+S, O and W are also handled in `menus.rs:27-50` |
| Print, Preferences, Command palette | Ctrl+P, Ctrl+`,`, Ctrl+Shift+P, Ctrl+F (opens the palette with an empty query) | `crates/ui-egui/src/menus.rs:38-66`, `lib.rs:134-170` (`UI_COMMANDS`) |
| Zoom, ribbon | Ctrl+= Zoom in, Ctrl+- Zoom out, Ctrl+0 Fit, Ctrl+F1 Collapse ribbon | `menus.rs:52-56` |
| View | Shift+F9 Gridlines, Alt+F9 Guides, Alt+F File tab | `menus.rs:31-37, 57-58` |
| Slide show | F5 from start, Shift+F5 from current | `menus.rs:14-25` |
| Edit | Ctrl+Z/Y/X/C/V/A/D, Ctrl+Shift+V Paste text | `crates/engine/src/cmd/edit.rs:13-21` |
| Font, paragraph | Ctrl+B/I/U, Ctrl+Shift+X strikethrough, Ctrl+Shift+= superscript, Ctrl+Shift+. / , font +/-, Shift+F3 change case, Ctrl+L/E/R/J alignment, Ctrl+Shift+C format painter | `crates/engine/src/cmd/format.rs:16-165` |
| Hyperlink | Ctrl+K | `cmd/insert.rs:56`, `menus.rs:59` (dialog) |
| New slide | Ctrl+Shift+N | `cmd/slide.rs:18` |
| Arrange | Ctrl+] / [ forward/backward, Ctrl+Shift+] / [ to front/back, Ctrl+Alt+G Group, Ctrl+Alt+Shift+G Ungroup, Ctrl+Alt+J Regroup | `cmd/arrange.rs:12-27` |
| Review | Ctrl+Alt+M New comment, F7 Spelling | `cmd/review.rs:13-19` |
| Animation, media | Alt+Shift+C Animation painter, Alt+Shift+V Apply animation, Alt+P Play media | `cmd/animation.rs:56-61`, `cmd/media.rs:13` |
| Plain keys | Delete, F2 Edit text (with a shape selected), Home/End/PgUp/PgDn first/last/previous/next slide (with nothing selected) | `keys.rs:85-117`, `cmd/slide.rs:27-30` |

That is 60 bindings: 29 Ctrl, 3 Alt, 3 Shift, 8 plain, 11 Ctrl+Shift, 3 Ctrl+Alt,
2 Alt+Shift and 1 Ctrl+Alt+Shift. ESC carries the program icon.

### Collisions resolved (only what the code actually does is drawn)

- **Ctrl+= is Zoom in.** The registry also lists Ctrl+= Subscript (format.rs:37), but
  `ui_shortcut` consumes the chord first, so Subscript never fires from the keyboard.
- **Ctrl+] / Ctrl+[** are Bring forward and Send backward on the canvas. While text is
  being edited, the same chords grow and shrink the font (keys.rs:162-168). The canvas
  action is drawn.
- **Ctrl+Shift+V** is registered twice: as `edit.pasteText` and `format.painterApply`.
  `command_specs()` lists edit before format, so Paste text wins.
  *Uncertain:* egui-winit may turn any Cmd+V into an `Event::Paste` before the key
  reaches `Session::key`. If it does, Ctrl+Shift+V behaves as plain Paste.
- **Ctrl+F** opens the command palette, as Ctrl+Shift+P does. It is not a Find, so both
  keys get the same palette icon and label.
- **Arrow keys** are context dependent: they nudge a selected shape (Alt for a fine
  nudge) and change slides when nothing is selected (keys.rs:88-110). The key legend is
  already an arrow, so they are not drawn.

### Not drawn: keys without a cell, or not keymap entries

- No cell for Space, Enter, Tab or Backspace. That leaves out Ctrl+Space Clear
  formatting, Ctrl+Enter and Ctrl+Shift+Enter play from current/start, Enter new slide
  or edit text, Tab and Shift+Tab list level and selection cycling, and Backspace
  delete. Escape is the program-icon cell.
- Caret navigation while editing text: Ctrl/Option+arrows, Ctrl+Home/End, and
  Ctrl+Backspace/Delete (keys.rs:156-200). These are generic text-field keys that
  differ per platform.
- Ctrl+F5 also starts the show, because `menus.rs:14` ignores `cmd` for F5. It is a
  side effect, not a binding.
- Slide-show mode keys (`crates/ui-egui/src/show.rs`) belong to a separate full-screen
  mode.

## Icons

- **Copied byte-for-byte from `../powerpoint/icons/`**, where the action is the same:
  new, open, save, saveas, print, close, newslide, duplicate, copy, cut, paste, undo,
  redo, selectall, bold, italic, underline, hyperlink, group, ungroup, left, center,
  right, justify, fontinc, fontdec, copyformat, slideshow, fromcurrent, spelling. All
  are Microsoft Fluent UI System Icons (MIT).
- **Copied from `../illustrator/icons/`**: forward and backward (Fluent Arrow Up/Down,
  MIT), tofront and toback (Fluent Position To Front/Back, MIT), and guides (the custom
  dashed cross drawn by illustrator's `fetch_icons.py`, white on transparent, so its
  binding uses `mode: alpha`).
- **Microsoft Fluent UI System Icons (MIT)**, from `microsoft/fluentui-system-icons`
  `main`, rendered at 96 px with cairosvg through `icon_fetch.fluent`: Text Strikethrough,
  Text Superscript, Zoom In, Zoom Out, Zoom Fit, Settings, Window Multiple, Panel Top
  Contract (20 px cut), Document Briefcase, Video Play Pause, Grid, Text Change Case,
  Rename, Delete, Arrow Previous, Arrow Next, Chevron Up, Chevron Down, Group Return,
  Comment Add, Paint Brush Sparkle, Sparkle, Clipboard Text Edit.
- **Google Material Symbols (Apache-2.0)**: `manage_search` for the command palette, at
  weight 300.
- Labels the shared renderer recognises (New, Open, Save, Print, Close, Undo, Redo,
  Cut, Copy, Paste, Select all, Bold, Italic, Underline, Zoom in/out, Change case,
  Delete, Save as, Superscript) are drawn by the shared concept renderer. The
  generator's placement table shows them as `concept:…`.

## Program icon (ESC, every layer)

`icons/deckcraft.png` is **DeckCraft's own app icon**:
`assets/app-icon/hicolor/scalable/apps/ai.storyteller.deckcraft.svg` at the commit
above. `assets/app-icon/` has no LICENSE file. `ATTRIBUTION.md:20-25` lists the app icon
(PNG, ICO/ICNS, SVG and its `.deckcraft` source) as the DeckCraft contributors' work
under **MIT OR Apache-2.0**. The README's licence section says the same: the app's icons
are original work, and only the ArtCraft marks in `docs/brand/` are trademarks. This
icon is not one of those marks. MIT and Apache-2.0 are both GPL-3.0-compatible.

Transformation, in `fetch_icons._draw_program_mark`: the orange background tile is
dropped, the orange bars are recoloured to the icon's black ink, and the result is
rendered with cairosvg at 256 px. The binding uses `program_icon_mode: luma`, threshold
150, region [46, 40], bottom-right, margin 0.

That choice came from a sweep of the unmodified SVG, the board-only SVG and the ICO
frames at 32, 48, 64 and 256, each in luma (t90–180), bright and alpha, at region
46×40 and 40×36:
- The unmodified icon in luma at t150 or above lights the whole orange tile as a
  frame around the board.
- At t90–120 the orange chart bars vanish.
- Alpha mode gives a solid blob.
- The board-only version at t150 keeps the board outline, all three bars, the dot and
  the stand.

The file is guarded, so a re-run never re-renders a committed `deckcraft.png`.

## Window matching

`match: [deckcraft, ai.storyteller.deckcraft]`:
- Windows: the executable is `deckcraft.exe` (`packaging/windows/deckcraft.wxs:48`),
  which matches as `deckcraft`.
- macOS: the bundle name and executable are `DeckCraft`
  (`packaging/macos/Info.plist.in`), which lowercases to `deckcraft`.
- Linux: the binary is `deckcraft` (`apps/deckcraft/Cargo.toml`). The Wayland app id
  and X11 WM_CLASS are `ai.storyteller.deckcraft` (`apps/deckcraft/src/main.rs:130,182`,
  `.desktop` `StartupWMClass`).
