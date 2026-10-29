# GridCraft overlay: sources and provenance

Reproducible record. Re-run `fetch_icons.py`, then `scripts/generate_app_overlays.py`
on `bindings.yaml`, to rebuild. The generator output is byte-identical between runs
(checked with sha256 on all five PNGs).

## App

GridCraft, an Excel-like spreadsheet from the ArtCraft "Crafting Apps" suite.
Repo: <https://github.com/storytold/gridcraft>, licence **MIT OR Apache-2.0**. It may be
shipped by this GPL-3.0-or-later host. Commit read: `84acf6293b1dc1fc09837524e035d674eb4d6741`.

## Window matching

`match: [gridcraft, ai.storyteller.gridcraft]`
- Windows: `gridcraft.exe` (`packaging/windows/gridcraft.wxs:164`, Cargo `[package] name = "gridcraft"`
  in `apps/gridcraft/Cargo.toml`), so the handler sees `gridcraft`.
- macOS: `CFBundleName`/`CFBundleExecutable` = `GridCraft` (`packaging/macos/Info.plist.in`),
  lowercased to `gridcraft`.
- Linux: eframe `with_app_id("ai.storyteller.gridcraft")` (`apps/gridcraft/src/main.rs:315`) and
  `StartupWMClass=ai.storyteller.gridcraft` (`packaging/linux/ai.storyteller.gridcraft.desktop`).
  The Wayland app id and the X11 WM_CLASS are both `ai.storyteller.gridcraft`.

## Shortcuts: the authority is GridCraft's own keymap

The source is GridCraft's code, not Microsoft's Excel tables. Only chords the code handles
are bound. Paths are under `crates/ui-egui/src/`:

| Group | Source |
|---|---|
| Plain Cmd/Ctrl letters and digits (New, Open, Save, Save as, Close, Undo, Redo, Fill, Find, Replace, Go to, Table, AutoSum, Format cells, Hide/Unhide rows/cols, Delete/Insert cells, Show formulas, Ctrl+; date) | `ribbon.rs:2406-2483` `shortcut()`, called from `grid.rs:2683` when `m.command` is set |
| Copy / Cut / Paste | egui `Event::Copy/Cut/Paste`, `grid.rs:2595-2601` |
| Ctrl+Shift number formats and borders, Ctrl+'/Ctrl+Shift+' | `keymap.rs:74-86` |
| Mac Control+; / Cmd+; | `keymap.rs:88-89` |
| Ctrl+2..5 (Windows/Linux only) | `keymap.rs:91-94` |
| OS-dependent letters (L, U, E, F, G, H, R, K, J, P) | `keymap.rs:96-109` |
| Cmd+Shift+. / , font size, Ctrl+Shift+Home/End, Shift+Home | `keymap.rs:110-120` |
| Ctrl+Alt / Cmd+Option chords (paste special, zoom, calculate, Mac borders, collapse ribbon) | `keymap.rs:122-133` |
| Alt / Option chords | `keymap.rs:134-145` |
| Function keys | `keymap.rs:146-160` |
| F2, F9, Alt+F8, Delete, Home, Ctrl+Home/End, Ctrl+PgUp/PgDn | `grid.rs:2626-2682` |
| F4 cycle reference while editing | `formula_bar.rs:255` |
| F10 key tips | `keytips.rs:93` |
| Alt+Enter / Ctrl+Enter edit cell, Backspace clear-and-edit | `grid.rs:2654-2659`, `grid.rs:2665-2672` |
| Ctrl+Shift+Enter array formula, Mac Cmd+Enter fill selection (editor) | `formula_bar.rs:169-200` |
| Shift+Space row, Ctrl+Space column, Cmd/Ctrl+Shift+Space select all | `keymap.rs:112-117` |

Enter chords are context-dependent. Per the brief the grid meaning wins: Alt+Enter and Ctrl+Enter
start editing in the grid (while editing, Alt+Enter is a line break and Ctrl/Cmd+Enter fills the
selection). Two exceptions, because in the grid they do nothing of their own: Ctrl+Shift+Enter
is drawn as **Array formula** (in the grid it only starts an edit), and Mac Cmd+Enter as
**Fill selection** (the grid moves down, as plain Enter).

`keymap::lookup()` runs before `ribbon::shortcut()`, so where both match, keymap wins (for
example, Windows Ctrl+Shift+F opens the Font tab, not the filter).

### Modifiers

egui's `m.command` is Ctrl on Windows/Linux and Cmd on macOS, so it is written **CMDCTRL**.
egui's `m.ctrl` is the Control key on every OS, so it is written **CTRL**. That is why the
`ctrl && s` number formats and Ctrl+'/Ctrl+; stay Control on macOS. Rows guarded by
`mac` / `!mac` are scoped with `only:`.

macOS-only differences, each scoped `only: [macos]` (Windows/Linux equivalents in brackets):
- Cmd+L align left, Control+L define name [Ctrl+L new table]
- Cmd+E align center; Control+E flash fill [Ctrl+E flash fill, via ribbon]
- Control+U edit cell [Ctrl+U underline, Mac Cmd+U underline]
- Cmd+Shift+F filter [Ctrl+Shift+F format font]; Control+Shift+L filter (also Cmd+Shift+L)
- Cmd+Shift+H replace [Ctrl+H]. Cmd+H is the system Hide, so Ctrl+H is `except: [macos]`
- Cmd+Shift+R sort, Cmd+Shift+K/J group/ungroup [Alt+Shift+Right/Left]
- Cmd+; insert time
- Cmd+F3 define name [Ctrl+F3 name manager]
- Cmd+Option+R collapse ribbon, Cmd+Option+0/-/arrows borders [Ctrl+Alt+- zoom out]
- Option+Right/Left next/previous sheet
- AutoSum is Alt+= on Windows/Linux only; Cmd/Ctrl+Shift+T works everywhere
- Ctrl+2..5 bold/italic/underline/strike: Windows/Linux only

### Not bound, and why

- **Escape** is the program-icon cell (grid.rs: clears the copy marquee / format painter).
- **Basic cursor movement / commit:** plain arrows, PgUp/PgDn, Shift+arrows (extend),
  Ctrl+arrows (jump), plain/Shift Enter (commit and move down/up; pastes a marked copy range),
  plain/Shift Tab (move right/left; accepts AutoComplete while editing).
- **Plain Space** types a space, except on a checkbox cell where it toggles it
  (`grid.rs:2677`): context-only, not drawn.
- **Ctrl+Alt+Enter** inserts a line break while editing (`formula_bar.rs:170`); in the grid it
  only starts editing like Ctrl+Enter. Not drawn separately.
- **Incidental matches:** `ribbon::shortcut()` ignores Shift on most keys (Ctrl+Shift+B bolds,
  Ctrl+Shift+H replaces on Windows, Mac Cmd+Shift+1 opens format cells, Cmd+Shift+G goes to).
  It also ignores Alt when keymap returns nothing. None of these is a deliberate binding.
- **Duplicate chords for one action:** Mac Control+Cmd+V paste special (Cmd+Option+V is drawn),
  Mac Control+Shift+F2 threaded comment (Cmd+Shift+F2 is drawn), Mac Control+Option variants
  of the Cmd+Option rows.
- `AltGr` (Ctrl+Alt that types a character) is text, not a shortcut (`keymap.rs` `dispatch`).

## Icons

Most glyphs are **Microsoft Fluent UI System Icons (MIT)**, from `microsoft/fluentui-system-icons`,
`main`, `assets/<Name>/SVG/ic_fluent_*_{24,20}_regular.svg`. They are rendered by
`icon_fetch.fluent` at 96 px. The full name map is in `fetch_icons.py`.

Where the action matches the Excel overlay, the same Fluent glyph is used: new, open, save,
saveas, close, print, cut, paste, undo, redo, selectall, bold, italic, underline, strike,
hyperlink, find, replace, goto, filldown, fillright, flashfill, formatcells, tableadd,
delcells, filter, autosum, calc, absref and currency. The PNGs are byte-identical to
`excel/icons/` except `copy.png`, which is drawn by the shared concept renderer anyway.

Seven are **Material Symbols (Apache-2.0)** at weight 300: `content_paste_go` (paste special), `add_row_below` (insert cells),
`select` (current region; also the base of the select-to composites), `vertical_align_bottom`
(value from above), `function` (insert function), `new_label` (names from selection) and
`arrow_drop_down_circle` (drop-down list).

Derived in `fetch_icons.py`:
- `hidecols`/`unhidecols` are `hiderows`/`unhiderows` (Fluent Arrow Minimize/Maximize Vertical)
  rotated 90 degrees. Fluent has no horizontal cut.
- `extendstart`/`extendend`/`extendrow` composite the Material `select` dotted box with the
  matching go-to arrow (Arrow Up Left / Arrow Down Right / Arrow Previous) at 56 px. They read
  as the "select to" twins of Ctrl+Home, Ctrl+End and Home.

Percent (Ctrl+Shift+5) is the text label `%`, as in the Excel overlay.

Enter/Backspace/Space icons: Edit (Fluent, as F2), Braces (array formula), Paint Bucket (fill
selection), Table Cell Edit (clear and edit), Table Insert Row / Table Insert Column (select
row / column, the same glyphs as `libreoffice/`), Select All On (as Ctrl+A).

## Program icon (ESC, all layers)

`icons/gridcraft.png` is GridCraft's **own** app icon. It is the 64 px frame of
`assets/app-icon/gridcraft.ico` at the commit above, fetched by `program_marks.own_icon`,
which leaves a committed file alone. Licence: **MIT OR Apache-2.0**
(`assets/app-icon/LICENSE.txt`). The upstream README marks it as a **placeholder** (a ledger
page on a green tile) until the owner's creature portrait arrives. When the upstream art
changes, delete the PNG and re-run `fetch_icons.py`.

Sweep: ICO frames 32/48/64/128/256 plus an SVG render, `luma` t80..150 and `bright` t150..210,
in a region of [46, 40] anchored bottom-right. Frames 64 and above converge.
- `luma` t150 (chosen) lights the green tile and leaves the page and grid dark. It reads as
  the real tile.
- `luma` t100 gives a thin page outline only.
- `bright` loses the page edge.

## Transformations

`bindings.yaml`: `mode: luma`, `threshold: 150`, `region: [36, 32]`, `anchor: bottom-right`,
`margin: 0` (as in the Excel overlay). Program icon: `luma` t150, [46, 40], bottom-right.
